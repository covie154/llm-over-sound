; ==================== Chunking & Transport ====================
; Message chunking, reassembly, retransmission, and audio receive processing.
#Requires AutoHotkey v2.0

; ---------------------------------------------------------------------------
; Outbound: splitting a message dict into transmittable chunk JSON strings
; ---------------------------------------------------------------------------

ChunkMessage(msgDict) {
    ; Split a message dict into an Array of JSON strings for transmission.
    ; Short messages (content < COMPRESSION_THRESHOLD and JSON fits in payload)
    ; are sent as a single frame with ci=0, cc=0.
    ; Longer messages are LZNT1-compressed, base64-encoded, and split into chunks.
    global COMPRESSION_THRESHOLD, MAX_PAYLOAD_SIZE, CHUNK_DATA_SIZE

    msgID := msgDict.Has("id") ? msgDict["id"] : ""
    content := msgDict.Has("ct") ? msgDict["ct"] : ""

    ; Build single-frame version
    single := Map()
    for key, val in msgDict {
        single[key] := val
    }
    single["ci"] := 0
    single["cc"] := 0
    if (single.Has("z")) {
        single.Delete("z")
    }
    singleJson := Jxon_Dump(single)

    if (StrLen(content) < COMPRESSION_THRESHOLD && StrLen(singleJson) <= MAX_PAYLOAD_SIZE) {
        LogMessage("CHUNK", "ID: " . msgID . " | Single frame (" . StrLen(singleJson) . " bytes)")
        return [singleJson]
    }

    ; Compress content with LZNT1 + Base64
    encoded := CompressString(content)
    if (encoded == "") {
        ; Compression failed - fall back to single frame
        LogMessage("CHUNK_FAIL", "ID: " . msgID . " | Compression failed, sending single uncompressed")
        return [singleJson]
    }

    originalLen := StrLen(content)
    encodedLen := StrLen(encoded)
    LogMessage("CHUNK", "ID: " . msgID . " | Content: " . originalLen . " chars -> Base64: " . encodedLen . " chars")

    ; Collect metadata (everything except id, ct, ci, cc, z)
    meta := Map()
    for key, val in msgDict {
        if (key != "id" && key != "ct" && key != "ci" && key != "cc" && key != "z") {
            meta[key] := val
        }
    }

    ; Split encoded data into chunks
    dataChunks := []
    pos := 1
    while (pos <= encodedLen) {
        dataChunks.Push(SubStr(encoded, pos, CHUNK_DATA_SIZE))
        pos += CHUNK_DATA_SIZE
    }

    cc := dataChunks.Length
    result := []

    Loop cc {
        ci := A_Index - 1
        chunk := Map("id", msgID, "ci", ci, "cc", cc)

        ; First chunk carries metadata
        if (ci == 0) {
            for key, val in meta {
                chunk[key] := val
            }
        }

        chunk["ct"] := dataChunks[A_Index]
        result.Push(Jxon_Dump(chunk))
    }

    LogMessage("CHUNK", "ID: " . msgID . " | Split into " . cc . " chunks")
    return result
}

SendChunkedMessage(chunks, msgID) {
    ; Send an array of chunk JSON strings sequentially via the DLL.
    ; Stores chunks in lastSentChunks for retransmission.
    global lastSentChunks, INTER_CHUNK_DELAY

    lastSentChunks[msgID] := chunks
    totalChunks := chunks.Length

    ; Show transmitting indicator
    if (totalChunks > 1) {
        ToolTip("[" . msgID . "] Transmitting " . totalChunks . " chunks...")
    } else {
        ToolTip("[" . msgID . "] Transmitting...")
    }

    for i, chunkJson in chunks {
        ; Send chunk with newline delimiter for minimodem framing
        result := SendData(chunkJson . "`n")

        if (result < 0) {
            errorMsg := GetMinimodemError()
            LogMessage("SEND_FAIL", "ID: " . msgID . " | Chunk " . i . "/" . totalChunks . " | Error: " . errorMsg)
            ToolTip()
            MsgBox("Failed to send chunk " . i . "/" . totalChunks . ": " . errorMsg, "Error", "Icon!")
            return false
        }

        LogMessage("SEND", "ID: " . msgID . " | Chunk " . i . "/" . totalChunks . " | Content: " . TruncateForLog(chunkJson))

        if (totalChunks > 1) {
            ToolTip("[" . msgID . "] Transmitting chunk " . i . "/" . totalChunks . "...")
        }

        ; Wait for transmission to complete
        while (DllCall("minimodem_simple\minimodem_simple_is_transmitting", "Int")) {
            Sleep(50)
        }

        ; Inter-chunk delay (except after last chunk)
        if (i < totalChunks) {
            Sleep(INTER_CHUNK_DELAY)
        }
    }

    ToolTip()  ; Clear tooltip
    LogMessage("SEND_OK", "ID: " . msgID . " | All " . totalChunks . " chunk(s) sent")
    return true
}

; ---------------------------------------------------------------------------
; Inbound: message handling
; ---------------------------------------------------------------------------

