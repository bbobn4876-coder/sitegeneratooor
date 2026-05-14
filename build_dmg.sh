#!/bin/bash
# Build script for macOS — creates PHP Site Generator.dmg
# Run on macOS: bash build_dmg.sh
set -e

APP_NAME="PHP Site Generator"
DMG_NAME="PHPSiteGenerator"
VERSION="82"

echo "=== PHP Site Generator — macOS build ==="
echo ""

# ── 1. Install dependencies ──────────────────────────────────────────────────
echo "[1/5] Installing Python dependencies..."
pip install -r requirements_build.txt --quiet

# ── 2. PyInstaller ───────────────────────────────────────────────────────────
echo "[2/5] Building app bundle with PyInstaller..."
pyinstaller phpgen_version82.spec --noconfirm --clean

# ── 3. Verify .app was created ───────────────────────────────────────────────
APP_PATH="dist/${APP_NAME}.app"
if [ ! -d "$APP_PATH" ]; then
    echo "ERROR: $APP_PATH not found. PyInstaller failed."
    exit 1
fi
echo "      App bundle: $APP_PATH"

# ── 4. Create .dmg ───────────────────────────────────────────────────────────
echo "[4/5] Creating DMG..."

DMG_TMP="${DMG_NAME}_tmp.dmg"
DMG_OUT="${DMG_NAME}_v${VERSION}.dmg"

# Clean old artifacts
rm -f "$DMG_TMP" "$DMG_OUT"

# Calculate size (MB) + 20 MB buffer
APP_SIZE_KB=$(du -sk "$APP_PATH" | cut -f1)
DMG_SIZE_MB=$(( (APP_SIZE_KB / 1024) + 20 ))

# Create writable DMG
hdiutil create -size "${DMG_SIZE_MB}m" -fs HFS+ \
    -volname "$APP_NAME" "$DMG_TMP" -quiet

# Mount it
MOUNT_DIR=$(hdiutil attach "$DMG_TMP" -readwrite -noverify -noautoopen \
    | grep "/Volumes/" | awk '{print $3}')

echo "      Mounted at: $MOUNT_DIR"

# Copy app
cp -R "$APP_PATH" "$MOUNT_DIR/"

# Symlink to /Applications for drag-install
ln -s /Applications "$MOUNT_DIR/Applications"

# Unmount
hdiutil detach "$MOUNT_DIR" -quiet

# Convert to compressed read-only DMG
hdiutil convert "$DMG_TMP" -format UDZO -o "$DMG_OUT" -quiet
rm -f "$DMG_TMP"

# ── 5. Done ──────────────────────────────────────────────────────────────────
echo "[5/5] Done!"
echo ""
echo "  Output: $(pwd)/${DMG_OUT}"
echo ""
echo "  Install: open ${DMG_OUT}"
