#!/bin/bash
# collect_dlls.sh — Copy minimodem_simple.dll into AHK/ and FAIL if it carries
#                   any non-system runtime dependency.
# Run this in an MSYS2 MinGW64 terminal after build_wrapper.sh succeeds.
#
# The whole point of static-linking fftw3f + the MinGW runtime is a single,
# copy-pasteable, dependency-free DLL. This script is the gate that proves it.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DLL_PATH="$SCRIPT_DIR/build/minimodem_simple.dll"
DEST="$SCRIPT_DIR/../AHK"

if [ ! -f "$DLL_PATH" ]; then
    echo "ERROR: minimodem_simple.dll not found at $DLL_PATH"
    echo "       Run build_wrapper.sh first."
    exit 1
fi

mkdir -p "$DEST"

# ---------------------------------------------------------------------------
# Dependency gate: enumerate the DLL's imports and FAIL on any forbidden dep.
# Allowed: Windows system DLLs only. Specifically forbid libgcc*, libwinpthread*,
# libstdc++*, libfftw3f* (their presence means static linking failed, Pitfall 5).
# ---------------------------------------------------------------------------
echo ">>> Checking runtime dependencies of minimodem_simple.dll ..."

# Allow-list of Windows system DLLs (lowercased, no version suffix matching).
is_system_dll() {
    case "$(echo "$1" | tr '[:upper:]' '[:lower:]')" in
        kernel32.dll|kernelbase.dll|msvcrt.dll|winmm.dll|user32.dll|advapi32.dll|\
        ole32.dll|ntdll.dll|ws2_32.dll|gdi32.dll|shell32.dll|rpcrt4.dll|\
        sechost.dll|combase.dll|ucrtbase.dll|win32u.dll|gdi32full.dll|\
        msvcp_win.dll|bcryptprimitives.dll|imm32.dll|powrprof.dll|\
        avrt.dll|setupapi.dll|cfgmgr32.dll)
            return 0 ;;
        *)
            return 1 ;;
    esac
}

# Gather the DLL's DIRECT imports (its own import table) -- that is what tells
# us whether libgcc/libwinpthread/libstdc++/libfftw3f leaked. We deliberately
# do NOT use `ntldd -R` for the gate: recursive resolution walks the whole
# Windows system DLL tree (api-ms-*/ext-ms-* API sets), which is noisy and
# irrelevant to "is THIS dll self-contained".
#
# objdump -p prints the import table directly and is preferred. ntldd (without
# -R) is the fallback; both yield only the directly-imported DLL names.
DEPS=""
if command -v objdump >/dev/null 2>&1; then
    echo "    (using objdump -p direct imports)"
    DEPS="$(objdump -p "$DLL_PATH" | awk '/DLL Name:/ {print $3}' || true)"
elif command -v ntldd >/dev/null 2>&1; then
    echo "    (objdump not found; using ntldd direct imports)"
    DEPS="$(ntldd "$DLL_PATH" | awk '{print $1}' | grep -i '\.dll$' || true)"
else
    echo "ERROR: neither objdump nor ntldd is available to verify dependencies."
    exit 1
fi

echo ""
echo "--- Imported DLLs ---"
echo "$DEPS" | sort -u

BAD=""
while read -r dep; do
    [ -z "$dep" ] && continue
    base="$(basename "$dep")"
    # The DLL itself may appear in recursive listings; skip it.
    if [ "$(echo "$base" | tr '[:upper:]' '[:lower:]')" = "minimodem_simple.dll" ]; then
        continue
    fi
    # api-ms-win-*.dll are virtual system API sets — always OK.
    case "$(echo "$base" | tr '[:upper:]' '[:lower:]')" in
        api-ms-win-*|ext-ms-*) continue ;;
    esac
    if ! is_system_dll "$base"; then
        BAD="$BAD $base"
    fi
done <<EOF
$DEPS
EOF

echo ""
if [ -n "$BAD" ]; then
    echo "FAIL: minimodem_simple.dll has non-system runtime dependencies:"
    for b in $BAD; do echo "   - $b"; done
    echo ""
    echo "Static linking failed (Pitfall 5). Ensure CMake uses"
    echo "  -static -static-libgcc -static-libstdc++ and links libfftw3f.a (not .dll.a)."
    exit 1
fi

echo "PASS: only Windows system DLLs are imported. DLL is self-contained."
echo ""

# ---------------------------------------------------------------------------
# Copy the verified DLL into AHK/. (Old ggwave_simple.dll + SDL2.dll are left
# in place; they are retired only after end-to-end verification in Plan 07-05.)
# ---------------------------------------------------------------------------
cp -v "$DLL_PATH" "$DEST/"

echo ""
echo "=== Summary ==="
echo "Copied minimodem_simple.dll -> $DEST/"
ls -1 "$DEST"/minimodem_simple.dll 2>/dev/null || true
echo ""
echo "Done. The AHK directory now has a dependency-free minimodem_simple.dll."
