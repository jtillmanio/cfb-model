<#
  Prints the next free ID for a numbered list kept in one file (a decisions log, by default), looking at every place
  another session may already have taken one: the working tree, origin/<base>, and the head branch of every open PR.
  Two branches that each append "the next" decision otherwise take the same ID.

  Usage (from anywhere in the repo):
    powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/next-id.ps1 -Path docs/decisions.md -Prefix D-
    powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/next-id.ps1 -Path docs/TASKS.md -List -Pattern '\d+\.\d+[a-z]?'

  -Path     The file, relative to the repo root.
  -Prefix   The ID prefix (default D-). An ID counts where it is defined: at the start of a table row, a heading, or a
            list item, optionally in bold. "Supersedes D-4" inside a row or a "next new decision: D-25" line doesn't.
  -List     Print every ID in use (matching -Pattern, at the same positions) per source, instead of the next one.
  -Pattern  Regex for -List (default: the prefix followed by digits).
  -NoFetch  Don't run git fetch first (offline, or already fetched).

  Open PR branches come from `gh pr list --state open`. Without gh (or outside GitHub) it reads every remote branch not
  merged into origin/<base>. PRs from forks are skipped with a note.

  Output: one "source: highest" line per source, then "Next: D-25". Exit 0; exit 1 if the file is missing everywhere.
  Compatible with Windows PowerShell 5.1 and PowerShell 7+.
#>
param(
    [Parameter(Mandatory = $true)][string]$Path,
    [string]$Prefix = 'D-',
    [switch]$List,
    [string]$Pattern = '',
    [switch]$NoFetch
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\lib-tasks.ps1"
[Console]::OutputEncoding = $script:Utf8NoBom

$root = Get-KitRoot
$config = Get-KitConfig $root
$base = 'main'
if ($config.workflow -and $config.workflow.baseBranch) { $base = [string]$config.workflow.baseBranch }
$rel = $Path.Replace('\', '/')
if ($rel.StartsWith('./')) { $rel = $rel.Substring(2) }

if (-not $Pattern) { $Pattern = [regex]::Escape($Prefix) + '\d+' }
# Definition positions only: "| D-12 |", "## D-12", "- D-12", "- **D-12**".
$defRegex = New-Object System.Text.RegularExpressions.Regex ('^\s*(?:\|\s*|#+\s*|[-*]\s+(?:\[[ xX]\]\s+)?)(?:\*\*)?(' + $Pattern + ')(?![\w.])'), 'Multiline'

function Get-Ids([string]$text) {
    $ids = New-Object System.Collections.Generic.List[string]
    foreach ($m in $defRegex.Matches($text)) { $ids.Add($m.Groups[1].Value) }
    return , $ids
}

function Get-Number([string]$id) {
    $m = [regex]::Match($id, '(\d+)$')
    if ($m.Success) { return [int]$m.Groups[1].Value }
    return -1
}

# Native commands below report failure through $LASTEXITCODE. With 'Stop', Windows PowerShell 5.1 turns a redirected
# stderr line (e.g. "path does not exist in origin/main") into a terminating error.
$ErrorActionPreference = 'Continue'

if (-not $NoFetch) { & git -C $root fetch --quiet origin 2>$null | Out-Null }

# ---- Sources: working tree, base, open PR heads ----------------------------------------------------------------
$sources = New-Object System.Collections.Generic.List[object]
$wt = Join-Path $root $rel
if (Test-Path -LiteralPath $wt) {
    $sources.Add([pscustomobject]@{ Name = 'working tree'; Text = (Get-Content -LiteralPath $wt -Raw -Encoding UTF8) })
}

function Get-FileAt([string]$ref) {
    $out = & git -C $root show "${ref}:$rel" 2>$null
    if ($LASTEXITCODE -ne 0) { return $null }
    return (@($out) -join "`n")
}

$baseText = Get-FileAt "origin/$base"
if ($null -ne $baseText) { $sources.Add([pscustomobject]@{ Name = "origin/$base"; Text = $baseText }) }

$heads = New-Object System.Collections.Generic.List[string]
$notes = New-Object System.Collections.Generic.List[string]
$prJson = $null
try { $prJson = & gh pr list --state open --limit 100 --json number,headRefName,isCrossRepository 2>$null } catch { $prJson = $null }
if ($LASTEXITCODE -eq 0 -and $prJson) {
    # Windows PowerShell 5.1 emits a JSON array as one object; ForEach-Object unrolls it.
    foreach ($pr in @((@($prJson) -join "`n") | ConvertFrom-Json | ForEach-Object { $_ })) {
        if ($pr.isCrossRepository) { $notes.Add("PR #$($pr.number) is from a fork; not read"); continue }
        $heads.Add([string]$pr.headRefName)
    }
} else {
    $notes.Add('gh unavailable: reading remote branches not merged into origin/' + $base)
    foreach ($b in @(& git -C $root branch -r --no-merged "origin/$base" 2>$null)) {
        $name = ([string]$b).Trim()
        if (-not $name -or $name -like '*->*') { continue }
        $heads.Add(($name -replace '^origin/', ''))
    }
}

foreach ($h in ($heads | Sort-Object -Unique)) {
    if ($h -eq $base) { continue }
    $text = Get-FileAt "origin/$h"
    if ($null -ne $text) { $sources.Add([pscustomobject]@{ Name = "origin/$h"; Text = $text }) }
}

if ($sources.Count -eq 0) {
    Write-Host "$rel not found in the working tree, on origin/$base, or on any open PR branch."
    exit 1
}

foreach ($n in $notes) { Write-Host "Note: $n" }

# ---- Report ----------------------------------------------------------------------------------------------------
if ($List) {
    $all = New-Object System.Collections.Generic.List[string]
    foreach ($s in $sources) {
        $ids = Get-Ids $s.Text
        foreach ($i in $ids) { $all.Add($i) }
        Write-Host ("{0}: {1}" -f $s.Name, (($ids | Select-Object -Unique) -join ', '))
    }
    Write-Host ('In use: ' + (($all | Sort-Object -Unique) -join ', '))
    exit 0
}

$max = 0
$width = 0
foreach ($s in $sources) {
    $ids = Get-Ids $s.Text
    $high = 0
    $highId = ''
    foreach ($i in $ids) {
        $n = Get-Number $i
        if ($n -gt $high) { $high = $n; $highId = $i }
        $digits = [regex]::Match($i, '(\d+)$').Groups[1].Value
        if ($digits.StartsWith('0') -and $digits.Length -gt $width) { $width = $digits.Length }
    }
    if ($high -gt $max) { $max = $high }
    if ($highId) { Write-Host ("{0}: {1}" -f $s.Name, $highId) } else { Write-Host ("{0}: none" -f $s.Name) }
}

$next = [string]($max + 1)
if ($width -gt $next.Length) { $next = $next.PadLeft($width, '0') }
Write-Host "Next: $Prefix$next"
