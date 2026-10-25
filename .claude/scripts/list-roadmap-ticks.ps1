<#
  Lists what it takes to keep the roadmap's done marks in step with the task files (.claude/skills/sync-roadmap/ticks.md).
  /implement-task runs it at close-out and accept, /sync-roadmap for a backfill. Read-only: Claude makes the edits.

  The tick doc: workflow.roadmap.path in roadmap mode; otherwise the "Roadmap" row of the Project docs table in CLAUDE.md,
  or its "Task list" row when the Roadmap row has no path. -Path overrides both. A mark is a checkbox ([ ] / [x]) or a
  glyph (U+2610 / U+2611, U+2B1C / U+2705, U+2714) at the start of a list item or heading, outside code fences.

  Usage (from anywhere in the repo):
    powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/list-roadmap-ticks.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/list-roadmap-ticks.ps1 -Include TASK-014
    powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/list-roadmap-ticks.ps1 -Path docs/roadmap.md -AsJson

  -Include  Task IDs (comma-separated) to count as finished although not Done: this task at close-out, in Review.
  -Path     The tick doc, relative to the repo root.
  -AsJson   Print JSON instead of text.

  Roadmap mode prints the open items whose tasks are all finished ("To tick"), ticked items whose task is Draft, Ready,
  In progress or Blocked, and finished tasks whose roadmap ID has no marked item. Otherwise matching items to tasks is a
  judgement (ticks.md), so it prints the finished tasks with their Context lines that cite the roadmap or task list and
  their Task list row, then every open item under its heading, with the task IDs the item names.

  Compatible with Windows PowerShell 5.1 and PowerShell 7+.
