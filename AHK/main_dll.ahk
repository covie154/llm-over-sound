; AHK V2 Script - ggwave Direct DLL Integration
; This script uses the ggwave_simple.dll wrapper for clean audio communication
#Requires AutoHotkey v2.0
#Include "include/_JXON.ahk"

; ==================== Global Variables ====================
global ggwaveDll := ""
global selectedSpeakerIndex := 0
global selectedMicrophoneIndex := 0
global isInitialized := false
global messageCounter := 0  ; For additional uniqueness

; ==================== Compression Configuration ====================
global COMPRESSION_THRESHOLD := 100  ; Only compress messages longer than this (in characters)
global COMPRESSION_ENGINE := 2       ; COMPRESSION_FORMAT_LZNT1=2, COMPRESSION_FORMAT_XPRESS=3, COMPRESSION_FORMAT_XPRESS_HUFF=4

; ==================== Logging Configuration ====================
global LOG_ENABLED := true                              ; Enable/disable logging
global LOG_FILE := A_ScriptDir . "\ggwave_log.txt"     ; Log file path
global LOG_MAX_CONTENT_LENGTH := 500                    ; Max content length to log (truncate longer messages)

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
        
        ; Prepare message content (compress if over threshold)
        messageContent := result.text
        isCompressed := false
        
        if (StrLen(messageContent) > COMPRESSION_THRESHOLD) {
            ; Try to compress
            compressed := CompressString(messageContent)
            if (compressed != "" && StrLen(compressed) < StrLen(messageContent)) {
                messageContent := compressed
                isCompressed := true
            }
        }
        
        ; Build JSON message
        sendJSON := Map(
            "id", msgID,
            "fn", "test"
        )
        
        if (isCompressed) {
            sendJSON["z"] := 1  ; Compression flag
        }
        sendJSON["ct"] := messageContent
        
        ; Send the message
        jsonStr := Jxon_Dump(sendJSON)
        SendMessage(jsonStr, msgID, isCompressed, StrLen(result.text), StrLen(jsonStr))
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

