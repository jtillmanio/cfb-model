<#
  Moves every task file with status: Done from docs/tasks/ to docs/tasks/archive/, using git mv so history follows
  the file. The renames are staged; the caller commits them. Does nothing when workflow.archiveDone is false.

  Run it on a task, docs, or chore branch, never on the base branch (nothing is committed there).
  /implement-task runs it at close-out and again at accept, so any Done task, whoever finished it, is archived by
  the next task that closes out.

  Usage (from anywhere in the repo):
    powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/archive-done.ps1 -DryRun
    powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/archive-done.ps1

  Prints one "Archived <ID>: <new path>" line per file moved. A file that also has unstaged edits (e.g. the
  status: Done line just written) needs a `git add <new path>` afterwards to stage them.

  Compatible with Windows PowerShell 5.1 and PowerShell 7+.
#>
param([switch]$DryRun)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\lib-tasks.ps1"

$root = Get-KitRoot
$config = Get-KitConfig $root
if (-not (Test-ArchiveDone $config)) {
    Write-Host 'workflow.archiveDone is false in .claude/kit.json; nothing archived.'
    exit 0
}

$base = 'main'
if ($config.workflow -and $config.workflow.baseBranch) { $base = [string]$config.workflow.baseBranch }
$branch = ([string](& git -C $root rev-parse --abbrev-ref HEAD)).Trim()
if ($branch -eq $base -and -not $DryRun) {
    Write-Host "On '$base'. Archive moves reach it through a PR: run this on a task, docs, or chore branch."
    exit 1
}

$done = @(Get-Tasks $root | Where-Object { $_.Status -eq 'Done' -and -not $_.Archived })
if ($done.Count -eq 0) {
    Write-Host 'No Done tasks outside docs/tasks/archive/.'
    exit 0
}

$archiveDir = Join-Path $root 'docs/tasks/archive'
$moved = 0
foreach ($t in $done) {
    $src = 'docs/tasks/' + $t.FileName
    $dest = 'docs/tasks/archive/' + $t.FileName
    if (Test-Path -LiteralPath (Join-Path $root $dest)) {
        Write-Host "Skipped $($t.Id): $dest already exists. Compare the two files and keep one."
        continue
    }
    if ($DryRun) {
        Write-Host "[dry-run] $src -> $dest"
        continue
    }
    if (-not (Test-Path -LiteralPath $archiveDir)) { New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null }

    $tracked = @(& git -C $root ls-files -- $src)
    if ($tracked.Count -gt 0) {
        & git -C $root mv -- $src $dest
        if ($LASTEXITCODE -ne 0) { throw "git mv $src $dest failed (exit $LASTEXITCODE)" }
        Write-Host "Archived $($t.Id): $dest"
    } else {
        Move-Item -LiteralPath $t.FullPath -Destination (Join-Path $root $dest)
        Write-Host "Archived $($t.Id): $dest (untracked; moved but not staged)"
    }
    $moved++
}

if (-not $DryRun) { Write-Host "Moved $moved task file(s). Commit the renames with this branch's next commit." }
