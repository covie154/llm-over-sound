; AHK V2 Script - ggwave Direct DLL Integration
; This script uses the ggwave_simple.dll wrapper for clean audio communication
#Requires AutoHotkey v2.0
#Include "include/_JXON.ahk"

; ==================== Global Variables ====================
global ggwaveDll := ""
global selectedSpeakerIndex := 0
global selectedMicrophoneIndex := 0
global isInitialized := false

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

        sendJSON := Map(
            "fn", "test",
            "ct", result.text
        )
        
        ; Send the message
        SendMessage(Jxon_Dump(sendJSON))
    }
}

GetMultilineInput() {
    ; Create a GUI for multiline text input
    inputGui := Gui("+AlwaysOnTop +Resize +MinSize400x300", "ggwave - Send Message")
    inputGui.SetFont("s10")
    
    inputGui.AddText("xm", "Enter your message to send via audio:")
    inputGui.AddText("xm y+5 cGray", "(Supports multiple lines. Press Ctrl+Enter to send, or click Send)")
    
    ; Multiline edit control
    editCtrl := inputGui.AddEdit("xm y+10 w380 h200 vMessageText Multi WantReturn")
    
    ; Buttons
    sendBtn := inputGui.AddButton("xm y+10 w100 Default", "Send")
    cancelBtn := inputGui.AddButton("x+10 w100", "Cancel")
    
    ; Result object
    result := {cancelled: false, text: ""}
    
    ; Button handlers
    sendBtn.OnEvent("Click", OnSend)
    cancelBtn.OnEvent("Click", OnCancel)
    inputGui.OnEvent("Close", OnCancel)
    inputGui.OnEvent("Escape", OnCancel)
    
    ; Ctrl+Enter hotkey to send
    editCtrl.OnEvent("Change", (*) => "")  ; Placeholder to keep edit active
    
    OnSend(*) {
        result.text := editCtrl.Value
        result.cancelled := false
        inputGui.Destroy()
    }
    
    OnCancel(*) {
        result.cancelled := true
        inputGui.Destroy()
        Cleanup()
        ExitApp()
    }
    
    inputGui.Show("w400 h300")
    
    ; Handle Ctrl+Enter to send (after Show creates the window)
    HotIfWinActive("ahk_id " . inputGui.Hwnd)
    Hotkey("^Enter", (*) => sendBtn.OnEvent("Click", OnSend) || OnSend())
    HotIfWinActive()
    
    ; Focus the edit control
    editCtrl.Focus()
    
    ; Wait for the GUI to close
    WinWaitClose(inputGui.Hwnd)
    
    ; Clean up hotkey
    ; HotIfWinActive("ahk_id " . inputGui.Hwnd)
    ; Hotkey("^Enter", "Off")
    ; HotIfWinActive()
    
    return result
}

; ==================== ggwave Functions ====================

SendMessage(message) {
    ; Send message via audio (volume 50 is a good default)
    result := DllCall("ggwave_simple\ggwave_simple_send",
        "AStr", message,
        "Int", 50,  ; Volume (1-100)
        "Int")
    
    if (result < 0) {
        errorMsg := GetGGWaveError()
        MsgBox("Failed to send message: " . errorMsg, "Error", "Icon!")
        return false
    }
    
    ; Show transmitting indicator
    ToolTip("Transmitting: " . message)
    
    ; Wait for transmission to complete
    while (DllCall("ggwave_simple\ggwave_simple_is_transmitting", "Int")) {
        Sleep(50)
    }
    
    ToolTip()  ; Clear tooltip
    return true
}

ProcessAudio() {
    ; This function is called periodically by a timer
    ; It processes incoming audio and checks for received messages
    
    if (!isInitialized) {
        return
    }
    
    ; Process audio buffers
    DllCall("ggwave_simple\ggwave_simple_process", "Int")
    
    ; Check for received message
    buffer_msg := Buffer(512, 0)
    received := DllCall("ggwave_simple\ggwave_simple_receive",
        "Ptr", buffer_msg.Ptr,
        "Int", 512,
        "Int")
    
    if (received > 0) {
        message := StrGet(buffer_msg, received, "UTF-8")
        
        ; Show received message
        ; ==============================
        ; TEMPORARY PLACEHOLDER
        ; =============================
        MsgBox("Received message:`n`n" . message, "ggwave - Message Received", "Iconi")
    }
}

