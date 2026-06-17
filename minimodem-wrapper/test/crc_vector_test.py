#!/usr/bin/env python3
"""crc_vector_test.py - Python side of the CRC32 cross-language agreement vector.

This is the medico-legal integrity gate (Wave 0). The transport attaches a
``crc`` field (CRC32 of the ``ct`` string's UTF-8 bytes) to every message; the
AHK frontend computes it via ``ntdll!RtlComputeCrc32(0, ...)`` and the Python
backend via ``zlib.crc32``. Both MUST produce byte-identical values or every
message would fail its CRC check and retransmit forever (Pitfall 4).

CRC contract (pinned per 07-RESEARCH.md § CRC32):
  crc = zlib.crc32(ct.encode("utf-8")) & 0xFFFFFFFF
  - standard reflected CRC-32, polynomial 0xEDB88320,
    init = 0xFFFFFFFF, xorout = 0xFFFFFFFF (== RtlComputeCrc32 with initial 0).

Run: ``python minimodem-wrapper/test/crc_vector_test.py``
Exits 0 and prints ``CRC OK`` on success; non-zero on any mismatch.

The expected values here are the SAME constants baked into the sibling
``crc_vector_test.ahk`` so the two sides are proven to agree on the identical
UTF-8 byte sequence.
"""

import sys
import zlib

# ---- The shared test vectors (identical byte sequences on both sides) ----

# 1. Canonical CRC-32 check value.
CANONICAL_INPUT = "123456789"
CANONICAL_EXPECTED = 0xCBF43926

# 2. Radiology-representative vector: UTF-8 multibyte ('é' = 0xC3 0xA9) + newline.
#    UTF-8 bytes: 4c 69 76 65 72 3a 20 6e 6f 72 6d 61 6c 2e 0a 43 52 43 c3 a9
UTF8_INPUT = "Liver: normal.\nCRCé"   # "Liver: normal.\nCRCé"
UTF8_EXPECTED = 0xBF16E982                 # computed once with zlib, baked as the contract


def crc32_str(text: str) -> int:
    """CRC32 of a UTF-8 string, matching AHK ntdll!RtlComputeCrc32(0, ...)."""
    return zlib.crc32(text.encode("utf-8")) & 0xFFFFFFFF


def main() -> int:
    failures = []

    got1 = crc32_str(CANONICAL_INPUT)
    print(f"crc32({CANONICAL_INPUT!r}) = 0x{got1:08X} (want 0x{CANONICAL_EXPECTED:08X})")
    if got1 != CANONICAL_EXPECTED:
        failures.append(
            f"canonical vector: got 0x{got1:08X} want 0x{CANONICAL_EXPECTED:08X}"
        )

    utf8_bytes = UTF8_INPUT.encode("utf-8")
    got2 = crc32_str(UTF8_INPUT)
    print(f"crc32({UTF8_INPUT!r}) = 0x{got2:08X} (want 0x{UTF8_EXPECTED:08X})")
    print(f"  utf-8 bytes: {utf8_bytes.hex()}")
    if got2 != UTF8_EXPECTED:
        failures.append(
            f"utf-8 vector: got 0x{got2:08X} want 0x{UTF8_EXPECTED:08X}"
        )

    if failures:
        for f in failures:
            print(f"CRC FAIL: {f}", file=sys.stderr)
        return 1

    print("CRC OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
