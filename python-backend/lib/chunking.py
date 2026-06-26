"""
Message framing, reassembly, and retransmission for the minimodem audio channel.

Phase 7 (v1 ACTIVE PATH): every message is sent as a SINGLE newline-delimited
frame (ci=0, cc=1) carrying a ``crc`` field = ``crc32_str(ct)``. On receive, the
CRC is verified before anything is surfaced; a mismatch triggers a full-message
retransmit request and NEVER surfaces a partial/corrupt report (CLAUDE.md
medico-legal rule). This mirrors the AHK frontend's ``chunking.ahk`` exactly so
the two ends interoperate byte-for-byte at the framing/CRC layer.

The multi-chunk split (``chunk_message``) and reassembly (``reassemble_chunks``)
code paths are RETAINED but DORMANT — kept ready for v2 chunking of large
payloads. The v1 path does not exercise them.

Transport: ``minimodem.send`` (FSK over the wrapper) replaces the old
ggwave.encode + PyAudio stream writes; the ggwave Python binding is no longer
imported here.

Wire shape of a v1 frame (serialized, separators=(",",":")):
    {"id":...,"fn":...,"ct":...,"st":...,"ci":0,"cc":1,"crc":<crc32_str(ct)>}
"""

import base64
import json
import time

from .config import (
    CHUNK_DATA_SIZE,
    CHUNK_REASSEMBLY_TIMEOUT,
    COMPRESSION_THRESHOLD,
    MODEM_PAYLOAD_LIMIT,
    INTER_CHUNK_DELAY,
    logger,
    truncate_for_log,
)
from .compression import lznt1_compress, lznt1_decompress, crc32_str
from . import minimodem

# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

# Security (07-RESEARCH.md V5 — Input Validation): decoded FSK bytes are
# untrusted. Cap accepted single-frame content length before processing to
# bound memory use. ct is post-compression/Base62; reports are well under this.
MAX_ACCEPT_CT_LEN = 65536

# ---------------------------------------------------------------------------
# Module-level buffers
# ---------------------------------------------------------------------------

# Incoming chunks: {msg_id: {"chunks": {ci: ct_data}, "cc": int, "meta": dict, "timestamp": float}}
# (dormant — only used by the retained multi-chunk path)
chunk_receive_buffer: dict = {}

# Last sent frame(s) for retransmission: {msg_id: [json_line, ...]}
# v1 stores exactly one newline-terminated frame per id.
last_sent_chunks: dict = {}


# ---------------------------------------------------------------------------
# Outbound (v1 ACTIVE): build a single CRC-protected frame
# ---------------------------------------------------------------------------

def build_single_frame(msg_dict: dict) -> str:
    """Build ONE newline-terminated single frame (ci=0, cc=1) with crc=crc32_str(ct).

    Copies all caller-supplied fields (id, fn, ct, st, ...), forces ci=0/cc=1,
    drops the legacy ``z`` flag, and attaches ``crc`` = CRC32 of the ``ct``
    string's UTF-8 bytes. Mirrors AHK ChunkMessage's v1 path.
    """
    msg_id = msg_dict.get("id", "")
    ct = msg_dict.get("ct", "")

    single = dict(msg_dict)
    single["ci"] = 0
    single["cc"] = 1
    single.pop("z", None)  # legacy compression flag never used on the v1 path
    single["crc"] = crc32_str(ct)

    # Newline-delimited framing: the wrapper accumulates bytes until "\n".
    single_json = json.dumps(single, separators=(",", ":")) + "\n"
    logger.debug(
        f"[CHUNK] ID: {msg_id} | Single frame ({len(single_json)} bytes, crc={single['crc']})"
    )
    return single_json


def chunk_message(msg_dict: dict) -> list[str]:
    """Build the transmittable frame list for a message.

    v1 ACTIVE PATH: always returns a single-element list holding ONE
    CRC-protected newline-terminated frame (from ``build_single_frame``). The
    single-element return keeps the ``send_chunks`` call site unchanged.

    NOTE: the multi-chunk split below is RETAINED but DORMANT (kept for v2). The
    v1 path returns before reaching it. Do not delete.
    """
    # ---- v1 ACTIVE: single CRC-protected frame ----
    return [build_single_frame(msg_dict)]

    # ---- DORMANT (v2 chunking) — retained, intentionally unreachable in v1 ----
    msg_id = msg_dict.get("id", "")  # noqa: E731  (dead code kept for v2)
    content = msg_dict.get("ct", "")

    single = dict(msg_dict)
    single["ci"] = 0
    single["cc"] = 0
    single.pop("z", None)
    single_json = json.dumps(single, separators=(",", ":"))

    if len(content) < COMPRESSION_THRESHOLD and len(single_json) <= MODEM_PAYLOAD_LIMIT:
        logger.debug(f"[CHUNK] ID: {msg_id} | Single frame ({len(single_json)} bytes)")
        return [single_json]

    content_bytes = content.encode("utf-8")
    compressed = lznt1_compress(content_bytes)
    encoded = base64.b64encode(compressed).decode("ascii")

    logger.info(
        f"[CHUNK] ID: {msg_id} | Content: {len(content)} chars -> "
        f"Compressed: {len(compressed)} bytes -> Base64: {len(encoded)} chars"
    )

    meta = {k: v for k, v in msg_dict.items() if k not in ("id", "ct", "ci", "cc", "z")}

    data_chunks = [encoded[i : i + CHUNK_DATA_SIZE] for i in range(0, len(encoded), CHUNK_DATA_SIZE)]
    cc = len(data_chunks)

    result: list[str] = []
    for ci, data in enumerate(data_chunks):
        chunk: dict = {"id": msg_id, "ci": ci, "cc": cc}
        if ci == 0:
            chunk.update(meta)
        chunk["ct"] = data
        chunk_json = json.dumps(chunk, separators=(",", ":"))

        if len(chunk_json) > MODEM_PAYLOAD_LIMIT:
            logger.warning(
                f"[CHUNK] ID: {msg_id} | Chunk {ci}/{cc} is {len(chunk_json)} bytes "
                f"(limit {MODEM_PAYLOAD_LIMIT}). Payload may be truncated."
            )

        result.append(chunk_json)

    logger.info(f"[CHUNK] ID: {msg_id} | Split into {cc} chunks")
    return result