GetGGWaveError() {
    errorPtr := DllCall("ggwave_simple\ggwave_simple_get_error", "Ptr")
    if (errorPtr) {
        return StrGet(errorPtr, "UTF-8")
    }
    return "Unknown error"
}

; ==================== DLL Management ====================

LoadGGWaveDll() {
    global ggwaveDll
    
    ; Try to load from script directory first
    dllPath := A_ScriptDir . "\ggwave_simple.dll"
    
    ggwaveDll := DllCall("LoadLibrary", "Str", dllPath, "Ptr")
    
    if (!ggwaveDll) {
        ; Try current directory
        ggwaveDll := DllCall("LoadLibrary", "Str", "ggwave_simple.dll", "Ptr")
    }
    
    return ggwaveDll != 0
}

UnloadGGWaveDll() {
    global ggwaveDll
    
    if (ggwaveDll) {
        DllCall("FreeLibrary", "Ptr", ggwaveDll)
        ggwaveDll := ""
    }
}

; ==================== Audio Device Selection ====================

SelectAudioDevices() {
    global selectedSpeakerIndex, selectedMicrophoneIndex
    
    ; Get device counts
    playbackCount := DllCall("ggwave_simple\ggwave_simple_get_playback_device_count", "Int")
    captureCount := DllCall("ggwave_simple\ggwave_simple_get_capture_device_count", "Int")
    
    if (playbackCount <= 0) {
        MsgBox("No playback devices found!", "Error", "Icon!")
        return false
    }
    
    if (captureCount <= 0) {
        MsgBox("No capture devices found!", "Error", "Icon!")
        return false
    }
    
    ; Get device names
    speakerNames := []
    Loop playbackCount {
        namePtr := DllCall("ggwave_simple\ggwave_simple_get_playback_device_name", 
            "Int", A_Index - 1, 
            "Ptr")
        if (namePtr) {
            speakerNames.Push(StrGet(namePtr, "UTF-8"))
        }
    }
    
    micNames := []
    Loop captureCount {
        namePtr := DllCall("ggwave_simple\ggwave_simple_get_capture_device_name", 
            "Int", A_Index - 1, 
            "Ptr")
        if (namePtr) {
            micNames.Push(StrGet(namePtr, "UTF-8"))
        }
    }
    
    ; Create the selection GUI
    deviceGui := Gui("+AlwaysOnTop", "Select Audio Devices")
    deviceGui.SetFont("s10")
    
    ; Speaker selection
    deviceGui.AddText("xm", "Select Speaker (Output):")
    speakerList := deviceGui.AddListBox("xm w400 h120 vSpeakerChoice", speakerNames)
    speakerList.Choose(1)
    
    ; Microphone selection
    deviceGui.AddText("xm y+15", "Select Microphone (Input):")
    micList := deviceGui.AddListBox("xm w400 h120 vMicrophoneChoice", micNames)
    micList.Choose(1)
    
    ; Protocol selection
    deviceGui.AddText("xm y+15", "Select Protocol:")
    protocols := ["Audible Normal", "Audible Fast", "Audible Fastest", 
                  "Ultrasound Normal", "Ultrasound Fast", "Ultrasound Fastest"]
    protocolList := deviceGui.AddDropDownList("xm w400 vProtocolChoice Choose2", protocols)
    
    ; Buttons
    deviceGui.AddButton("xm y+20 w100", "OK").OnEvent("Click", OnOK)
    deviceGui.AddButton("x+20 w100", "Cancel").OnEvent("Click", OnCancel)
    
    dialogResult := false
    
    OnOK(*) {
        dialogResult := true
        selectedSpeakerIndex := speakerList.Value - 1
        selectedMicrophoneIndex := micList.Value - 1
        deviceGui.Destroy()
    }
    
    OnCancel(*) {
        dialogResult := false
        deviceGui.Destroy()
    }
    
    deviceGui.OnEvent("Close", OnCancel)
    deviceGui.Show()
    
    WinWaitClose(deviceGui.Hwnd)
    
    return dialogResult
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
    Cleanup()
}
