#!/bin/bash
# build_deps.sh — Build all dependencies for quiet_simple.dll
# Run this in an MSYS2 MinGW64 terminal (not MSYS2 MSYS terminal).
#
# Usage:
#   ./build_deps.sh
#
# Prerequisites:
#   - MSYS2 installed with the mingw-w64-x86_64-toolchain group
#   - Internet access (clones libfec and liquid-dsp)

set -euo pipefail

JOBS="$(nproc)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
QUIET_SRC="$(cd "$SCRIPT_DIR/../quiet" 2>/dev/null && pwd)" || {
    echo "ERROR: Cannot find quiet source at ../quiet relative to this script"
    exit 1
}
BUILD_ROOT="$SCRIPT_DIR/_deps"

echo "=== quiet_simple dependency builder ==="
echo "  MSYS2 prefix : /mingw64"
echo "  quiet source : $QUIET_SRC"
echo "  build root   : $BUILD_ROOT"
echo ""

# ------------------------------------------------------------------
# Step 0: Install MSYS2 packages
# ------------------------------------------------------------------
echo ">>> Installing MSYS2 packages..."
pacman -S --needed --noconfirm \
    mingw-w64-x86_64-gcc \
    mingw-w64-x86_64-jansson \
    mingw-w64-x86_64-portaudio \
    mingw-w64-x86_64-cmake \
    mingw-w64-x86_64-pkgconf \
    autoconf automake libtool make

echo ""

mkdir -p "$BUILD_ROOT"
cd "$BUILD_ROOT"

# ------------------------------------------------------------------
# Step 1: Build libfec
# ------------------------------------------------------------------
echo ">>> Building libfec..."
if [ ! -d libfec ]; then
    git clone https://github.com/quiet/libfec.git
fi
cd libfec
rm -rf build && mkdir build && cd build
cmake .. -G "MSYS Makefiles" \
    -DCMAKE_INSTALL_PREFIX=/mingw64 \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
    -DCMAKE_C_FLAGS="-Drandom=rand -DMAX_RANDOM=RAND_MAX"
make -j"$JOBS"
make install
cd "$BUILD_ROOT"
echo "  libfec installed."
echo ""

# ------------------------------------------------------------------
# Step 2: Build liquid-dsp (devel branch)
# ------------------------------------------------------------------
echo ">>> Building liquid-dsp (devel branch)..."
if [ ! -d liquid-dsp ]; then
    git clone https://github.com/quiet/liquid-dsp.git -b devel --single-branch
fi
cd liquid-dsp
# Regenerate configure if needed
if [ ! -f configure ]; then
    ./bootstrap.sh
fi
./configure --prefix=/mingw64
make -j"$JOBS"
make install
cd "$BUILD_ROOT"
echo "  liquid-dsp installed."
echo ""

# ------------------------------------------------------------------
# Step 3: Build libquiet
# ------------------------------------------------------------------
echo ">>> Building libquiet from $QUIET_SRC..."
mkdir -p quiet-build && cd quiet-build
cmake "$QUIET_SRC" -G "MSYS Makefiles" \
    -DCMAKE_INSTALL_PREFIX=/mingw64 \
    -DCMAKE_BUILD_TYPE=Release
make -j"$JOBS"
make install
cd "$BUILD_ROOT"
echo "  libquiet installed."
echo ""

# ------------------------------------------------------------------
# Step 4: Verify
# ------------------------------------------------------------------
echo "=== Verification ==="
PASS=true

check_lib() {
    if [ -f "/mingw64/lib/$1" ] || [ -f "/mingw64/bin/$1" ]; then
        echo "  [OK] $1"
    else
        echo "  [MISSING] $1"
        PASS=false
    fi
}

check_header() {
    if [ -f "/mingw64/include/$1" ]; then
        echo "  [OK] $1"
    else
        echo "  [MISSING] $1"
        PASS=false
    fi
}

echo "Libraries:"
check_lib "libfec.a"
check_lib "libliquid.dll.a"
check_lib "libquiet.dll.a"
check_lib "libportaudio.dll.a"
check_lib "libjansson.dll.a"

echo "Headers:"
check_header "fec.h"
check_header "liquid/liquid.h"
check_header "quiet.h"
check_header "quiet-portaudio.h"
check_header "portaudio.h"
check_header "jansson.h"

echo ""
if $PASS; then
    echo "All dependencies installed successfully."
    echo "You can now run build_wrapper.sh to build quiet_simple.dll."
else
    echo "WARNING: Some dependencies are missing. Check the output above."
    exit 1
fi
