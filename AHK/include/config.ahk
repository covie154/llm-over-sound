; ==================== Global Configuration ====================
; Shared constants and global variables for the minimodem AHK frontend.
#Requires AutoHotkey v2.0

; ==================== Global Variables ====================
global minimodemDll := ""
global selectedSpeakerIndex := 0
global selectedMicrophoneIndex := 0
global isInitialized := false
global messageCounter := 0  ; For additional uniqueness

; ==================== Compression Configuration ====================
global COMPRESSION_THRESHOLD := 100  ; Only compress messages longer than this (in characters)
global COMPRESSION_ENGINE := 2       ; COMPRESSION_FORMAT_LZNT1=2, COMPRESSION_FORMAT_XPRESS=3, COMPRESSION_FORMAT_XPRESS_HUFF=4

; ==================== Transport Configuration ====================
global BAUD_RATE := 1200              ; minimodem FSK baud rate (link parameter; both ends MUST match)

; ==================== Chunking Configuration ====================
; NOTE (Phase 7, v1): chunking is DORMANT. The active transport sends a single
; frame (ci=0, cc=1) with a CRC32 field. The constants below are retained for the
; dormant split/reassemble code path, reserved for v2 chunking.
global MODEM_PAYLOAD_LIMIT := 140    ; (dormant) Max bytes per minimodem transmission
global CHUNK_DATA_SIZE := 70          ; (dormant) Max base64 content chars per chunk
global INTER_CHUNK_DELAY := 200       ; (dormant) Milliseconds between chunk transmissions
global CHUNK_REASSEMBLY_TIMEOUT := 30000  ; (dormant) Milliseconds before requesting retransmission

; ==================== Chunk Buffers ====================
global chunkReceiveBuffer := Map()    ; {msgID: Map("chunks",Map(), "cc",N, "meta",Map(), "timestamp",tick)}
global lastSentChunks := Map()        ; {msgID: [chunkJson1, chunkJson2, ...]}

; ==================== Logging Configuration ====================
global LOG_ENABLED := true                              ; Enable/disable logging
global LOG_FILE := A_ScriptDir . "\minimodem_log.txt"   ; Log file path
global LOG_MAX_CONTENT_LENGTH := 500                    ; Max content length to log (truncate longer messages)