SendMessage(message, msgID := "", isCompressed := false, originalSize := 0, compressedSize := 0) {
    ; Send message via audio (volume 50 is a good default)
    result := DllCall("ggwave_simple\ggwave_simple_send",
        "AStr", message,
        "Int", 50,  ; Volume (1-100)
        "Int")
    
    if (result < 0) {
        errorMsg := GetGGWaveError()
        LogMessage("SEND_FAIL", "ID: " . msgID . " | Error: " . errorMsg)
        MsgBox("Failed to send message: " . errorMsg, "Error", "Icon!")
        return false
    }
    
    ; Log the send attempt
    compressionInfo := isCompressed ? " | Compressed: " . originalSize . "->" . compressedSize . " bytes" : ""
    LogMessage("SEND_START", "ID: " . msgID . compressionInfo . " | Content: " . TruncateForLog(message))
    
    ; Show transmitting indicator with ID and compression info
    displayMsg := msgID != "" ? "[" . msgID . "] " : ""
    if (isCompressed && originalSize > 0) {
        ratio := Round((1 - compressedSize / originalSize) * 100)
        displayMsg .= "Transmitting (compressed " . ratio . "% smaller)..."
    } else {
        displayMsg .= "Transmitting..."
    }
    ToolTip(displayMsg)
    
    ; Wait for transmission to complete
    while (DllCall("ggwave_simple\ggwave_simple_is_transmitting", "Int")) {
        Sleep(50)
    }
    
    ToolTip()  ; Clear tooltip
    LogMessage("SEND_OK", "ID: " . msgID . " | Transmission complete")
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
        
        ; Log raw received data
        LogMessage("RECV_RAW", "Bytes: " . received . " | Raw: " . TruncateForLog(message))
        
        ; Parse JSON and extract ID if present
        try {
            receivedJSON := Jxon_Load(&message)
            msgID := receivedJSON.Has("id") ? receivedJSON["id"] : "[no-id]"
            content := receivedJSON.Has("ct") ? receivedJSON["ct"] : message
            isCompressed := receivedJSON.Has("z") && receivedJSON["z"] = 1
            
            ; Decompress if needed
            if (isCompressed) {
                decompressed := DecompressString(content)
                if (decompressed != "") {
                    content := decompressed
                    LogMessage("RECV_OK", "ID: " . msgID . " | Decompressed | Content: " . TruncateForLog(content))
                } else {
                    content := "[Decompression failed] " . content
                    LogMessage("RECV_FAIL", "ID: " . msgID . " | Decompression failed")
                }
            } else {
                LogMessage("RECV_OK", "ID: " . msgID . " | Content: " . TruncateForLog(content))
            }
            
            ; Show received message with ID
            compressionNote := isCompressed ? " (was compressed)" : ""
            MsgBox("Message ID: " . msgID . compressionNote . "`n`nContent:`n" . content, "ggwave - Message Received", "Iconi")
        } catch as e {
            ; Fallback if not valid JSON
            LogMessage("RECV_FAIL", "JSON parse error: " . e.Message . " | Raw: " . TruncateForLog(message))
            MsgBox("Received message:`n`n" . message . "`n`nParse error: " . e.Message, "ggwave - Message Received", "Iconi")
        }
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

; ==================== Logging Functions ====================

InitializeLog() {
    global LOG_ENABLED, LOG_FILE
    
    if (!LOG_ENABLED) {
        return
    }
    
    ; Create or append to log file with session separator
    try {
        separator := "`n" . "=" . "=".Repeat(78) . "`n"
        header := separator . "ggwave Session Started: " . FormatTime(, "yyyy-MM-dd HH:mm:ss") . separator
        FileAppend(header, LOG_FILE, "UTF-8")
    }
}

LogMessage(logType, content) {
    global LOG_ENABLED, LOG_FILE
    
    if (!LOG_ENABLED) {
        return
    }
    
    try {
        timestamp := FormatTime(, "yyyy-MM-dd HH:mm:ss." . A_MSec)
        logLine := "[" . timestamp . "] [" . logType . "] " . content . "`n"
        FileAppend(logLine, LOG_FILE, "UTF-8")
    }
}

TruncateForLog(text) {
    global LOG_MAX_CONTENT_LENGTH
    
    ; Replace newlines with \n for single-line logging
    text := StrReplace(text, "`r`n", "\n")
    text := StrReplace(text, "`n", "\n")
    text := StrReplace(text, "`r", "\n")
    
    if (StrLen(text) > LOG_MAX_CONTENT_LENGTH) {
        return SubStr(text, 1, LOG_MAX_CONTENT_LENGTH) . "... [truncated, " . StrLen(text) . " total chars]"
    }
    return text
}

; ==================== Compression Functions (Windows NTDLL API) ====================

CompressString(str) {
    global COMPRESSION_ENGINE
    
    ; Convert string to UTF-8 bytes
    utf8Size := StrPut(str, "UTF-8") - 1  ; Exclude null terminator
    if (utf8Size <= 0) {
        return ""
    }
    
    inputBuffer := Buffer(utf8Size, 0)
    StrPut(str, inputBuffer, "UTF-8")
    
    ; Allocate output buffer (worst case: same size + overhead)
    outputSize := utf8Size + 256
    outputBuffer := Buffer(outputSize, 0)
    finalSize := Buffer(8, 0)  ; ULONG for final compressed size
    
    ; Get workspace size
    workspaceSize := Buffer(8, 0)
    fragmentWorkspaceSize := Buffer(8, 0)
    
    result := DllCall("ntdll\RtlGetCompressionWorkSpaceSize",
        "UShort", COMPRESSION_ENGINE,
        "Ptr", workspaceSize.Ptr,
        "Ptr", fragmentWorkspaceSize.Ptr,
        "UInt")
    
    if (result != 0) {
        return ""  ; Failed to get workspace size
    }
    
    ; Allocate workspace
    wsSize := NumGet(workspaceSize, 0, "UInt")
    workspace := Buffer(wsSize, 0)
    
    ; Compress the data
    result := DllCall("ntdll\RtlCompressBuffer",
        "UShort", COMPRESSION_ENGINE,
        "Ptr", inputBuffer.Ptr,
        "UInt", utf8Size,
        "Ptr", outputBuffer.Ptr,
        "UInt", outputSize,
        "UInt", 4096,  ; Chunk size
        "Ptr", finalSize.Ptr,
        "Ptr", workspace.Ptr,
        "UInt")
    
    if (result != 0) {
        return ""  ; Compression failed
    }
    
    compressedLen := NumGet(finalSize, 0, "UInt")
    
    ; Convert compressed bytes to Base64
    return Base64Encode(outputBuffer, compressedLen)
}

DecompressString(base64Str) {
    global COMPRESSION_ENGINE
    
    ; Decode Base64 to bytes
    compressedBuffer := Base64Decode(base64Str)
    if (!compressedBuffer || compressedBuffer.Size = 0) {
        return ""
    }
    
    ; Allocate output buffer (decompressed could be much larger)
    ; Start with 4x the compressed size, expand if needed
    outputSize := compressedBuffer.Size * 8
    outputBuffer := Buffer(outputSize, 0)
    finalSize := Buffer(8, 0)
    
    ; Decompress the data
    result := DllCall("ntdll\RtlDecompressBuffer",
        "UShort", COMPRESSION_ENGINE,
        "Ptr", outputBuffer.Ptr,
        "UInt", outputSize,
        "Ptr", compressedBuffer.Ptr,
        "UInt", compressedBuffer.Size,
        "Ptr", finalSize.Ptr,
        "UInt")
    
    if (result != 0) {
        return ""  ; Decompression failed
    }
    
    decompressedLen := NumGet(finalSize, 0, "UInt")
    
    ; Convert UTF-8 bytes back to string
    return StrGet(outputBuffer, decompressedLen, "UTF-8")
}

; ==================== Base64 Functions (Windows Crypt32 API) ====================

Base64Encode(buffer, size) {
    ; First call to get required output size
    requiredSize := 0
    DllCall("Crypt32\CryptBinaryToStringW",
        "Ptr", buffer.Ptr,
        "UInt", size,
        "UInt", 0x40000001,  ; CRYPT_STRING_BASE64 | CRYPT_STRING_NOCRLF
        "Ptr", 0,
        "UInt*", &requiredSize,
        "Int")
    
    if (requiredSize <= 0) {
        return ""
    }
    
    ; Allocate output buffer (wide chars)
    outputBuffer := Buffer(requiredSize * 2, 0)
    
    ; Second call to actually encode
    result := DllCall("Crypt32\CryptBinaryToStringW",
        "Ptr", buffer.Ptr,
        "UInt", size,
        "UInt", 0x40000001,  ; CRYPT_STRING_BASE64 | CRYPT_STRING_NOCRLF
        "Ptr", outputBuffer.Ptr,
        "UInt*", &requiredSize,
        "Int")
    
    if (!result) {
        return ""
    }
    
    return StrGet(outputBuffer, "UTF-16")
}

Base64Decode(base64Str) {
    ; First call to get required output size
    requiredSize := 0
    DllCall("Crypt32\CryptStringToBinaryW",
        "Str", base64Str,
        "UInt", 0,
        "UInt", 0x00000001,  ; CRYPT_STRING_BASE64
        "Ptr", 0,
        "UInt*", &requiredSize,
        "Ptr", 0,
        "Ptr", 0,
        "Int")
    
    if (requiredSize <= 0) {
        return Buffer(0)
    }
    
    ; Allocate output buffer
    outputBuffer := Buffer(requiredSize, 0)
    
    ; Second call to actually decode
    result := DllCall("Crypt32\CryptStringToBinaryW",
        "Str", base64Str,
        "UInt", 0,
        "UInt", 0x00000001,  ; CRYPT_STRING_BASE64
        "Ptr", outputBuffer.Ptr,
        "UInt*", &requiredSize,
        "Ptr", 0,
        "Ptr", 0,
        "Int")
    
    if (!result) {
        return Buffer(0)
    }
    
    return outputBuffer
}

; ==================== Message ID Generation ====================

GenerateMessageID() {
    global messageCounter
    
    ; Combine timestamp (24 bits) + counter (8 bits) + random (8 bits)
    timestamp := A_TickCount & 0xFFFFFF           ; 24 bits (~4.6 hour cycle)
    messageCounter := (messageCounter + 1) & 0xFF ; 8 bits (0-255 cycle)
    randomPart := Random(0, 0xFF)                 ; 8 bits
    
    ; Combine into 40-bit value
    combined := (timestamp << 16) | (messageCounter << 8) | randomPart
    
    ; Encode to Base62
    return EncodeBase62(combined)
}

EncodeBase62(num) {
    ; Base62: 0-9, a-z, A-Z
    chars := "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    result := ""
    
    if (num == 0) {
        return "0000000"
    }
    
    while (num > 0) {
        result := SubStr(chars, Mod(num, 62) + 1, 1) . result
        num := num // 62
    }
    
    ; Pad to 7 characters for consistency
    while (StrLen(result) < 7) {
        result := "0" . result
    }
    
    return result
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
