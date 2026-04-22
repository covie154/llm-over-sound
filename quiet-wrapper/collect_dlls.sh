#!/bin/bash
# collect_dlls.sh — Gather quiet_simple.dll, all runtime DLLs, and the
#                   profiles JSON into the AHK/ directory.
# Run this in an MSYS2 MinGW64 terminal after build_wrapper.sh succeeds.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DLL_PATH="$SCRIPT_DIR/build/quiet_simple.dll"
DEST="$SCRIPT_DIR/../AHK"
QUIET_SRC="$SCRIPT_DIR/../quiet"

if [ ! -f "$DLL_PATH" ]; then
    echo "ERROR: quiet_simple.dll not found at $DLL_PATH"
    echo "       Run build_wrapper.sh first."
    exit 1
fi

mkdir -p "$DEST"

echo ">>> Collecting DLLs into $DEST ..."

# Copy quiet_simple.dll itself
cp -v "$DLL_PATH" "$DEST/"

# Use ldd to find all MinGW64 DLL dependencies (skip Windows system DLLs)
echo ""
echo "--- Runtime dependencies ---"
ldd "$DLL_PATH" | grep -i mingw64 | awk '{print $3}' | sort -u | while read -r dep; do
    if [ -f "$dep" ]; then
        cp -v "$dep" "$DEST/"
    else
        echo "  WARNING: $dep listed by ldd but not found on disk"
    fi
done

# Also copy libquiet.dll from the install prefix if not already caught
for lib in libquiet.dll libliquid.dll libfec.dll; do
    src="/mingw64/bin/$lib"
    if [ -f "$src" ] && [ ! -f "$DEST/$lib" ]; then
        cp -v "$src" "$DEST/"
    fi
done

# Copy quiet-profiles.json
if [ -f "$QUIET_SRC/quiet-profiles.json" ]; then
    cp -v "$QUIET_SRC/quiet-profiles.json" "$DEST/"
    echo ""
    echo "Copied quiet-profiles.json."
else
    echo ""
    echo "WARNING: quiet-profiles.json not found at $QUIET_SRC/quiet-profiles.json"
fi

echo ""
echo "=== Summary ==="
echo "Files in $DEST:"
ls -1 "$DEST"/*.dll "$DEST"/quiet-profiles.json 2>/dev/null || true
echo ""
echo "Done. The AHK directory is ready to use quiet_simple.dll."
