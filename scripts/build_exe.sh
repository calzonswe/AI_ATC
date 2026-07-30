#!/usr/bin/env bash
# ─────────────────────────────────────────────────────
# OpenATC Client — Build Standalone Executable
# ─────────────────────────────────────────────────────
# Builds the PySide6 GUI into a single-file executable
# using PyInstaller.
#
# Usage:
#   ./scripts/build_exe.sh
#
# Output: apps/client/dist/OpenATC_Client/OpenATC_Client.exe
#         (or platform-equivalent binary)
# ─────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CLIENT_DIR="$PROJECT_ROOT/apps/client"
SPEC_FILE="$CLIENT_DIR/build_exe.spec"

echo "==> OpenATC Client — PyInstaller Build"
echo "    Project root: $PROJECT_ROOT"

# ── Check prerequisites ────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 is required"
    exit 1
fi

# ── Ensure PyInstaller is available ────────────────
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "==> Installing PyInstaller..."
    pip3 install pyinstaller 2>&1 | tail -3
fi

# ── Ensure PySide6 + sounddevice + numpy are available ──
echo "==> Checking Python dependencies..."
for pkg in PySide6 sounddevice numpy; do
    if ! python3 -c "import $pkg" 2>/dev/null; then
        echo "==> Installing $pkg..."
        pip3 install "$pkg" 2>&1 | tail -3
    fi
done

# ── Generate a simple icon if none exists ──────────
ICON_FILE="$CLIENT_DIR/client_icon.ico"
if [ ! -f "$ICON_FILE" ]; then
    echo "==> Note: No client_icon.ico found — building without icon"
    echo "    Place a 256x256 .ico file at $ICON_FILE to include an icon"
fi

# ── Build ──────────────────────────────────────────
echo "==> Building executable (this may take a few minutes)..."
cd "$CLIENT_DIR"
python3 -m PyInstaller \
    --clean \
    --noconfirm \
    "$SPEC_FILE" 2>&1

# ── Report ─────────────────────────────────────────
DIST_DIR="$CLIENT_DIR/dist/OpenATC_Client"
if [ -d "$DIST_DIR" ]; then
    echo ""
    echo "============================================"
    echo "  Build successful!"
    echo ""
    echo "  Output: $DIST_DIR"
    if [ "$(uname -s)" = "MINGW"* ] || [ "$(uname -s)" = "CYGWIN"* ]; then
        echo "  Executable: $DIST_DIR/OpenATC_Client.exe"
    else
        echo "  Binary: $DIST_DIR/OpenATC_Client"
    fi
    echo ""
    echo "  To run on Windows gaming PC:"
    echo "    1. Copy the entire dist/OpenATC_Client folder"
    echo "    2. Run OpenATC_Client.exe"
    echo "============================================"
else
    echo "Error: Build output not found at $DIST_DIR"
    exit 1
fi
