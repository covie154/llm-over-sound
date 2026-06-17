#!/bin/bash
# build_deps.sh — Install/verify build dependencies for minimodem_simple.dll
# Run this in an MSYS2 MinGW64 terminal (not the MSYS2 MSYS terminal).
#
# Usage:
#   ./build_deps.sh
#
# Prerequisites:
#   - MSYS2 installed with the mingw-w64-x86_64 toolchain
#
# This phase vendors minimodem's C sources in-repo and links exactly one
# external numerical library, single-precision FFTW (fftw3f), statically.
# No language-package-manager packages are installed.

set -euo pipefail

echo "=== minimodem_simple dependency builder ==="
echo "  MSYS2 prefix : /mingw64"
echo ""

# ------------------------------------------------------------------
# Step 0: Install MSYS2 MinGW64 packages
# ------------------------------------------------------------------
# Locate pacman. In a proper MSYS2 MinGW64 terminal it is on PATH; if this
# script is launched from a plain Git Bash, fall back to the standard MSYS2
# location so the verify step can still run.
PACMAN=""
if command -v pacman >/dev/null 2>&1; then
    PACMAN="pacman"
elif [ -x /c/msys64/usr/bin/pacman.exe ]; then
    PACMAN="/c/msys64/usr/bin/pacman.exe"
fi

if [ -n "$PACMAN" ]; then
    echo ">>> Installing MSYS2 MinGW64 packages..."
    "$PACMAN" -S --needed --noconfirm \
        mingw-w64-x86_64-gcc \
        mingw-w64-x86_64-fftw \
        mingw-w64-x86_64-cmake \
        mingw-w64-x86_64-pkgconf \
        mingw-w64-x86_64-ntldd-git \
        make
else
    echo ">>> pacman not found; skipping package install."
    echo "    (Run this in an MSYS2 MinGW64 terminal to auto-install toolchain"
    echo "     packages. The verification step below confirms what is present.)"
fi

echo ""

# ------------------------------------------------------------------
# Step 1: Verify the static fftw3f library is present (ASSUMPTION A1)
# ------------------------------------------------------------------
echo "=== Verification ==="
PASS=true

# In an MSYS2 MinGW64 shell /mingw64 is the prefix; from plain Git Bash the same
# tree lives at /c/msys64/mingw64. Check both.
find_in_prefix() {
    for p in /mingw64 /c/msys64/mingw64; do
        if [ -f "$p/$1" ]; then
            echo "$p/$1"
            return 0
        fi
    done
    return 1
}

if FFTW_STATIC="$(find_in_prefix lib/libfftw3f.a)"; then
    echo "  [OK] libfftw3f.a ($FFTW_STATIC)"
else
    echo "  [MISSING] libfftw3f.a"
    echo ""
    echo "  The pacman mingw-w64-x86_64-fftw package did not provide the static"
    echo "  archive. Build fftw3f from source instead:"
    echo ""
    echo "      curl -O http://www.fftw.org/fftw-3.3.10.tar.gz"
    echo "      tar xf fftw-3.3.10.tar.gz && cd fftw-3.3.10"
    echo "      ./configure --enable-single --enable-static --disable-shared \\"
    echo "                  --enable-sse2 --prefix=/mingw64"
    echo "      make && make install   # yields /mingw64/lib/libfftw3f.a"
    echo ""
    PASS=false
fi

if FFTW_HEADER="$(find_in_prefix include/fftw3.h)"; then
    echo "  [OK] fftw3.h ($FFTW_HEADER)"
else
    echo "  [MISSING] fftw3.h"
    PASS=false
fi

echo ""
if $PASS; then
    echo "All dependencies present. Run build_wrapper.sh to build minimodem_simple.dll."
else
    echo "WARNING: Some dependencies are missing. See above."
    exit 1
fi
