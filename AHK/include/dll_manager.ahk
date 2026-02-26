; ==================== DLL Management ====================
; Loading, unloading, and error retrieval for ggwave_simple.dll.
#Requires AutoHotkey v2.0

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

GetGGWaveError() {
    errorPtr := DllCall("ggwave_simple\ggwave_simple_get_error", "Ptr")
    if (errorPtr) {
        return StrGet(errorPtr, "UTF-8")
    }
    return "Unknown error"
}
