<#
  PreToolUse hook (Bash, PowerShell): stops shell commands that destroy work nobody can give back:
  deleting the project, the repository, the home folder, a drive, or anything outside the project;
  discarding uncommitted work; deleting the GitHub repository; erasing disks.

  Denied (exit 2; Claude is told to stop and ask the user):
    - deleting anything outside the project (or worktree) other than inside the temp folder or a
      destructiveGuard.allowPaths entry: a drive, the home folder, system folders, another repository;
    - deleting the project itself, a folder that contains it, everything in it ("rm -rf *"), its .git
      folder, a nested repository or worktree, or a protectedPaths file;
    - a recursive delete whose path can't be resolved (a variable, command substitution, xargs input):
      an empty variable turns "rm -rf $DIR/" into "rm -rf /";
    - disk and OS tools (format, diskpart, Format-Volume, Clear-Disk, mkfs, dd to a device, ...);
    - gh repo delete / archive / visibility changes, git push --mirror, force pushes, deleting the
      base branch on the remote.

  Asked (the user approves or declines in the permission prompt):
    - a recursive delete inside the project of a folder holding tracked files (use git rm -r) or
      untracked files git doesn't ignore (possibly the owner's work in progress);
    - git commands that discard uncommitted work or history: git clean -f, git reset --hard,
      git checkout -- ., git restore ., git stash drop/clear, git worktree remove --force,
      filter-branch, reflog expire;
    - deletes it can't check: inline code (python -c, node -e) that removes folders, a non-recursive
      delete of an unresolved path;
    - each destructiveGuard.commands rule (decision "ask" unless it says "deny").
  In permission mode bypassPermissions nobody can answer a prompt, so these are denied too.

  Allowed without a prompt: deleting files, and folders whose contents git ignores (node_modules,
  build output, caches), inside the project; anything inside the temp folder.

  It reads the commands the Bash tool (Git Bash) and the PowerShell tool run, and what they hand to
  bash -c, powershell -Command / -EncodedCommand, cmd /c, wsl, $( ) and heredocs. It is a net, not a
  sandbox: a script file that deletes things, or a spelling it doesn't parse, gets through. The
  CLAUDE.md stop-and-ask list is the rule; this hook catches the slips.

  kit.json (optional; a missing key takes these defaults):
    "destructiveGuard": {
      "allowPaths": [".kit-incoming"],
      "commands": []
    }
    allowPaths: project-relative patterns (-like, forward slashes) or absolute folders that deletes may
                touch without a check. Replaces the default list when present.
    commands:   extra rules, { "pattern": "<regex, matched case-insensitively against the command>",
                "decision": "ask" | "deny", "reason": "..." }, e.g. "prisma migrate reset".

  Every deny and ask is appended to .claude/state/guard-destructive.log (git-ignored).

  Hook contract:
    exit 2               -> blocked; stderr tells Claude why
    exit 0 + JSON "ask"  -> the user is asked to approve
    exit 0, no output    -> no opinion; the normal permission rules apply
  Register it with "onFailure": "block" (Claude Code 2.1.295+) so a crash or timeout blocks the
  command instead of letting it through. Compatible with Windows PowerShell 5.1 and PowerShell 7+.
#>
$ErrorActionPreference = 'Continue'
$utf8 = New-Object System.Text.UTF8Encoding($false)

try {
    $reader = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), $utf8)
    $raw = $reader.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($raw)) { exit 0 }
    $payload = $raw | ConvertFrom-Json
} catch {
    exit 0
}

$command = [string]$payload.tool_input.command
if ([string]::IsNullOrWhiteSpace($command)) { exit 0 }

$toolMode = 'bash'
if ([string]$payload.tool_name -eq 'PowerShell') { $toolMode = 'powershell' }
$bypass = ([string]$payload.permission_mode -eq 'bypassPermissions')

# ---- Path helpers -----------------------------------------------------------------------------

