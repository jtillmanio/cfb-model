<#
  Runs specific test files across both apps (testAudit.run in .claude/kit.json).

    powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/run-tests.ps1 <file> [<file> ...]

  Paths are relative to the repo root, with either slash. Routing:
    python/**/test_*.py, python/**/*_test.py -> pytest  (uv --directory python run pytest)
    web/e2e/**/*.spec.ts                     -> Playwright (needs the migrated, seeded test DB)
    web/**/*.test.ts(x)                      -> Vitest
  Anything else (conftest.py, fixtures) is skipped with a note.

  Every group runs even if an earlier one fails. Exit code: 0 if all groups pass, 1 if any
  group fails, 2 if no file could be routed.
  Compatible with Windows PowerShell 5.1 and PowerShell 7+.
#>
$ErrorActionPreference = 'Continue'

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

$pytest = New-Object System.Collections.Generic.List[string]
$vitest = New-Object System.Collections.Generic.List[string]
$playwright = New-Object System.Collections.Generic.List[string]

foreach ($arg in $args) {
    $path = ([string]$arg).Replace('\', '/').TrimStart('.', '/')
    $name = [System.IO.Path]::GetFileName($path)
    if ($path -like 'python/*' -and ($name -like 'test_*.py' -or $name -like '*_test.py')) {
        $pytest.Add($path.Substring('python/'.Length))
    } elseif ($path -like 'web/e2e/*.spec.ts') {
        $playwright.Add($path.Substring('web/'.Length))
    } elseif ($path -like 'web/*' -and ($name -like '*.test.ts' -or $name -like '*.test.tsx')) {
        $vitest.Add($path.Substring('web/'.Length))
    } else {
        Write-Output "run-tests: skipped '$path' (no runner for this file)"
    }
}

$groups = @(
    @{ Name = 'pytest'; Files = $pytest; Cmd = 'uv --directory python run pytest' },
    @{ Name = 'vitest'; Files = $vitest; Cmd = 'pnpm --dir web exec vitest run' },
    @{ Name = 'playwright'; Files = $playwright; Cmd = 'pnpm --dir web exec playwright test' }
) | Where-Object { $_.Files.Count -gt 0 }

if ($groups.Count -eq 0) {
    Write-Output 'run-tests: no runnable test files given.'
    exit 2
}

$failed = $false
Push-Location -LiteralPath $root
try {
    foreach ($g in $groups) {
        $cmd = "$($g.Cmd) $($g.Files -join ' ')"
        Write-Output "run-tests: [$($g.Name)] $cmd"
        & cmd.exe /d /s /c "$cmd 2>&1"
        if ($LASTEXITCODE -ne 0) {
            Write-Output "run-tests: [$($g.Name)] FAILED (exit $LASTEXITCODE)"
            $failed = $true
        }
    }
} finally {
    Pop-Location
}

if ($failed) { exit 1 }
exit 0
