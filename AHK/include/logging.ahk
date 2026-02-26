; ==================== Logging Functions ====================
; File-based logging for the ggwave AHK frontend.
#Requires AutoHotkey v2.0

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
