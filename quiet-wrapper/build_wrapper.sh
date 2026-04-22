#!/bin/bash
# build_wrapper.sh — Build quiet_simple.dll
# Run this in an MSYS2 MinGW64 terminal after build_deps.sh has succeeded.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ">>> Building quiet_simple.dll..."
mkdir -p build
cd build

cmake .. -G "MSYS Makefiles" \
    -DCMAKE_PREFIX_PATH=/mingw64 \
    -DCMAKE_BUILD_TYPE=Release

make -j"$(nproc)"

echo ""
if [ -f quiet_simple.dll ]; then
    echo "Build succeeded: $(pwd)/quiet_simple.dll"
    echo "Run collect_dlls.sh to copy the DLL and its dependencies to the AHK directory."
else
    echo "ERROR: quiet_simple.dll was not produced."
    exit 1
fi