HandleCompleteMessage(msgDict) {
    ; Display a fully reassembled (or single-frame) message to the user.
    msgID := msgDict.Has("id") ? msgDict["id"] : "[no-id]"
    content := msgDict.Has("ct") ? msgDict["ct"] : ""
    status := msgDict.Has("st") ? msgDict["st"] : ""

    LogMessage("RECV_OK", "ID: " . msgID . " | Content: " . TruncateForLog(content))
    MsgBox("Message ID: " . msgID . "`nStatus: " . status . "`n`nContent:`n" . content, "minimodem - Message Received", "Iconi")
}

; ---------------------------------------------------------------------------
; Reassembly
; ---------------------------------------------------------------------------

ReassembleChunks(msgID) {
    ; Reassemble a complete set of buffered chunks into the original message.
    ; Returns a Map on success or false on failure.
    global chunkReceiveBuffer

    if (!chunkReceiveBuffer.Has(msgID)) {
        return false
    }

    buf := chunkReceiveBuffer[msgID]
    cc := buf["cc"]

    ; Concatenate chunk data in ci order
    encoded := ""
    Loop cc {
        ci := A_Index - 1
        if (!buf["chunks"].Has(ci)) {
            LogMessage("REASSEMBLE_FAIL", "ID: " . msgID . " | Missing chunk " . ci)
            return false
        }
        encoded .= buf["chunks"][ci]
    }

    ; Decompress (Base64 decode + LZNT1 decompress)
    content := DecompressString(encoded)
    if (content == "") {
        LogMessage("REASSEMBLE_FAIL", "ID: " . msgID . " | Decompression failed")
        chunkReceiveBuffer.Delete(msgID)
        return false
    }

    ; Reconstruct complete message dict
    result := Map("id", msgID, "ct", content)
    for key, val in buf["meta"] {
        result[key] := val
    }

    LogMessage("REASSEMBLE", "ID: " . msgID . " | Reassembled " . cc . " chunks -> " . StrLen(content) . " chars")
    chunkReceiveBuffer.Delete(msgID)
    return result
}

; ---------------------------------------------------------------------------
; Timeout / retransmission
; ---------------------------------------------------------------------------

CheckChunkTimeouts() {
    ; Check for timed-out chunk reassemblies and request retransmission.
    global chunkReceiveBuffer, CHUNK_REASSEMBLY_TIMEOUT

    if (chunkReceiveBuffer.Count == 0) {
        return
    }

    now := A_TickCount
    toDelete := []

    for msgID, buf in chunkReceiveBuffer {
        elapsed := now - buf["timestamp"]
        if (elapsed > CHUNK_REASSEMBLY_TIMEOUT) {
            ; Find missing chunks
            missing := []
            Loop buf["cc"] {
                ci := A_Index - 1
                if (!buf["chunks"].Has(ci)) {
                    missing.Push(ci)
                }
            }

            if (missing.Length > 0) {
                SendRetransmissionRequest(msgID, missing)
                buf["timestamp"] := now  ; Reset timeout
            } else {
                toDelete.Push(msgID)
            }
        }
    }

    for _, msgID in toDelete {
        chunkReceiveBuffer.Delete(msgID)
    }
}

SendRetransmissionRequest(msgID, missingChunks) {
    ; Send a retransmission request for missing chunks.
    retxDict := Map(
        "id", msgID,
        "fn", "retx",
        "ci", missingChunks
    )

    retxJson := Jxon_Dump(retxDict)
    LogMessage("RETX_SEND", "ID: " . msgID . " | Requesting chunks: " . Jxon_Dump(missingChunks))

    result := SendData(retxJson . "`n")

    if (result < 0) {
        LogMessage("RETX_FAIL", "ID: " . msgID . " | Send failed: " . GetMinimodemError())
        return
    }

    ; Wait for transmission to complete
    while (DllCall("minimodem_simple\minimodem_simple_is_transmitting", "Int")) {
        Sleep(50)
    }
}

HandleRetransmissionRequest(retxDict) {
    ; Handle a retransmission request by resending the requested chunks.
    global lastSentChunks, INTER_CHUNK_DELAY

    msgID := retxDict.Has("id") ? retxDict["id"] : ""
    requested := retxDict.Has("ci") ? retxDict["ci"] : []

    if (!lastSentChunks.Has(msgID)) {
        LogMessage("RETX", "ID: " . msgID . " | No chunks in send buffer")
        return
    }

    chunks := lastSentChunks[msgID]

    for _, ci in requested {
        ; AHK arrays are 1-indexed, ci is 0-indexed
        idx := ci + 1
        if (idx >= 1 && idx <= chunks.Length) {
            LogMessage("RETX", "ID: " . msgID . " | Resending chunk " . ci)

            result := SendData(chunks[idx] . "`n")

            if (result < 0) {
                LogMessage("RETX_FAIL", "ID: " . msgID . " | Send failed: " . GetMinimodemError())
                continue
            }

            ; Wait for transmission to complete
            while (DllCall("minimodem_simple\minimodem_simple_is_transmitting", "Int")) {
                Sleep(50)
            }

            Sleep(INTER_CHUNK_DELAY)
        } else {
            LogMessage("RETX", "ID: " . msgID . " | Chunk " . ci . " out of range")
        }
    }
}
