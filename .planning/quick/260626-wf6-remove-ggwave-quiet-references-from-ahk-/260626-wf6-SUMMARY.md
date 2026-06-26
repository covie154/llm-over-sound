---
quick_id: 260626-wf6
slug: remove-ggwave-quiet-references-from-ahk-
status: complete
date: 2026-06-26
commits:
  - 1965bb5
  - ae589bc
  - fb0664c
---

# Quick Task 260626-wf6: Remove ggwave/quiet References

## What Was Done

### Task 1 — AHK + .gitignore
- `AHK/include/config.ahk`: `GGWAVE_PAYLOAD_LIMIT` → `MODEM_PAYLOAD_LIMIT`; log file `ggwave_log.txt` → `minimodem_log.txt`
- `AHK/include/chunking.ahk`: two uses of `GGWAVE_PAYLOAD_LIMIT` → `MODEM_PAYLOAD_LIMIT`; MsgBox title → "minimodem - Message Received"
- `AHK/include/gui.ahk`: window title → "minimodem - Send Message"
- `AHK/include/logging.ahk`: session header → "minimodem Session Started"
- `AHK/main_dll.ahk`: comment about old ggwave protocol-id rephrased to past-tense
- `.gitignore`: `ggwave_log.txt` → `minimodem_log.txt`

### Task 2 — Python
- `python-backend/lib/config.py`: docstring, `MODEM_PAYLOAD_LIMIT`, logger name `minimodem_backend`, session start string
- `python-backend/lib/chunking.py`: import and all uses renamed to `MODEM_PAYLOAD_LIMIT`
- `python-backend/lib/__init__.py`: docstring updated
- `python-backend/lib/minimodem.py`: comment updated
- `python-backend/backend.py`: comment updated (past-tense)
- `python-backend/lib/pipeline.py`: logger → `minimodem_backend`
- `python-backend/tests/test_pipeline_integration.py`: caplog logger → `minimodem_backend`
- `python-backend/tests/test_loader.py`: docstring updated (assertion literal `"import ggwave"` preserved as detection pattern)
- `python-backend/tests/test_registry.py`: docstring + comment updated (assertion literals preserved)
- **Deleted**: `python-backend/test-output-audio.py` (legacy ggwave test, imported ggwave directly)
- **Deleted**: `python-backend/testing-audio.py` (legacy audio test)

### Task 3 — Git Submodule Runbook
- Created `documentation/retire-legacy-submodules.md` with exact `git rm ggwave && git rm quiet && git commit` commands for user to run manually

## Why ggwave/quiet Directories Cannot Be Moved

All three — `ggwave`, `quiet`, and `minimodem` — are registered as **git submodules** in the index (mode `160000`), even though the `.gitmodules` file is missing. Git tracks them as submodule commit references, so moving them breaks those tracked paths. See the runbook at `documentation/retire-legacy-submodules.md` for removal instructions.

## What Was Left Alone
- `AHK/main.ahk` — legacy file for old ggwave-cli approach, left as historical record
- `AHK/ggwave_log.txt` — existing log file; the .gitignore update now ignores `minimodem_log.txt` going forward
- `python-backend/tests/test_loader.py` / `test_registry.py` — assertion literals `"import ggwave"` preserved (they detect unwanted ggwave imports — valid post-migration test)
