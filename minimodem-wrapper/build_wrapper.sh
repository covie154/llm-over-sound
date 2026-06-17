#!/bin/bash
# build_wrapper.sh — Build minimodem_simple.dll
# Run this in an MSYS2 MinGW64 terminal after build_deps.sh has succeeded.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ">>> Building minimodem_simple.dll..."
mkdir -p build
cd build

# Prefer Ninja if present (faster); fall back to MSYS Makefiles.
if command -v ninja >/dev/null 2>&1; then
    GEN="Ninja"
else
    GEN="MSYS Makefiles"
fi

cmake .. -G "$GEN" \
    -DCMAKE_PREFIX_PATH=/mingw64 \
    -DCMAKE_BUILD_TYPE=Release

cmake --build . -j"$(nproc)"

echo ""
if [ -f minimodem_simple.dll ]; then
    echo "Build succeeded: $(pwd)/minimodem_simple.dll"
    echo "Run collect_dlls.sh to copy the DLL to AHK/ and verify zero non-system deps."
else
    echo "ERROR: minimodem_simple.dll was not produced."
    exit 1
fi