function Get-Full([string]$p) {
    if ([string]::IsNullOrWhiteSpace($p)) { return $null }
    try { $f = [System.IO.Path]::GetFullPath($p) } catch { return $null }
    if ($f.Length -gt 3) { $f = $f.TrimEnd('\') }
    return $f
}

function Test-Same([string]$a, [string]$b) {
    if (-not $a -or -not $b) { return $false }
    return [string]::Equals($a.TrimEnd('\'), $b.TrimEnd('\'), [System.StringComparison]::OrdinalIgnoreCase)
}

# True when $p is strictly inside $root.
function Test-Inside([string]$p, [string]$root) {
    if (-not $p -or -not $root) { return $false }
    return $p.StartsWith($root.TrimEnd('\') + '\', [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-Related([string]$a, [string]$b) {
    return (Test-Same $a $b) -or (Test-Inside $a $b) -or (Test-Inside $b $a)
}

# /c/Users/x (Git Bash), /mnt/c/x (WSL), /cygdrive/c/x -> C:\Users\x
function Convert-MsysPath([string]$p) {
    if ($p -match '^/(?:mnt/|cygdrive/)?([A-Za-z])(?:/(.*))?$') {
        return $matches[1].ToUpperInvariant() + ':\' + ([string]$matches[2]).Replace('/', '\')
    }
    return $p
}

# ---- Context ----------------------------------------------------------------------------------

$script:projectDir = $env:CLAUDE_PROJECT_DIR
if ([string]::IsNullOrWhiteSpace($script:projectDir)) { $script:projectDir = [string]$payload.cwd }
if ([string]::IsNullOrWhiteSpace($script:projectDir)) { $script:projectDir = (Get-Location).Path }
$script:projectDir = Get-Full (Convert-MsysPath $script:projectDir)
$script:startCwd = Get-Full (Convert-MsysPath ([string]$payload.cwd))
if (-not $script:startCwd) { $script:startCwd = $script:projectDir }

$script:homeDir = Get-Full $env:USERPROFILE
$script:tempRoots = New-Object System.Collections.Generic.List[string]
$tempCandidates = @([System.IO.Path]::GetTempPath(), $env:TEMP, $env:TMP)
if ($env:LOCALAPPDATA) { $tempCandidates += (Join-Path $env:LOCALAPPDATA 'Temp') }
foreach ($t in $tempCandidates) {
    $f = Get-Full $t
    if ($f -and -not ($script:tempRoots -contains $f)) { $script:tempRoots.Add($f) }
}
$script:tempMain = 'C:\Windows\Temp'
if ($script:tempRoots.Count -gt 0) { $script:tempMain = $script:tempRoots[0] }

$config = $null
if ($script:projectDir) {
    $cfgPath = Join-Path $script:projectDir '.claude/kit.json'
    if (Test-Path -LiteralPath $cfgPath) {
        try { $config = Get-Content -LiteralPath $cfgPath -Raw | ConvertFrom-Json } catch { $config = $null }
    }
}

$script:protected = @()
$script:customRules = @()
$script:baseBranch = 'main'
$script:allowLease = $false
$allowList = @('.kit-incoming')
if ($config) {
    $script:protected = @($config.protectedPaths | Where-Object { $_ -and -not [string]::IsNullOrWhiteSpace($_.pattern) } | ForEach-Object { ([string]$_.pattern).Replace('\', '/') })
    if ($config.workflow) {
        if (-not [string]::IsNullOrWhiteSpace($config.workflow.baseBranch)) { $script:baseBranch = [string]$config.workflow.baseBranch }
        if ($config.workflow.allowForceWithLease -eq $true) { $script:allowLease = $true }
    }
    $guardCfg = $config.destructiveGuard
    if ($guardCfg) {
        if ($null -ne $guardCfg.allowPaths) { $allowList = @($guardCfg.allowPaths) }
        $script:customRules = @($guardCfg.commands | Where-Object { $_ -and -not [string]::IsNullOrWhiteSpace($_.pattern) })
    }
}
$script:allowRel = New-Object System.Collections.Generic.List[string]
$script:allowAbs = New-Object System.Collections.Generic.List[string]
foreach ($entry in $allowList) {
    $s = Convert-MsysPath ([string]$entry)
    if ([string]::IsNullOrWhiteSpace($s)) { continue }
    if ($s -match '^([A-Za-z]:[\\/]|\\\\)') {
        $f = Get-Full $s
        if ($f) { $script:allowAbs.Add($f) }
    } else {
        $script:allowRel.Add($s.Replace('\', '/').Trim('/'))
    }
}

# Project roots: the project dir, the git top level of the session's folder (a worktree), and the main
# checkout behind a worktree. A repository unrelated to the project is never a root.
$script:roots = $null
function Get-Roots {
    if ($null -ne $script:roots) { return ,$script:roots }
    $list = New-Object System.Collections.Generic.List[string]
    if ($script:projectDir) { $list.Add($script:projectDir) }
    $where = $script:startCwd
    if (-not $where) { $where = $script:projectDir }
    if ($where -and (Test-Path -LiteralPath $where)) {
        $out = @(& git -C $where rev-parse --path-format=absolute --show-toplevel --git-common-dir 2>$null)
        if ($LASTEXITCODE -eq 0 -and $out.Count -ge 1) {
            $cands = New-Object System.Collections.Generic.List[string]
            $top = Get-Full ([string]$out[0])
            if ($top) { $cands.Add($top) }
            if ($out.Count -ge 2) {
                $common = Get-Full ([string]$out[1])
                if ($common -and (Split-Path -Leaf $common) -ieq '.git') { $cands.Add((Get-Full (Split-Path -Parent $common))) }
            }
            foreach ($c in $cands) {
                if (-not $c -or ($list -contains $c)) { continue }
                if (-not $script:projectDir -or (Test-Related $c $script:projectDir)) { $list.Add($c) }
            }
        }
    }
    $script:roots = $list
    return ,$list
}

# ---- Findings ---------------------------------------------------------------------------------

$script:findings = New-Object System.Collections.Generic.List[object]
function Add-Finding([string]$decision, [string]$reason) {
    $script:findings.Add([pscustomobject]@{ Decision = $decision; Reason = $reason })
}

# ---- Tokenizers -------------------------------------------------------------------------------
# Each returns a list of segments: { Sep (operator before it), Toks, Nested (command substitutions and
# script blocks to check separately), Marker (bash "(" / ")"), Stdin (heredoc body) }.
# A token is { T = text with quotes removed and known variables expanded, D = holds something
# unresolvable, Q = was quoted }.

$script:PwdMark = [string][char]1 + 'PWD' + [string][char]1
$script:rxHeredoc = New-Object System.Text.RegularExpressions.Regex('\G(?:''([^'']*)''|"([^"]*)"|\\?([A-Za-z0-9_.-]+))')
$script:rxBashVar = New-Object System.Text.RegularExpressions.Regex('\G(?:[A-Za-z_][A-Za-z0-9_]*|[0-9@*#?$!-])')
$script:rxPsVar = New-Object System.Text.RegularExpressions.Regex('\G(?:[A-Za-z_][A-Za-z0-9_]*:)?(?:[A-Za-z0-9_]+|[?^$])')

function New-Segment([string]$sep, $toks, $nested, [string]$marker) {
    return [pscustomobject]@{ Sep = $sep; Toks = $toks; Nested = $nested; Marker = $marker; Stdin = '' }
}

function New-State($shadow) {
    if ($null -eq $shadow) { $shadow = @{} }
    return @{
        Shadow = $shadow; Sub = $false
        Segs = (New-Object System.Collections.Generic.List[object])
        Toks = (New-Object System.Collections.Generic.List[object])
        Nested = (New-Object System.Collections.Generic.List[object])
        Buf = (New-Object System.Text.StringBuilder)
        InTok = $false; Dyn = $false; Quoted = $false; SkipNext = $false; Sep = ''
        Heredocs = (New-Object System.Collections.Generic.List[string])
    }
}

function Close-Token($st) {
    if ($st.InTok) {
        if ($st.SkipNext) { $st.SkipNext = $false }
        else { $st.Toks.Add([pscustomobject]@{ T = $st.Buf.ToString(); D = $st.Dyn; S = $st.Sub; Q = $st.Quoted }) }
    }
    [void]$st.Buf.Clear()
    $st.InTok = $false; $st.Dyn = $false; $st.Sub = $false; $st.Quoted = $false
}

function Close-Segment($st, [string]$nextSep) {
    Close-Token $st
    $st.SkipNext = $false
    if ($st.Toks.Count -gt 0 -or $st.Nested.Count -gt 0) {
        $st.Segs.Add((New-Segment $st.Sep $st.Toks $st.Nested ''))
    }
    $st.Toks = New-Object System.Collections.Generic.List[object]
    $st.Nested = New-Object System.Collections.Generic.List[object]
    $st.Sep = $nextSep
}

function Add-Marker($st, [string]$marker) {
    Close-Segment $st ';'
    $st.Segs.Add((New-Segment ';' (New-Object System.Collections.Generic.List[object]) (New-Object System.Collections.Generic.List[object]) $marker))
}

function Add-Text($st, [string]$s) {
    [void]$st.Buf.Append($s)
    $st.InTok = $true
}

function Get-EnvValue([string]$name) {
    $v = [Environment]::GetEnvironmentVariable($name)
    if ([string]::IsNullOrEmpty($v)) { return $null }
    return $v
}

function Get-VarValue([string]$name, [string]$mode) {
    $u = $name.ToUpperInvariant()
    if ($u -eq 'PWD' -or ($mode -eq 'cmd' -and $u -eq 'CD')) { return $script:PwdMark }
    if ($mode -eq 'cmd') { return Get-EnvValue $name }
    if ($mode -eq 'powershell') {
        if ($u -eq 'TRUE' -or $u -eq 'FALSE' -or $u -eq 'NULL') { return '$' + $name.ToLowerInvariant() }
        if ($u -eq 'HOME') { return $env:USERPROFILE }
        if ($u.StartsWith('ENV:')) { return Get-EnvValue $name.Substring(4) }
        return $null
    }
    if ($u -eq 'HOME') {
        $h = Get-EnvValue 'HOME'
        if (-not $h) { $h = $env:USERPROFILE }
        return $h
    }
    if ($name -match '^[A-Za-z_][A-Za-z0-9_]*$') { return Get-EnvValue $name }
    return $null
}

function Add-Var($st, [string]$name, [string]$mode) {
    $v = $null
    if (-not $st.Shadow.ContainsKey($name)) { $v = Get-VarValue $name $mode }
    if ($null -eq $v) {
        $st.Dyn = $true
        Add-Text $st ('${' + $name + '}')
    } else {
        Add-Text $st $v
    }
}

# Skips heredoc bodies starting at $i (the line after the << operator). Returns { Index, Body }.
function Skip-Heredocs([string]$text, [int]$i, $delims) {
    $body = New-Object System.Text.StringBuilder
    foreach ($d in $delims) {
        while ($i -lt $text.Length) {
            $j = $text.IndexOf("`n", $i)
            if ($j -lt 0) { $j = $text.Length }
            $line = $text.Substring($i, $j - $i).TrimEnd("`r")
            $i = $j + 1
            if ($line.Trim() -eq $d) { break }
            [void]$body.AppendLine($line)
        }
    }
    return [pscustomobject]@{ Index = $i; Body = $body.ToString() }
}

# Index of the bracket closing the one just before $i, skipping quotes, escapes and heredocs.
function Find-Close([string]$s, [int]$i, [string]$open, [string]$close, [string]$mode) {
    $depth = 1
    $q = ''
    $pending = New-Object System.Collections.Generic.List[string]
    while ($i -lt $s.Length) {
        $c = [string]$s[$i]
        if ($q -ne '') {
            if ($c -eq $q) { $q = '' }
            elseif ($c -eq '\' -and $q -eq '"' -and $mode -eq 'bash') { $i++ }
            $i++
            continue
        }
        if ($c -eq "`n" -and $pending.Count -gt 0) {
            $r = Skip-Heredocs $s ($i + 1) $pending
            $pending.Clear()
            $i = $r.Index
            continue
        }
        if ($mode -eq 'bash' -and $c -eq '\') { $i += 2; continue }
        if ($mode -eq 'powershell' -and $c -eq '`') { $i += 2; continue }
        if ($c -eq "'" -or $c -eq '"') { $q = $c }
        elseif ($mode -eq 'bash' -and $c -eq '<' -and $i + 2 -lt $s.Length -and $s[$i + 1] -eq '<' -and $s[$i + 2] -ne '<') {
            $k = $i + 2
            if ($s[$k] -eq '-') { $k++ }
            while ($k -lt $s.Length -and ($s[$k] -eq ' ' -or $s[$k] -eq "`t")) { $k++ }
            $m = $script:rxHeredoc.Match($s, $k)
            if ($m.Success -and $m.Length -gt 0) {
                $pending.Add($m.Groups[1].Value + $m.Groups[2].Value + $m.Groups[3].Value)
                $i = $k + $m.Length
                continue
            }
        }
        elseif ($c -eq $open) { $depth++ }
        elseif ($c -eq $close) {
            $depth--
            if ($depth -eq 0) { return $i }
        }
        $i++
    }
    return $s.Length
}

function Read-Dollar($st, [string]$text, [int]$i, [string]$mode) {
    $n = $text.Length
    if ($i + 1 -ge $n) { Add-Text $st '$'; return $i + 1 }
    $c = $text[$i + 1]
    if ($c -eq '(') {
        $j = Find-Close $text ($i + 2) '(' ')' $mode
        $end = [Math]::Min($j, $n)
        $st.Nested.Add([pscustomobject]@{ Text = $text.Substring($i + 2, [Math]::Max(0, $end - $i - 2)); Mode = $mode })
        $st.Dyn = $true; $st.Sub = $true
        Add-Text $st '$(...)'
        return $j + 1
    }
    if ($c -eq '{') {
        $j = $text.IndexOf('}', $i + 2)
        if ($j -lt 0) { $j = $n }
        Add-Var $st $text.Substring($i + 2, $j - $i - 2) $mode
        return $j + 1
    }
    $rx = $script:rxBashVar
    if ($mode -eq 'powershell') { $rx = $script:rxPsVar }
    $m = $rx.Match($text, $i + 1)
    if (-not $m.Success) { Add-Text $st '$'; return $i + 1 }
    Add-Var $st $m.Value $mode
    return $i + 1 + $m.Length
}

function Read-Backtick($st, [string]$text, [int]$i) {
    $j = $text.IndexOf('`', $i + 1)
    if ($j -lt 0) { $j = $text.Length }
    $st.Nested.Add([pscustomobject]@{ Text = $text.Substring($i + 1, $j - $i - 1); Mode = 'bash' })
    $st.Dyn = $true; $st.Sub = $true
    Add-Text $st '`...`'
    return $j + 1
}

# > >> 2> &> *> 2>&1 <: drops the redirect target (the next word) and an fd prefix.
function Read-Redirect($st, [string]$text, [int]$i) {
    if ($st.InTok -and -not $st.Quoted -and $st.Buf.ToString() -match '^(\d+|\*)$') {
        [void]$st.Buf.Clear()
        $st.InTok = $false; $st.Dyn = $false; $st.Sub = $false
    } else {
        Close-Token $st
    }
    while ($i -lt $text.Length -and '<>&|'.Contains([string]$text[$i])) { $i++ }
    $st.SkipNext = $true
    return $i
}

function Split-Bash([string]$text, $shadow) {
    $st = New-State $shadow
    $n = $text.Length
    $i = 0
    while ($i -lt $n) {
        $c = $text[$i]
        if ($c -eq "`n") {
            Close-Segment $st ';'
            $i++
            if ($st.Heredocs.Count -gt 0) {
                $r = Skip-Heredocs $text $i $st.Heredocs
                $i = $r.Index
                if ($st.Segs.Count -gt 0) { $st.Segs[$st.Segs.Count - 1].Stdin = $r.Body }
                $st.Heredocs.Clear()
            }
            continue
        }
        if ($c -eq ' ' -or $c -eq "`t" -or $c -eq "`r") { Close-Token $st; $i++; continue }
        if ($c -eq '\') {
            if ($i + 1 -lt $n) {
                if ($text[$i + 1] -ne "`n") { Add-Text $st ([string]$text[$i + 1]) }
                $i += 2
            } else { $i++ }
            continue
        }
        if ($c -eq "'") {
            $j = $text.IndexOf("'", $i + 1)
            if ($j -lt 0) { $j = $n }
            Add-Text $st $text.Substring($i + 1, $j - $i - 1)
            $st.Quoted = $true
            $i = $j + 1
            continue
        }
        if ($c -eq '"') {
            $st.InTok = $true; $st.Quoted = $true
            $i++
            while ($i -lt $n -and $text[$i] -ne '"') {
                $d = $text[$i]
                if ($d -eq '\' -and $i + 1 -lt $n -and '"$`\'.Contains([string]$text[$i + 1])) { Add-Text $st ([string]$text[$i + 1]); $i += 2; continue }
                if ($d -eq '$') { $i = Read-Dollar $st $text $i 'bash'; continue }
                if ($d -eq '`') { $i = Read-Backtick $st $text $i; continue }
                Add-Text $st ([string]$d)
                $i++
            }
            $i++
            continue
        }
        if ($c -eq '$') { $i = Read-Dollar $st $text $i 'bash'; continue }
        if ($c -eq '`') { $i = Read-Backtick $st $text $i; continue }
        if ($c -eq '#' -and -not $st.InTok) {
            $j = $text.IndexOf("`n", $i)
            if ($j -lt 0) { $j = $n }
            $i = $j
            continue
        }
        if ($c -eq ';') { Close-Segment $st ';'; $i++; continue }
        if ($c -eq '&') {
            if ($i + 1 -lt $n -and $text[$i + 1] -eq '&') { Close-Segment $st '&&'; $i += 2; continue }
            if ($i + 1 -lt $n -and $text[$i + 1] -eq '>') { Close-Token $st; $i = Read-Redirect $st $text ($i + 1); continue }
            Close-Segment $st ';'
            $i++
            continue
        }
        if ($c -eq '|') {
            if ($i + 1 -lt $n -and $text[$i + 1] -eq '|') { Close-Segment $st '||'; $i += 2; continue }
            Close-Segment $st '|'
            $i++
            if ($i -lt $n -and $text[$i] -eq '&') { $i++ }
            continue
        }
        if ($c -eq '(' -and -not $st.InTok) { Add-Marker $st 'push'; $i++; continue }
        if ($c -eq ')') { Add-Marker $st 'pop'; $i++; continue }
        if ($c -eq '<' -and $i + 1 -lt $n -and $text[$i + 1] -eq '<') {
            Close-Token $st
            if ($i + 2 -lt $n -and $text[$i + 2] -eq '<') { $i = Read-Redirect $st $text $i; continue }
            $i += 2
            if ($i -lt $n -and $text[$i] -eq '-') { $i++ }
            while ($i -lt $n -and ($text[$i] -eq ' ' -or $text[$i] -eq "`t")) { $i++ }
            $m = $script:rxHeredoc.Match($text, $i)
            if ($m.Success -and $m.Length -gt 0) {
                $st.Heredocs.Add($m.Groups[1].Value + $m.Groups[2].Value + $m.Groups[3].Value)
                $i += $m.Length
            }
            continue
        }
        if ($c -eq '>' -or $c -eq '<') { $i = Read-Redirect $st $text $i; continue }
        Add-Text $st ([string]$c)
        $i++
    }
    Close-Segment $st ''
    return ,$st.Segs
}

function Split-PowerShell([string]$text, $shadow) {
    $st = New-State $shadow
    $n = $text.Length
    $i = 0
    while ($i -lt $n) {
        $c = $text[$i]
        if ($c -eq "`n") { Close-Segment $st ';'; $i++; continue }
        if ($c -eq ' ' -or $c -eq "`t" -or $c -eq "`r" -or $c -eq ',') { Close-Token $st; $i++; continue }
        if ($c -eq '`') {
            if ($i + 1 -lt $n -and $text[$i + 1] -eq "`r") { $i += 3; continue }
            if ($i + 1 -lt $n) {
                if ($text[$i + 1] -ne "`n") { Add-Text $st ([string]$text[$i + 1]) }
                $i += 2
            } else { $i++ }
            continue
        }
        if ($c -eq '@' -and -not $st.InTok -and $i + 1 -lt $n -and ($text[$i + 1] -eq "'" -or $text[$i + 1] -eq '"')) {
            $q = [string]$text[$i + 1]
            $k = $i + 2
            while ($k -lt $n -and ($text[$k] -eq ' ' -or $text[$k] -eq "`t" -or $text[$k] -eq "`r")) { $k++ }
            if ($k -lt $n -and $text[$k] -eq "`n") {
                $end = $text.IndexOf("`n" + $q + '@', $k)
                $next = $n
                if ($end -lt 0) { $end = $n } else { $next = $end + 3 }
                $body = $text.Substring($k + 1, [Math]::Max(0, $end - $k - 1))
                Add-Text $st $body
                $st.Quoted = $true
                if ($q -eq '"' -and $body.Contains('$')) { $st.Dyn = $true; $st.Sub = $true }
                $i = $next
                continue
            }
        }
        if ($c -eq "'") {
            $sb = New-Object System.Text.StringBuilder
            $i++
            while ($i -lt $n) {
                if ($text[$i] -eq "'") {
                    if ($i + 1 -lt $n -and $text[$i + 1] -eq "'") { [void]$sb.Append("'"); $i += 2; continue }
                    break
                }
                [void]$sb.Append($text[$i])
                $i++
            }
            Add-Text $st $sb.ToString()
            $st.Quoted = $true
            $i++
            continue
        }
        if ($c -eq '"') {
            $st.InTok = $true; $st.Quoted = $true
            $i++
            while ($i -lt $n) {
                $d = $text[$i]
                if ($d -eq '"') {
                    if ($i + 1 -lt $n -and $text[$i + 1] -eq '"') { Add-Text $st '"'; $i += 2; continue }
                    break
                }
                if ($d -eq '`' -and $i + 1 -lt $n) { Add-Text $st ([string]$text[$i + 1]); $i += 2; continue }
                if ($d -eq '$') { $i = Read-Dollar $st $text $i 'powershell'; continue }
                Add-Text $st ([string]$d)
                $i++
            }
            $i++
            continue
        }
        if ($c -eq '$') { $i = Read-Dollar $st $text $i 'powershell'; continue }
        if ($c -eq '<' -and $i + 1 -lt $n -and $text[$i + 1] -eq '#') {
            $j = $text.IndexOf('#>', $i + 2)
            if ($j -lt 0) { $i = $n } else { $i = $j + 2 }
            continue
        }
        if ($c -eq '#' -and -not $st.InTok) {
            $j = $text.IndexOf("`n", $i)
            if ($j -lt 0) { $j = $n }
            $i = $j
            continue
        }
        if ($c -eq '(' -or $c -eq '{') {
            $close = ')'
            if ($c -eq '{') { $close = '}' }
            $j = Find-Close $text ($i + 1) ([string]$c) $close 'powershell'
            $end = [Math]::Min($j, $n)
            $st.Nested.Add([pscustomobject]@{ Text = $text.Substring($i + 1, [Math]::Max(0, $end - $i - 1)); Mode = 'powershell' })
            if ($st.InTok -and $st.Buf.ToString() -eq '@') { [void]$st.Buf.Clear(); $st.InTok = $false }
            Close-Token $st
            $st.Toks.Add([pscustomobject]@{ T = '(...)'; D = $true; S = $true; Q = $false })
            $i = $j + 1
            continue
        }
        if ($c -eq ')' -or $c -eq '}') { Close-Token $st; $i++; continue }
        if ($c -eq ';') { Close-Segment $st ';'; $i++; continue }
        if ($c -eq '&') {
            if ($i + 1 -lt $n -and $text[$i + 1] -eq '&') { Close-Segment $st '&&'; $i += 2; continue }
            Close-Token $st
            $i++
            continue
        }
        if ($c -eq '|') {
            if ($i + 1 -lt $n -and $text[$i + 1] -eq '|') { Close-Segment $st '||'; $i += 2; continue }
            Close-Segment $st '|'
            $i++
            continue
        }
        if ($c -eq '>') { $i = Read-Redirect $st $text $i; continue }
        Add-Text $st ([string]$c)
        $i++
    }
    Close-Segment $st ''
    return ,$st.Segs
}

function Split-Cmd([string]$text, $shadow) {
    $st = New-State $shadow
    $n = $text.Length
    $i = 0
    $inQ = $false
    while ($i -lt $n) {
        $c = $text[$i]
        if ($c -eq '"') { $inQ = -not $inQ; $st.InTok = $true; $st.Quoted = $true; $i++; continue }
        if ($c -eq '%') {
            $j = $text.IndexOf('%', $i + 1)
            if ($j -gt $i + 1) {
                $name = $text.Substring($i + 1, $j - $i - 1)
                if ($name -match '^[A-Za-z_][A-Za-z0-9_()]*$') { Add-Var $st $name 'cmd'; $i = $j + 1; continue }
            }
            $st.Dyn = $true; $st.Sub = $true
            Add-Text $st '%'
            $i++
            continue
        }
        if ($inQ) { Add-Text $st ([string]$c); $i++; continue }
        if ($c -eq '^') {
            if ($i + 1 -lt $n) { Add-Text $st ([string]$text[$i + 1]); $i += 2 } else { $i++ }
            continue
        }
        if ($c -eq ' ' -or $c -eq "`t" -or $c -eq "`r" -or $c -eq ',' -or $c -eq ';') { Close-Token $st; $i++; continue }
        if ($c -eq "`n" -or $c -eq '(' -or $c -eq ')') { Close-Segment $st ';'; $i++; continue }
        if ($c -eq '&') {
            if ($i + 1 -lt $n -and $text[$i + 1] -eq '&') { Close-Segment $st '&&'; $i += 2; continue }
            Close-Segment $st ';'
            $i++
            continue
        }
        if ($c -eq '|') {
            if ($i + 1 -lt $n -and $text[$i + 1] -eq '|') { Close-Segment $st '||'; $i += 2; continue }
            Close-Segment $st '|'
            $i++
            continue
        }
        if ($c -eq '>' -or $c -eq '<') { $i = Read-Redirect $st $text $i; continue }
        Add-Text $st ([string]$c)
        $i++
    }
    Close-Segment $st ''
    return ,$st.Segs
}

# ---- Targets ----------------------------------------------------------------------------------

function New-Tok([string]$t, [bool]$d) {
    return [pscustomobject]@{ T = $t; D = $d; S = $d; Q = $false }
}

# Fills ${name} placeholders from variables the same command assigned earlier. $null when one is
# still unknown, or when the token holds a command substitution.
function Expand-ShellVars($tok, $ctx) {
    $text = [string]$tok.T
    if (-not $tok.D) { return $text }
    if ($tok.S) { return $null }
    $sb = New-Object System.Text.StringBuilder
    $pos = 0
    foreach ($m in [regex]::Matches($text, '\$\{([^}]*)\}')) {
        $n = $m.Groups[1].Value
        if (-not $ctx.Vars.ContainsKey($n) -or $null -eq $ctx.Vars[$n]) { return $null }
        [void]$sb.Append($text.Substring($pos, $m.Index - $pos))
        [void]$sb.Append([string]$ctx.Vars[$n])
        $pos = $m.Index + $m.Length
    }
    [void]$sb.Append($text.Substring($pos))
    return $sb.ToString()
}

function Set-ShellVar($ctx, [string]$name, $tok) {
    $ctx.Vars[$name] = Expand-ShellVars $tok $ctx
}

# NAME=value token -> ctx.Vars.
function Set-Assignment($ctx, $tok) {
    $text = [string]$tok.T
    $eq = $text.IndexOf('=')
    $vt = [pscustomobject]@{ T = $text.Substring($eq + 1); D = $tok.D; S = $tok.S; Q = $tok.Q }
    Set-ShellVar $ctx $text.Substring(0, $eq) $vt
}

# Names the command assigns itself: never filled from the hook's environment.
function Get-ShadowNames([string]$text, [string]$mode) {
    $set = @{}
    $rx = '(?:^|[\s;&|(])(?:export\s+|declare\s+|local\s+)?([A-Za-z_][A-Za-z0-9_]*)='
    if ($mode -eq 'powershell') { $rx = '\$([A-Za-z_][A-Za-z0-9_:]*)\s*[+*/-]?=(?!=)' }
    elseif ($mode -eq 'cmd') { $rx = '(?i)\bset\s+"?([A-Za-z_][A-Za-z0-9_]*)=' }
    foreach ($m in [regex]::Matches($text, $rx)) { $set[$m.Groups[1].Value] = $true }
    return $set
}

# Resolves a delete target. Kind: path (Full = the folder or file; Pattern = a wildcard tail, if any),
# skip (nothing on disk: /dev/null, env:), unknown (unresolvable), system (outside every drive path
# the guard reasons about: /usr, UNC, registry, a Linux path).
function Resolve-Target($tok, $ctx, [bool]$literal) {
    $res = [pscustomobject]@{ Kind = 'path'; Full = $null; Pattern = ''; Display = [string]$tok.T }
    $p = Expand-ShellVars $tok $ctx
    if ($null -eq $p) { $res.Kind = 'unknown'; return $res }
    $res.Display = $p
    if ($p.Contains($script:PwdMark)) {
        if (-not $ctx.Cwd) { $res.Kind = 'unknown'; return $res }
        $p = $p.Replace($script:PwdMark, $ctx.Cwd)
        $res.Display = $p
    }
    $p = $p.Trim()
    if ($p -eq '' -or $p -in @('/dev/null', 'nul', 'nul:', '$null', '$true', '$false')) { $res.Kind = 'skip'; return $res }
    if ($p -eq '~' -or $p -match '^~[\\/]') { $p = $env:USERPROFILE + $p.Substring(1) }
    elseif ($p.StartsWith('~')) { $res.Kind = 'unknown'; return $res }
    if ($ctx.Mode -ne 'cmd') {
        if ($p -match '^/(?:mnt/|cygdrive/)?([A-Za-z])(?:/(.*))?$') { $p = $matches[1] + ':\' + [string]$matches[2] }
        elseif ($ctx.Mode -eq 'bash' -and $p -match '^/(?:var/)?tmp(?:/(.*))?$') { $p = $script:tempMain + '\' + [string]$matches[1] }
        elseif ($ctx.Mode -eq 'bash' -and $p.StartsWith('/') -and -not $p.StartsWith('//')) { $res.Kind = 'system'; return $res }
    }
    if ($p -match '^(\\\\|//)') { $res.Kind = 'system'; return $res }
    if ($p -match '^[A-Za-z][A-Za-z0-9.]*::') { $res.Kind = 'system'; return $res }
    if ($p -match '^([A-Za-z][A-Za-z0-9]+):') {
        if ($matches[1] -in @('env', 'variable', 'function', 'alias')) { $res.Kind = 'skip' } else { $res.Kind = 'system' }
        return $res
    }

    $norm = $p.Replace('/', '\')
    $wildChars = ''
    if (-not $literal) {
        if ($ctx.Mode -eq 'cmd') { $wildChars = '*?' } else { $wildChars = '*?[' }
    }
    $basePart = $norm
    if ($wildChars) {
        $parts = $norm.Split('\')
        $wi = -1
        for ($q = 0; $q -lt $parts.Count; $q++) {
            if ($parts[$q].IndexOfAny($wildChars.ToCharArray()) -ge 0) { $wi = $q; break }
        }
        if ($wi -ge 0) {
            $basePart = ''
            if ($wi -gt 0) { $basePart = [string]::Join('\', $parts[0..($wi - 1)]) }
            $res.Pattern = [string]::Join('\', $parts[$wi..($parts.Count - 1)])
            if ($basePart -eq '' -and $norm.StartsWith('\')) { $basePart = '\' }
            if ($basePart -match '^[A-Za-z]:$') { $basePart += '\' }
        }
    }
    if ($basePart -eq '') { $basePart = '.' }
    if (-not [System.IO.Path]::IsPathRooted($basePart)) {
        if (-not $ctx.Cwd) { $res.Kind = 'unknown'; return $res }
        $dir = $ctx.Cwd
        if ($dir.EndsWith(':')) { $dir += '\' }
        $basePart = [System.IO.Path]::Combine($dir, $basePart)
    }
    $full = Get-Full $basePart
    if (-not $full) { $res.Kind = 'unknown'; return $res }
    $res.Full = $full
    return $res
}

function Get-Sample($lines) {
    $s = @($lines | Select-Object -First 3) -join ', '
    if (@($lines).Count -gt 3) { $s += ', ...' }
    return $s
}

# Decides one delete target. recursive: removes folders with their contents. literal: no wildcards
# (PowerShell -LiteralPath). scoped: removes only entries matching a filter (find -name, -Include),
# so the base folder itself is not the target.
function Test-Target($tok, $ctx, [bool]$recursive, [bool]$literal, [bool]$scoped, [string]$verb) {
    $r = Resolve-Target $tok $ctx $literal
    $shown = $r.Display
    if ($r.Kind -eq 'skip') { return }
    if ($r.Kind -eq 'unknown') {
        if ($recursive -and -not $scoped) {
            Add-Finding 'deny' ("$verb '$shown' is a recursive delete of a path that holds a variable, command substitution, or piped input the guard can't resolve (an empty variable turns 'rm -rf `$DIR/' into 'rm -rf /'). Resolve the path first and pass it literally.")
        } else {
            Add-Finding 'ask' ("$verb '$shown': the guard can't resolve this path.")
        }
        return
    }
    if ($r.Kind -eq 'system') {
        Add-Finding 'deny' ("$verb '$shown' is outside the project (a system, network, registry, or Linux path).")
        return
    }

    $full = $r.Full
    $pat = $r.Pattern
    $extent = 'files'
    if ($recursive -and -not $scoped) {
        if ($pat) { $extent = 'contents' } else { $extent = 'tree' }
    }
    $allMatch = ($pat -ne '' -and $pat -match '^(\*+|\.\*|\*\.\*)$')

    $roots = Get-Roots
    foreach ($root in $roots) {
        if ($extent -ne 'files' -and (Test-Inside $root $full)) {
            Add-Finding 'deny' ("$verb '$shown' would delete a folder that contains the project ($root).")
            return
        }
        if ((Test-Same $full $root) -and ($extent -eq 'tree' -or ($extent -eq 'contents' -and $allMatch))) {
            Add-Finding 'deny' ("$verb '$shown' would delete the whole project ($root).")
            return
        }
    }
    $best = $null
    foreach ($root in $roots) {
        if ((Test-Same $full $root) -or (Test-Inside $full $root)) {
            if (-not $best -or $root.Length -gt $best.Length) { $best = $root }
        }
    }
    if ($best) { Test-ProjectTarget $full $pat $extent $best $shown $verb; return }

    foreach ($t in $script:tempRoots) {
        if (Test-Inside $full $t) { return }
        if ($extent -eq 'files' -and (Test-Same $full $t)) { return }
    }
    foreach ($t in $script:allowAbs) {
        if ((Test-Same $full $t) -or (Test-Inside $full $t)) { return }
    }

    $what = 'outside the project'
    if ($full -match '^[A-Za-z]:\\?$') { $what = 'a whole drive' }
    elseif ($script:homeDir -and ((Test-Same $full $script:homeDir) -or (Test-Inside $script:homeDir $full))) { $what = 'the home folder' }
    else {
        foreach ($t in $script:tempRoots) { if (Test-Same $full $t) { $what = 'the whole temp folder' } }
    }
    Add-Finding 'deny' ("$verb '$shown' targets $what ($full). Deletes may touch only the project and the temp folder.")
}

function Test-ProjectTarget([string]$full, [string]$pat, [string]$extent, [string]$root, [string]$shown, [string]$verb) {
    $rel = ''
    if (-not (Test-Same $full $root)) { $rel = $full.Substring($root.TrimEnd('\').Length).TrimStart('\').Replace('\', '/') }
    $relPat = $rel
    if ($pat) { $relPat = ($rel + '/' + $pat.Replace('\', '/')).TrimStart('/') }
    $where = $relPat
    if (-not $where) { $where = '.' }

    if (('/' + $relPat + '/') -match '/\.git/') {
        if ($extent -eq 'files' -and -not $pat -and $relPat -match '\.lock$') { return }
        Add-Finding 'deny' ("$verb '$shown' reaches into the repository's .git ($where).")
        return
    }
    foreach ($ap in $script:allowRel) {
        if ($rel -ne '' -and ($rel -like $ap -or $rel -like ($ap + '/*'))) { return }
    }
    foreach ($pp in $script:protected) {
        if ($relPat -like $pp) {
            Add-Finding 'deny' ("$verb '$shown' deletes $where, which matches protectedPaths '$pp' in .claude/kit.json.")
            return
        }
        if ($extent -ne 'files' -and $rel -ne '' -and $pp -like ([System.Management.Automation.WildcardPattern]::Escape($rel) + '/*') -and
            (Test-Path -LiteralPath (Join-Path $root $pp))) {
            Add-Finding 'deny' ("$verb '$shown' deletes $where, which holds protectedPaths '$pp' in .claude/kit.json.")
            return
        }
    }
    if ($extent -eq 'files') { return }
    if (-not (Test-Path -LiteralPath $full)) { return }
    if ($extent -eq 'tree' -and -not (Test-Path -LiteralPath $full -PathType Container)) { return }
    if ($extent -eq 'tree' -and (Test-Path -LiteralPath (Join-Path $full '.git'))) {
        Add-Finding 'deny' ("$verb '$shown' deletes $where, which is a git repository or worktree. Remove a worktree with 'git worktree remove'; deleting a repository is the user's call.")
        return
    }
    foreach ($line in @(& git -C $root worktree list --porcelain 2>$null)) {
        if ([string]$line -match '^worktree (.+)$') {
            $w = Get-Full $matches[1]
            if ($w -and -not (Test-Same $w $root) -and ((Test-Same $w $full) -or (Test-Inside $w $full))) {
                Add-Finding 'deny' ("$verb '$shown' would delete the worktree $w. Use 'git worktree remove' (it refuses when the worktree has uncommitted work).")
                return
            }
        }
    }

    $tracked = @(& git -C $root ls-files -- $relPat 2>$null)
    $gitOk = ($LASTEXITCODE -eq 0)
    $untracked = @()
    if ($gitOk) {
        $untracked = @(& git -C $root ls-files --others --exclude-standard --directory --no-empty-directory -- $relPat 2>$null)
        $gitOk = ($LASTEXITCODE -eq 0)
    }
    if (-not $gitOk) {
        Add-Finding 'ask' ("$verb '$shown' deletes $where, and git can't say what is in it.")
        return
    }
    if ($tracked.Count -gt 0) {
        Add-Finding 'ask' ("$verb '$shown' deletes $($tracked.Count) tracked file(s) under $where (" + (Get-Sample $tracked) + "). Delete tracked files with 'git rm -r', so the deletion shows in the diff.")
        return
    }
    if ($untracked.Count -gt 0) {
        Add-Finding 'ask' ("$verb '$shown' deletes files under $where that git neither tracks nor ignores (" + (Get-Sample $untracked) + "), possibly the owner's uncommitted work.")
    }
}

# bash brace expansion: rm -rf {src,docs} -> src docs
function Expand-Braces($list, $ctx) {
    $out = New-Object System.Collections.Generic.List[object]
    foreach ($t in $list) {
        if ($ctx.Mode -ne 'bash' -or $t.Q -or $t.D -or -not ([string]$t.T -match '\{[^{}]*,[^{}]*\}')) { $out.Add($t); continue }
        $queue = New-Object System.Collections.Generic.List[string]
        $queue.Add([string]$t.T)
        $done = New-Object System.Collections.Generic.List[string]
        while ($queue.Count -gt 0 -and ($done.Count + $queue.Count) -lt 64) {
            $s = $queue[0]
            $queue.RemoveAt(0)
            $m = [regex]::Match($s, '\{([^{}]*,[^{}]*)\}')
            if (-not $m.Success) { $done.Add($s); continue }
            foreach ($alt in $m.Groups[1].Value.Split(',')) { $queue.Add($s.Substring(0, $m.Index) + $alt + $s.Substring($m.Index + $m.Length)) }
        }
        foreach ($s in $done) { $out.Add((New-Tok $s $false)) }
        foreach ($s in $queue) { $out.Add((New-Tok $s $false)) }
    }
    return ,$out
}

# ---- Commands ---------------------------------------------------------------------------------

function Get-CmdName([string]$t) {
    $x = $t
    $k = [Math]::Max($x.LastIndexOf('/'), $x.LastIndexOf('\'))
    if ($k -ge 0 -and $k -lt $x.Length - 1) { $x = $x.Substring($k + 1) }
    $x = $x.ToLowerInvariant().TrimStart('@')
    return ($x -replace '\.(exe|cmd|bat|com)$', '')
}

function Get-Slice($a, [int]$from) {
    $out = New-Object System.Collections.Generic.List[object]
    for ($j = $from; $j -lt $a.Count; $j++) { $out.Add($a[$j]) }
    return ,$out
}

# Rebuilds the rest of a command line for a nested shell: one token is the script as is; several
# are joined, re-quoting tokens that hold spaces.
function Join-Rest($a, [int]$from, [string]$mode) {
    if ($from -ge $a.Count) { return '' }
    if ($a.Count - $from -eq 1) { return [string]$a[$from].T }
    $parts = New-Object System.Collections.Generic.List[string]
    for ($j = $from; $j -lt $a.Count; $j++) {
        $s = [string]$a[$j].T
        if ($s -match '\s') {
            if ($mode -eq 'cmd') { $s = '"' + $s + '"' }
            elseif ($mode -eq 'powershell') { $s = "'" + $s.Replace("'", "''") + "'" }
            else { $s = "'" + $s.Replace("'", "'\''") + "'" }
        }
        $parts.Add($s)
    }
    return [string]::Join(' ', $parts)
}

function Set-Cwd($ctx, $a) {
    $target = $null
    for ($j = 0; $j -lt $a.Count; $j++) {
        $t = $a[$j]
        $s = [string]$t.T
        if (-not $t.Q -and $s -eq '-') { $ctx.Cwd = $null; return }
        if (-not $t.Q -and $ctx.Mode -eq 'powershell' -and $s -match '^-(p|pa|pat|path|l\w*|lp)$') {
            if ($j + 1 -lt $a.Count) { $target = $a[$j + 1] }
            break
        }
        if (-not $t.Q -and ($s.StartsWith('-') -or ($ctx.Mode -eq 'cmd' -and $s -match '^/[A-Za-z]$'))) { continue }
        $target = $t
        break
    }
    if ($null -eq $target) {
        if ($ctx.Mode -eq 'bash') { $ctx.Cwd = $script:homeDir }
        return
    }
    $r = Resolve-Target $target $ctx $true
    if ($r.Kind -eq 'path') { $ctx.Cwd = $r.Full } else { $ctx.Cwd = $null }
}

function Test-Rm($a, $ctx, [string]$verb) {
    $rec = $false
    $paths = New-Object System.Collections.Generic.List[object]
    $endOpts = $false
    foreach ($t in $a) {
        $s = [string]$t.T
        if (-not $endOpts -and -not $t.Q) {
            if ($s -eq '--') { $endOpts = $true; continue }
            if ($s -eq '--no-preserve-root') { Add-Finding 'deny' "$verb --no-preserve-root switches off rm's own protection of /."; continue }
            if ($s -eq '--recursive') { $rec = $true; continue }
            if ($s.StartsWith('--')) { continue }
            if ($s.StartsWith('-') -and $s.Length -gt 1) {
                if ($s -cmatch '[rR]') { $rec = $true }
                continue
            }
        }
        $paths.Add($t)
    }
    foreach ($p in (Expand-Braces $paths $ctx)) { Test-Target $p $ctx $rec $false $false $verb }
}

function Test-AllRecursive($a, $ctx, [string]$verb) {
    $paths = New-Object System.Collections.Generic.List[object]
    foreach ($t in $a) { if ($t.Q -or -not ([string]$t.T).StartsWith('-')) { $paths.Add($t) } }
    foreach ($p in (Expand-Braces $paths $ctx)) { Test-Target $p $ctx $true $false $false $verb }
}

$script:riValueParams = @('ea', 'erroraction', 'wa', 'warningaction', 'infa', 'informationaction', 'ev', 'errorvariable',
    'wv', 'warningvariable', 'iv', 'informationvariable', 'ov', 'outvariable', 'ob', 'outbuffer', 'pv', 'pipelinevariable')

function Test-RemoveItem($a, $ctx, [int]$k, [string]$verb) {
    $rec = $false
    $filtered = $false
    $paths = New-Object System.Collections.Generic.List[object]
    $lits = New-Object System.Collections.Generic.List[object]
    for ($j = 0; $j -lt $a.Count; $j++) {
        $t = $a[$j]
        $s = [string]$t.T
        if (-not $t.Q -and $s -match '^-([A-Za-z]+)(:(.*))?$') {
            $pn = $matches[1].ToLowerInvariant()
            $hasInline = [bool]$matches[2]
            $inline = [string]$matches[3]
            $val = $null
            if ($hasInline) { $val = New-Tok $inline $t.D }
            elseif ($j + 1 -lt $a.Count) { $val = $a[$j + 1] }
            if ($pn -in $script:riValueParams -or $pn.StartsWith('cr') -or $pn.StartsWith('st')) {
                if (-not $hasInline) { $j++ }
                continue
            }
            if ($pn.StartsWith('r')) {
                if (-not ($hasInline -and $inline -eq '$false')) { $rec = $true }
                continue
            }
            if ($pn.StartsWith('wh') -or $pn -eq 'wi') {
                if (-not ($hasInline -and $inline -eq '$false')) { return }
                continue
            }
            if ($pn -eq 'pspath' -or ($pn.StartsWith('p') -and 'path'.StartsWith($pn))) {
                if ($val) { $paths.Add($val); if (-not $hasInline) { $j++ } }
                continue
            }
            if ($pn.StartsWith('l')) {
                if ($val) { $lits.Add($val); if (-not $hasInline) { $j++ } }
                continue
            }
            if ($pn.StartsWith('fi') -or $pn.StartsWith('in') -or $pn.StartsWith('ex')) {
                $filtered = $true
                if (-not $hasInline) { $j++ }
                continue
            }
            continue
        }
        $paths.Add($t)
    }
    if ($paths.Count -eq 0 -and $lits.Count -eq 0) { Test-PipedRemove $ctx $k $rec $filtered $verb; return }
    foreach ($p in $paths) { Test-Target $p $ctx $rec $false $filtered $verb }
    foreach ($p in $lits) { Test-Target $p $ctx $rec $true $filtered $verb }
}

# Get-ChildItem <dir> | Remove-Item: the pipeline's source decides what is deleted.
function Test-PipedRemove($ctx, [int]$k, [bool]$rec, [bool]$filtered, [string]$verb) {
    $segs = $ctx.Segs
    if ($segs[$k].Sep -ne '|') { return }
    $h = $k - 1
    while ($h -ge 0 -and $segs[$h].Sep -eq '|') {
        if ($segs[$h].Toks.Count -gt 0 -and (Get-CmdName ([string]$segs[$h].Toks[0].T)) -in @('where-object', 'where', '?', 'select-object', 'select')) { $filtered = $true }
        $h--
    }
    $unknown = New-Tok '(piped input)' $true
    if ($h -lt 0 -or $segs[$h].Toks.Count -eq 0) { Test-Target $unknown $ctx $rec $false $filtered $verb; return }
    $head = $segs[$h].Toks
    $name = Get-CmdName ([string]$head[0].T)
    if ($name -notin @('get-childitem', 'gci', 'ls', 'dir', 'get-item', 'gi')) { Test-Target $unknown $ctx $rec $false $filtered $verb; return }

    $src = $null
    $lit = $false
    $gciRec = $false
    $positional = 0
    for ($j = 1; $j -lt $head.Count; $j++) {
        $t = $head[$j]
        $s = [string]$t.T
        if (-not $t.Q -and $s -match '^-([A-Za-z]+)(:(.*))?$') {
            $pn = $matches[1].ToLowerInvariant()
            $hasInline = [bool]$matches[2]
            if ($pn.StartsWith('r')) { $gciRec = $true; continue }
            if ($pn.StartsWith('fi') -and $pn -ne 'file' -or $pn.StartsWith('in') -or $pn.StartsWith('ex')) { $filtered = $true; if (-not $hasInline) { $j++ }; continue }
            if ($pn -eq 'pspath' -or ($pn.StartsWith('p') -and 'path'.StartsWith($pn))) { if (-not $hasInline -and $j + 1 -lt $head.Count) { $src = $head[$j + 1]; $j++ } elseif ($hasInline) { $src = New-Tok $matches[3] $t.D }; continue }
            if ($pn.StartsWith('l')) { $lit = $true; if (-not $hasInline -and $j + 1 -lt $head.Count) { $src = $head[$j + 1]; $j++ } elseif ($hasInline) { $src = New-Tok $matches[3] $t.D }; continue }
            if ($pn -in @('depth', 'attributes', 'af', 'ad', 'ah', 'ar', 'as') -and -not $hasInline) { $j++ }
            continue
        }
        $positional++
        if ($positional -eq 1) { $src = $t } else { $filtered = $true }
    }
    if ($null -eq $src) { $src = New-Tok '.' $false }
    $tok = $src
    if ($name -notin @('get-item', 'gi') -and -not $src.D) {
        $txt = ([string]$src.T).TrimEnd('\', '/')
        if ($txt.IndexOfAny([char[]]'*?[') -lt 0) { $tok = [pscustomobject]@{ T = ($txt + '\*'); D = $false; Q = $src.Q } }
    }
    Test-Target $tok $ctx ($rec -or $gciRec) $lit $filtered $verb
}

function Test-CmdDel($a, $ctx, [bool]$isRd, [string]$verb) {
    $rec = $false
    $paths = New-Object System.Collections.Generic.List[object]
    foreach ($t in $a) {
        $s = [string]$t.T
        if (-not $t.Q -and $s -match '^/[A-Za-z](:.*)?$') {
            if ($s -ieq '/s') { $rec = $true }
            continue
        }
        $paths.Add($t)
    }
    foreach ($p in $paths) {
        if ($isRd) { Test-Target $p $ctx $rec $false $false $verb; continue }
        # del /s removes matching files in every subfolder; a folder argument means every file under it.
        $txt = [string]$p.T
        $leaf = ($txt -split '[\\/]')[-1]
        if ($rec -and $txt.IndexOfAny([char[]]'*?') -ge 0 -and $leaf -notmatch '^(\*+|\*\.\*)$') { Test-Target $p $ctx $false $false $true $verb }
        else { Test-Target $p $ctx $rec $false $false $verb }
    }
}

function Test-Find($a, $ctx) {
    $starts = New-Object System.Collections.Generic.List[object]
    $j = 0
    while ($j -lt $a.Count -and ([string]$a[$j].T) -match '^-([HLP]|O\d*|D.*)$') { $j++ }
    while ($j -lt $a.Count) {
        $s = [string]$a[$j].T
        if ($s.StartsWith('-') -or $s -in @('(', '!', ')')) { break }
        $starts.Add($a[$j])
        $j++
    }
    $deletes = $false
    $filtered = $false
    for (; $j -lt $a.Count; $j++) {
        $s = ([string]$a[$j].T).ToLowerInvariant()
        if ($s -eq '-delete') { $deletes = $true }
        elseif ($s -in @('-exec', '-execdir', '-ok', '-okdir') -and $j + 1 -lt $a.Count) {
            if ((Get-CmdName ([string]$a[$j + 1].T)) -in @('rm', 'rmdir', 'shred', 'unlink', 'remove-item')) { $deletes = $true }
        }
        elseif ($s -in @('-name', '-iname', '-path', '-ipath', '-regex', '-iregex', '-wholename', '-iwholename', '-newer',
                '-mtime', '-mmin', '-atime', '-amin', '-ctime', '-cmin', '-size', '-empty', '-user', '-group', '-perm',
                '-lname', '-ilname', '-samefile', '-inum', '-links')) { $filtered = $true }
    }
    if (-not $deletes) { return }
    if ($starts.Count -eq 0) { $starts.Add((New-Tok '.' $false)) }
    foreach ($p in $starts) { Test-Target $p $ctx (-not $filtered) $false $filtered 'find -delete' }
}

function Test-Xargs($a, $ctx) {
    for ($j = 0; $j -lt $a.Count; $j++) {
        $nm = Get-CmdName ([string]$a[$j].T)
        if ($nm -notin @('rm', 'shred', 'unlink', 'rimraf', 'remove-item', 'rmdir')) { continue }
        $rec = ($nm -eq 'rimraf')
        for ($q = $j + 1; $q -lt $a.Count; $q++) {
            $s = [string]$a[$q].T
            if ($s -eq '--recursive' -or ($s -match '^-[^-]' -and $s -cmatch '[rR]')) { $rec = $true }
        }
        Test-Target (New-Tok '(paths from xargs)' $true) $ctx $rec $false $false "xargs $nm"
        return
    }
}

function Test-Robocopy($a, $ctx) {
    $pos = New-Object System.Collections.Generic.List[object]
    $mir = $false
    $move = $false
    foreach ($t in $a) {
        $s = [string]$t.T
        if ($s -match '^//?[A-Za-z]+(:[^/\\]*)?$') {
            $u = $s.TrimStart('/').ToUpperInvariant()
            if ($u -eq 'MIR' -or $u -eq 'PURGE') { $mir = $true }
            if ($u -eq 'MOVE') { $move = $true }
            continue
        }
        $pos.Add($t)
    }
    if ($mir -and $pos.Count -ge 2) { Test-Target $pos[1] $ctx $true $true $false 'robocopy /MIR' }
    if ($move -and $pos.Count -ge 1) { Test-Target $pos[0] $ctx $true $true $false 'robocopy /MOVE' }
}

function Test-PackageRunner($a, $ctx, [string]$name) {
    $j = 0
    if ($name -in @('npm', 'pnpm', 'yarn')) {
        while ($j -lt $a.Count -and ([string]$a[$j].T).StartsWith('-')) { $j++ }
        if ($j -ge $a.Count -or ([string]$a[$j].T).ToLowerInvariant() -notin @('exec', 'dlx', 'x')) { return }
        $j++
    }
    while ($j -lt $a.Count -and ([string]$a[$j].T).StartsWith('-')) { $j++ }
    if ($j -ge $a.Count) { return }
    $tool = (Get-CmdName ([string]$a[$j].T)) -replace '(?<=.)@[^/]*$', ''
    if ($tool -in @('rimraf', 'del-cli', 'trash', 'trash-cli')) { Test-AllRecursive (Get-Slice $a ($j + 1)) $ctx $tool }
}

function Get-GitParts($a) {
    $opts = New-Object System.Collections.Generic.List[string]
    $pos = New-Object System.Collections.Generic.List[string]
    $after = New-Object System.Collections.Generic.List[string]
    $dd = $false
    foreach ($t in $a) {
        $s = [string]$t.T
        if ($dd) { $after.Add($s); continue }
        if ($s -eq '--') { $dd = $true; continue }
        if ($s.StartsWith('-') -and $s.Length -gt 1) { $opts.Add($s) } else { $pos.Add($s) }
    }
    return [pscustomobject]@{ Opts = $opts; Pos = $pos; After = $after }
}

function Test-Short($parts, [string]$letter) {
    foreach ($o in $parts.Opts) { if ($o -match '^-[^-]' -and $o.Substring(1).Contains($letter)) { return $true } }
    return $false
}

function Test-Long($parts, [string]$prefix) {
    foreach ($o in $parts.Opts) { if ($o -eq $prefix -or $o.StartsWith($prefix + '=')) { return $true } }
    return $false
}

function Test-WholeTree($specs) {
    foreach ($s in $specs) { if ($s -in @('.', './', '.\', ':/', ':/.', ':(top)', ':(top).', '*', ':/*')) { return $true } }
    return $false
}

function Test-Git($a, $ctx) {
    $j = 0
    while ($j -lt $a.Count) {
        $s = [string]$a[$j].T
        if ($s -in @('-C', '-c', '--git-dir', '--work-tree', '--namespace', '--exec-path', '--config-env')) { $j += 2; continue }
        if ($s.StartsWith('-')) { $j++; continue }
        break
    }
    if ($j -ge $a.Count) { return }
    $sub = ([string]$a[$j].T).ToLowerInvariant()
    $p = Get-GitParts (Get-Slice $a ($j + 1))
    $specs = @($p.Pos) + @($p.After)

    switch ($sub) {
        'clean' {
            $force = (Test-Short $p 'f') -or (Test-Long $p '--force')
            $dry = (Test-Short $p 'n') -or (Test-Long $p '--dry-run')
            if ($force -and -not $dry -and -not (Test-Short $p 'X')) {
                Add-Finding 'ask' "git clean -f deletes untracked files, which may be the owner's uncommitted work. 'git clean -n' lists them first."
            }
        }
        'reset' {
            if (Test-Long $p '--hard') { Add-Finding 'ask' "git reset --hard discards every uncommitted change in the working tree." }
        }
        'checkout' {
            if ((Test-Short $p 'f') -or (Test-Long $p '--force')) { Add-Finding 'ask' "git checkout --force discards uncommitted changes." }
            elseif (Test-WholeTree $specs) { Add-Finding 'ask' "git checkout on the whole tree discards every uncommitted change." }
        }
        'switch' {
            if ((Test-Short $p 'f') -or (Test-Long $p '--force') -or (Test-Long $p '--discard-changes')) { Add-Finding 'ask' "git switch --discard-changes discards uncommitted changes." }
        }
        'restore' {
            $staged = (Test-Short $p 'S') -or (Test-Long $p '--staged')
            $worktree = (Test-Short $p 'W') -or (Test-Long $p '--worktree')
            if ((-not $staged -or $worktree) -and (Test-WholeTree $specs)) { Add-Finding 'ask' "git restore on the whole tree discards every uncommitted change." }
        }
        'stash' {
            if ($p.Pos.Count -gt 0 -and $p.Pos[0] -in @('drop', 'clear')) { Add-Finding 'ask' ("git stash " + $p.Pos[0] + " deletes stashed work, which may be the owner's.") }
        }
        'worktree' {
            if ($p.Pos.Count -gt 0 -and $p.Pos[0] -eq 'remove' -and ((Test-Short $p 'f') -or (Test-Long $p '--force'))) { Add-Finding 'ask' "git worktree remove --force deletes a worktree together with its uncommitted work." }
        }
        'push' {
            if (Test-Long $p '--mirror') { Add-Finding 'deny' "git push --mirror overwrites or deletes every branch and tag on the remote." }
            if ((Test-Short $p 'f') -or (Test-Long $p '--force')) { Add-Finding 'deny' "git push --force rewrites history on the remote. The kit never force-pushes." }
            if ((Test-Long $p '--force-with-lease') -and -not $script:allowLease) { Add-Finding 'deny' "git push --force-with-lease is off (workflow.allowForceWithLease is false)." }
            foreach ($r in $p.Pos) {
                if ($r.StartsWith('+')) { Add-Finding 'deny' "git push '$r' is a force push (the + refspec). The kit never force-pushes." }
                if ($r -eq (':' + $script:baseBranch) -or $r -eq (':refs/heads/' + $script:baseBranch)) { Add-Finding 'deny' "git push '$r' deletes the base branch on the remote." }
            }
            if ((Test-Short $p 'd') -or (Test-Long $p '--delete')) {
                foreach ($r in $p.Pos) { if ($r -eq $script:baseBranch -or $r -eq ('refs/heads/' + $script:baseBranch)) { Add-Finding 'deny' "git push --delete $r deletes the base branch on the remote." } }
            }
        }
        'filter-branch' { Add-Finding 'ask' "git filter-branch rewrites the repository's history." }
        'filter-repo' { Add-Finding 'ask' "git filter-repo rewrites the repository's history." }
        'reflog' {
            if ($p.Pos.Count -gt 0 -and $p.Pos[0] -in @('expire', 'delete')) { Add-Finding 'ask' "git reflog $($p.Pos[0]) removes the record that lets lost commits be recovered." }
        }
        'gc' {
            foreach ($o in $p.Opts) { if ($o -match '^--prune=(now|all)$') { Add-Finding 'ask' "git gc $o deletes unreachable commits now instead of after the grace period." } }
        }
        'update-ref' {
            if (Test-Short $p 'd') { Add-Finding 'ask' "git update-ref -d deletes a ref." }
        }
        'rm' {
            if ((Test-Short $p 'r') -and (Test-WholeTree $specs)) { Add-Finding 'ask' "git rm -r on the whole tree deletes every tracked file." }
        }
    }
}

function Test-Gh($a, $ctx) {
    $words = New-Object System.Collections.Generic.List[string]
    $method = ''
    for ($j = 0; $j -lt $a.Count; $j++) {
        $s = [string]$a[$j].T
        if ($s -in @('-R', '--repo', '-H', '--header', '-f', '-F', '--field', '--raw-field', '--jq', '-q', '--template', '-t', '--hostname', '--input')) { $j++; continue }
        if ($s -in @('-X', '--method')) { if ($j + 1 -lt $a.Count) { $method = [string]$a[$j + 1].T }; $j++; continue }
        if ($s -match '^(-X|--method=)(.+)$') { $method = $matches[2]; continue }
        if ($s.StartsWith('-')) { continue }
        $words.Add($s)
    }
    if ($words.Count -eq 0) { return }
    $w0 = $words[0].ToLowerInvariant()
    $w1 = ''
    if ($words.Count -gt 1) { $w1 = $words[1].ToLowerInvariant() }
    if ($w0 -eq 'repo') {
        if ($w1 -eq 'delete') { Add-Finding 'deny' "gh repo delete deletes the GitHub repository, its issues, PRs, and history." }
        elseif ($w1 -eq 'archive') { Add-Finding 'deny' "gh repo archive makes the GitHub repository read-only." }
        elseif ($w1 -eq 'edit') {
            foreach ($t in $a) { if (([string]$t.T) -like '--visibility*') { Add-Finding 'deny' "gh repo edit --visibility changes who can see the repository (CLAUDE.md stop-and-ask list)." } }
        }
        elseif ($w1 -eq 'rename') { Add-Finding 'ask' "gh repo rename renames the GitHub repository." }
    }
    elseif ($w0 -eq 'release' -and $w1 -eq 'delete') { Add-Finding 'ask' "gh release delete deletes a published release." }
    elseif ($w0 -eq 'api' -and $method -ieq 'DELETE') {
        if ($w1 -match '^/?repos/[^/]+/[^/]+/?$') { Add-Finding 'deny' "gh api DELETE $w1 deletes the GitHub repository." }
        else { Add-Finding 'ask' "gh api DELETE $w1 deletes something on GitHub." }
    }
}

function Test-ShellExe($a, $ctx, $seg) {
    for ($j = 0; $j -lt $a.Count; $j++) {
        $s = [string]$a[$j].T
        if (-not $a[$j].Q -and $s -match '^-[A-Za-z]*c[A-Za-z]*$') {
            if ($j + 1 -lt $a.Count) { Invoke-Analysis ([string]$a[$j + 1].T) 'bash' $ctx.Cwd ($ctx.Depth + 1) $ctx.Vars }
            return
        }
        if (-not $s.StartsWith('-')) { return }
    }
    if ($seg.Stdin) { Invoke-Analysis $seg.Stdin 'bash' $ctx.Cwd ($ctx.Depth + 1) $ctx.Vars }
}

function Test-PowerShellExe($a, $ctx, $seg) {
    for ($j = 0; $j -lt $a.Count; $j++) {
        $t = $a[$j]
        $s = [string]$t.T
        if ($t.Q -or -not $s.StartsWith('-')) {
            Invoke-Analysis (Join-Rest $a $j 'powershell') 'powershell' $ctx.Cwd ($ctx.Depth + 1) $ctx.Vars
            return
        }
        $pn = $s.Substring(1).ToLowerInvariant()
        if ($pn -eq '') { if ($seg.Stdin) { Invoke-Analysis $seg.Stdin 'powershell' $ctx.Cwd ($ctx.Depth + 1) $ctx.Vars }; return }
        if ($pn.StartsWith('c') -and 'command'.StartsWith($pn)) {
            if ($j + 1 -lt $a.Count -and [string]$a[$j + 1].T -eq '-' -and $seg.Stdin) { Invoke-Analysis $seg.Stdin 'powershell' $ctx.Cwd ($ctx.Depth + 1) $ctx.Vars }
            else { Invoke-Analysis (Join-Rest $a ($j + 1) 'powershell') 'powershell' $ctx.Cwd ($ctx.Depth + 1) $ctx.Vars }
            return
        }
        if ($pn.StartsWith('e') -and 'encodedcommand'.StartsWith($pn) -and $pn -ne 'ex' -and $pn -ne 'ep') {
            if ($j + 1 -lt $a.Count) {
                try {
                    $code = [System.Text.Encoding]::Unicode.GetString([Convert]::FromBase64String([string]$a[$j + 1].T))
                    Invoke-Analysis $code 'powershell' $ctx.Cwd ($ctx.Depth + 1) $ctx.Vars
                } catch {
                    Add-Finding 'ask' "powershell -EncodedCommand with a payload the guard can't decode."
                }
            }
            return
        }
        if ($pn.StartsWith('f') -and 'file'.StartsWith($pn)) { return }
        if ($pn -in @('ex', 'ep', 'executionpolicy', 'w', 'windowstyle', 'o', 'outputformat', 'i', 'inputformat', 'v', 'version',
                'configurationname', 'psconsolefile', 'wd', 'workingdirectory', 'ea', 'encodedarguments', 'settingsfile')) { $j++ }
    }
}

function Test-CmdExe($a, $ctx) {
    for ($j = 0; $j -lt $a.Count; $j++) {
        $s = ([string]$a[$j].T).ToLowerInvariant()
        if ($s -in @('/c', '/k', '/r', '//c', '//k')) {
            Invoke-Analysis (Join-Rest $a ($j + 1) 'cmd') 'cmd' $ctx.Cwd ($ctx.Depth + 1) $ctx.Vars
            return
        }
    }
}

function Test-Wsl($a, $ctx) {
    $j = 0
    while ($j -lt $a.Count) {
        $s = [string]$a[$j].T
        if ($s -in @('-d', '--distribution', '-u', '--user', '--cd')) { $j += 2; continue }
        if ($s -in @('-e', '--exec', '--')) { $j++; break }
        if ($s.StartsWith('-')) { $j++; continue }
        break
    }
    if ($j -lt $a.Count) { Invoke-Analysis (Join-Rest $a $j 'bash') 'bash' $ctx.Cwd ($ctx.Depth + 1) $ctx.Vars }
}

$script:rxInlineDelete = '(?i)(rmtree|rmSync|rmdirSync|\bfs\.(promises\.)?(rm|rmdir)\b|rimraf|remove_dir_all|\brm_r\b|removedirs|Remove-Item|\brm\s+-[A-Za-z]*[rR]|\b(rd|rmdir)\s+/s|\bdel\s+/s|Directory\]?::Delete|DeleteDirectory)'
$script:rxDotNetDelete = '(?i)(Directory\]::Delete|DeleteDirectory|\.Delete\(\s*\$true\s*\))'

function Test-Inline($a, $ctx, $seg, [string]$name) {
    $code = New-Object System.Collections.Generic.List[string]
    for ($j = 0; $j -lt $a.Count - 1; $j++) {
        if (([string]$a[$j].T).ToLowerInvariant() -in @('-c', '-e', '--eval', '-p', '--print', '-r', 'eval', '-x')) { $code.Add([string]$a[$j + 1].T) }
    }
    if ($seg.Stdin) { $code.Add($seg.Stdin) }
    foreach ($c in $code) {
        if ($c -match $script:rxInlineDelete) {
            Add-Finding 'ask' ("$name runs inline code that deletes ($($matches[0])); the guard can't check what it deletes.")
            return
        }
    }
}

$script:diskTools = @('diskpart', 'clear-disk', 'format-volume', 'initialize-disk', 'remove-partition', 'clear-partition',
    'mkfs', 'fdisk', 'sfdisk', 'parted', 'wipefs', 'mkswap')

function Test-SystemTool([string]$name, $a) {
    $texts = @($a | ForEach-Object { ([string]$_.T).ToLowerInvariant() })
    if ($name -in $script:diskTools -or $name -like 'mkfs.*') { Add-Finding 'deny' "$name erases disks or partitions."; return }
    if ($name -eq 'format') {
        foreach ($s in $texts) { if ($s -match '^[a-z]:\\?$') { Add-Finding 'deny' "format $s erases a drive."; return } }
    }
    if ($name -eq 'cipher' -and ($texts | Where-Object { $_ -like '/w*' })) { Add-Finding 'deny' "cipher /w overwrites free disk space; deleted files become unrecoverable."; return }
    if ($name -eq 'vssadmin' -and ($texts -contains 'delete' -or $texts -contains 'resize')) { Add-Finding 'deny' "vssadmin delete removes shadow copies (restore points)."; return }
    if ($name -eq 'wmic' -and ($texts -contains 'shadowcopy') -and ($texts -contains 'delete')) { Add-Finding 'deny' "wmic shadowcopy delete removes restore points."; return }
    if ($name -eq 'wbadmin' -and ($texts | Where-Object { $_ -like 'delete*' })) { Add-Finding 'deny' "wbadmin delete removes system backups."; return }
    if ($name -eq 'bcdedit' -and $texts.Count -gt 0 -and $texts[0] -notin @('/enum', '/?', '/v')) { Add-Finding 'deny' "bcdedit changes the boot configuration."; return }
    if ($name -eq 'reg' -and $texts.Count -gt 1 -and $texts[0] -eq 'delete') {
        if ($texts[1] -match '^(hklm|hkey_local_machine|hkcr|hkey_classes_root|hku|hkey_users|hkcc|hkey_current_config)') { Add-Finding 'deny' "reg delete $($texts[1]) deletes machine-wide registry keys." }
        else { Add-Finding 'ask' "reg delete $($texts[1]) deletes registry keys." }
        return
    }
    if ($name -eq 'dd') {
        foreach ($s in $texts) { if ($s -match '^of=(/dev/|\\\\\.\\)') { Add-Finding 'deny' "dd $s writes straight to a device."; return } }
    }
}

$script:wrappers = @('sudo', 'doas', 'nohup', 'time', 'command', 'builtin', 'exec', 'env', 'nice', 'stdbuf', 'call', 'timeout', 'unbuffer')
$script:keywords = @('if', 'then', 'else', 'elif', 'fi', 'do', 'done', 'while', 'until', 'for', 'in', 'case', 'esac', '!', '{', '}',
    'function', 'select', 'coproc', '.', '&', 'foreach', 'try', 'finally', 'return', '@')
$script:interpreters = @('python', 'python3', 'py', 'pythonw', 'node', 'nodejs', 'deno', 'bun', 'ruby', 'perl', 'php', 'tsx', 'ts-node')
$script:systemNames = @('format', 'cipher', 'vssadmin', 'wmic', 'wbadmin', 'bcdedit', 'reg', 'dd') + $script:diskTools

function Test-Segment($ctx, [int]$k) {
    $seg = $ctx.Segs[$k]
    $toks = $seg.Toks
    if ($ctx.Mode -eq 'powershell' -and $toks.Count -ge 1 -and $toks[0].D -and -not $toks[0].S) {
        # $x = 'C:\path' is known from here on; $x = Join-Path ... is not.
        if ($toks.Count -ge 2 -and [string]$toks[0].T -match '^\$\{([^}]+)\}$') {
            $vn = $matches[1]
            $op = [string]$toks[1].T
            if ($op -eq '=' -and $toks.Count -eq 3) { Set-ShellVar $ctx $vn $toks[2]; return }
            if ($op -match '^[+*/-]?=$') { $ctx.Vars[$vn] = $null; return }
        }
        if ([string]$toks[0].T -match '^\$\{([^}]+)\}[+*/-]?=') { $ctx.Vars[$matches[1]] = $null; return }
    }
    $assigns = New-Object System.Collections.Generic.List[object]
    $idx = 0
    while ($idx -lt $toks.Count) {
        $t = [string]$toks[$idx].T
        $lc = $t.ToLowerInvariant()
        if ($ctx.Mode -eq 'bash' -and $t -match '^[A-Za-z_][A-Za-z0-9_]*=') { $assigns.Add($toks[$idx]); $idx++; continue }
        if ($script:keywords -contains $lc) { $idx++; continue }
        if ($script:wrappers -contains $lc) {
            $idx++
            while ($idx -lt $toks.Count -and (([string]$toks[$idx].T).StartsWith('-') -or ($lc -eq 'env' -and ([string]$toks[$idx].T) -match '^[A-Za-z_][A-Za-z0-9_]*='))) { $idx++ }
            if ($lc -eq 'timeout' -and $idx -lt $toks.Count) { $idx++ }
            continue
        }
        break
    }
    if ($idx -ge $toks.Count) {
        # NAME=value with no command sets a shell variable (with a command, only that command's environment).
        foreach ($t in $assigns) { Set-Assignment $ctx $t }
        return
    }
    if ($toks[$idx].D) { return }
    $name = Get-CmdName ([string]$toks[$idx].T)
    $a = Get-Slice $toks ($idx + 1)
    $m = $ctx.Mode

    if ($m -eq 'bash' -and $name -in @('export', 'declare', 'local', 'readonly', 'typeset')) {
        foreach ($t in $a) { if (([string]$t.T) -match '^[A-Za-z_][A-Za-z0-9_]*=') { Set-Assignment $ctx $t } }
        return
    }
    if ($m -eq 'cmd' -and $name -eq 'set' -and $a.Count -ge 1 -and ([string]$a[0].T) -match '^[A-Za-z_][A-Za-z0-9_]*=') { Set-Assignment $ctx $a[0]; return }

    if ($name -in @('cd', 'chdir', 'pushd', 'set-location', 'sl', 'push-location')) { Set-Cwd $ctx $a; return }
    if ($name -in @('popd', 'pop-location')) { $ctx.Cwd = $null; return }
    if ($m -eq 'powershell' -and $name -in @('remove-item', 'rm', 'del', 'erase', 'rd', 'rmdir', 'ri')) { Test-RemoveItem $a $ctx $k $name; return }
    if ($m -eq 'cmd' -and $name -in @('del', 'erase')) { Test-CmdDel $a $ctx $false $name; return }
    if ($m -eq 'cmd' -and $name -in @('rd', 'rmdir')) { Test-CmdDel $a $ctx $true $name; return }
    if ($name -in @('rm', 'shred', 'unlink')) { Test-Rm $a $ctx $name; return }
    if ($name -in @('rimraf', 'del-cli', 'trash', 'trash-put')) { Test-AllRecursive $a $ctx $name; return }
    if ($name -in @('npx', 'bunx', 'pnpx', 'npm', 'pnpm', 'yarn')) { Test-PackageRunner $a $ctx $name; return }
    if ($m -eq 'bash' -and $name -eq 'find') { Test-Find $a $ctx; return }
    if ($name -eq 'xargs') { Test-Xargs $a $ctx; return }
    if ($name -eq 'robocopy') { Test-Robocopy $a $ctx; return }
    if ($name -eq 'git') { Test-Git $a $ctx; return }
    if ($name -eq 'gh') { Test-Gh $a $ctx; return }
    if ($name -in @('bash', 'sh', 'zsh', 'dash', 'ksh', 'git-bash')) { Test-ShellExe $a $ctx $seg; return }
    if ($name -in @('powershell', 'pwsh')) { Test-PowerShellExe $a $ctx $seg; return }
    if ($name -eq 'cmd') { Test-CmdExe $a $ctx; return }
    if ($name -eq 'wsl') { Test-Wsl $a $ctx; return }
    if ($name -in @('invoke-expression', 'iex')) {
        if ($a.Count -gt 0 -and -not $a[0].D) { Invoke-Analysis (Join-Rest $a 0 'powershell') 'powershell' $ctx.Cwd ($ctx.Depth + 1) $ctx.Vars }
        return
    }
    if ($name -in $script:interpreters) { Test-Inline $a $ctx $seg $name; return }
    if ($name -in $script:systemNames -or $name -like 'mkfs.*') { Test-SystemTool $name $a; return }
}

function Test-TextRules([string]$text, [string]$mode) {
    foreach ($rule in $script:customRules) {
        $pat = [string]$rule.pattern
        $hit = $false
        try { $hit = [regex]::IsMatch($text, $pat, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase) }
        catch { $hit = $text.ToLowerInvariant().Contains($pat.ToLowerInvariant()) }
        if ($hit) {
            $dec = 'ask'
            if ([string]$rule.decision -eq 'deny') { $dec = 'deny' }
            $why = ([string]$rule.reason).TrimEnd('.')
            if (-not $why) { $why = 'listed in .claude/kit.json' }
            Add-Finding $dec ("Matches destructiveGuard.commands '$pat': $why.")
        }
    }
    if ($mode -eq 'powershell' -and $text -match $script:rxDotNetDelete) {
        Add-Finding 'ask' ("Deletes through .NET ($($matches[0])); the guard can't check the path.")
    }
}

function Invoke-Analysis([string]$text, [string]$mode, $cwd, [int]$depth, $vars) {
    if ([string]::IsNullOrWhiteSpace($text)) { return }
    if ($depth -gt 6) { Add-Finding 'ask' 'The command nests shells too deeply to check.'; return }
    Test-TextRules $text $mode
    $shadow = Get-ShadowNames $text $mode
    $own = @{}
    if ($vars) { foreach ($key in $vars.Keys) { $own[$key] = $vars[$key]; $shadow[$key] = $true } }
    if ($mode -eq 'powershell') { $segs = Split-PowerShell $text $shadow }
    elseif ($mode -eq 'cmd') { $segs = Split-Cmd $text $shadow }
    else { $segs = Split-Bash $text $shadow }
    $ctx = @{ Cwd = $cwd; Mode = $mode; Depth = $depth; Segs = $segs; Vars = $own }
    $stack = New-Object System.Collections.Stack
    for ($k = 0; $k -lt $segs.Count; $k++) {
        $seg = $segs[$k]
        if ($seg.Marker -eq 'push') { $stack.Push($ctx.Cwd); continue }
        if ($seg.Marker -eq 'pop') { if ($stack.Count -gt 0) { $ctx.Cwd = $stack.Pop() }; continue }
        foreach ($ns in $seg.Nested) { Invoke-Analysis $ns.Text $ns.Mode $ctx.Cwd ($depth + 1) $ctx.Vars }
        Test-Segment $ctx $k
    }
}

# ---- Decide -----------------------------------------------------------------------------------

function Write-GuardLog([string]$decision, $reasons) {
    try {
        if (-not $script:projectDir) { return }
        $dir = Join-Path $script:projectDir '.claude/state'
        if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        $one = ($command -replace '\s+', ' ').Trim()
        if ($one.Length -gt 300) { $one = $one.Substring(0, 300) + '...' }
        $line = '{0} {1} [{2}] {3} :: {4}' -f (Get-Date).ToString('s'), $decision, [string]$payload.tool_name, $one, ($reasons -join ' | ')
        [System.IO.File]::AppendAllText((Join-Path $dir 'guard-destructive.log'), $line + "`n", $utf8)
    } catch { }
}

function Write-Stream([System.IO.Stream]$stream, [string]$text) {
    $bytes = $utf8.GetBytes($text)
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Flush()
}

try {
    Invoke-Analysis $command $toolMode $script:startCwd 0 @{}
} catch {
    # A bug in the guard must not wave a delete through, nor block every command.
    if ($command -match '(?i)\b(rm|rmdir|rd|del|erase|remove-item|ri|unlink|shred|rimraf|find|xargs|clean|reset|checkout|restore|stash|push|filter-branch|gh|format|diskpart|robocopy|dd|mkfs|cipher|vssadmin|reg)\b') {
        Add-Finding 'ask' ("The destructive-command guard failed while checking this command (" + $_.Exception.Message + ").")
    }
}

$deny = New-Object System.Collections.Generic.List[string]
$ask = New-Object System.Collections.Generic.List[string]
foreach ($f in $script:findings) {
    if ($f.Decision -eq 'deny') { if (-not $deny.Contains($f.Reason)) { $deny.Add($f.Reason) } }
    elseif (-not $ask.Contains($f.Reason)) { $ask.Add($f.Reason) }
}
if ($bypass -and $ask.Count -gt 0) {
    foreach ($r in $ask) { $deny.Add($r + " (This needs the user's approval, and permission mode bypassPermissions has nobody to ask.)") }
    $ask.Clear()
}

if ($deny.Count -gt 0) {
    Write-GuardLog 'deny' $deny
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add('Blocked by .claude/hooks/guard-destructive.ps1:')
    foreach ($r in $deny) { $lines.Add('  - ' + $r) }
    $lines.Add("Don't work around this block with another command, tool, script, or spelling of the path. If the deletion is really needed, stop and ask the user: show the exact command and why, and let them run it.")
    Write-Stream ([Console]::OpenStandardError()) (($lines -join "`n") + "`n")
    exit 2
}
if ($ask.Count -gt 0) {
    Write-GuardLog 'ask' $ask
    $reason = 'guard-destructive: ' + ($ask -join ' ') + ' Approve only if this is intended.'
    $out = @{ hookSpecificOutput = @{ hookEventName = 'PreToolUse'; permissionDecision = 'ask'; permissionDecisionReason = $reason } } | ConvertTo-Json -Depth 4 -Compress
    Write-Stream ([Console]::OpenStandardOutput()) $out
    exit 0
}
exit 0
