; ==================== Minimodem DLL Loopback Test ====================
; Standalone test script that verifies the minimodem_simple DLL can
; initialize, send FSK audio, receive it back via loopback, and return
; the original data. Requires an audio loopback (cable from line-out
; to line-in, or a virtual audio cable).
;
; Tests:
;   1. Send short JSON, verify round-trip
;   2. Verify receive() returns 0 when idle (empty poll)
;   3. Send longer payload (~500 chars), verify round-trip
;
; Usage: Run with AutoHotkey v2.0. Press Escape to abort.
#Requires AutoHotkey v2.0

#Include "include/config.ahk"
#Include "include/logging.ahk"
#Include "include/dll_manager.ahk"

; ==================== Test Helpers ====================

SendTestData(data) {
    buf := Buffer(StrPut(data, "UTF-8") - 1)
    StrPut(data, buf, "UTF-8")
    result := DllCall("minimodem_simple\minimodem_simple_send", "Ptr", buf, "Int", buf.Size, "Int")
    return result
}

WaitForTxComplete(timeoutMs := 15000) {
    deadline := A_TickCount + timeoutMs
    Loop {
        if (A_TickCount > deadline)
            return false
        tx := DllCall("minimodem_simple\minimodem_simple_is_transmitting", "Int")
        if (tx == 0)
            return true
        Sleep(50)
    }
}

PollForReceive(timeoutMs := 10000, pollIntervalMs := 50) {
    recvBuf := Buffer(8192)
    accumulated := ""
    deadline := A_TickCount + timeoutMs

    Loop {
        if (A_TickCount > deadline)
            break
        bytesReceived := DllCall("minimodem_simple\minimodem_simple_receive", "Ptr", recvBuf, "Int", recvBuf.Size, "Int")
        if (bytesReceived > 0) {
            chunk := StrGet(recvBuf, bytesReceived, "UTF-8")
            accumulated .= chunk
        }
        ; If we have data and nothing new came in the last poll cycle, give a
        ; short grace period then stop (the FSK stream may arrive in bursts).
        if (accumulated != "" && bytesReceived == 0) {
            ; Wait a bit more in case more data is incoming
            grace := A_TickCount + 500
            while (A_TickCount < grace && A_TickCount < deadline) {
                Sleep(pollIntervalMs)
                bytesReceived := DllCall("minimodem_simple\minimodem_simple_receive", "Ptr", recvBuf, "Int", recvBuf.Size, "Int")
                if (bytesReceived > 0) {
                    accumulated .= StrGet(recvBuf, bytesReceived, "UTF-8")
                    grace := A_TickCount + 500  ; extend grace
                }
            }
            break
        }
        Sleep(pollIntervalMs)
    }
    return accumulated
}

FormatResult(testName, passed, details := "") {
    status := passed ? "PASS" : "FAIL"
    line := "[" . status . "] " . testName
    if (details != "")
        line .= " -- " . details
    return line
}

; ==================== Device Enumeration ====================

EnumerateDevices() {
    output := "=== Audio Devices ===`n`n"

    playbackCount := DllCall("minimodem_simple\minimodem_simple_get_playback_device_count", "Int")
    output .= "Playback devices (" . playbackCount . "):`n"
    Loop playbackCount {
        idx := A_Index - 1
        namePtr := DllCall("minimodem_simple\minimodem_simple_get_playback_device_name", "Int", idx, "Ptr")
        name := (namePtr != 0) ? StrGet(namePtr, "UTF-8") : "(null)"
        output .= "  [" . idx . "] " . name . "`n"
    }

    captureCount := DllCall("minimodem_simple\minimodem_simple_get_capture_device_count", "Int")
    output .= "`nCapture devices (" . captureCount . "):`n"
    Loop captureCount {
        idx := A_Index - 1
        namePtr := DllCall("minimodem_simple\minimodem_simple_get_capture_device_name", "Int", idx, "Ptr")
        name := (namePtr != 0) ? StrGet(namePtr, "UTF-8") : "(null)"
        output .= "  [" . idx . "] " . name . "`n"
    }

    return output
}

; ==================== Main ====================

