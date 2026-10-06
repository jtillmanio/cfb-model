<#
  PostToolUse hook: runs the "fast" checks from .claude/kit.json after Claude edits a source file.

  Hook contract:
    exit 0 -> checks passed, or nothing to check. Claude continues.
    exit 2 -> a check failed. stderr is fed back to Claude so it fixes the error.

  Compatible with Windows PowerShell 5.1 and PowerShell 7+.
#>
$ErrorActionPreference = 'Continue'

# ---- 1. Read the hook payload (JSON on stdin) -------------------------------
try {
    $raw = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($raw)) { exit 0 }
    $payload = $raw | ConvertFrom-Json
} catch {
    exit 0
}

# ---- 2. Locate the project and its config -----------------------------------
$projectDir = $env:CLAUDE_PROJECT_DIR
if ([string]::IsNullOrWhiteSpace($projectDir)) { $projectDir = $payload.cwd }
if ([string]::IsNullOrWhiteSpace($projectDir)) { $projectDir = (Get-Location).Path }

$configPath = Join-Path $projectDir '.claude/kit.json'
if (-not (Test-Path -LiteralPath $configPath)) { exit 0 }

try {
    $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
} catch {
    [Console]::Error.WriteLine('post-edit-verify: .claude/kit.json is not valid JSON, so fast checks did not run. Fix the file.')
    exit 2
}
if ($null -eq $config.verify) { exit 0 }

$fast = @($config.verify.fast | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
if ($fast.Count -eq 0) { exit 0 }

# ---- 3. Only react to source files inside the project -----------------------
$filePath = $payload.tool_input.file_path
if ([string]::IsNullOrWhiteSpace($filePath)) { $filePath = $payload.tool_input.notebook_path }
if ([string]::IsNullOrWhiteSpace($filePath)) { exit 0 }

$extensions = @($config.verify.sourceExtensions | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object { $_.ToLowerInvariant() })
if ($extensions.Count -gt 0) {
    $ext = [System.IO.Path]::GetExtension($filePath).ToLowerInvariant()
    if ($extensions -notcontains $ext) { exit 0 }
}

$root = [System.IO.Path]::GetFullPath($projectDir).TrimEnd('\', '/')
$fullFile = [System.IO.Path]::GetFullPath($filePath)
if (-not $fullFile.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) { exit 0 }
$relFile = $fullFile.Substring($root.Length).TrimStart('\', '/')
$fileArg = $relFile
if ($relFile.Contains(' ')) { $fileArg = '"' + $relFile + '"' }

# ---- 4. Run each fast check --------------------------------------------------
$maxLines = 60
if ($config.verify.maxOutputLines) { $maxLines = [int]$config.verify.maxOutputLines }

$failures = New-Object System.Collections.Generic.List[string]
Push-Location -LiteralPath $root
try {
    foreach ($template in $fast) {
        $cmd = $template.Replace('{file}', $fileArg)
        $timer = [System.Diagnostics.Stopwatch]::StartNew()
        $output = & cmd.exe /d /s /c "$cmd 2>&1"
        $code = $LASTEXITCODE
        $timer.Stop()

        if ($code -ne 0) {
            $lines = @($output | ForEach-Object { "$_" })
            if ($lines.Count -gt $maxLines) {
                $trimmed = $lines.Count - $maxLines
                $lines = @("... ($trimmed earlier lines trimmed) ...") + $lines[($lines.Count - $maxLines)..($lines.Count - 1)]
            }
            $seconds = [math]::Round($timer.Elapsed.TotalSeconds, 1)
            $failures.Add("FAILED (exit $code, ${seconds}s): $cmd`n" + ($lines -join "`n"))
        }
    }
} finally {
    Pop-Location
}

# ---- 5. Report ---------------------------------------------------------------
if ($failures.Count -gt 0) {
    [Console]::Error.WriteLine("Fast checks failed after editing $relFile.")
    [Console]::Error.WriteLine('If you are mid-way through a multi-file change, finish it first; otherwise fix these now.')
    [Console]::Error.WriteLine('')
    foreach ($f in $failures) {
        [Console]::Error.WriteLine($f)
        [Console]::Error.WriteLine('')
    }
    exit 2
}
exit 0
