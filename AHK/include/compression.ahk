; ==================== Compression Functions (Windows NTDLL API) ====================
; LZNT1 compression/decompression and Base64 encoding/decoding via Windows APIs.
#Requires AutoHotkey v2.0

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
