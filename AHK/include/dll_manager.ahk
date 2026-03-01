; ==================== DLL Management ====================
; Loading, unloading, and error retrieval for minimodem_simple.dll.
#Requires AutoHotkey v2.0

global minimodemDll := 0

LoadMinimodemDll() {
    global minimodemDll
    dllPath := A_ScriptDir "\minimodem_simple.dll"

    if !FileExist(dllPath) {
        MsgBox("DLL not found: " dllPath)
        ExitApp
    }

    minimodemDll := DllCall("LoadLibrary", "Str", dllPath, "Ptr")
    if !minimodemDll {
        MsgBox("Failed to load DLL: " dllPath)
        ExitApp
    }
}

UnloadMinimodemDll() {
    global minimodemDll
    if minimodemDll {
        DllCall("FreeLibrary", "Ptr", minimodemDll)
        minimodemDll := 0
    }
}

GetMinimodemError() {
    return StrGet(DllCall("minimodem_simple\minimodem_simple_get_error", "Ptr"), "UTF-8")
}
