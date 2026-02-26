; ==================== Global Configuration ====================
; Shared constants and global variables for the ggwave AHK frontend.
#Requires AutoHotkey v2.0

; ==================== Global Variables ====================
global ggwaveDll := ""
global selectedSpeakerIndex := 0
global selectedMicrophoneIndex := 0
global isInitialized := false
global messageCounter := 0  ; For additional uniqueness

; ==================== Compression Configuration ====================
global COMPRESSION_THRESHOLD := 100  ; Only compress messages longer than this (in characters)
global COMPRESSION_ENGINE := 2       ; COMPRESSION_FORMAT_LZNT1=2, COMPRESSION_FORMAT_XPRESS=3, COMPRESSION_FORMAT_XPRESS_HUFF=4

; ==================== Chunking Configuration ====================
global GGWAVE_PAYLOAD_LIMIT := 140   ; Max bytes per ggwave transmission
global CHUNK_DATA_SIZE := 70          ; Max base64 content chars per chunk
global INTER_CHUNK_DELAY := 200       ; Milliseconds between chunk transmissions
global CHUNK_REASSEMBLY_TIMEOUT := 30000  ; Milliseconds before requesting retransmission

; ==================== Chunk Buffers ====================
global chunkReceiveBuffer := Map()    ; {msgID: Map("chunks",Map(), "cc",N, "meta",Map(), "timestamp",tick)}
global lastSentChunks := Map()        ; {msgID: [chunkJson1, chunkJson2, ...]}

; ==================== Logging Configuration ====================
global LOG_ENABLED := true                              ; Enable/disable logging
global LOG_FILE := A_ScriptDir . "\ggwave_log.txt"     ; Log file path
global LOG_MAX_CONTENT_LENGTH := 500                    ; Max content length to log (truncate longer messages)
