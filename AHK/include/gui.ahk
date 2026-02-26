; ==================== GUI Dialogs ====================
; Audio device selection and multiline input dialogs.
#Requires AutoHotkey v2.0

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
    
    return result
}
