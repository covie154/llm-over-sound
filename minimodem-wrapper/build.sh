#!/bin/bash
# Build minimodem_simple.dll using MSYS2 MinGW-w64
# Run from MSYS2 MINGW64 shell

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"

echo "=== Installing dependencies ==="
pacman -S --needed --noconfirm \
    mingw-w64-x86_64-fftw \
    mingw-w64-x86_64-portaudio \
    mingw-w64-x86_64-cmake \
    mingw-w64-x86_64-gcc

echo "=== Configuring ==="
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"
cmake -G "MinGW Makefiles" "$SCRIPT_DIR"

echo "=== Building ==="
mingw32-make -j$(nproc)

echo "=== Done ==="
echo "DLL at: $BUILD_DIR/minimodem_simple.dll"
