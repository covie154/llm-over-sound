#!/bin/bash
# Collect runtime DLLs into AHK/ directory for portable deployment
# Run from MSYS2 MINGW64 shell after build.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
AHK_DIR="$SCRIPT_DIR/../AHK"
MINGW_BIN="/mingw64/bin"

echo "=== Collecting DLLs ==="

cp "$BUILD_DIR/minimodem_simple.dll" "$AHK_DIR/"
cp "$MINGW_BIN/libfftw3f-3.dll"     "$AHK_DIR/"
cp "$MINGW_BIN/libportaudio-2.dll"   "$AHK_DIR/"

# MinGW runtime (only if not statically linked)
if ldd "$BUILD_DIR/minimodem_simple.dll" | grep -q "libgcc_s_seh"; then
    cp "$MINGW_BIN/libgcc_s_seh-1.dll"  "$AHK_DIR/"
fi
if ldd "$BUILD_DIR/minimodem_simple.dll" | grep -q "libwinpthread"; then
    cp "$MINGW_BIN/libwinpthread-1.dll"  "$AHK_DIR/"
fi

echo "=== DLLs collected in $AHK_DIR ==="
ls -la "$AHK_DIR"/*.dll