# ---------------------------------------------------------------------------
# Inbound: receiving frames; CRC-verified single-frame (v1) + dormant reassembly
# ---------------------------------------------------------------------------

def extract_json_frame(raw: str) -> str | None:
    """Recover a single JSON object from a received line wrapped in FSK garbage.

    Async FSK demodulation emits a few spurious bytes while the carrier ramps up,
    and noise between frames can trigger a brief spurious carrier lock. Those
    bytes get prepended/appended to the newline-delimited line, so a raw
    ``json.loads`` fails even when the real frame arrived intact.

    A naive "first ``{`` to last ``}``" slice breaks when the leading garbage
    itself contains a stray ``{`` (observed: ``\\x..{+...&{"cc":1,...}`` -> the
    slice starts at the junk brace and won't parse). Instead we scan every ``{``
    and use ``raw_decode`` to parse one object starting there, returning the first
    that yields a dict. ``raw_decode`` also stops at the end of that object, so
    trailing garbage after the closing ``}`` is ignored. The downstream CRC check
    remains the real integrity gate — a wrongly-extracted frame fails CRC and is
    rejected, never silently accepted.

    Returns the ``{...}`` substring, or None if no ``{`` begins a valid JSON
    object (pure noise — the caller should skip it silently, not log a parse error).
    """
    if not raw:
        return None
    decoder = json.JSONDecoder()
    i = raw.find("{")
    while i != -1:
        try:
            obj, end = decoder.raw_decode(raw, i)
            if isinstance(obj, dict):
                return raw[i:end]
        except json.JSONDecodeError:
            pass
        i = raw.find("{", i + 1)
    return None


def handle_received_chunk(chunk_dict: dict) -> dict | None:
    """Process a received frame.

    v1 ACTIVE PATH (cc == 1): verify ``crc32_str(ct) == crc``. On match, return
    the message dict (ci/cc/crc stripped). On mismatch: log [RECV_FAIL], request
    a FULL-message retransmit, and return None — never surface a partial/corrupt
    report (CLAUDE.md medico-legal rule).

    The cc != 1 (chunked / cc==0) branch and ``reassemble_chunks`` are RETAINED
    but DORMANT for v2.
    """
    global chunk_receive_buffer

    msg_id = chunk_dict.get("id", "")
    ci = chunk_dict.get("ci", 0)
    cc = chunk_dict.get("cc", 0)

    # ---- v1 ACTIVE PATH: single frame with CRC32 ----
    if cc == 1:
        ct = chunk_dict.get("ct", "")

        # Security (V5): bound accepted content length before processing.
        if len(ct) > MAX_ACCEPT_CT_LEN:
            logger.error(
                f"[RECV_FAIL] ID: {msg_id} | ct length {len(ct)} exceeds "
                f"MAX_ACCEPT_CT_LEN ({MAX_ACCEPT_CT_LEN}) - rejecting, requesting retransmit"
            )
            _request_full_retransmit(msg_id)
            return None

        received_crc = chunk_dict.get("crc")
        expected_crc = crc32_str(ct)

        # crc travels as a JSON number; compare numerically.
        try:
            crc_ok = received_crc is not None and int(received_crc) == expected_crc
        except (TypeError, ValueError):
            crc_ok = False

        if not crc_ok:
            logger.error(
                f"[RECV_FAIL] ID: {msg_id} | CRC mismatch (got {received_crc} "
                f"expected {expected_crc}) - requesting full retransmit"
            )
            _request_full_retransmit(msg_id)
            return None

        # Integrity verified — surface the message (drop framing/integrity fields).
        return {k: v for k, v in chunk_dict.items() if k not in ("ci", "cc", "crc")}

    # ---- DORMANT (v2): single message with no chunking (cc == 0) ----
    if cc == 0:
        return {k: v for k, v in chunk_dict.items() if k not in ("ci", "cc")}

    # ---- DORMANT (v2): multi-chunk reassembly ----
    if msg_id not in chunk_receive_buffer:
        chunk_receive_buffer[msg_id] = {
            "chunks": {},
            "cc": cc,
            "meta": {},
            "timestamp": time.time(),
        }

    buf = chunk_receive_buffer[msg_id]
    buf["chunks"][ci] = chunk_dict.get("ct", "")

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
    """Reassemble a complete set of chunks into the original message dict.

    DORMANT (v2): the v1 single-frame path does not reach this.
    """
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
# Timeout / retransmission request
# ---------------------------------------------------------------------------

