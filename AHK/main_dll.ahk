; AHK V2 Script — minimodem Direct DLL Integration
; Entrypoint: loads modules and runs the main loop.
#Requires AutoHotkey v2.0

; ==================== Includes ====================
#Include "include/_JXON.ahk"
#Include "include/config.ahk"
#Include "include/logging.ahk"
#Include "include/compression.ahk"
#Include "include/dll_manager.ahk"
#Include "include/msgid.ahk"
#Include "include/gui.ahk"
#Include "include/chunking.ahk"

; ==================== Main Entry Point ====================
Main()

SendData(data) {
    buf := Buffer(StrPut(data, "UTF-8") - 1)
    StrPut(data, buf, "UTF-8")
    result := DllCall("minimodem_simple\minimodem_simple_send", "Ptr", buf, "Int", buf.Size, "Int")
    return result
}

Main() {
    global selectedSpeakerIndex, selectedMicrophoneIndex, selectedBaudRate, isInitialized

    ; Load the DLL
    LoadMinimodemDll()

    ; Show audio device selection dialog
    if (!SelectAudioDevices()) {
        UnloadMinimodemDll()
        ExitApp()
    }

    ; Initialize minimodem with selected devices and baud rate
    result := DllCall("minimodem_simple\minimodem_simple_init",
        "Int", selectedSpeakerIndex,
        "Int", selectedMicrophoneIndex,
        "Int", selectedBaudRate,
        "Int")

    if (result < 0) {
        errorMsg := GetMinimodemError()
        MsgBox("Failed to initialize minimodem: " . errorMsg, "Error", "Icon!")
        UnloadMinimodemDll()
        ExitApp()
    }

    isInitialized := true

    ; Initialize logging
    InitializeLog()
    LogMessage("SESSION", "Application started - Speaker: " . selectedSpeakerIndex . ", Mic: " . selectedMicrophoneIndex . ", Baud: " . selectedBaudRate)

    ; Start the receive polling timer (no ProcessAudio needed — PortAudio runs in background)
    SetTimer(PollReceive, 50)

    ; Main loop
    MainLoop()

    ; Cleanup
    Cleanup()
}

MainLoop() {
    Loop {
        ; Get multiline input from user
        result := GetMultilineInput()

        ; Check if user cancelled
        if (result.cancelled) {
            break
        }

        ; Skip empty input
        if (result.text = "") {
            MsgBox("Please enter a message.", "Warning", "Icon!")
            continue
        }

        ; Generate unique message ID
        msgID := GenerateMessageID()

        ; Build message dict
        sendDict := Map(
            "id", msgID,
            "fn", "test",
            "ct", result.text
        )

        ; Chunk the message (handles compression internally)
        chunks := ChunkMessage(sendDict)

        ; Send all chunks sequentially
        SendChunkedMessage(chunks, msgID)
    }
}

; ==================== Cleanup ====================

PollReceive() {
    ; Called periodically by a timer. Polls for incoming data, handles
    ; chunk buffering and reassembly, and checks for timeouts.
    global isInitialized, chunkReceiveBuffer, lastSentChunks

    if (!isInitialized) {
        return
    }

    ; Check for received data
    recvBuf := Buffer(8192)
    bytesReceived := DllCall("minimodem_simple\minimodem_simple_receive", "Ptr", recvBuf, "Int", recvBuf.Size, "Int")

    if (bytesReceived > 0) {
        message := StrGet(recvBuf, bytesReceived, "UTF-8")
        LogMessage("RECV_RAW", "Bytes: " . bytesReceived . " | Raw: " . TruncateForLog(message))

        try {
            chunkDict := Jxon_Load(&message)

            ; Handle retransmission request from backend
            if (chunkDict.Has("fn") && chunkDict["fn"] == "retx") {
                HandleRetransmissionRequest(chunkDict)
                return
            }

            ; Get ci/cc
            ci := chunkDict.Has("ci") ? chunkDict["ci"] : 0
            cc := chunkDict.Has("cc") ? chunkDict["cc"] : 0

            ; Single message (no chunking)
            if (cc == 0) {
                completeMsg := Map()
                for key, val in chunkDict {
                    if (key != "ci" && key != "cc") {
                        completeMsg[key] := val
                    }
                }
                HandleCompleteMessage(completeMsg)
                return
            }

            ; Chunked message - buffer the chunk
            msgID := chunkDict.Has("id") ? chunkDict["id"] : ""

            if (!chunkReceiveBuffer.Has(msgID)) {
                chunkReceiveBuffer[msgID] := Map(
                    "chunks", Map(),
                    "cc", cc,
                    "meta", Map(),
                    "timestamp", A_TickCount
                )
            }

            buf := chunkReceiveBuffer[msgID]
            buf["chunks"][ci] := chunkDict.Has("ct") ? chunkDict["ct"] : ""

            ; Store metadata from first chunk
            if (ci == 0) {
                for key, val in chunkDict {
                    if (key != "id" && key != "ci" && key != "cc" && key != "ct") {
                        buf["meta"][key] := val
                    }
                }
            }

            LogMessage("CHUNK_RECV", "ID: " . msgID . " | Chunk " . (ci + 1) . "/" . cc
                . " | Have " . buf["chunks"].Count . "/" . cc)

            ; Check if all chunks received
            if (buf["chunks"].Count == cc) {
                completeMsg := ReassembleChunks(msgID)
                if (completeMsg) {
                    HandleCompleteMessage(completeMsg)
                }
            }

        } catch as e {
            LogMessage("RECV_FAIL", "Error: " . e.Message . " | Raw: " . TruncateForLog(StrGet(recvBuf, bytesReceived, "UTF-8")))
        }
    }

    ; Periodically check for chunk reassembly timeouts
    CheckChunkTimeouts()
}

Cleanup() {
    global isInitialized

    SetTimer(PollReceive, 0)  ; Stop the timer

    if (isInitialized) {
        DllCall("minimodem_simple\minimodem_simple_cleanup")
        isInitialized := false
    }

    UnloadMinimodemDll()
}

; ==================== Hotkeys ====================

; Press Escape to exit
Esc::
{
    Cleanup()
    ExitApp()
}

; Handle app exit
OnExit(ExitFunc)

ExitFunc(ExitReason, ExitCode) {
    LogMessage("SESSION", "Application closing - Reason: " . ExitReason)
    Cleanup()
}
