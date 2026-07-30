# ─────────────────────────────────────────────────────
# OpenATC Client — Build Standalone Executable (Windows)
# ─────────────────────────────────────────────────────
# Builds the PySide6 GUI into a single .exe file using
# PyInstaller on Windows.
#
# Usage:
#   .\scripts\build_exe.ps1
#
# Output: apps\client\dist\OpenATC_Client\OpenATC_Client.exe
# ─────────────────────────────────────────────────────

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$ClientDir = Join-Path $ProjectRoot "apps" "client"
$SpecFile = Join-Path $ClientDir "build_exe.spec"
$IconFile = Join-Path $ClientDir "client_icon.ico"

Write-Host "==> OpenATC Client - PyInstaller Build (Windows)"
Write-Host "    Project root: $ProjectRoot"

# ── Check Python ───────────────────────────────────
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Error "Python is required. Install Python 3.10+ from https://www.python.org/"
    exit 1
}

# ── Ensure PyInstaller ─────────────────────────────
try {
    python -c "import PyInstaller" 2>$null
} catch {
    Write-Host "==> Installing PyInstaller..."
    python -m pip install pyinstaller
}

# ── Ensure dependencies ────────────────────────────
Write-Host "==> Checking dependencies..."
foreach ($pkg in @("PySide6", "sounddevice", "numpy")) {
    try {
        python -c "import $pkg" 2>$null
    } catch {
        Write-Host "==> Installing $pkg..."
        python -m pip install $pkg
    }
}

# ── Icon check ─────────────────────────────────────
if (-not (Test-Path $IconFile)) {
    Write-Host "==> Note: No client_icon.ico found - building without icon"
    Write-Host "    Place a 256x256 .ico file at $IconFile to include an icon"
}

# ── Build ──────────────────────────────────────────
Write-Host "==> Building executable (this may take a few minutes)..."
Push-Location $ClientDir
try {
    python -m PyInstaller --clean --noconfirm $SpecFile
} finally {
    Pop-Location
}

# ── Report ─────────────────────────────────────────
$DistDir = Join-Path $ClientDir "dist" "OpenATC_Client"
if (Test-Path $DistDir) {
    Write-Host ""
    Write-Host "============================================"
    Write-Host "  Build successful!"
    Write-Host ""
    Write-Host "  Output: $DistDir"
    Write-Host "  Executable: $DistDir\OpenATC_Client.exe"
    Write-Host ""
    Write-Host "  To run on your gaming PC:"
    Write-Host "    1. Copy the entire dist\OpenATC_Client folder"
    Write-Host "    2. Run OpenATC_Client.exe"
    Write-Host "============================================"
} else {
    Write-Error "Build failed: output not found at $DistDir"
    exit 1
}
