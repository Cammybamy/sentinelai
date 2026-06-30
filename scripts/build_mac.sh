#!/usr/bin/env bash
# Builds SentinelAI.app for macOS and packages it in a .dmg.
# Run from repo root with the venv activated:
#   source .venv/bin/activate
#   ./scripts/build_mac.sh
set -euo pipefail

echo ""
echo "  SentinelAI — macOS Build Script"
echo "  ─────────────────────────────────"
echo ""

# Install PyInstaller if needed.
echo "  → Installing PyInstaller..."
pip install pyinstaller --quiet
echo "  ✓ PyInstaller ready"

# Build the .app bundle.
echo "  → Running PyInstaller..."
pyinstaller sentinelai.spec --clean --noconfirm
echo "  ✓ Built: dist/SentinelAI.app"

# Create a .dmg if create-dmg is available.
if command -v create-dmg &>/dev/null; then
    echo "  → Creating .dmg..."
    create-dmg \
        --volname "SentinelAI" \
        --window-pos 200 120 \
        --window-size 600 300 \
        --icon-size 100 \
        --icon "SentinelAI.app" 175 120 \
        --hide-extension "SentinelAI.app" \
        --app-drop-link 425 120 \
        "dist/SentinelAI.dmg" \
        "dist/SentinelAI.app"
    echo "  ✓ Installer: dist/SentinelAI.dmg"
else
    echo "  (create-dmg not found — skipping .dmg)"
    echo "  Install with: brew install create-dmg"
fi

echo ""
echo "  Build complete: dist/SentinelAI.app"
echo ""