def _request_full_retransmit(msg_id: str) -> None:
    """Send a full-message retransmit request over minimodem.

    Mirrors the AHK retx shape ``{id, fn:"retx", ci:[0]}`` (ci=[0] => whole
    single-frame message). Sent immediately rather than buffered so the peer can
    resend without waiting for a poll cycle.
    """
    retx = {"id": msg_id, "fn": "retx", "ci": [0]}
    retx_json = json.dumps(retx, separators=(",", ":")) + "\n"
    try:
        result = minimodem.send(retx_json, 50)
        if result < 0:
            logger.error(f"[RETX_FAIL] ID: {msg_id} | Send failed: {minimodem.get_error()}")
            return
        while minimodem.is_transmitting():
            time.sleep(0.05)
        logger.info(f"[RETX_SEND] ID: {msg_id} | Requesting full-message retransmit (ci=[0])")
    except Exception as e:
        logger.error(f"[RETX_FAIL] ID: {msg_id} | {e}")


def check_chunk_timeouts() -> list[dict]:
    """Check for timed-out chunk reassemblies (DORMANT v2 path).

    Returns retransmission request dicts for messages with missing chunks. The
    v1 single-frame path leaves ``chunk_receive_buffer`` empty, so this returns
    an empty list in normal operation.
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
                buf["timestamp"] = now
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
# Sending (v1: single frame over minimodem)
# ---------------------------------------------------------------------------

def send_chunks(chunks: list[str], volume: int, msg_id: str = ""):
    """Transmit frame(s) sequentially via minimodem.

    v1: ``chunks`` is a single-element list holding ONE newline-terminated
    CRC-protected frame (from ``chunk_message``). Stored in ``last_sent_chunks``
    so a ``retx`` request resends the same frame. The loop also tolerates the
    dormant multi-chunk path.

    NOTE: the legacy ``stream_output``/``protocol_id`` params are GONE — transport
    now goes through the minimodem binding. All call sites pass (chunks, volume,
    msg_id).
    """
    global last_sent_chunks

    if msg_id:
        last_sent_chunks[msg_id] = chunks

    total = len(chunks)
    for i, chunk_json in enumerate(chunks):
        result = minimodem.send(chunk_json, volume)
        if result < 0:
            logger.error(
                f"[SEND_FAIL] ID: {msg_id} | Frame {i + 1}/{total} | "
                f"Error: {minimodem.get_error()}"
            )
            return
        logger.info(
            f"[SEND] ID: {msg_id} | Frame {i + 1}/{total} | "
            f"Content: {truncate_for_log(chunk_json)}"
        )

        # Wait for transmission to complete before the next frame (mirrors AHK).
        while minimodem.is_transmitting():
            time.sleep(0.05)

        if i < total - 1:
            time.sleep(INTER_CHUNK_DELAY)  # dormant for the single-frame path

    logger.info(f"[SEND_OK] ID: {msg_id} | All {total} frame(s) transmitted")


def handle_retransmission_request(retx_dict: dict, volume: int):
    """Resend the stored frame(s) for a retransmission request via minimodem.

    v1: ``last_sent_chunks[msg_id]`` holds exactly one frame (index 0), so a
    ``retx`` with ci=[0] resends the whole message. The loop also covers the
    dormant multi-chunk case.

    NOTE: ``stream_output``/``protocol_id`` params removed; signature is now
    (retx_dict, volume).
    """
    msg_id = retx_dict.get("id", "")
    requested = retx_dict.get("ci", [])

    if msg_id not in last_sent_chunks:
        logger.warning(f"[RETX] ID: {msg_id} | No frames in send buffer")
        return

    stored_chunks = last_sent_chunks[msg_id]

    for ci in requested:
        if isinstance(ci, int) and 0 <= ci < len(stored_chunks):
            logger.info(f"[RETX] ID: {msg_id} | Resending frame {ci}")
            result = minimodem.send(stored_chunks[ci], volume)
            if result < 0:
                logger.error(f"[RETX_FAIL] ID: {msg_id} | Send failed: {minimodem.get_error()}")
                continue
            while minimodem.is_transmitting():
                time.sleep(0.05)
            time.sleep(INTER_CHUNK_DELAY)
        else:
            logger.warning(f"[RETX] ID: {msg_id} | Frame {ci} out of range (have {len(stored_chunks)})")
