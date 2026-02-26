"""
Message chunking, reassembly, and retransmission for the ggwave audio channel.
"""

import base64
import json
import time

import ggwave

from .config import (
    CHUNK_DATA_SIZE,
    CHUNK_REASSEMBLY_TIMEOUT,
    COMPRESSION_THRESHOLD,
    GGWAVE_PAYLOAD_LIMIT,
    INTER_CHUNK_DELAY,
    logger,
    truncate_for_log,
)
from .compression import lznt1_compress, lznt1_decompress

# ---------------------------------------------------------------------------
# Module-level buffers
# ---------------------------------------------------------------------------

# Incoming chunks: {msg_id: {"chunks": {ci: ct_data}, "cc": int, "meta": dict, "timestamp": float}}
chunk_receive_buffer: dict = {}

# Last sent chunks for retransmission: {msg_id: [json_str, ...]}
last_sent_chunks: dict = {}


# ---------------------------------------------------------------------------
# Outbound: splitting a message dict into transmittable chunk JSON strings
# ---------------------------------------------------------------------------

def chunk_message(msg_dict: dict) -> list[str]:
    """Split a message dict into chunk JSON strings for transmission.

    If the message content is < COMPRESSION_THRESHOLD chars and the full JSON
    fits in GGWAVE_PAYLOAD_LIMIT, sends as a single frame with ci=0, cc=0.

    Otherwise, compresses the ct field with LZNT1, base64-encodes it, and
    splits across multiple chunk frames.  First chunk (ci=0) carries metadata
    fields (fn, st, etc.); subsequent chunks carry only id/ci/cc/ct.
    """
    msg_id = msg_dict.get("id", "")
    content = msg_dict.get("ct", "")

    # Build single-frame version
    single = dict(msg_dict)
    single["ci"] = 0
    single["cc"] = 0
    single.pop("z", None)  # Remove legacy compression flag
    single_json = json.dumps(single, separators=(",", ":"))

    if len(content) < COMPRESSION_THRESHOLD and len(single_json) <= GGWAVE_PAYLOAD_LIMIT:
        logger.debug(f"[CHUNK] ID: {msg_id} | Single frame ({len(single_json)} bytes)")
        return [single_json]

    # Compress content with LZNT1 + base64
    content_bytes = content.encode("utf-8")
    compressed = lznt1_compress(content_bytes)
    encoded = base64.b64encode(compressed).decode("ascii")

    logger.info(
        f"[CHUNK] ID: {msg_id} | Content: {len(content)} chars -> "
        f"Compressed: {len(compressed)} bytes -> Base64: {len(encoded)} chars"
    )

    # Collect metadata fields (everything except id, ct, z)
    meta = {k: v for k, v in msg_dict.items() if k not in ("id", "ct", "ci", "cc", "z")}

    # Split encoded data into CHUNK_DATA_SIZE pieces
    data_chunks = [encoded[i : i + CHUNK_DATA_SIZE] for i in range(0, len(encoded), CHUNK_DATA_SIZE)]
    cc = len(data_chunks)

    result: list[str] = []
    for ci, data in enumerate(data_chunks):
        chunk: dict = {"id": msg_id, "ci": ci, "cc": cc}
        if ci == 0:
            chunk.update(meta)
        chunk["ct"] = data
        chunk_json = json.dumps(chunk, separators=(",", ":"))

        if len(chunk_json) > GGWAVE_PAYLOAD_LIMIT:
            logger.warning(
                f"[CHUNK] ID: {msg_id} | Chunk {ci}/{cc} is {len(chunk_json)} bytes "
                f"(limit {GGWAVE_PAYLOAD_LIMIT}). Payload may be truncated."
            )

        result.append(chunk_json)

    logger.info(f"[CHUNK] ID: {msg_id} | Split into {cc} chunks")
    return result


# ---------------------------------------------------------------------------
# Inbound: receiving chunks and reassembling
# ---------------------------------------------------------------------------

def handle_received_chunk(chunk_dict: dict) -> dict | None:
    """Process a received chunk.

    Returns the reassembled message dict when all chunks are received,
    or None if still waiting for more chunks.
    """
    global chunk_receive_buffer

    msg_id = chunk_dict.get("id", "")
    ci = chunk_dict.get("ci", 0)
    cc = chunk_dict.get("cc", 0)

    # Single message (no chunking)
    if cc == 0:
        return {k: v for k, v in chunk_dict.items() if k not in ("ci", "cc")}

    # Initialise buffer for this message if needed
    if msg_id not in chunk_receive_buffer:
        chunk_receive_buffer[msg_id] = {
            "chunks": {},
            "cc": cc,
            "meta": {},
            "timestamp": time.time(),
        }

    buf = chunk_receive_buffer[msg_id]
    buf["chunks"][ci] = chunk_dict.get("ct", "")

    # Store metadata from first chunk (fn, st, etc.)
    if ci == 0:
        for key, val in chunk_dict.items():
            if key not in ("id", "ci", "cc", "ct"):
                buf["meta"][key] = val

    logger.info(
        f"[CHUNK_RECV] ID: {msg_id} | Chunk {ci + 1}/{cc} | "
        f"Have {len(buf['chunks'])}/{cc}"
    )

    if len(buf["chunks"]) == cc:
        return reassemble_chunks(msg_id)

    return None


