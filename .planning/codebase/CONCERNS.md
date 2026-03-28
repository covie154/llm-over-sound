# Codebase Concerns

**Analysis Date:** 2026-03-28

## Tech Debt

**LLM Pipeline Not Implemented:**
- Issue: The Python backend pipeline (`python-backend/lib/pipeline.py`) contains only stub methods. Stages 1, 3, 4, and 5 (study type classification, findings extraction, report rendering, impression generation) raise `NotImplementedError`. Currently using `TestPipeline` which echoes messages back.
- Files: `python-backend/lib/pipeline.py` (lines 83-84, 109-127), `python-backend/backend.py` (line 93)
- Impact: The system cannot actually process radiology reports. All processing is bypassed; messages are echoed. This blocks the core feature of the application.
- Fix approach: Implement the five-stage pipeline with LLM calls. Stage 1 and 3 are LLM-dependent (study classification, findings extraction); stages 2, 4, 5 are template/text processing. Initialize LLM client in `__init__`, implement each stage method, add audit logging for stages 1, 3, 4, 5 as per CLAUDE.md spec.

**Template System Undefined:**
- Issue: Templates are referenced in CLAUDE.md but do not exist. No markdown template files with YAML frontmatter, study names, aliases, or anatomical fields have been created.
- Files: None exist; would live in a `templates/` directory per TODO.md
- Impact: Stage 1 (study classification) cannot match to template files; Stage 2 (template retrieval) has no templates to load; Stage 3 (findings mapping) has no field definitions. The entire backend architecture depends on templates.
- Fix approach: Create `templates/` directory. Define template file format (YAML frontmatter with study name, aliases, anatomical fields; body with template skeleton and placeholder tokens). Create initial templates for common studies (CT abdomen/pelvis, CT chest, MRI brain, CXR, ultrasound abdomen). Build template index at backend startup.

**Error Handling Gaps:**
- Issue: AHK frontend has minimal error recovery. When DLL calls fail (e.g., audio device unavailable, compression fails), functions return empty strings or false without propagating context. Backend exception handling is broad (catches all `Exception`) and logs to file, but does not distinguish between recoverable and fatal errors.
- Files: `AHK/include/compression.ahk` (lines 11, 32, 52, 87), `AHK/include/chunking.ahk` (line 38-41), `python-backend/backend.py` (lines 173-174, 202-203)
- Impact: Silent failures. If compression fails on the frontend, the user sees no message; if decompression fails on the backend, the message is dropped. No user feedback for recoverable errors (e.g., "volume too low, please recalibrate").
- Fix approach: Add specific exception types in Python backend (CompressionError, TemplateNotFoundError, LLMError). Return structured error dicts with actionable messages. On frontend, display errors in GUI before silently failing. Log stack traces for debugging.

## Known Bugs

**Chunk Timeout Uses Milliseconds on Frontend, Seconds on Backend:**
- Symptoms: Inconsistent chunk reassembly behavior between AHK and Python. Frontend uses `CHUNK_REASSEMBLY_TIMEOUT := 30000` (milliseconds), backend uses `CHUNK_REASSEMBLY_TIMEOUT = 30` (seconds). If timing is misconfigured, chunks may be requested for retransmission prematurely on one side but not the other.
- Files: `AHK/include/config.ahk` (line 20), `python-backend/lib/config.py` (line 20)
- Trigger: Long message transmission (> 1 second of inter-chunk delays) that approaches 30-second window. One side times out while the other waits longer, causing asymmetric retransmission requests.
- Workaround: None currently. Both sides happen to use 30 in absolute value, but units differ.

**Hardcoded Volume in AHK Chunking:**
- Symptoms: All chunk transmissions use hardcoded volume=50, not respecting user-configured or calibrated volume. Backend accepts `--volume` argument but frontend ignores volume calibration.
- Files: `AHK/include/chunking.ahk` (lines 104, 342)
- Trigger: User sets volume via backend CLI but AHK uses fixed 50, leading to inconsistent audio levels between frontend and backend.
- Workaround: Manually set volume in AHK source code before compiling.

