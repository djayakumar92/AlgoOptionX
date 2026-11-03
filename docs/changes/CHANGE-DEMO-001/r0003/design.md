# Evidence packaging design amendment

All visual/interaction wireframes, chart definitions and acceptance cases from
revision 2 remain unchanged. Add only backward-compatible decoding of a native
per-case area bundle in ui_execution.py. The bundle contains case_id and an areas
mapping whose keys exactly match the frozen case checks. Each nested body retains
its case_id, area, status and optional measurements; reject any mismatch.

Each actual Playwright test appends run-contained attachment references to the
already generated file for its case. The test writes one measured profile file
per identical content hash; compare bytes on collision. Screenshots and comparison
reports remain separate and individually hashed. Native report outcome, source,
approval, secure-reader, file-count/size, screenshot and performance checks remain
fully enforced. No validator cap or public design/approval schema changes.

Additional source: src/algooptionx_harness/ui_execution.py and
 tests/control_plane/test_ui_execution.py. Existing approved demo test and guide
paths hold the attachment producer and reproducibility notes. Rollback only this
packed-report support/producer; preserve prior flat compatibility and all history.