def reassemble_chunks(msg_id: str) -> dict | None:
    """Reassemble a complete set of chunks into the original message dict."""
    global chunk_receive_buffer

    if msg_id not in chunk_receive_buffer:
        return None

    buf = chunk_receive_buffer[msg_id]
    cc = buf["cc"]

    encoded_parts: list[str] = []
    for ci in range(cc):
        if ci not in buf["chunks"]:
            logger.error(f"[REASSEMBLE] ID: {msg_id} | Missing chunk {ci}")
            return None
        encoded_parts.append(buf["chunks"][ci])

    encoded = "".join(encoded_parts)

    try:
        compressed = base64.b64decode(encoded)
        decompressed = lznt1_decompress(compressed)
        content = decompressed.decode("utf-8")
    except Exception as e:
        logger.error(f"[REASSEMBLE] ID: {msg_id} | Decompression failed: {e}")
        del chunk_receive_buffer[msg_id]
        return None

    result = {"id": msg_id, "ct": content}
    result.update(buf["meta"])

    logger.info(f"[REASSEMBLE] ID: {msg_id} | Reassembled {cc} chunks -> {len(content)} chars")

    del chunk_receive_buffer[msg_id]
    return result


# ---------------------------------------------------------------------------
# Timeout / retransmission
# ---------------------------------------------------------------------------

def check_chunk_timeouts() -> list[dict]:
    """Check for timed-out chunk reassemblies.

    Returns list of retransmission request dicts for messages with missing chunks.
    """
    global chunk_receive_buffer

    now = time.time()
    retx_requests: list[dict] = []
    expired: list[str] = []

    for msg_id, buf in chunk_receive_buffer.items():
        elapsed = now - buf["timestamp"]
        if elapsed > CHUNK_REASSEMBLY_TIMEOUT:
            missing = [ci for ci in range(buf["cc"]) if ci not in buf["chunks"]]
            if missing:
                retx_requests.append({
                    "id": msg_id,
                    "fn": "retx",
                    "ci": missing,
                })
                buf["timestamp"] = now  # Reset timeout for next cycle
                logger.warning(
                    f"[TIMEOUT] ID: {msg_id} | Missing chunks: {missing} | "
                    "Requesting retransmission"
                )
            else:
                expired.append(msg_id)

    for msg_id in expired:
        del chunk_receive_buffer[msg_id]

    return retx_requests


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------

def send_chunks(chunks: list[str], stream_output, protocol_id: int, volume: int, msg_id: str = ""):
    """Transmit a list of chunk JSON strings sequentially via ggwave."""
    global last_sent_chunks

    if msg_id:
        last_sent_chunks[msg_id] = chunks

    for i, chunk_json in enumerate(chunks):
        waveform = ggwave.encode(chunk_json, protocolId=protocol_id, volume=volume)
        logger.info(
            f"[SEND] ID: {msg_id} | Chunk {i + 1}/{len(chunks)} | "
            f"Content: {truncate_for_log(chunk_json)}"
        )
        stream_output.write(waveform, len(waveform) // 4)

        if i < len(chunks) - 1:
            time.sleep(INTER_CHUNK_DELAY)

    logger.info(f"[SEND_OK] ID: {msg_id} | All {len(chunks)} chunk(s) transmitted")


def handle_retransmission_request(retx_dict: dict, stream_output, protocol_id: int, volume: int):
    """Handle a retransmission request by resending the requested chunks."""
    msg_id = retx_dict.get("id", "")
    requested = retx_dict.get("ci", [])

    if msg_id not in last_sent_chunks:
        logger.warning(f"[RETX] ID: {msg_id} | No chunks in send buffer")
        return

    stored_chunks = last_sent_chunks[msg_id]

    for ci in requested:
        if isinstance(ci, int) and 0 <= ci < len(stored_chunks):
            logger.info(f"[RETX] ID: {msg_id} | Resending chunk {ci}")
            waveform = ggwave.encode(stored_chunks[ci], protocolId=protocol_id, volume=volume)
            stream_output.write(waveform, len(waveform) // 4)
            time.sleep(INTER_CHUNK_DELAY)
        else:
            logger.warning(f"[RETX] ID: {msg_id} | Chunk {ci} out of range (have {len(stored_chunks)})")
