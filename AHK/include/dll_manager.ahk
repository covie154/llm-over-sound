; ==================== DLL Management ====================
; Loading, unloading, and error retrieval for minimodem_simple.dll.
#Requires AutoHotkey v2.0

LoadMinimodemDll() {
    global minimodemDll

    ; Try to load from script directory first
    dllPath := A_ScriptDir . "\minimodem_simple.dll"

    minimodemDll := DllCall("LoadLibrary", "Str", dllPath, "Ptr")

    if (!minimodemDll) {
        ; Try current directory
        minimodemDll := DllCall("LoadLibrary", "Str", "minimodem_simple.dll", "Ptr")
    }

    return minimodemDll != 0
}

UnloadMinimodemDll() {
    global minimodemDll

    if (minimodemDll) {
        DllCall("FreeLibrary", "Ptr", minimodemDll)
        minimodemDll := ""
    }
}

GetMinimodemError() {
    errorPtr := DllCall("minimodem_simple\minimodem_simple_get_error", "Ptr")
    if (errorPtr) {
        return StrGet(errorPtr, "UTF-8")
    }
    return "Unknown error"
}
