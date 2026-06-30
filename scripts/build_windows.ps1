<#
.SYNOPSIS
    Builds the SentinelAI Windows installer.

.DESCRIPTION
    1. Installs PyInstaller into the project venv.
    2. Runs PyInstaller with sentinelai.spec → dist\SentinelAI\SentinelAI.exe
    3. (Optional) Compiles an Inno Setup installer if ISCC.exe is in PATH.

.NOTES
    Run from the root of the sentinelai repo in an activated venv:
        .\.venv\Scripts\Activate.ps1
        .\scripts\build_windows.ps1
#>
[CmdletBinding()]
param(
    [switch]$SkipInno  # Skip Inno Setup step even if ISCC is found.
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Step { param([string]$M) Write-Host "  → $M" -ForegroundColor Cyan }
function Write-OK   { param([string]$M) Write-Host "  ✓ $M" -ForegroundColor Green }
function Write-Fail { param([string]$M) Write-Host "  ✗ $M" -ForegroundColor Red; exit 1 }

Write-Host ''
Write-Host '  SentinelAI — Windows Build Script' -ForegroundColor White
Write-Host '  ───────────────────────────────────' -ForegroundColor DarkGray
Write-Host ''

# Verify venv is active
if (-not $env:VIRTUAL_ENV) {
    Write-Fail 'No virtualenv active. Run: .\.venv\Scripts\Activate.ps1'
}

Write-Step 'Installing PyInstaller...'
pip install pyinstaller --quiet
Write-OK 'PyInstaller ready'

Write-Step 'Running PyInstaller...'
pyinstaller sentinelai.spec --clean --noconfirm
if ($LASTEXITCODE -ne 0) { Write-Fail 'PyInstaller failed' }
Write-OK "Built: dist\SentinelAI\SentinelAI.exe"

# Optional Inno Setup step
$iscc = Get-Command 'ISCC.exe' -ErrorAction SilentlyContinue
if ($iscc -and -not $SkipInno) {
    Write-Step 'Compiling Inno Setup installer...'
    & $iscc.Source 'scripts\installer.iss'
    if ($LASTEXITCODE -ne 0) { Write-Fail 'Inno Setup compilation failed' }
    Write-OK 'Installer built: dist\SentinelAI-Setup.exe'
} else {
    Write-Host '  (Inno Setup not found — skipping installer compilation)' -ForegroundColor DarkGray
    Write-Host '  Install from: https://jrsoftware.org/isdl.php' -ForegroundColor DarkGray
}

Write-Host ''
Write-Host '  Build complete.' -ForegroundColor Green
Write-Host "  Executable: $PWD\dist\SentinelAI\SentinelAI.exe" -ForegroundColor DarkGray
Write-Host ''
