<#
  Shared helpers for the kit scripts. Dot-source it:  . "$PSScriptRoot\lib-tasks.ps1"
  Compatible with Windows PowerShell 5.1 and PowerShell 7+.
#>

$script:Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Get-KitRoot {
    $root = (& git rev-parse --show-toplevel 2>$null)
    if (-not $root) { throw 'Not inside a git repository. Run this from your project.' }
    return ([string]$root).Trim()
}

function Get-KitConfig([string]$Root) {
    $path = Join-Path $Root '.claude/kit.json'
    if (-not (Test-Path -LiteralPath $path)) { throw ".claude/kit.json not found under $Root" }
    return (Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function ConvertFrom-FrontMatterValue([string]$Value) {
    # Strip a "# comment" (hash followed by a space, at the start or after whitespace) but keep values like "Fix #12".
    $v = [regex]::Replace($Value.Trim(), '(^|\s+)#\s.*$', '').Trim()
    if ($v.StartsWith('[') -and $v.EndsWith(']')) {
        $inner = $v.Substring(1, $v.Length - 2)
        return ,@($inner.Split(',') | ForEach-Object { $_.Trim().Trim('"').Trim("'") } | Where-Object { $_ })
    }
    return $v.Trim('"').Trim("'")
}

function Get-FmString($Map, [string]$Key, [string]$Default = '') {
    if ($Map.ContainsKey($Key) -and $null -ne $Map[$Key] -and "$($Map[$Key])" -ne '') { return [string]$Map[$Key] }
    return $Default
}

function Test-ArchiveDone($Config) {
    # workflow.archiveDone: Done task files move to docs/tasks/archive/. Default true; only an explicit false turns it off.
    if ($Config -and $Config.workflow -and $null -ne $Config.workflow.archiveDone) { return [bool]$Config.workflow.archiveDone }
    return $true
}

function Get-Tasks([string]$Root) {
    # Reads docs/tasks/TASK-*.md and docs/tasks/archive/TASK-*.md. Archived tasks stay visible to
    # dependency checks, ID numbering, and the board's metrics.
    $result = New-Object System.Collections.Generic.List[object]
    $files = @()
    foreach ($sub in @('docs/tasks', 'docs/tasks/archive')) {
        $dir = Join-Path $Root $sub
        if (Test-Path -LiteralPath $dir) { $files += @(Get-ChildItem -LiteralPath $dir -Filter 'TASK-*.md' -File) }
    }

    foreach ($file in ($files | Sort-Object Name)) {
        $archived = ((Split-Path -Leaf (Split-Path -Parent $file.FullName)) -eq 'archive')
        $lines = @(Get-Content -LiteralPath $file.FullName -Encoding UTF8)
        if ($lines.Count -lt 3 -or $lines[0].Trim() -ne '---') { continue }

        $fm = @{}
        for ($i = 1; $i -lt $lines.Count; $i++) {
            if ($lines[$i].Trim() -eq '---') { break }
            $m = [regex]::Match($lines[$i], '^([A-Za-z_]+)\s*:\s*(.*)$')
            if ($m.Success) { $fm[$m.Groups[1].Value] = ConvertFrom-FrontMatterValue $m.Groups[2].Value }
        }

        $metrics = @{}
        foreach ($line in $lines) {
            $mm = [regex]::Match($line, '^\s*-\s*(Verify rounds|Review rounds|First-pass AC FAILs|Plan revisions after approval)\s*:\s*(.*)$')
            if ($mm.Success) { $metrics[$mm.Groups[1].Value] = $mm.Groups[2].Value.Trim() }
        }

        $deps = @()
        if ($fm.ContainsKey('depends_on') -and $null -ne $fm['depends_on']) {
            $deps = @($fm['depends_on'] | Where-Object { $_ } | ForEach-Object { [string]$_ })
        }

        $result.Add([pscustomobject]@{
            Id              = Get-FmString $fm 'id'
            Title           = Get-FmString $fm 'title'
            Status          = Get-FmString $fm 'status' 'Draft'
            DependsOn       = $deps
            Size            = Get-FmString $fm 'size'
            Model           = Get-FmString $fm 'model' 'sonnet'
            Autonomy        = Get-FmString $fm 'autonomy' 'attended'
            Ui              = Get-FmString $fm 'ui' 'false'
            PlanStatus      = Get-FmString $fm 'plan_status' 'none'
            PlannedAtCommit = Get-FmString $fm 'planned_at_commit'
            FileName        = $file.Name
            FullPath        = $file.FullName
            Archived        = $archived
            RelPath         = $(if ($archived) { 'archive/' + $file.Name } else { $file.Name })  # relative to docs/tasks
            Metrics         = $metrics
        })
    }
    return $result
}

function Test-DepsDone($Task, $ById) {
    foreach ($d in $Task.DependsOn) {
        if (-not $ById.ContainsKey($d)) { return $false }
        if ($ById[$d].Status -ne 'Done') { return $false }
    }
    return $true
}

function Write-Utf8File([string]$Path, [string]$Text) {
    $dirName = Split-Path -Parent $Path
    if ($dirName -and -not (Test-Path -LiteralPath $dirName)) { New-Item -ItemType Directory -Path $dirName -Force | Out-Null }
    [System.IO.File]::WriteAllText($Path, $Text, $script:Utf8NoBom)
}
