#Requires -Version 5.1
<#
.SYNOPSIS
    SentinelAI PowerShell integration module.
    Intercepts commands at the Enter key before they execute.

.DESCRIPTION
    Hooks into PSReadLine's Enter key handler. When the user presses Enter,
    SentinelAI analyzes the command using its local rule engine. Dangerous
    commands show a colored warning and prompt for confirmation. Benign
    commands pass through with zero visible overhead.

.NOTES
    Run Install-SentinelAIHook once (or via profile) to activate.
    Requires PSReadLine 2.0+ (included in PowerShell 7+, available on PS 5.1).
#>

Set-StrictMode -Version Latest

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

$script:ConfigPath = Join-Path $HOME '.sentinelai' 'config.json'
$script:PythonPath  = $null   # resolved lazily

function Get-SentinelAIConfig {
    if (Test-Path $script:ConfigPath) {
        return Get-Content $script:ConfigPath -Raw | ConvertFrom-Json
    }
    return $null
}

function Resolve-SentinelAIPython {
    if ($script:PythonPath) { return $script:PythonPath }

    $cfg = Get-SentinelAIConfig
    if ($cfg -and $cfg.python_path -and (Test-Path $cfg.python_path)) {
        $script:PythonPath = $cfg.python_path
        return $script:PythonPath
    }

    # Fall back to PATH.
    foreach ($candidate in @('python', 'python3', 'py')) {
        try {
            $found = Get-Command $candidate -ErrorAction Stop
            $script:PythonPath = $found.Source
            return $script:PythonPath
        } catch { }
    }

    return $null
}

# ---------------------------------------------------------------------------
# PS-side command filter (runs before the subprocess call)
# These short-circuit to "safe" without ever invoking Python.
# ---------------------------------------------------------------------------

$script:BenignFirstTokens = [System.Collections.Generic.HashSet[string]]@(
    'ls', 'dir', 'cd', 'pushd', 'popd', 'pwd',
    'echo', 'write-host', 'write-output',
    'git', 'gh', 'docker', 'kubectl', 'terraform',
    'cat', 'type', 'get-content', 'set-content',
    'get-childitem', 'get-item', 'get-location',
    'clear', 'cls', 'exit', 'history', 'get-history',
    'code', 'notepad', 'explorer',
    'ping', 'nslookup', 'tracert', 'ipconfig', 'ifconfig',
    'set-location', 'new-item', 'remove-item', 'copy-item', 'move-item',
    'select-string', 'where-object', 'foreach-object',
    'get-process', 'get-service', 'start-service', 'stop-service',
    'test-path', 'test-connection',
    'measure-object', 'sort-object', 'group-object',
    'format-table', 'format-list',
    'out-file', 'out-null', 'out-string',
    'help', 'man', 'get-help', 'get-command', 'get-alias'
)

$script:PipeShellPatterns = @(
    '| bash', '|bash', '| sh', '|sh', '| zsh', '|zsh',
    '| pwsh', '|pwsh', '| powershell', '|powershell',
    '| python', '|python', '| iex', '|iex'
)

$script:SuspiciousFirstTokens = [System.Collections.Generic.HashSet[string]]@(
    'curl', 'wget', 'powershell', 'powershell.exe', 'pwsh', 'pwsh.exe',
    'bash', 'sh', 'zsh', 'fish', 'dash',
    'python', 'python3', 'python.exe',
    'pip', 'pip3', 'pip.exe',
    'sudo', 'su', 'runas',
    'npm', 'yarn', 'npx', 'pnpm',
    'iex', 'irm', 'iwr',
    'invoke-expression', 'invoke-webrequest', 'start-process',
    'chmod', 'chown', 'rm', 'del', 'rmdir',
    'reg', 'regedit', 'schtasks', 'sc.exe',
    'nohup', 'nc', 'ncat', 'netcat', 'socat',
    'cmd', 'cmd.exe',
    'mshta', 'wscript', 'cscript', 'msiexec', 'regsvr32',
    'certutil', 'bitsadmin', 'forfiles'
)

function Test-SentinelAINeedsCheck {
    param([string]$Line)

    $trimmed = $Line.Trim()
    if ($trimmed.Length -lt 8) { return $false }

    # Fast benign-list bypass.
    $firstToken = ($trimmed -split '\s+')[0].ToLower().TrimStart('$').TrimEnd(';').TrimEnd('(')
    if ($script:BenignFirstTokens.Contains($firstToken)) { return $false }

    # Pipe-to-shell is always suspicious regardless of first token.
    $lower = $trimmed.ToLower()
    foreach ($p in $script:PipeShellPatterns) {
        if ($lower.Contains($p)) { return $true }
    }

    return $script:SuspiciousFirstTokens.Contains($firstToken)
}

# ---------------------------------------------------------------------------
# Analysis via the SentinelAI CLI
# ---------------------------------------------------------------------------

