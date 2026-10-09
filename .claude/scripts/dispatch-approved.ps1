<#
  Level 2 dispatcher: starts one background Claude Code session per eligible task, up to the WIP limit.

  Eligible = status: Ready, plan_status: approved, autonomy: unattended, every depends_on task Done,
  and not already dispatched. Each session runs "/implement-task <ID> --unattended" and appears in
  agent view (claude agents), isolated in its own worktree.

  Usage (from the main checkout, on the base branch, after the PR with the approved plans is merged and pulled):
    powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/dispatch-approved.ps1 -DryRun
    powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/dispatch-approved.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/dispatch-approved.ps1 -Max 1
    powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/dispatch-approved.ps1 -Release TASK-014

  -Release removes a task's claim (use after abandoning or deleting its session).
  Claims live in .claude/state/dispatch.json (git-ignored) and clear automatically once the task is Done.

  Compatible with Windows PowerShell 5.1 and PowerShell 7+.
#>
param(
    [int]$Max = 0,
    [switch]$DryRun,
    [string]$PermissionMode = '',
    [string[]]$Release = @()
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\lib-tasks.ps1"

$root = Get-KitRoot
$config = Get-KitConfig $root
$wf = $config.workflow

$base = 'main'
if ($wf -and $wf.baseBranch) { $base = [string]$wf.baseBranch }
$wip = 2
if ($wf -and $wf.wipLimit) { $wip = [int]$wf.wipLimit }
$wipReason = ''
if ($wf -and $wf._wipLimitReason) { $wipReason = [string]$wf._wipLimitReason }
if ($Max -le 0) { $Max = $wip }
if (-not $PermissionMode) {
    $PermissionMode = 'acceptEdits'
    if ($wf -and $wf.unattendedPermissionMode) { $PermissionMode = [string]$wf.unattendedPermissionMode }
}

# ---- Preconditions ------------------------------------------------------------
$branch = ([string](& git -C $root rev-parse --abbrev-ref HEAD)).Trim()
if ($branch -ne $base) {
    Write-Host "Check out '$base' in the main checkout first (currently on '$branch'). Dispatched sessions branch from it."
    exit 1
}
$dirtyTasks = @(& git -C $root status --porcelain -- docs/tasks)
if ($dirtyTasks.Count -gt 0) {
    Write-Host 'docs/tasks has uncommitted changes. Dispatched sessions only see plans committed on the base branch:'
    Write-Host "move approved plans to a docs/plans-<date> branch, commit them by path, open a PR, merge it, then pull '$base'."
    $dirtyTasks | ForEach-Object { Write-Host "  $_" }
    exit 1
}
$ahead = 0
try { $ahead = [int]([string](& git -C $root rev-list --count "origin/$base..$base" 2>$null)).Trim() } catch { $ahead = 0 }
if ($ahead -gt 0) {
    Write-Host "Warning: local '$base' is $ahead commit(s) ahead of origin/$base. Nothing should be committed on it; move those commits to a branch and open a PR, or task PRs will carry them."
}
if (-not $DryRun -and -not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Write-Host "'claude' is not on PATH."
    exit 1
}

# ---- Load claims and tasks ----------------------------------------------------
$claimsPath = Join-Path $root '.claude/state/dispatch.json'
$claims = @{}
if (Test-Path -LiteralPath $claimsPath) {
    $obj = Get-Content -LiteralPath $claimsPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($obj) { foreach ($p in $obj.PSObject.Properties) { $claims[$p.Name] = $p.Value } }
}
foreach ($id in $Release) {
    if ($claims.ContainsKey($id)) { $claims.Remove($id); Write-Host "Released claim on $id." }
}

$tasks = @(Get-Tasks $root)
$byId = @{}
foreach ($t in $tasks) { if (-not $byId.ContainsKey($t.Id)) { $byId[$t.Id] = $t } }

foreach ($id in @($claims.Keys)) {
    if ($byId.ContainsKey($id) -and $byId[$id].Status -eq 'Done') { $claims.Remove($id) }
}
if (-not $DryRun -or $Release.Count -gt 0) { Write-Utf8File $claimsPath ($claims | ConvertTo-Json -Depth 4) }

$unclaimedActive = @($tasks | Where-Object { ($_.Status -eq 'In progress' -or $_.Status -eq 'Review') -and -not $claims.ContainsKey($_.Id) })
$inFlight = $claims.Count + $unclaimedActive.Count
$inFlightIds = @($claims.Keys) + @($unclaimedActive | ForEach-Object { $_.Id })

# ---- Eligibility ---------------------------------------------------------------
$eligible = New-Object System.Collections.Generic.List[object]
$skipped = New-Object System.Collections.Generic.List[string]
foreach ($t in $tasks) {
    if ($t.Status -ne 'Ready') { continue }
    if ($claims.ContainsKey($t.Id)) { continue }
    if ($t.Autonomy -ne 'unattended') { $skipped.Add("$($t.Id): autonomy is '$($t.Autonomy)' (run it with /implement-task)"); continue }
    if ($t.PlanStatus -ne 'approved') { $skipped.Add("$($t.Id): plan_status is '$($t.PlanStatus)' (run /plan-batch, then approve)"); continue }
    if (-not (Test-DepsDone $t $byId)) {
        $waiting = @($t.DependsOn | Where-Object { -not $byId.ContainsKey($_) -or $byId[$_].Status -ne 'Done' })
        $skipped.Add("$($t.Id): waiting on $($waiting -join ', ')")
        continue
    }
    $eligible.Add($t)
}

Write-Host "In flight: $inFlight / $wip  $(if ($inFlightIds.Count -gt 0) { '(' + ($inFlightIds -join ', ') + ')' })"
Write-Host "Eligible:  $($eligible.Count)  $(if ($eligible.Count -gt 0) { '(' + (($eligible | ForEach-Object { $_.Id }) -join ', ') + ')' })"
if ($skipped.Count -gt 0) {
    Write-Host 'Not eligible:'
    foreach ($s in $skipped) { Write-Host "  - $s" }
}

$slots = [Math]::Min($Max, $wip - $inFlight)
if ($slots -le 0) {
    Write-Host 'WIP limit reached. Review and merge open PRs (or -Release abandoned tasks), then rerun.'
    if ($wipReason) { Write-Host "WIP limit $wip because: $wipReason" }
    exit 0
}
if ($eligible.Count -eq 0) {
    Write-Host 'Nothing to dispatch.'
    exit 0
}

# ---- Dispatch -----------------------------------------------------------------
$dispatched = 0
Push-Location -LiteralPath $root
try {
    foreach ($t in ($eligible | Select-Object -First $slots)) {
        $model = $t.Model
        if ([string]::IsNullOrWhiteSpace($model)) { $model = 'sonnet' }
        $prompt = "/implement-task $($t.Id) --unattended"
        $cliArgs = @('--bg', '--name', $t.Id, '--model', $model, '--permission-mode', $PermissionMode, $prompt)

        if ($DryRun) {
            Write-Host ("[dry-run] claude " + (($cliArgs | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -join ' '))
            continue
        }

        Write-Host "Dispatching $($t.Id) ($model, $PermissionMode)..."
        & claude @cliArgs
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  Failed to dispatch $($t.Id) (exit $LASTEXITCODE). Not claimed."
            continue
        }
        $claims[$t.Id] = [pscustomobject]@{ dispatchedAt = (Get-Date).ToString('s'); model = $model; permissionMode = $PermissionMode }
        $dispatched++
    }
} finally {
    Pop-Location
}

if (-not $DryRun) {
    Write-Utf8File $claimsPath ($claims | ConvertTo-Json -Depth 4)
    Write-Host "Dispatched $dispatched. Monitor with: claude agents"
}
