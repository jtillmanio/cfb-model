<#
  Lists the Follow-ups of merged PRs: for each PR, every bullet under its "## Follow-ups" heading, with the destination
  the bullet already names ("-> <path> (section) <section>" or "-> not tracked: <reason>"), if any. /track-follow-ups reads
  this, then decides what is already tracked and places the rest. Read-only.

  Usage (from anywhere in the repo):
    powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/list-follow-ups.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/list-follow-ups.ps1 -Since 53
    powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/list-follow-ups.ps1 -Since 2026-10-01 -AsJson

  -Since     A PR number (#53 or 53: that PR and every PR merged after it) or a date (merged on or after it).
             Default: the PR that installed the kit, i.e. the commit that first added .claude/kit-version. Its
             squash subject ends in "(#n)"; without one, that commit's date is used.
  -FromJson  Read PRs from a file instead of gh: a JSON array of { number, title, body, mergedAt, url }, the shape
             `gh pr list --state merged --json number,title,body,mergedAt,url` prints. For tests and offline runs.
  -Limit     How many merged PRs to ask gh for (default 200).
  -AsJson    Print JSON (one object per PR with its bullets) instead of text.

  Compatible with Windows PowerShell 5.1 and PowerShell 7+.
#>
param(
    [string]$Since = '',
    [string]$FromJson = '',
    [int]$Limit = 200,
    [switch]$AsJson
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\lib-tasks.ps1"
[Console]::OutputEncoding = $script:Utf8NoBom
$arrow = [string][char]0x2192

$root = Get-KitRoot
$config = Get-KitConfig $root
$base = 'main'
if ($config.workflow -and $config.workflow.baseBranch) { $base = [string]$config.workflow.baseBranch }

# Native commands report failure through $LASTEXITCODE; see next-id.ps1 for why not 'Stop'.
$ErrorActionPreference = 'Continue'

# ---- PRs ---------------------------------------------------------------------------------------------------------
if ($FromJson) {
    $parsed = Get-Content -LiteralPath $FromJson -Raw -Encoding UTF8 | ConvertFrom-Json
} else {
    $raw = & gh pr list --state merged --base $base --limit $Limit --json number,title,body,mergedAt,url
    if ($LASTEXITCODE -ne 0) { Write-Host 'gh pr list failed. Run gh auth status, or pass -FromJson.'; exit 1 }
    $parsed = (@($raw) -join "`n") | ConvertFrom-Json
}
# Windows PowerShell 5.1 emits a JSON array as one object; unroll it.
$prs = @($parsed | ForEach-Object { $_ })

function ConvertTo-Date($v) {
    if ($null -eq $v -or "$v" -eq '') { return $null }
    if ($v -is [datetime]) { return $v.ToUniversalTime() }
    return ([datetime]::Parse([string]$v, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AdjustToUniversal -bor [Globalization.DateTimeStyles]::AssumeUniversal))
}

# ---- Since -------------------------------------------------------------------------------------------------------
$sinceNumber = 0
$sinceDate = $null
$sinceLabel = ''
if (-not $Since) {
    $log = @(& git -C $root log --diff-filter=A --format='%s%x09%cI' -- .claude/kit-version 2>$null)
    if ($log.Count -gt 0 -and $log[-1]) {
        $parts = ([string]$log[-1]).Split("`t")
        $m = [regex]::Match($parts[0], '\(#(\d+)\)\s*$')
        if ($m.Success) { $Since = $m.Groups[1].Value; $sinceLabel = " (the PR that installed the kit)" }
        else { $Since = $parts[1]; $sinceLabel = " (the commit that installed the kit: $($parts[0]))" }
    }
}
if ($Since) {
    $n = $Since.TrimStart('#')
    if ($n -match '^\d+$') {
        $sinceNumber = [int]$n
        $anchor = @($prs | Where-Object { [int]$_.number -eq $sinceNumber })
        if ($anchor.Count -gt 0 -and $anchor[0].mergedAt) { $sinceDate = ConvertTo-Date $anchor[0].mergedAt }
    } else {
        $sinceDate = ConvertTo-Date $Since
    }
}

$selected = @($prs | Where-Object {
    $merged = ConvertTo-Date $_.mergedAt
    if ($sinceDate) { return ($null -ne $merged -and $merged -ge $sinceDate) }
    if ($sinceNumber -gt 0) { return ([int]$_.number -ge $sinceNumber) }
    return $true
} | Sort-Object { ConvertTo-Date $_.mergedAt }, { [int]$_.number })

# ---- Follow-ups section ------------------------------------------------------------------------------------------
function Get-FollowUps([string]$body) {
    $items = New-Object System.Collections.Generic.List[object]
    if (-not $body) { return , $items }
    $text = [regex]::Replace($body, '(?s)<!--.*?-->', '')
    $lines = $text -split "`r?`n"
    $in = $false
    $current = $null
    foreach ($line in $lines) {
        if ($line -match '^\s{0,3}#{1,6}\s') {
            if ($in) { break }
            if ($line -match '^\s{0,3}#{2,3}\s*Follow-?ups\b') { $in = $true }
            continue
        }
        if (-not $in) { continue }
        $bm = [regex]::Match($line, '^\s{0,3}(?:[-*+]|\d+[.)])\s+(.*)$')
        if ($bm.Success) {
            if ($current) { $items.Add($current) }
            $current = [System.Text.StringBuilder]::new($bm.Groups[1].Value.Trim())
        } elseif ($current -and $line.Trim()) {
            [void]$current.Append(' ').Append($line.Trim())
        }
    }
    if ($current) { $items.Add($current) }

    $result = New-Object System.Collections.Generic.List[object]
    foreach ($sb in $items) {
        $t = $sb.ToString().Trim()
        if (-not $t -or $t -match '^(?i)(none|n/?a|nothing|-)\.?$') { continue }
        $dest = ''
        $i = [Math]::Max($t.LastIndexOf($arrow), $t.LastIndexOf(' -> '))
        if ($i -gt 0) {
            $len = 1
            if ($t.Substring($i, 1) -ne $arrow) { $len = 4 }
            $dest = $t.Substring($i + $len).Trim()
            $t = $t.Substring(0, $i).Trim()
        }
        $result.Add([pscustomobject]@{ Text = $t; Destination = $dest })
    }
    return , $result
}

$out = New-Object System.Collections.Generic.List[object]
foreach ($pr in $selected) {
    $out.Add([pscustomobject]@{
        Number    = [int]$pr.number
        Title     = [string]$pr.title
        MergedAt  = [string]$pr.mergedAt
        Url       = [string]$pr.url
        FollowUps = (Get-FollowUps ([string]$pr.body)).ToArray()
    })
}

if ($AsJson) {
    ConvertTo-Json -InputObject $out.ToArray() -Depth 5
    exit 0
}

$total = 0
foreach ($p in $out) { $total += $p.FollowUps.Count }
if ($Since) { Write-Host "Since: $Since$sinceLabel" } else { Write-Host 'Since: every merged PR (no kit install commit found)' }
Write-Host ("{0} merged PR(s), {1} follow-up(s)" -f $out.Count, $total)
foreach ($p in $out) {
    if ($p.FollowUps.Count -eq 0) { continue }
    $date = ''
    $d = ConvertTo-Date $p.MergedAt
    if ($d) { $date = ' (merged ' + $d.ToString('yyyy-MM-dd') + ')' }
    Write-Host ''
    Write-Host ("#{0} {1}{2}" -f $p.Number, $p.Title, $date)
    $k = 0
    foreach ($f in $p.FollowUps) {
        $k++
        if ($f.Destination) { Write-Host ("  {0}. {1}  {2} {3}" -f $k, $f.Text, $arrow, $f.Destination) }
        else { Write-Host ("  {0}. {1}  {2} (no destination)" -f $k, $f.Text, $arrow) }
    }
}
