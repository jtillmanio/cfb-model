<#
  PreToolUse hook (Read): stops a whole-file Read of a file listed in "largeFiles" in .claude/kit.json,
  so one accidental read of a huge design export, roadmap or data file doesn't spend the context a task needs.

  Each entry: { "pattern": "design/mockups.html", "hint": "Print one screen with scripts/screen.ps1 <id>", "always": false }
    - A Read without offset or limit on a matching file is denied, and the hint is returned to Claude.
    - "always": true denies every Read of the file, with or without offset/limit (generated data: query it instead).

  Patterns use PowerShell -like wildcards, matched case-insensitively against the path relative to the
  project root with forward slashes, the same as protectedPaths. "*" also matches across folders.

  This guards only the Read tool. Reading the file through a shell command is not blocked; the hint
  should name the cheap way to get at the part Claude needs.

  Hook contract:
    exit 0 -> allowed
    exit 2 -> blocked; stderr tells Claude why and what to do instead

  Fails open (allows the read) if the payload or config can't be read.
  Compatible with Windows PowerShell 5.1 and PowerShell 7+.
#>
$ErrorActionPreference = 'Continue'

try {
    $raw = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($raw)) { exit 0 }
    $payload = $raw | ConvertFrom-Json
} catch {
    exit 0
}

$projectDir = $env:CLAUDE_PROJECT_DIR
if ([string]::IsNullOrWhiteSpace($projectDir)) { $projectDir = $payload.cwd }
if ([string]::IsNullOrWhiteSpace($projectDir)) { $projectDir = (Get-Location).Path }

$configPath = Join-Path $projectDir '.claude/kit.json'
if (-not (Test-Path -LiteralPath $configPath)) { exit 0 }
try {
    $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
} catch {
    exit 0
}

$rules = @($config.largeFiles | Where-Object { $_ -and -not [string]::IsNullOrWhiteSpace($_.pattern) })
if ($rules.Count -eq 0) { exit 0 }

$filePath = $payload.tool_input.file_path
if ([string]::IsNullOrWhiteSpace($filePath)) { exit 0 }

$root = [System.IO.Path]::GetFullPath($projectDir).TrimEnd('\', '/')
$fullFile = [System.IO.Path]::GetFullPath($filePath)
if (-not $fullFile.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) { exit 0 }
$rel = $fullFile.Substring($root.Length).TrimStart('\', '/').Replace('\', '/')

$hasRange = ($null -ne $payload.tool_input.offset) -or ($null -ne $payload.tool_input.limit)

foreach ($rule in $rules) {
    $pattern = ([string]$rule.pattern).Replace('\', '/')
    if (-not ($rel -like $pattern)) { continue }
    $always = ($rule.always -eq $true)
    if ($hasRange -and -not $always) { exit 0 }

    $hint = 'Read only the part you need: pass offset and limit, or search it first with Grep.'
    if (-not [string]::IsNullOrWhiteSpace($rule.hint)) { $hint = [string]$rule.hint }
    if ($always) {
        [Console]::Error.WriteLine("Blocked: '$rel' matches largeFiles pattern '$pattern' in .claude/kit.json and is never read with the Read tool.")
    } else {
        [Console]::Error.WriteLine("Blocked: '$rel' matches largeFiles pattern '$pattern' in .claude/kit.json. Don't read it whole.")
    }
    [Console]::Error.WriteLine($hint)
    exit 2
}
exit 0
