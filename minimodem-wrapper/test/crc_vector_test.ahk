#Requires AutoHotkey v2.0
; crc_vector_test.ahk - AHK side of the CRC32 cross-language agreement vector.
;
; The medico-legal integrity gate (Wave 0). The frontend attaches a `crc` field
; (CRC32 of the `ct` string's UTF-8 bytes) to every message; this must be
; byte-identical to the Python backend's zlib.crc32 or every message fails its
; CRC check and retransmits forever (Pitfall 4).
;
; CRC contract (pinned per 07-RESEARCH.md): crc = CRC32 of the UTF-8 bytes of
; the string, standard reflected CRC-32 (poly 0xEDB88320, init/xorout
; 0xFFFFFFFF). ntdll!RtlComputeCrc32(0, data, len) implements exactly this and
; equals Python zlib.crc32. This script PROVES it on a fixed vector against the
; real ntdll on the developer's box.
;
; Crc32Str() below is the EXACT helper that ships in AHK/include/compression.ahk
; in Plan 07-03 (authored here against the same StrPut UTF-8 byte sequence).
;
; Run with AutoHotkey v2. Writes "CRC OK" or "CRC FAIL: ..." to crc_result.txt
; (next to this script) and exits 0 on success / 1 on failure. AHK has no console
; exit-code convention, so the result file is the inspectable artifact and the
; ExitApp code is for any harness that does read it.

; ===== The shared test vectors (IDENTICAL byte sequences to crc_vector_test.py) =====
CANONICAL_INPUT    := "123456789"
CANONICAL_EXPECTED := 0xCBF43926

; UTF-8 multibyte ('é' = C3 A9) + newline. In AHK v2 `n is a literal newline.
; Bytes: 4c 69 76 65 72 3a 20 6e 6f 72 6d 61 6c 2e 0a 43 52 43 c3 a9
UTF8_INPUT    := "Liver: normal.`nCRCé"
UTF8_EXPECTED := 0xBF16E982   ; same constant baked into crc_vector_test.py

; ===== Crc32Str: CRC32 of a UTF-8 string, matching Python zlib.crc32 =====
Crc32Str(str) {
    ; StrPut returns the count INCLUDING the null terminator; exclude it.
    utf8Size := StrPut(str, "UTF-8") - 1
    if (utf8Size <= 0) {
        return 0
    }
    buf := Buffer(utf8Size, 0)
    StrPut(str, buf, "UTF-8")
    ; RtlComputeCrc32(DWORD initial, PVOID data, INT length) -> DWORD
    crc := DllCall("ntdll\RtlComputeCrc32", "UInt", 0, "Ptr", buf.Ptr, "Int", utf8Size, "UInt")
    return crc
}

ToHex(n) {
    return "0x" . Format("{:08X}", n)
}

Main() {
    resultFile := A_ScriptDir . "\crc_result.txt"
    try FileDelete(resultFile)

    failures := []

    got1 := Crc32Str(CANONICAL_INPUT)
    if (got1 != CANONICAL_EXPECTED) {
        failures.Push("canonical vector: got " . ToHex(got1) . " want " . ToHex(CANONICAL_EXPECTED))
    }

    got2 := Crc32Str(UTF8_INPUT)
    if (got2 != UTF8_EXPECTED) {
        failures.Push("utf-8 vector: got " . ToHex(got2) . " want " . ToHex(UTF8_EXPECTED))
    }

    if (failures.Length > 0) {
        msg := "CRC FAIL:"
        for f in failures {
            msg .= "`n  " . f
        }
        msg .= "`ncanonical " . ToHex(got1) . " utf8 " . ToHex(got2)
        FileAppend(msg . "`n", resultFile)
        ExitApp(1)
    }

    FileAppend("CRC OK`ncanonical " . ToHex(got1) . " utf8 " . ToHex(got2) . "`n", resultFile)
    ExitApp(0)
}

Main()
