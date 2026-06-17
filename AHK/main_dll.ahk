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

Main() {
    global selectedSpeakerIndex, selectedMicrophoneIndex, isInitialized, BAUD_RATE

    ; Load the DLL
    if (!LoadMinimodemDll()) {
        MsgBox("Failed to load minimodem_simple.dll`n`nMake sure the DLL is in the same folder as this script.", "Error", "Icon!")
        ExitApp()
    }

    ; Show audio device selection dialog
    if (!SelectAudioDevices()) {
        UnloadMinimodemDll()
        ExitApp()
    }

    ; Initialize minimodem with selected devices.
    ; The old ggwave protocol-id parameter is now the FSK baud rate (link
    ; parameter; both ends MUST match — see BAUD_RATE in config.ahk).
    result := DllCall("minimodem_simple\minimodem_simple_init",
        "Int", selectedSpeakerIndex,
        "Int", selectedMicrophoneIndex,
        "Int", BAUD_RATE,  ; FSK baud rate
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
    LogMessage("SESSION", "Application started - Speaker: " . selectedSpeakerIndex . ", Mic: " . selectedMicrophoneIndex . ", Baud: " . BAUD_RATE)
    
    ; Start the receive monitoring timer
    SetTimer(ProcessAudio, 10)  ; Process audio every 10ms
    
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

Cleanup() {
    global isInitialized
    
    SetTimer(ProcessAudio, 0)  ; Stop the timer
    
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