RunTests() {
    results := []
    report := ""

    ; Load DLL
    LoadMinimodemDll()

    ; Enumerate devices
    deviceInfo := EnumerateDevices()
    report .= deviceInfo . "`n"

    ; Initialize with default devices at configured baud rate
    report .= "Initializing minimodem (playback=-1, capture=-1, baud=" . BAUD_RATE . ")...`n"
    initResult := DllCall("minimodem_simple\minimodem_simple_init",
        "Int", -1,
        "Int", -1,
        "Int", BAUD_RATE,
        "Int")

    if (initResult < 0) {
        errMsg := GetMinimodemError()
        report .= "INIT FAILED: " . errMsg . "`n"
        MsgBox(report, "Minimodem Loopback Test - INIT FAILURE", "Icon!")
        UnloadMinimodemDll()
        return
    }
    report .= "Init OK.`n`n"

    ; Initialize logging for test session
    InitializeLog()
    LogMessage("TEST", "Loopback test session started")

    ; ------------------------------------------------------------------
    ; Test 1: Short JSON round-trip
    ; ------------------------------------------------------------------
    testMsg1 := '{"id":"TEST","fn":"ping","ct":"hello world"}'
    report .= "--- Test 1: Short JSON round-trip ---`n"
    report .= "Sending: " . testMsg1 . "`n"
    LogMessage("TEST1", "Sending: " . testMsg1)

    sendResult := SendTestData(testMsg1)
    if (sendResult < 0) {
        errMsg := GetMinimodemError()
        result1 := FormatResult("Test 1: Short JSON", false, "send() failed: " . errMsg)
    } else {
        report .= "Send queued OK. Waiting for TX complete...`n"
        txDone := WaitForTxComplete(15000)
        if (!txDone) {
            result1 := FormatResult("Test 1: Short JSON", false, "TX did not complete within 15s")
        } else {
            report .= "TX complete. Polling for RX (10s timeout)...`n"
            received := PollForReceive(10000)
            received := Trim(received)
            if (received == testMsg1) {
                result1 := FormatResult("Test 1: Short JSON", true, "Round-trip match")
            } else if (received == "") {
                result1 := FormatResult("Test 1: Short JSON", false, "No data received (check loopback)")
            } else {
                result1 := FormatResult("Test 1: Short JSON", false, "Mismatch`nExpected: " . testMsg1 . "`nGot:      " . received)
            }
        }
    }
    results.Push(result1)
    report .= result1 . "`n`n"
    LogMessage("TEST1", result1)

    ; ------------------------------------------------------------------
    ; Test 2: Empty poll (receive returns 0 when idle)
    ; ------------------------------------------------------------------
    report .= "--- Test 2: Empty poll ---`n"
    Sleep(500)  ; brief pause to let any residual audio drain

    recvBuf := Buffer(8192)
    bytesIdle := DllCall("minimodem_simple\minimodem_simple_receive", "Ptr", recvBuf, "Int", recvBuf.Size, "Int")
    if (bytesIdle == 0) {
        result2 := FormatResult("Test 2: Empty poll", true, "receive() returned 0 when idle")
    } else if (bytesIdle < 0) {
        result2 := FormatResult("Test 2: Empty poll", false, "receive() returned error: " . bytesIdle)
    } else {
        spurious := StrGet(recvBuf, bytesIdle, "UTF-8")
        result2 := FormatResult("Test 2: Empty poll", false, "Unexpected data (" . bytesIdle . " bytes): " . spurious)
    }
    results.Push(result2)
    report .= result2 . "`n`n"
    LogMessage("TEST2", result2)

    ; ------------------------------------------------------------------
    ; Test 3: Longer payload (~500 chars)
    ; ------------------------------------------------------------------
    ; Build a payload of approximately 500 characters
    longContent := ""
    Loop 10 {
        longContent .= "Line " . A_Index . ": The quick brown fox jumps over the lazy dog. "
    }
    testMsg3 := '{"id":"TEST3","fn":"longping","ct":"' . longContent . '"}'
    msg3Len := StrLen(testMsg3)

    report .= "--- Test 3: Long payload (" . msg3Len . " chars) ---`n"
    LogMessage("TEST3", "Sending " . msg3Len . " chars")

    sendResult3 := SendTestData(testMsg3)
    if (sendResult3 < 0) {
        errMsg := GetMinimodemError()
        result3 := FormatResult("Test 3: Long payload", false, "send() failed: " . errMsg)
    } else {
        report .= "Send queued OK. Waiting for TX complete...`n"
        ; Longer timeout for larger payload — at 1200 baud this could take a while
        txDone3 := WaitForTxComplete(60000)
        if (!txDone3) {
            result3 := FormatResult("Test 3: Long payload", false, "TX did not complete within 60s")
        } else {
            report .= "TX complete. Polling for RX (30s timeout)...`n"
            received3 := PollForReceive(30000)
            received3 := Trim(received3)
            if (received3 == testMsg3) {
                result3 := FormatResult("Test 3: Long payload", true, msg3Len . " chars round-trip match")
            } else if (received3 == "") {
                result3 := FormatResult("Test 3: Long payload", false, "No data received")
            } else {
                ; Partial match check
                matchLen := 0
                Loop Min(StrLen(received3), StrLen(testMsg3)) {
                    if (SubStr(received3, A_Index, 1) != SubStr(testMsg3, A_Index, 1))
                        break
                    matchLen := A_Index
                }
                result3 := FormatResult("Test 3: Long payload", false,
                    "Mismatch. Sent " . msg3Len . " chars, got " . StrLen(received3) . " chars. "
                    . "First " . matchLen . " chars match.")
            }
        }
    }
    results.Push(result3)
    report .= result3 . "`n`n"
    LogMessage("TEST3", result3)

    ; ------------------------------------------------------------------
    ; Summary
    ; ------------------------------------------------------------------
    passCount := 0
    failCount := 0
    for r in results {
        if (SubStr(r, 1, 6) == "[PASS]")
            passCount++
        else
            failCount++
    }

    summary := "=== SUMMARY: " . passCount . " passed, " . failCount . " failed out of " . results.Length . " tests ==="
    report .= summary . "`n"
    LogMessage("TEST", summary)

    ; Cleanup
    DllCall("minimodem_simple\minimodem_simple_cleanup")
    UnloadMinimodemDll()
    LogMessage("TEST", "Loopback test session ended")

    ; Show results
    icon := (failCount == 0) ? "Iconi" : "Icon!"
    MsgBox(report, "Minimodem Loopback Test Results", icon)
}

; Run
RunTests()
ExitApp()

; Press Escape to abort
Esc::
{
    DllCall("minimodem_simple\minimodem_simple_cleanup")
    UnloadMinimodemDll()
    ExitApp()
}