#>
param(
    [string[]]$Include = @(),
    [string]$Path = '',
    [switch]$AsJson
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\lib-tasks.ps1"
[Console]::OutputEncoding = $script:Utf8NoBom

$root = Get-KitRoot
$config = Get-KitConfig $root
$roadmap = $null
if ($config.workflow -and $config.workflow.roadmap -and $config.workflow.roadmap.path) { $roadmap = $config.workflow.roadmap }

# -File passes "TASK-1,TASK-2" as one string; split it.
$included = @($Include | ForEach-Object { $_ -split '[,\s]+' } | Where-Object { $_ })

# ---- Tick doc ----------------------------------------------------------------------------------------------------
function Get-RolePath([string]$Label) {
    $md = Join-Path $root 'CLAUDE.md'
    if (-not (Test-Path -LiteralPath $md)) { return '' }
    foreach ($line in (Get-Content -LiteralPath $md -Encoding UTF8)) {
        $m = [regex]::Match($line, '^\s*\|\s*' + $Label + '\b[^|]*\|([^|]*)\|')
        if (-not $m.Success) { continue }
        $p = [regex]::Match($m.Groups[1].Value, '`([^`]+)`')
        if (-not $p.Success) { return '' }
        return ([regex]::Replace($p.Groups[1].Value, '\s*' + [char]0x00A7 + '.*$', '')).Trim()
    }
    return ''
}

$taskListPath = Get-RolePath 'Task list'
$source = ''
if ($Path) { $source = '-Path' }
elseif ($roadmap) { $Path = [string]$roadmap.path; $source = 'workflow.roadmap.path' }
else {
    $Path = Get-RolePath 'Roadmap'
    if ($Path) { $source = 'CLAUDE.md Project docs: Roadmap' }
    elseif ($taskListPath) { $Path = $taskListPath; $source = 'CLAUDE.md Project docs: Task list' }
}

if (-not $Path) {
    Write-Host 'No tick doc: roadmap mode is off and the Project docs table names no Roadmap or Task list path. Nothing to tick.'
    exit 0
}
$full = Join-Path $root $Path
if (-not (Test-Path -LiteralPath $full)) {
    Write-Host "Tick doc $Path ($source) not found."
    exit 1
}

# ---- Marks -------------------------------------------------------------------------------------------------------
# Glyphs are built from code points: the source stays ASCII for Windows PowerShell 5.1.
$glyphs = -join @([char]0x2610, [char]0x2611, [char]0x2B1C, [char]0x2705, [char]0x2714)
$markRe = '^\s*(?:#{1,6}\s+|(?:[-*+]|\d+[.)])\s+)?(\[[ xX]\]|[' + $glyphs + '])(?![(\[:])' + [char]0xFE0F + '?\s*(\S.*)$'
$openMarks = @('[ ]', [string][char]0x2610, [string][char]0x2B1C)
$idPattern = ''
if ($roadmap) {
    $idPattern = [string]$roadmap.idPattern
    if (-not $idPattern) { $idPattern = '\d+\.\d+[a-z]?' }
}

$items = New-Object System.Collections.Generic.List[object]
$heading = ''
$inFence = $false
$n = 0
foreach ($line in (Get-Content -LiteralPath $full -Encoding UTF8)) {
    $n++
    if ($line -match '^\s*(```|~~~)') { $inFence = -not $inFence; continue }
    if ($inFence) { continue }
    $m = [regex]::Match($line, $markRe)
    if (-not $m.Success) {
        $h = [regex]::Match($line, '^\s{0,3}#{1,6}\s+(.*)$')
        if ($h.Success) { $heading = $h.Groups[1].Value.Trim() }
        continue
    }
    $text = $m.Groups[2].Value.Trim()
    $id = ''
    if ($idPattern) {
        $im = [regex]::Match(($text -replace '^[\s*_`\[]+', ''), '^(?:' + $idPattern + ')(?!\w)')
        if ($im.Success) { $id = $im.Value }
    }
    $items.Add([pscustomobject]@{
        Line    = $n
        Done    = ($openMarks -notcontains $m.Groups[1].Value)
        Id      = $id
        Text    = $text
        Heading = $heading
        Tasks   = @([regex]::Matches($text, 'TASK-\d+') | ForEach-Object { $_.Value } | Select-Object -Unique)
    })
}

$doneCount = @($items | Where-Object { $_.Done }).Count
$openCount = $items.Count - $doneCount
if ($items.Count -eq 0) {
    Write-Host "Tick doc: $Path ($source)"
    Write-Host 'No done marks in it: nothing to tick. Never add them (ticks.md).'
    exit 0
}

# ---- Tasks -------------------------------------------------------------------------------------------------------
$tasks = @(Get-Tasks $root)
$byTaskId = @{}
foreach ($t in $tasks) { $byTaskId[$t.Id] = $t }
function Test-Finished($t) { return ($t.Status -eq 'Done' -or $included -contains $t.Id) }
$unfinished = @('Draft', 'Ready', 'In progress', 'Blocked')

function Get-Short([string]$s, [int]$max = 160) {
    if ($s.Length -le $max) { return $s }
    return $s.Substring(0, $max - 3) + '...'
}

$result = [ordered]@{
    TickDoc   = $Path
    Source    = $source
    Mode      = $(if ($roadmap) { 'roadmap' } else { 'judgement' })
    DoneMarks = $doneCount
    OpenMarks = $openCount
}

if ($roadmap) {
    $byItemId = @{}
    foreach ($it in $items) { if ($it.Id -and -not $byItemId.ContainsKey($it.Id)) { $byItemId[$it.Id] = $it } }

    $groups = @{}
    foreach ($t in $tasks) {
        $rm = [regex]::Match($t.Title, $idPattern)
        if (-not $rm.Success) { continue }
        if (-not $groups.ContainsKey($rm.Value)) { $groups[$rm.Value] = New-Object System.Collections.Generic.List[object] }
        $groups[$rm.Value].Add($t)
    }

    $toTick = New-Object System.Collections.Generic.List[object]
    $tickedNotDone = New-Object System.Collections.Generic.List[object]
    $noItem = New-Object System.Collections.Generic.List[object]
    foreach ($rid in ($groups.Keys | Sort-Object)) {
        $ts = $groups[$rid].ToArray()
        $allFinished = (@($ts | Where-Object { -not (Test-Finished $_) }).Count -eq 0)
        $taskText = (@($ts | ForEach-Object { "$($_.Id) ($($_.Status))" }) -join ', ')
        if (-not $byItemId.ContainsKey($rid)) {
            if (@($ts | Where-Object { Test-Finished $_ }).Count -gt 0) { $noItem.Add([pscustomobject]@{ Id = $rid; Tasks = $taskText }) }
            continue
        }
        $it = $byItemId[$rid]
        if ($allFinished -and -not $it.Done) {
            $toTick.Add([pscustomobject]@{ Line = $it.Line; Id = $rid; Tasks = $taskText; Text = $it.Text })
        } elseif ($it.Done -and @($ts | Where-Object { $unfinished -contains $_.Status -and $included -notcontains $_.Id }).Count -gt 0) {
            $tickedNotDone.Add([pscustomobject]@{ Line = $it.Line; Id = $rid; Tasks = $taskText; Text = $it.Text })
        }
    }
    $result.ToTick = $toTick.ToArray()
    $result.TickedNotDone = $tickedNotDone.ToArray()
    $result.NoItem = $noItem.ToArray()

    if ($AsJson) { ConvertTo-Json -InputObject ([pscustomobject]$result) -Depth 5; exit 0 }

    Write-Host "Tick doc: $Path ($source)"
    Write-Host "Marks: $doneCount done, $openCount open"
    Write-Host ''
    Write-Host "To tick ($($toTick.Count)):"
    foreach ($x in $toTick) { Write-Host ("  line {0}  {1}  {2}  {3}" -f $x.Line, $x.Id, $x.Tasks, (Get-Short $x.Text 100)) }
    if ($tickedNotDone.Count -gt 0) {
        Write-Host ''
        Write-Host "Ticked, but its task isn't finished (report only; never untick) ($($tickedNotDone.Count)):"
        foreach ($x in $tickedNotDone) { Write-Host ("  line {0}  {1}  {2}" -f $x.Line, $x.Id, $x.Tasks) }
    }
    if ($noItem.Count -gt 0) {
        Write-Host ''
        Write-Host "Finished tasks with no marked item for their roadmap ID ($($noItem.Count)):"
        foreach ($x in $noItem) { Write-Host ("  {0}  {1}" -f $x.Id, $x.Tasks) }
    }
    exit 0
}

# ---- Judgement mode: list both sides -----------------------------------------------------------------------------
$docLeaf = Split-Path -Leaf $Path
$taskListLines = @()
if ($taskListPath -and $taskListPath -ne $Path -and (Test-Path -LiteralPath (Join-Path $root $taskListPath))) {
    $taskListLines = @(Get-Content -LiteralPath (Join-Path $root $taskListPath) -Encoding UTF8)
}

$finished = New-Object System.Collections.Generic.List[object]
foreach ($t in ($tasks | Where-Object { Test-Finished $_ })) {
    $context = New-Object System.Collections.Generic.List[string]
    $in = $false
    foreach ($line in (Get-Content -LiteralPath $t.FullPath -Encoding UTF8)) {
        if ($line -match '^##\s') { $in = ($line -match '^##\s+Context\b'); continue }
        if (-not $in -or -not $line.Trim()) { continue }
        if ($line.IndexOf($docLeaf, [StringComparison]::OrdinalIgnoreCase) -ge 0 -or $line -match '(?i)roadmap|task ?list') {
            if ($context.Count -lt 3) { $context.Add((Get-Short $line.Trim() 200)) }
        }
    }
    $row = ''
    foreach ($line in $taskListLines) {
        if ($line -match ('\b' + [regex]::Escape($t.Id) + '\b')) { $row = Get-Short $line.Trim() 200; break }
    }
    $finished.Add([pscustomobject]@{ Id = $t.Id; Status = $t.Status; Title = $t.Title; File = $t.RelPath; Context = $context.ToArray(); TaskListRow = $row })
}

$open = @($items | Where-Object { -not $_.Done })
$tickedNotDone = @($items | Where-Object {
    $_.Done -and @($_.Tasks | Where-Object { $byTaskId.ContainsKey($_) -and $unfinished -contains $byTaskId[$_].Status -and $included -notcontains $_ }).Count -gt 0
})

$result.FinishedTasks = $finished.ToArray()
$result.OpenItems = @($open | ForEach-Object { [pscustomobject]@{ Line = $_.Line; Heading = $_.Heading; Text = $_.Text; Tasks = $_.Tasks } })
$result.TickedNotDone = @($tickedNotDone | ForEach-Object { [pscustomobject]@{ Line = $_.Line; Text = $_.Text; Tasks = $_.Tasks } })

if ($AsJson) { ConvertTo-Json -InputObject ([pscustomobject]$result) -Depth 5; exit 0 }

Write-Host "Tick doc: $Path ($source)"
Write-Host "Marks: $doneCount done, $openCount open. Match items to tasks by the rules in .claude/skills/sync-roadmap/ticks.md."
Write-Host ''
Write-Host "Finished tasks ($($finished.Count)):"
foreach ($f in $finished) {
    Write-Host ("  {0} [{1}] {2}  ({3})" -f $f.Id, $f.Status, (Get-Short $f.Title 110), $f.File)
    foreach ($c in $f.Context) { Write-Host "      Context: $c" }
    if ($f.TaskListRow) { Write-Host "      Task list: $($f.TaskListRow)" }
}
Write-Host ''
Write-Host "Open items ($($open.Count)):"
$last = $null
foreach ($it in $open) {
    if ($it.Heading -ne $last) { Write-Host "  # $($it.Heading)"; $last = $it.Heading }
    $names = ''
    if ($it.Tasks.Count -gt 0) { $names = '  [' + ($it.Tasks -join ', ') + ']' }
    Write-Host ("    {0}: {1}{2}" -f $it.Line, (Get-Short $it.Text), $names)
}
if ($tickedNotDone.Count -gt 0) {
    Write-Host ''
    Write-Host "Ticked items naming a task that isn't finished (report only; never untick) ($($tickedNotDone.Count)):"
    foreach ($it in $tickedNotDone) { Write-Host ("    {0}: {1}  [{2}]" -f $it.Line, (Get-Short $it.Text 100), ($it.Tasks -join ', ')) }
}
