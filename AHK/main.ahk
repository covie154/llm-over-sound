; AHK V2 Script - STDIO Communication with Backend
#Requires AutoHotkey v2.0

; Global variables
global shellProcess := ""  ; Single process handles both TX and RX
global audioDevices := Map()
global selectedSpeakerIndex := 0
global selectedMicrophoneIndex := 0

; Main entry point
Main()

Main() {
    global shellProcess, selectedSpeakerIndex, selectedMicrophoneIndex
    
    ; First, show audio device selection dialog
    if (!SelectAudioDevices()) {
        ExitApp()  ; User cancelled device selection
    }
    
    ; Start the ggwave-cli backend process (handles both TX and RX)
    try {
        shellProcess := StartBackendTransmitter()
    } catch as e {
        MsgBox("Failed to start backend: " . e.Message, "Error", "Icon!")
        ExitApp()
    }
    
    ; Main loop - keep asking for input
    Loop {
        ; Get input from user
        result := InputBox("Enter your message (Cancel to exit):`n`nNote: The same process handles sending AND receiving.", "Send to Backend")
        
        ; Check if user cancelled
        if (result.Result != "OK") {
            break
        }
        
        ; Skip empty input
        if (result.Value = "") {
            MsgBox("Please enter a message.", "Warning", "Icon!")
            continue
        }
        
        ; Send to backend
        try {
            responseFromTx := SendToBackend(shellProcess, result.Value)
            MsgBox("Transmission started:`n" . responseFromTx . "`n`nNow listening for received audio...", "Transmitting", "Iconi")
            
            ; Listen for received message (from another device)
            responseFromRx := ListenToBackend(shellProcess)
            MsgBox("Received from audio:`n`n" . responseFromRx, "Received Message", "Iconi")
        } catch as e {
            MsgBox("Error: " . e.Message, "Error", "Icon!")
        }
    }
    
    ; Cleanup
    CloseBackend(shellProcess)
    ExitApp()
}

; ==================== Audio Device Selection ====================