**Chunk Reassembly Does Not Clear Buffer on Decompression Failure:**
- Symptoms: If reassembly decompression fails in the frontend, the chunk buffer is cleared. However, if the user requests retransmission and a later chunk is corrupted, the reassembly will fail again, potentially creating an infinite loop of failed retransmissions.
- Files: `AHK/include/chunking.ahk` (lines 272-276)
- Trigger: Bit-flip or audio corruption on any chunk during reception. Retransmission request succeeds, but decompression fails again on the same chunk.
- Workaround: Manual restart of the application.

## Security Considerations

**No Message Authentication:**
- Risk: Audio channel is open to eavesdropping and tampering. No encryption, MAC, or signature. An attacker with access to the audio interface could inject malicious findings or fabricated reports.
- Files: `AHK/include/chunking.ahk`, `python-backend/lib/chunking.py` — both accept raw JSON from audio without verification
- Current mitigation: Physical cable connection between dedicated USB audio interfaces assumes adversary has no access to the audio path. No wireless step mentioned in hardware setup.
- Recommendations: If moving to wireless audio or shared network, add HMAC-SHA256 signing of all messages. Implement replay attack protection with monotonic message counters and timestamp validation. Consider AES-256-GCM encryption for sensitive reports.

**No Input Validation on JSON:**
- Risk: Backend `json.loads()` and AHK `Jxon_Load()` parse untrusted input from the audio channel. A malformed or oversized JSON payload could cause denial of service or memory exhaustion.
- Files: `python-backend/backend.py` (lines 144, 166), `AHK/include/chunking.ahk` (line 166)
- Current mitigation: Python catches `json.JSONDecodeError` and logs; AHK catches generic exception. No size limits enforced.
- Recommendations: Validate JSON schema (e.g., required keys "id", "ct"); enforce payload size limits (e.g., max 1MB reassembled content); reject unknown fields. Use schema validation library in Python (jsonschema).

**LLM Prompt Injection Risk:**
- Risk: User-provided radiology draft (from radiologist via AHK frontend) is passed directly to LLM without sanitization. A malicious or crafted prompt could trick the LLM into ignoring instructions, fabricating findings, or revealing system prompts.
- Files: `python-backend/lib/pipeline.py` (lines 109-127, stubs) — will be filled in with LLM calls
- Current mitigation: None (not yet implemented).
- Recommendations: Implement strict prompt construction. Use temperature=0 and constrained output (e.g., JSON schema validation on LLM responses). Never concatenate user input directly into prompts. Use role-based tokens (e.g., "clinician input:", "finding:"). Sanitize findings before interpolating into template (check against expected anatomical fields only).

