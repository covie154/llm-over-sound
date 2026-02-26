; AHK V2 Script — ggwave Direct DLL Integration
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
    global selectedSpeakerIndex, selectedMicrophoneIndex, isInitialized
    
    ; Load the DLL
    if (!LoadGGWaveDll()) {
        MsgBox("Failed to load ggwave_simple.dll`n`nMake sure the DLL is in the same folder as this script.", "Error", "Icon!")
        ExitApp()
    }
    
    ; Show audio device selection dialog
    if (!SelectAudioDevices()) {
        UnloadGGWaveDll()
        ExitApp()
    }
    
    ; Initialize ggwave with selected devices
    ; Protocol 1 = AUDIBLE_FAST (good balance of speed and reliability)
    result := DllCall("ggwave_simple\ggwave_simple_init", 
        "Int", selectedSpeakerIndex,
        "Int", selectedMicrophoneIndex,
        "Int", 1,  ; Protocol: AUDIBLE_FAST
        "Int")
    
    if (result < 0) {
        errorMsg := GetGGWaveError()
        MsgBox("Failed to initialize ggwave: " . errorMsg, "Error", "Icon!")
        UnloadGGWaveDll()
        ExitApp()
    }
    
    isInitialized := true
    
    ; Initialize logging
    InitializeLog()
    LogMessage("SESSION", "Application started - Speaker: " . selectedSpeakerIndex . ", Mic: " . selectedMicrophoneIndex)
    
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
        DllCall("ggwave_simple\ggwave_simple_cleanup")
        isInitialized := false
    }
    
    UnloadGGWaveDll()
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
