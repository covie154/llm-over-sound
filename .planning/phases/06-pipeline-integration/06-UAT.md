---
status: testing
phase: 06-pipeline-integration
source: [06-01-SUMMARY.md, 06-02-SUMMARY.md]
started: 2026-04-03T00:00:00Z
updated: 2026-04-03T00:00:00Z
---

## Current Test

number: 1
name: fn='render' produces a US HBS report
expected: |
  Run: `cd python-backend && python -c "import json; from lib.pipeline import LLMPipeline; p = LLMPipeline(); r = p.process({'id':'t1','fn':'render','ct':json.dumps({'study_type':'us hbs','findings':{'liver':'Normal in size and echotexture.'}})}); print(r['st']); print(r['ct'][:200])"`
  Status should be `S`. Output should contain a report with "liver" findings text preserved.
awaiting: user response

## Tests

### 1. fn='render' produces a US HBS report
expected: Run `cd python-backend && python -c "import json; from lib.pipeline import LLMPipeline; p = LLMPipeline(); r = p.process({'id':'t1','fn':'render','ct':json.dumps({'study_type':'us hbs','findings':{'liver':'Normal in size and echotexture.'}})}); print(r['st']); print(r['ct'][:200])"` — status is `S`, output contains liver findings text preserved verbatim.
result: [pending]

### 2. fn='render' produces a CT TAP composite report
expected: Run `cd python-backend && python -c "import json; from lib.pipeline import LLMPipeline; p = LLMPipeline(); r = p.process({'id':'t2','fn':'render','ct':json.dumps({'study_type':'ct tap','findings':{'lungs':'Clear.','liver':'Normal.'}})}); print(r['st']); print(r['ct'][:300])"` — status is `S`, output contains both thorax and abdomen sections.
result: [pending]

### 3. Unknown study type returns error
expected: Run `cd python-backend && python -c "import json; from lib.pipeline import LLMPipeline; p = LLMPipeline(); r = p.process({'id':'t3','fn':'render','ct':json.dumps({'study_type':'mri brain','findings':{'a':'b'}})}); print(r['st'], r['ct'])"` — status is `E`, message is "Unknown study type".
result: [pending]

### 4. fn='report' returns friendly stub error
expected: Run `cd python-backend && python -c "from lib.pipeline import LLMPipeline; p = LLMPipeline(); r = p.process({'id':'t4','fn':'report','ct':'some draft text'}); print(r['st'], r['ct'])"` — status is `E`, message contains "requires LLM connection".
result: [pending]

### 5. Standalone render demo runs
expected: Run `cd python-backend && python examples/render_demo.py` — exits 0, prints "RENDERED REPORT" header followed by a formatted US HBS radiology report.
result: [pending]

### 6. Full test suite passes
expected: Run `cd python-backend && python -m pytest tests/ -q` — all 161 tests pass, 0 failures.
result: [pending]

### 7. PIPELINE_MODE env var switching
expected: Run `cd python-backend && PIPELINE_MODE=llm python -c "import os; from lib.pipeline import LLMPipeline; p = LLMPipeline(); print(type(p).__name__, hasattr(p, '_registry'))"` — prints "LLMPipeline True".
result: [pending]

## Summary

total: 7
passed: 0
issues: 0
pending: 7
skipped: 0
blocked: 0

## Gaps

[none yet]
