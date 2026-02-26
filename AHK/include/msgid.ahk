; ==================== Message ID Generation ====================
; Unique message ID generation using timestamp + counter + random, encoded as Base62.
#Requires AutoHotkey v2.0

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