SelectAudioDevices() {
    global selectedSpeakerIndex, selectedMicrophoneIndex, audioDevices
    
    ; Enumerate audio devices using SDL2
    if (!EnumerateAudioDevices()) {
        return false
    }
    
    ; Get device lists from global map
    playbackDevices := audioDevices["playback"]
    captureDevices := audioDevices["capture"]
    
    if (playbackDevices.Length = 0) {
        MsgBox("No speaker devices found!", "Error", "Icon!")
        return false
    }
    
    if (captureDevices.Length = 0) {
        MsgBox("No microphone devices found!", "Error", "Icon!")
        return false
    }
    
    ; Extract device names for ListBox
    speakerNames := []
    for device in playbackDevices {
        speakerNames.Push(device.name)
    }
    
    micNames := []
    for device in captureDevices {
        micNames.Push(device.name)
    }
    
    ; Create the selection GUI
    deviceGui := Gui("+AlwaysOnTop", "Select Audio Devices")
    deviceGui.SetFont("s10")
    
    ; Speaker selection
    deviceGui.AddText("xm", "Select Speaker (Output):")
    speakerList := deviceGui.AddListBox("xm w400 h120 vSpeakerChoice", speakerNames)
    speakerList.Choose(1)  ; Select first item by default
    
    ; Microphone selection
    deviceGui.AddText("xm y+15", "Select Microphone (Input):")
    micList := deviceGui.AddListBox("xm w400 h120 vMicrophoneChoice", micNames)
    micList.Choose(1)  ; Select first item by default
    
    ; Buttons
    deviceGui.AddButton("xm y+20 w100", "OK").OnEvent("Click", OnOK)
    deviceGui.AddButton("x+20 w100", "Cancel").OnEvent("Click", OnCancel)
    
    ; Variables to track result
    dialogResult := false
    
    OnOK(*) {
        dialogResult := true
        ; Get 0-based index (ListBox returns 1-based, SDL uses 0-based)
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
    
    ; Wait for the GUI to close
    WinWaitClose(deviceGui.Hwnd)
    
    return dialogResult
}

; =================== Audio Device Enumeration ====================

EnumerateAudioDevices() {
    global audioDevices
    
    ; First we need to get all the audio devices on the system for the user to choose which one to use
    ; Use SDL2 to enumerate audio devices since ggwave uses it internally
    
    ; Load SDL2.dll
    SDL2 := DllCall("LoadLibrary", "Str", "SDL2.dll", "Ptr")
    if !SDL2 {
        MsgBox("Failed to load SDL2.dll")
        return false
    }
    
    ; Initialize SDL Audio subsystem
    SDL_INIT_AUDIO := 0x00000010
    result := DllCall("SDL2\SDL_Init", "UInt", SDL_INIT_AUDIO, "Int")
    if (result < 0) {
        DllCall("FreeLibrary", "Ptr", SDL2)
        MsgBox("Failed to initialize SDL")
        return false
    }
    
    ; Helper function to get devices by type
    GetDeviceList(isCapture) {
        devices := []
        
        ; Get device count
        count := DllCall("SDL2\SDL_GetNumAudioDevices", "Int", isCapture, "Int")
        
        if (count < 0) {
            return devices  ; No explicit list available
        }
        
        ; Enumerate devices
        Loop count {
            index := A_Index - 1  ; SDL uses 0-based index
            
            ; Get device name (returns pointer to UTF-8 string)
            namePtr := DllCall("SDL2\SDL_GetAudioDeviceName", 
                            "Int", index, 
                            "Int", isCapture, 
                            "Ptr")
            
            if (namePtr) {
                ; Convert UTF-8 string to AHK string
                deviceName := StrGet(namePtr, "UTF-8")
                devices.Push({index: index, name: deviceName})
            }
        }
        
        return devices
    }
    
    ; Get all playback devices (isCapture = 0)
    playbackDevices := GetDeviceList(0)
    OutputDebug("Found " playbackDevices.Length " playback devices:`n")
    for device in playbackDevices {
        OutputDebug("  - Playback device #" device.index ": '" device.name "'`n")
    }
    
    ; Get all capture devices (isCapture = 1)
    captureDevices := GetDeviceList(1)
    OutputDebug("Found " captureDevices.Length " capture devices:`n")
    for device in captureDevices {
        OutputDebug("  - Capture device #" device.index ": '" device.name "'`n")
    }
    
    ; Store in global map
    audioDevices["playback"] := playbackDevices
    audioDevices["capture"] := captureDevices
    
    ; Cleanup SDL
    DllCall("SDL2\SDL_Quit")
    DllCall("FreeLibrary", "Ptr", SDL2)
    
    return true
}

; ==================== ggwave Backend Communication ====================

; NOTE: ggwave-cli and ggwave-tx-rx both handle TX and RX in one process.
; ggwave-rx does NOT print received messages - it's incomplete for STDIO use.
; We use ggwave-cli which outputs "Received text: <message>" when it receives data.

StartBackendTransmitter() {
    global selectedMicrophoneIndex, selectedSpeakerIndex
    
    ; Create a shell object to run the backend
    shell := ComObject("WScript.Shell")
    
    ; Get the script directory
    scriptDir := A_ScriptDir
    
    ; Start ggwave-cli which handles both TX and RX
    ; It will print "Received text: <message>" when it receives audio data
    process := shell.Exec('ggwave-cli -c' . selectedMicrophoneIndex . ' -p' . selectedSpeakerIndex)
    
    ; Give the process a moment to start and print initial output
    Sleep(1000)
    
    ; Check if process started successfully
    if (process.Status != 0) {
        throw Error("Backend process failed to start")
    }
    
    ; Consume initial output (device info, protocol list, etc.)
    ; This prevents the initial messages from being read as "responses"
    ConsumeInitialOutput(process)
    
    return process
}

ConsumeInitialOutput(process) {
    ; Read and discard initial output until we see "Enter text:"
    ; This clears the buffer of startup messages
    startTime := A_TickCount
    timeout := 5000
    
    while (A_TickCount - startTime < timeout) {
        if (!process.StdOut.AtEndOfStream) {
            line := process.StdOut.ReadLine()
            OutputDebug("Init: " . line . "`n")
            ; Look for the prompt that indicates ready state
            if (InStr(line, "Enter text:")) {
                break
            }
        }
        Sleep(10)
    }
}

; NOTE: StartBackendReceiver is no longer needed since ggwave-cli handles both TX and RX.
; The ggwave-rx utility does NOT print received messages to stdout, making it unsuitable
; for STDIO-based communication. Use ggwave-cli instead.

ListenToBackend(process) {
    ; ggwave-cli outputs received messages in format: "Received text: <message>"
    ; We need to look for this pattern in the output
    response := ""
    startTime := A_TickCount
    timeout := 15000  ; 15 second timeout for receiving audio
    
    while (A_TickCount - startTime < timeout) {
        if (!process.StdOut.AtEndOfStream) {
            line := process.StdOut.ReadLine()
            OutputDebug("RX: " . line . "`n")
            
            ; Check if this line contains the received text
            if (InStr(line, "Received text:")) {
                ; Extract the message after "Received text: "
                response := SubStr(line, InStr(line, "Received text:") + 15)
                response := Trim(response)
                break
            }
            ; Also check for "Received data" which precedes the text
            if (InStr(line, "Received data")) {
                ; Continue reading, the actual text comes next
                continue
            }
        }
        Sleep(10)
    }
    
    if (response = "") {
        throw Error("Timeout waiting for backend response")
    }
    
    return response
}

SendToBackend(process, message) {
    ; Write message to stdin
    ; ggwave-cli will respond with "Sending ..." and then transmit the audio
    process.StdIn.WriteLine(message)
    
    ; Give it a moment to process
    Sleep(100)
    
    ; Consume the "Sending ..." response and any other output until we see "Enter text:" again
    startTime := A_TickCount
    timeout := 10000  ; 10 second timeout
    
    while (A_TickCount - startTime < timeout) {
        if (!process.StdOut.AtEndOfStream) {
            line := process.StdOut.ReadLine()
            OutputDebug("TX: " . line . "`n")
            
            ; If we see the prompt again, transmission is complete
            if (InStr(line, "Enter text:")) {
                return "Sent: " . message
            }
            ; If we see "Sending", transmission started
            if (InStr(line, "Sending")) {
                continue
            }
        }
        Sleep(10)
    }
    
    ; Return success even if we didn't get the prompt back
    ; (the audio transmission takes time)
    return "Sent: " . message
}

CloseBackend(process) {
    try {
        ; Send exit command to gracefully close the backend
        process.StdIn.Write(Chr(3))  ; Send Ctrl+C (SIGINT)
        Sleep(200)
        
        ; Terminate if still running
        if (process.Status = 0) {
            process.Terminate()
        }
    }
}

; Hotkey to exit the application
Esc::ExitApp()