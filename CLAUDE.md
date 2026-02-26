# Project: LLM Over Sound — Radiology Report Formatting System

## Overview
This system uses ggwave (data-over-sound) to pipe messages between an AutoHotkey v2
frontend (Windows GUI) and a Python backend running on a Raspberry Pi or equivalent SBC (Assume it's running linux).
The backend connects to an LLM over the network. The audio channel is the sole IPC
mechanism — messages are transmitted as sound over a direct USB audio interface cable
connection between the two machines [1]. No shared filesystem or network link exists
between the frontend and backend other than the audio pipe.

The primary use case is AI-powered radiology report formatting. A radiologist writes
draft findings (structured point form, brief notes, or incomplete drafts) on the AHK
frontend. The draft is transmitted over ggwave to the Python backend, which classifies
the study type, selects the appropriate report template, extracts and maps findings to
anatomical fields using the LLM, and transmits the formatted report back over ggwave
for review and completion.

## Architecture
- **AHK Frontend** (`AHK/main_dll.ahk`): Windows GUI that captures the radiologist's
  draft input via a multiline Edit control [2], encodes it, and transmits via the
  ggwave_simple DLL. Receives the formatted report back, presents __NOT_DOCUMENTED__
  fields for review, and handles final report approval. Uses LZNT1/XPRESS compression
  (via ntdll) and Base62 encoding for payload efficiency [2].
- **Python Backend** (`python-backend/backend.py`): Runs on a Raspberry Pi connected to
  the user's PC. It has not yet been determined if the connection is a speaker-microphone or wired audio connection. Listens for ggwave signals,
  decodes messages, orchestrates the LLM-powered report formatting pipeline, and
  transmits results back over ggwave [3]. Connects to the LLM over the network.
- **ggwave Wrapper** (`ggwave-wrapper/`): C/C++ DLL wrapper around the ggwave library,
  built with CMake. Provides a simplified interface for the AHK frontend. Completed as of Feb 2026.
- **ggwave** (`ggwave/`): The upstream ggwave library (data-over-sound).
- **Templates** (markdown files): Each template file contains a study name with aliases
  for matching, a list of expected anatomical fields, and the report template skeleton
  with placeholder tokens.

## Structure of a Radiology Report
- A radiology report generally consists of give main sections.
  1. Clinical history: This is the reason for ordering the scan. Ideally, this should include what the referring clinician is looking for on the scan
    including their differentials
  2. Technique: A technical section detailing how the study was performed. Usually, the imaging modality is indicated here, along with other factors like 
    phase of the study and whether contrast was administered.
  3. Comparison: The presence/absence of prior comparison study/studies, if available.
  4. Findings: This section details radiological observations (e.g. a rim-enhancing collection around the appendix). It should not include recommendations, which
    should go to the conclusion. Some reports organise the findings by body system, while others organise the findings by abnormal-first (with normal findings summed up below).
  5. Conclusion/Impression/Comment: This section provides a very brief summary of the report. It should answer the clinical question. The next points can detail important
    incidental findings (e.g. incidental cancers). Recommendations will go here (e.g. histological correlation is suggested).

## Report Formatting Pipeline
The backend runs a five-stage pipeline. Only stages 1, 3, 4 and 5 involve the LLM.

1. **Study type classification** (LLM): Identify imaging modality and body region from
   the draft. Output is constrained to the closed set of known study types extracted
   from template file metadata. 
   TODO: If ambiguous, return a clarification request rather than guessing.
2. **Template retrieval** (deterministic): Load and parse the matching markdown template
   file by study type. Not an LLM call. An index of study aliases to template file
   paths is built at startup for fast lookup.
3. **Findings extraction and mapping** (LLM): Extract findings from the draft and assign
   to anatomical fields defined in the template. Output is structured JSON keyed by
   field name. Fields not mentioned in the draft are marked __NOT_DOCUMENTED__ — the
   LLM must NOT fabricate findings. The model must
   preserve the radiologist's clinical language and intent. In other words, if a full sentence is provided in a finding, preserve it and do not alter it in any way.
   Log every input-output pair for audit trail and medico-legal traceability.
4. **Report rendering** (LLM): Populate the template skeleton with extracted
   findings. You may only add normal findings if assume_normal is set to True.
5. **Impression generation** (LLM): Generate the impression/conclusion of the report. 

## Audio Channel Constraints
- The ggwave audio pipe is bandwidth-limited. The default protocol is Audible Fast
  (protocol ID 1). Payload ceiling is approximately 140 bytes per transmission.
- Messages are compressed above COMPRESSION_THRESHOLD (100 chars) using LZNT1 [2].
- For payloads exceeding the per-transmission limit (especially formatted reports
  returning to the frontend), chunking is required. Compress the entire report first
  as a single block for best compression ratio, then chunk the compressed output.
  Each chunk includes a sequencing header (message ID, chunk index "ci", chunk
  count "cc"). Target pre-compression chunk input of ~200 characters as a safe
  starting point.
- The AHK frontend must buffer incoming chunks by message ID and reassemble only when
  all chunks for a given ID have arrived. Implement a timeout for missing chunks and
  request retransmission rather than silently producing an incomplete report.
- All data must travel over ggwave. No shared filesystem or secondary network channel
  between frontend and backend.

## Hardware Setup
- Testing currently is with a USB speaker/microphone. 
- Eventually, the plan is to use a class-compliant USB audio interface for both input and output. Do not use the Pi's onboard 3.5mm jack.
- The PC uses a second USB audio interface or built-in line-in/line-out if available. If audio cables are used, two 1/4" TRS cables connect the devices: Pi line-out to PC line-in, PC line-out to
  Pi line-in. This provides a full-duplex dedicated audio path.
- Volume calibration is critical. Use --volume on the backend and Windows audio settings
  on the PC side. Test each direction independently before running ggwave.

## Key Constraints
- AHK scripts require AutoHotkey v2.0. Do not use v1 syntax [2].
- If you modify message encoding, compression, framing, or chunking on one side, the
  other side MUST be updated to match or the pipe will break.
- The LLM must never fabricate radiology findings. The extraction prompt must constrain
  the model to only surface information present in the draft input.
- All logging is file-based: `ggwave_log.txt` for AHK [2], `backend_log.txt` for
  Python [3].

## Build
- The C++ wrapper is built via CMake from `ggwave-wrapper/`. Output goes to `build/`.
- The Python backend has its own dependencies (see `python-backend/`).

## Conventions
- AHK global config variables are ALL_CAPS_SNAKE_CASE [2].