function Invoke-SentinelAIAnalyze {
    param([string]$Command)

    $python = Resolve-SentinelAIPython
    if (-not $python) {
        Write-Warning 'SentinelAI: Python not found. Hook is inactive.'
        return $null
    }

    try {
        # Pipe the command via stdin to avoid all quoting and injection concerns.
        $jsonOut = $Command | & $python -m sentinelai.cli analyze - `
            --shell powershell `
            --source shell_hook `
            --skip-llm `
            2>$null

        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($jsonOut)) {
            return $null
        }
        return $jsonOut | ConvertFrom-Json
    }
    catch {
        return $null
    }
}

# ---------------------------------------------------------------------------
# Terminal warning renderer
# ---------------------------------------------------------------------------

$script:RiskColors = @{
    critical = 'Red'
    high     = @{ fg = 'White'; bg = 'DarkRed' }
    medium   = 'Yellow'
    low      = 'Cyan'
    safe     = 'Green'
}

function Write-SentinelAIWarning {
    param(
        [PSCustomObject]$Verdict,
        [string]$Command
    )

    $level = $Verdict.risk_level.ToUpper()
    $color = switch ($Verdict.risk_level) {
        'critical' { 'Red' }
        'high'     { 'DarkRed' }
        'medium'   { 'Yellow' }
        'low'      { 'Cyan' }
        default    { 'White' }
    }

    Write-Host ''
    Write-Host "  ⛔  SentinelAI — $level RISK  " -ForegroundColor White -BackgroundColor $color -NoNewline
    Write-Host ''
    Write-Host ''
    Write-Host '  ' -NoNewline
    Write-Host $Verdict.explanation -ForegroundColor White
    Write-Host ''

    if ($Verdict.dangerous_elements -and $Verdict.dangerous_elements.Count -gt 0) {
        Write-Host '  Threats identified:' -ForegroundColor DarkGray
        foreach ($elem in $Verdict.dangerous_elements | Select-Object -First 5) {
            Write-Host "    •  $elem" -ForegroundColor $color
        }
        Write-Host ''
    }

    if ($Verdict.rule_ids -and $Verdict.rule_ids.Count -gt 0) {
        $ids = $Verdict.rule_ids -join '  '
        Write-Host "  Rules: $ids" -ForegroundColor DarkGray
        Write-Host ''
    }
}

# ---------------------------------------------------------------------------
# PSReadLine Enter key handler
# ---------------------------------------------------------------------------

function Register-SentinelAIHook {
    <#
    .SYNOPSIS
        Installs the SentinelAI Enter-key hook into the current PS session.
    #>
    if (-not (Get-Module -Name PSReadLine)) {
        Write-Warning 'SentinelAI: PSReadLine not loaded — hook not installed.'
        return
    }

    Set-PSReadLineKeyHandler -Key Enter -ScriptBlock {
        $line   = $null
        $cursor = $null
        [Microsoft.PowerShell.PSConsoleReadLine]::GetBufferState([ref]$line, [ref]$cursor)

        # Empty line — pass straight through.
        if ([string]::IsNullOrWhiteSpace($line)) {
            [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
            return
        }

        # PS-side filter: skip the subprocess call for obviously benign commands.
        if (-not (Test-SentinelAINeedsCheck -Line $line)) {
            [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
            return
        }

        # Analyze via Python CLI (rule engine only, ~200–400 ms).
        $verdict = Invoke-SentinelAIAnalyze -Command $line

        # If analysis failed or returned safe, allow through.
        if ($null -eq $verdict -or -not $verdict.should_warn) {
            [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
            return
        }

        # Show the warning.
        Write-SentinelAIWarning -Verdict $verdict -Command $line

        if ($verdict.should_block) {
            $choice = Read-Host '  Allow anyway? [y/N]'
            Write-Host ''
            if ($choice -ne 'y' -and $choice -ne 'Y') {
                Write-Host '  Command blocked.' -ForegroundColor DarkGray
                Write-Host ''
                [Microsoft.PowerShell.PSConsoleReadLine]::RevertLine()
                return
            }
        }

        # User chose to proceed (or risk was only a warning, not a block).
        Write-Host '  Proceeding...' -ForegroundColor DarkGray
        Write-Host ''
        [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
    }

    Write-Host '  [SentinelAI] Shell hook active.' -ForegroundColor DarkGreen
}

function Unregister-SentinelAIHook {
    <#
    .SYNOPSIS
        Removes the SentinelAI hook and restores the default Enter behavior.
    #>
    Set-PSReadLineKeyHandler -Key Enter -Function AcceptLine
    Write-Host '  [SentinelAI] Shell hook removed.' -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# Auto-register when the module is imported.
# ---------------------------------------------------------------------------

Register-SentinelAIHook

Export-ModuleMember -Function @(
    'Register-SentinelAIHook',
    'Unregister-SentinelAIHook',
    'Invoke-SentinelAIAnalyze',
    'Test-SentinelAINeedsCheck',
    'Get-SentinelAIConfig'
)