**Clinical Safety: No LLM Output Validation:**
- Risk: Stage 3 (findings extraction) must not fabricate pathology. LLM could generate false findings if not constrained. Stage 5 (impression generation) could provide incorrect clinical guidance. No post-hoc verification that extracted findings actually appear in the source draft.
- Files: `python-backend/lib/pipeline.py` (lines 117-127)
- Current mitigation: CLAUDE.md specifies strict extraction rules, but not yet implemented.
- Recommendations: Implement lexical/semantic overlap verification (check extracted finding text against original draft). Use `__NOT_DOCUMENTED__` sentinel for unmapped fields. Add confidence score to LLM outputs; reject low-confidence findings. Implement audit logging of input-output pairs for medico-legal traceability (spec'd in CLAUDE.md, not yet done). Consider a secondary "validation" LLM call to verify findings against draft before returning.

## Performance Bottlenecks

**LZNT1 Compression Search is O(n²):**
- Problem: `_lznt1_compress_chunk()` in `python-backend/lib/compression.py` (lines 128-140) uses a naive search for back-references: for each position, it searches backward from pos-1 through search_start, checking every position. For 4096-byte chunks, this is `O(4096²)` comparisons.
- Files: `python-backend/lib/compression.py` (lines 128-140)
- Cause: No hash table or suffix tree for position lookup. Comparison is repeated for every position in the chunk.
- Improvement path: Use a hash table mapping (byte[0:2] or byte[0:3]) to list of positions. For each new position, hash the bytes and check only stored positions. Reduces search from O(n²) to O(n * m) where m is average matches per hash.

**Chunk Buffering Unbounded:**
- Problem: `chunk_receive_buffer` (Python) and `chunkReceiveBuffer` (AHK) can grow without limit. If a frontend or backend is interrupted mid-transmission, chunks accumulate in memory indefinitely until the process restarts.
- Files: `python-backend/lib/chunking.py` (line 27), `AHK/include/chunking.ahk` (line 23)
- Cause: No automatic cleanup except on timeout (30 seconds). If timeout is not reached or process stays alive for days, buffer grows.
- Improvement path: Add a maximum buffer size per message (e.g., 10 MB) and per total buffer (e.g., 100 MB). Implement LRU eviction. Set more aggressive timeouts for development (e.g., 5 seconds).

**No Volume Calibration Caching:**
- Problem: CLAUDE.md specifies volume calibration at startup but not yet implemented. Every run requires manual calibration, slowing down testing.
- Files: TODO.md (lines 41), CLAUDE.md (section "Hardware and Audio Setup")
- Cause: Not yet implemented.
- Improvement path: Implement one-time volume calibration on first run or when `--recalibrate` is passed. Store calibration in `config.json`. Load and apply on subsequent runs.

## Fragile Areas

**Compression Compatibility:**
- Files: `AHK/include/compression.ahk` (Windows NTDLL RtlCompressBuffer), `python-backend/lib/compression.py` (pure Python LZNT1)
- Why fragile: AHK uses Windows NTDLL API; Python uses custom LZNT1 implementation. Both claim LZNT1 compatibility but the Python implementation is from-scratch. If decompression logic differs (e.g., displacement calculation, chunk header format), messages fail to reassemble silently.
- Safe modification: Add interoperability tests. Create test vectors: compress with AHK, decompress with Python, and vice versa. Check against known LZNT1 test vectors. Log compression headers and structure for debugging.
- Test coverage: No integration tests between AHK and Python compression. Only unit tests on each side.

**Message ID Generation:**
- Files: `AHK/include/msgid.ahk` (generates Base62 7-char IDs), `python-backend/backend.py` (echoes back ID from received message)
- Why fragile: If message ID collides (low probability with Base62 but non-zero), retransmission requests could target the wrong message. ID is generated on frontend; backend trusts it. No validation of format or uniqueness.
- Safe modification: Ensure frontend increments a global counter (`messageCounter`) as tiebreaker; verify ID format on backend (regex match `[0-9a-zA-Z]{7}`). Log ID generation and collision.
- Test coverage: No tests for ID uniqueness over time.

**ggwave Protocol Hardcoded:**
- Files: `AHK/main_dll.ahk` (line 38, `"Int", 1,  ; Protocol: AUDIBLE_FAST`), `python-backend/backend.py` (line 98, `default=1`)
- Why fragile: Protocol ID is compile-time constant on AHK, CLI argument on Python. If user selects different protocols on each side, encoding/decoding fails silently (message received but garbage data).
- Safe modification: Make protocol configurable on AHK frontend (GUI dropdown exists in `gui.ahk` but not wired to initialization). Add validation that both sides use the same protocol.
- Test coverage: Manual testing only; no automated protocol negotiation or verification.

**Retransmission Loop Termination:**
- Files: `AHK/include/chunking.ahk` (lines 307-329), `python-backend/lib/chunking.py` (lines 199-220)
- Why fragile: If a chunk is consistently corrupted (e.g., audio path has persistent noise), retransmission requests will loop forever. Timeout resets on each request, allowing infinite retransmissions.
- Safe modification: Add a max retransmission count per message (e.g., 3 attempts). After max, discard message and notify user. Implement exponential backoff on timeout resets.
- Test coverage: No test for corrupted chunks or retransmission exhaustion.

## Scaling Limits

**Audio Bandwidth Constraint:**
- Current capacity: ggwave Audible Fast protocol (~140 bytes per transmission), ~0.5 second inter-chunk delay. Maximum ~280 bytes/second (560 with 0.25s delay). For a 10KB formatted report, ~36-72 seconds transmission time.
- Limit: Scales poorly with report length. Long reports (> 50KB formatted) would take > 3 minutes to transmit. User experience degrades.
- Scaling path: Implement optional higher-bandwidth protocols (DT protocols mentioned in TODO.md). Test protocol 2-4 with hardware. Add adaptive inter-chunk delay based on success rate (shorter delays if no retransmissions needed). Consider dual-channel if hardware supports stereo audio.

**Memory for Chunk Buffering:**
- Current capacity: Unbounded (see Fragile Areas). Typical report ~10KB, compressed ~3KB. With 70-char chunks and Base64, ~4KB in memory per message.
- Limit: If 1000+ messages are buffered (backend crash and restart), memory grows to 4MB+. On embedded systems (Raspberry Pi), could cause OOM.
- Scaling path: Set hard limit on buffered messages (e.g., 10 active messages max). Implement priority eviction (oldest first). Pre-allocate fixed-size buffer at startup.

**Template Lookup:**
- Current capacity: Not implemented. Spec'd as "build template alias index at startup."
- Limit: Linear search through template directory on every classification. With 50+ templates, could slow down pipeline.
- Scaling path: Build in-memory index at startup (dict of study aliases -> file paths). Cache parsed templates in memory (with size limit and LRU eviction).

## Dependencies at Risk

**ggwave Library Vendored:**
- Risk: `ggwave/` directory is checked into the repo. Updates to upstream ggwave are manual and may lag. If upstream has security fixes or bug fixes, the system may not benefit.
- Impact: Security vulnerabilities in ggwave library persist until manually merged. Build breaks if upstream API changes and we have not updated.
- Migration plan: Consider using ggwave as a git submodule or importing via package manager (if available). Test upstream updates in CI before merging.

**Python LZNT1 Implementation Custom:**
- Risk: Custom LZNT1 implementation in Python (`python-backend/lib/compression.py`). If bug is found, must be fixed manually. Maintenance burden on future developers unfamiliar with LZNT1 spec.
- Impact: Decompression failures, silent data corruption, performance regression if bugs are introduced during refactoring.
- Migration plan: Consider using a vetted LZNT1 library (if available in Python) or falling back to zlib compression (lower ratio but simpler, tested). Add comprehensive test vectors.

**ggwave Python Bindings:**
- Risk: Python `ggwave` package is external dependency. Requires `pip install ggwave` or compiled bindings. If bindings are not available for target Python version or platform, backend cannot run.
- Impact: Setup complexity. Raspberry Pi OS may not have pre-built wheels; may require compilation.
- Migration plan: Document build steps for Pi (e.g., `apt-get install libggwave-dev`, then `pip install ggwave`). Consider bundling bindings or using pre-built wheels.

**AutoHotkey v2.0:**
- Risk: Script uses AHK v2.0 syntax exclusively. v1 scripts would break. AHK v2 is relatively new; ecosystem smaller than v1. Some libraries may not be v2-compatible.
- Impact: Difficulty finding AHK experts; limited third-party library support. If AHK v2 has breaking changes in future versions, scripts may break.
- Migration plan: Keep tests and documentation up-to-date with AHK releases. Monitor upstream for breaking changes.

## Missing Critical Features

**No Hardware Calibration Workflow:**
- Problem: CLAUDE.md states "volume calibration is critical" but frontend and backend have no calibration UI. User must manually adjust Windows volume and Pi volume settings without automated feedback.
- Blocks: Reliable audio transmission. Without calibration, messages may be too quiet or distorted.
- Recommendation: Implement one-time calibration on startup. Play test tones on each direction, ask user to adjust until level is optimal. Store calibration in config file.

**No Ambiguity Resolution in Study Classification:**
- Problem: TODO.md (line 55) specifies "handle ambiguous study type classification by returning a clarification request to the frontend." Not implemented.
- Blocks: If draft could match multiple templates (e.g., "CT head or CT c-spine?"), system guesses instead of asking.
- Recommendation: In Stage 1, if LLM confidence is low or multiple templates match, return dict with "fn": "clarify", listing candidates. Frontend shows dialog for user to select. Backend waits for response before proceeding to Stage 3.

**No Audit Trail Beyond Logging:**
- Problem: CLAUDE.md specifies "log every input-output pair for audit trail and medico-legal traceability" (Stage 3). Current logging goes to files but no structured audit table or database. Hard to query or audit retroactively.
- Blocks: Compliance with medical regulations (e.g., HIPAA requires full audit trails). Cannot easily prove that findings were or were not fabricated by LLM.
- Recommendation: Implement structured audit logging (JSON or CSV with timestamp, user ID, draft hash, LLM prompt, LLM response, final report hash). Store in a tamper-evident log file or database. Add audit query tools.

**No Field Validation Against Template:**
- Problem: Stage 3 extraction maps to template fields. No validation that all extracted fields are actually defined in the template. If LLM invents a field, it passes through.
- Blocks: Potential for silent hallucination. Report ends up with extra fields that should not be there.
- Recommendation: After Stage 3, validate that all extracted field keys exist in template["fields"]. Drop unknown fields with warning log.

## Test Coverage Gaps

**No Cross-Device Integration Tests:**
- What's not tested: End-to-end message transmission from AHK frontend to Python backend and back, with compression and chunking. Only unit tests on each side.
- Files: No test files found. Unit tests not present in either AHK or Python code.
- Risk: Subtle incompatibilities between compression, chunking, or JSON parsing could be missed until deployment. INTER_CHUNK_DELAY difference (milliseconds vs seconds) was not caught because no test compares timing across sides.
- Priority: High. Add integration test harness that runs both frontend and backend in test mode, sends test messages, and verifies round-trip integrity.

**No Protocol Compatibility Tests:**
- What's not tested: Switching between ggwave protocols (1, 2, 3, 4, etc.). Current tests assume protocol 1.
- Files: No tests for protocol switching.
- Risk: If user switches protocol, message may fail to decode. No early warning.
- Priority: Medium. Test all protocols; document which are supported.

**No Stress Tests for Chunk Buffering:**
- What's not tested: Sending multiple large messages in rapid succession. Chunk buffer limits. Timeout behavior under load.
- Files: No stress test harness.
- Risk: Buffer grows unbounded; timeouts may not trigger; memory leak on long-running system.
- Priority: Medium. Add test that sends 10+ large messages and verifies cleanup.

**No LLM Output Validation Tests:**
- What's not tested: LLM stages (1, 3, 4, 5) exist only as stubs. No tests for prompt injection, hallucination, field validation.
- Files: `python-backend/lib/pipeline.py` (not testable; all methods raise NotImplementedError).
- Risk: When LLM stages are implemented, validation gaps could let invalid findings through.
- Priority: High. Before implementing stages, write tests for expected outputs, edge cases, and malformed inputs.

**No Compression Interop Tests:**
- What's not tested: LZNT1 compressed by AHK decompressed by Python, and vice versa. Custom Python LZNT1 implementation not validated against reference test vectors.
- Files: No test comparing AHK and Python compression/decompression.
- Risk: Decompression fails silently (returns empty string) if implementations differ. Messages lost without diagnosis.
- Priority: High. Create test vectors and cross-platform tests.

---

*Concerns audit: 2026-03-28*
