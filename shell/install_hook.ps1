#Requires -Version 5.1
<#
.SYNOPSIS
    Installs the SentinelAI PowerShell hook.

.DESCRIPTION
    1. Locates (or installs) the sentinelai Python package.
    2. Writes ~/.sentinelai/config.json with the resolved Python path.
    3. Copies SentinelAI.psm1 to your PS Modules directory.
    4. Adds `Import-Module SentinelAI` to your PowerShell profile.

.PARAMETER PythonPath
    Optional. Full path to the Python executable that has sentinelai installed.
    If omitted, the installer searches PATH for python / python3 / py.

.PARAMETER Force
    Re-run even if SentinelAI is already installed.

.EXAMPLE
    # Simple install (Python already in PATH):
    .\install_hook.ps1

    # Explicit path (e.g. inside a virtualenv):
    .\install_hook.ps1 -PythonPath "C:\Users\you\.venv\Scripts\python.exe"
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$PythonPath = '',
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Step { param([string]$Msg) Write-Host "  → $Msg" -ForegroundColor Cyan }
function Write-OK   { param([string]$Msg) Write-Host "  ✓ $Msg" -ForegroundColor Green }
function Write-Fail { param([string]$Msg) Write-Host "  ✗ $Msg" -ForegroundColor Red; exit 1 }
function Write-Warn { param([string]$Msg) Write-Host "  ! $Msg" -ForegroundColor Yellow }

Write-Host ''
Write-Host '  SentinelAI — Shell Hook Installer' -ForegroundColor White
Write-Host '  ──────────────────────────────────' -ForegroundColor DarkGray
Write-Host ''

# ---------------------------------------------------------------------------
# Step 1: Find Python
# ---------------------------------------------------------------------------
Write-Step 'Locating Python with sentinelai installed...'

$resolvedPython = $null

if ($PythonPath -ne '') {
    if (-not (Test-Path $PythonPath)) {
        Write-Fail "Provided PythonPath does not exist: $PythonPath"
    }
    $resolvedPython = $PythonPath
} else {
    foreach ($candidate in @('python', 'python3', 'py')) {
        try {
            $exe = (Get-Command $candidate -ErrorAction Stop).Source
            # Verify sentinelai is importable from this Python.
            $check = & $exe -c "import sentinelai; print('ok')" 2>$null
            if ($check -eq 'ok') {
                $resolvedPython = $exe
                break
            }
        } catch { }
    }
}

if (-not $resolvedPython) {
    Write-Warn 'Could not find Python with sentinelai installed.'
    Write-Warn 'Install it first:  pip install -e path/to/sentinelai'
    Write-Warn 'Then re-run this installer with -PythonPath "path\to\python.exe"'
    exit 1
}

Write-OK "Found Python: $resolvedPython"

# ---------------------------------------------------------------------------
# Step 2: Write config.json
# ---------------------------------------------------------------------------
Write-Step 'Writing ~/.sentinelai/config.json...'

$sentinelDir = Join-Path $HOME '.sentinelai'
if (-not (Test-Path $sentinelDir)) {
    New-Item -ItemType Directory -Path $sentinelDir | Out-Null
}

$config = @{
    python_path  = $resolvedPython
    installed_at = (Get-Date -Format 'o')
    version      = '0.1.0'
} | ConvertTo-Json -Depth 3

$configPath = Join-Path $sentinelDir 'config.json'
Set-Content -Path $configPath -Value $config -Encoding UTF8
Write-OK "Config written to $configPath"

# ---------------------------------------------------------------------------
# Step 3: Copy PSM1 to Modules directory
# ---------------------------------------------------------------------------
Write-Step 'Installing SentinelAI PowerShell module...'

# Prefer the user-scope Modules directory (no admin required).
$modulesRoot = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'PowerShell' 'Modules'
if (-not (Test-Path $modulesRoot)) {
    $modulesRoot = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'WindowsPowerShell' 'Modules'
}

$moduleDir = Join-Path $modulesRoot 'SentinelAI'
if (-not (Test-Path $moduleDir)) {
    New-Item -ItemType Directory -Path $moduleDir | Out-Null
}

$psm1Source = Join-Path $PSScriptRoot 'SentinelAI.psm1'
if (-not (Test-Path $psm1Source)) {
    Write-Fail "SentinelAI.psm1 not found at $psm1Source — run this script from the shell/ directory."
}

Copy-Item -Path $psm1Source -Destination (Join-Path $moduleDir 'SentinelAI.psm1') -Force
Write-OK "Module installed to $moduleDir"

# ---------------------------------------------------------------------------
# Step 4: Add to PowerShell profile
# ---------------------------------------------------------------------------
Write-Step 'Updating PowerShell profile...'

$profilePath = $PROFILE.CurrentUserAllHosts
if (-not (Test-Path (Split-Path $profilePath -Parent))) {
    New-Item -ItemType Directory -Path (Split-Path $profilePath -Parent) -Force | Out-Null
}
if (-not (Test-Path $profilePath)) {
    New-Item -ItemType File -Path $profilePath -Force | Out-Null
}

$importLine = 'Import-Module SentinelAI  # SentinelAI shell hook'
$profileContent = Get-Content $profilePath -Raw -ErrorAction SilentlyContinue

if ($profileContent -notmatch 'Import-Module SentinelAI') {
    Add-Content -Path $profilePath -Value "`n$importLine"
    Write-OK "Added to profile: $profilePath"
} elseif ($Force) {
    Write-OK "Profile already contains Import-Module SentinelAI (skipped, use -Force to re-add)"
} else {
    Write-OK "Profile already set up — no changes needed"
}

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
Write-Host ''
Write-Host '  SentinelAI hook installed successfully.' -ForegroundColor Green
Write-Host ''
Write-Host '  Restart PowerShell (or run: Import-Module SentinelAI) to activate.' -ForegroundColor DarkGray
Write-Host '  To remove:  Unregister-SentinelAIHook' -ForegroundColor DarkGray
Write-Host ''
