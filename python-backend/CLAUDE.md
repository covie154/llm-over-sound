# Python Backend — Radiology Report Formatting Pipeline

## Role
Runs on a Raspberry Pi or equivalent SBC. Listens for ggwave audio signals on the USB
audio interface input, decodes messages, orchestrates the LLM-powered report formatting
pipeline, and transmits the formatted report back over the USB audio interface
output [3]. Connects to the LLM over the network.

## Dependencies
- PyAudio for audio device I/O [3].
- ggwave Python bindings [3].
- Logging is file-based to backend_log.txt (UTF-8), controlled by LOG_ENABLED [3].
  Long messages are truncated to LOG_MAX_CONTENT_LENGTH (500 chars) in log output [3].

## Report Formatting Pipeline
The pipeline has four stages. Only stages 1 and 3 involve the LLM.

Stage 1 — Study type classification (LLM): Given the radiologist's draft text,
classify the study type by selecting from the closed set of study names and aliases
defined in template file metadata. Do not allow the model to invent study types outside
this set. If the draft is ambiguous, return a clarification request to the frontend
rather than guessing.

Stage 2 — Template retrieval (deterministic): Load the matching markdown template
file by study type. Parse frontmatter to extract the list of anatomical fields and
default values. Parse the body to extract the template skeleton with placeholder tokens.
Build an index of study aliases to template file paths at startup for fast lookup.

Stage 3 — Findings extraction and mapping (LLM): This is the most safety-critical
step. The LLM extracts findings from the draft and maps them to the anatomical fields
from the template. The output must be structured JSON keyed by field name. Strict rules
for the extraction prompt: only include findings explicitly stated in the draft; do not
infer or fabricate pathology; mark unmentioned fields as __NOT_DOCUMENTED__ rather than
inserting normal boilerplate; preserve the radiologist's clinical language and intent;
do not add comparisons to prior studies unless mentioned; do not generate an impression
unless one is provided in the draft. Log every input-output pair at this stage for
audit trail and medico-legal traceability.

Stage 4 — Report rendering (deterministic): Populate the template skeleton with the
extracted findings JSON. Pure string interpolation. Produce the final formatted report
text.

## Chunked Transmission
- Formatted reports will typically exceed the ggwave per-transmission payload limit
  (~140 bytes for Audible Fast).
- Compress the entire rendered report as a single block using the same compression
  scheme the AHK frontend expects (LZNT1 by default) for optimal compression ratio.
- Chunk the compressed output into segments that fit within the payload limit after
  adding the sequencing header (message ID, chunk index "ci", chunk count "cc").
- Transmit chunks sequentially. Handle retransmission requests from the frontend for
  any missing chunks.

## When Modifying
- process_input() is the central dispatch function [3]. The four-stage pipeline lives
  here or is called from here.
- Any change to response encoding, compression, or chunking must be coordinated with
  the AHK frontend or the pipe will break.
- Template markdown files are the single source of truth for study types and anatomical
  fields. Adding a new study type means adding a new template file; no code changes
  should be needed.
- Audio device enumeration handles missing default devices gracefully via
  try/except [3]. Always verify the USB audio interface is selected using --list before
  running.