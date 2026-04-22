# AHK Frontend — Radiology Report Review Interface

## Language & Runtime
AutoHotkey v2.0 strict. Do not use v1-style syntax (e.g., no `=` for assignment in
expressions, no legacy command syntax) [2].

## Dependencies
- `include/_JXON.ahk` — JSON parser for AHK v2 [2].
- `ggwave_simple.dll` — custom C wrapper built from `ggwave-wrapper/`.
- Windows system DLLs: `ntdll.dll` (RtlCompressBuffer/RtlDecompressBuffer),
  `Crypt32.dll` (CryptBinaryToStringW) [2].

## Key Details
- Compression uses COMPRESSION_ENGINE global (default LZNT1=2). Only applied to
  messages exceeding COMPRESSION_THRESHOLD (100 chars) [2].
- Message IDs use Base62 encoding, zero-padded to 7 characters [2].
- The messageCounter global provides additional uniqueness for message IDs [2].
- The audio device selection GUI enumerates playback and capture devices via the
  ggwave_simple DLL. The USB audio interface used for the cable connection to the
  Pi must be selected here.
- Logging is controlled by LOG_ENABLED and writes to LOG_FILE
  (`ggwave_log.txt`) [2]. Log entries include timestamps with millisecond precision
  and are truncated to LOG_MAX_CONTENT_LENGTH [2].
- The Escape key exits the application and triggers cleanup [2].

## Chunked Message Reassembly
- The frontend must handle chunked responses from the backend. Incoming chunks are
  identified by message ID with chunk index ("ci") and chunk count ("cc") fields.
- Buffer chunks keyed by message ID. Only decompress and assemble when all chunks for
  a given ID have been received (the backend compresses the full report before chunking).
- Implement a timeout mechanism: if a chunk is missing after a reasonable window,
  request retransmission of the specific missing chunk rather than displaying an
  incomplete report.

## Report Review Workflow
- The radiologist's draft input is captured via a multiline Edit control with send and
  cancel buttons [2]. Ctrl+Enter is bound as an alternative send shortcut [2].
- The formatted report returned from the backend is displayed in a multiline Edit
  control for review.
- __NOT_DOCUMENTED__ sentinel values are replaced with a visible placeholder such as
  `[*** NOT DOCUMENTED — please complete ***]`.
- A status line indicates how many fields remain incomplete and lists them by name.
- Before final submission, scan the report text for remaining __NOT_DOCUMENTED__
  sentinels. If any are found, show a confirmation dialog asking whether the omission
  is intentional or whether the radiologist wants to go back and complete them.
- Do not allow silent submission of incomplete reports.

## Testing
No automated test harness. Test by running alongside the Python backend with the USB
audio cable connection and verifying round-trip message integrity. Test chunked
transmission with report-length payloads. Calibrate volume on both sides before
running ggwave.