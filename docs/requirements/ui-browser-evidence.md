# Native browser evidence execution bindings

## UXRUN-01 — execute and collect
Use the existing native runner's passing Playwright result/report. Frozen design
case IDs are the exact spec titles `UI::CASE-ID` in that report. A case must have
one test/result, expectedStatus passed, no retries, no unexpected outcome and no
errors. Its attachments include ui-context JSON with exact renderer, fixture,
viewport and theme; and one ui-AREA JSON report for each required validation area.
Visual reports also attach ui-screenshot and ui-comparison artifacts. Performance
reports supply actual measurements matching approved budget IDs and samples.
No extra, duplicated, omitted or nonpassing cases become passing UI evidence.
All attachments must be contained regular non-symlink files in the native run's
report directory; byte hashes and source/task/report bindings are retained.

## UXRUN-02 — gate and collect share one verification
Closure rederives the case matrix from the referenced native browser report and
compares it with the UIValidationEvidence record. Supplying hand-written case
results unrelated to that executed report cannot satisfy the gate. The collector
writes only a new exclusive .harness JSON output after source/native evidence and
frozen design verification. Native UI approval remains separately verified at
closure. A collector result is evidence, not human acceptance or release.

Local coherent fabrication is not authenticated execution provenance. Browser
assertions and report contents must be independently reviewed; screenshot capture
is not design approval or WCAG certification. Candidate screenshots never become
approved by CI regeneration. Renderer, fixture or case changes require review of
a new design revision, task recapture and fresh source-bound execution.

## Grouped preimplementation review
Native `chat.request_group` may present plan, architecture, UI (when applicable)
and implementation as one frozen proposal. Every existing stage retains its own
request ID and source/task binding; one actual explicit reply is recorded for all
using `record_group`. The group has one exact requested timestamp, one exact
recorded timestamp, identical task/source/summary, recorded operator and actual
message. The verifier permits overlapping timestamps only for that exact group.
QA/release cannot join it; normal separate-request chronology remains strict.
This avoids redundant prompts without dropping stages, fabricating decisions,
changing signed-external gates or granting any additional authority. Any changed
source/task requires a new reviewed group; an old reply cannot approve it.
