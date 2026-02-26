# TODO

## Chunking Implementation
- [x] Define chunk header format (message ID, chunk index "ci", chunk count "cc") and
      agree on JSON schema between both sides.
      Schema: ci=0,cc=0 → single uncompressed frame. cc>0 → chunked (ct is a piece of
      base64-encoded LZNT1-compressed payload). Metadata (fn, st) on chunk 0 only.
      Retransmission request: {"id":"X","fn":"retx","ci":[missing indices]}.
- [x] Python backend: implement full-report compression followed by chunking to payload
      size limit. Transmit chunks sequentially with inter-chunk delay (0.5 s).
- [x] AHK frontend: implement chunk buffering keyed by message ID, reassembly on
      completion, and timeout/retransmission logic for missing chunks.
- [x] Determine safe per-chunk payload size empirically. Set CHUNK_DATA_SIZE=70 base64
      chars per chunk to stay within the 140-byte ggwave limit (kMaxLengthVariable)
      with headroom for JSON framing overhead.

## Template System
- [ ] Define the markdown template file format: YAML frontmatter (study name, aliases,
      anatomical fields, default values) and body (template skeleton with placeholder
      tokens).
- [ ] Create initial set of template files for common study types (CT abdomen/pelvis,
      CT chest, MRI brain, chest X-ray, ultrasound abdomen, etc.).
- [ ] Build template index at backend startup: parse all template files and map study
      name aliases to file paths.

## LLM Pipeline (Python Backend)
- [ ] Implement Stage 1: study type classification prompt with constrained output to
      closed set of known study types from the template index.
- [ ] Implement Stage 2: template file loader and parser (frontmatter + body).
- [ ] Implement Stage 3: findings extraction prompt. Design the prompt to prevent
      hallucination — only extract explicitly stated findings, mark unmentioned fields
      as __NOT_DOCUMENTED__, preserve clinical language. Output as structured JSON.
- [ ] Implement Stage 4: template renderer that populates placeholder tokens from the
      Stage 3 JSON output.
- [ ] Implement Stage 5, Impression/conclusion generation: generate an impression if required by the template
- [ ] Add input-output logging for every LLM call (Stages 1, 3, 4, 5) for audit trail.


## Hardware and Audio Setup
- [ ] Test chunked transmission with report-length payloads over the air.
- [ ] Calibrate volume in both directions (Pi to PC and PC to Pi) with test tones and save the configuration in a file. Run on first run/if the config is not present.
- [ ] Test round-trip message integrity over the cable connection with short messages.
- [ ] Test chunked transmission with report-length payloads over the cable connection.

## Protocol Testing
- [ ] Test DT protocols for higher payload limits
- [ ] Document chosen protocol and rationale.

## Future Considerations

- [ ] Post-hoc verification step: check whether each extracted finding has lexical or
      semantic overlap with the source draft to catch hallucination.
- [ ] Domain-specific dictionary encoding for common radiology phrases to improve
      compression ratio over the
- [ ] Handle ambiguous study type classification by returning a clarification request
      to the frontend instead of guessing.