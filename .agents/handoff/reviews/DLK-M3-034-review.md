---
task_id: DLK-M3-034
reviewed_commit: 7a55e65f4f3ad3a733289393f6f5a832ba47db52
decision: accepted
reviewed_by: ChatGPT planner/reviewer
---

# Review: DLK-M3-034

## Decision

Accepted at `7a55e65f4f3ad3a733289393f6f5a832ba47db52`. The repeated-point defect is corrected and the task's bounded outline contract is met. The original finding below is retained for traceability.

## Final correction review of 7a55e65

- The helper now checks that the count of normalized distinct point keys equals the number of published points. Nonconsecutive repeats return a null outline and a specific warning. Consecutive repeats and a closing repeat are removed before the check.
- Unit regressions exercise the actual helper for nonconsecutive repeats, consecutive repeats, and closing repeats. An API regression checks that an omitted outline warning reaches both region and top-level results while DETECTED/CALIBRATED remain intact; it mocks the helper, so it is a warning-propagation test rather than a second geometry test.
- Changes stay within allowed paths, preserve diagnostic classification and numeric measurements, and synchronize the queue with the task report. The committed diff has no whitespace errors.
- Gemini reports 52 focused tests and 543 backend tests passed, plus task validator VALID. The reviewer inspected the implementation and test code but did not independently rerun tests under the PROJECT.md role split.
- Documentation follow-up: the task report says contours with self-intersections are safely omitted. The code detects repeated vertices, not every geometrically self-intersecting polygon. Correct that sentence during the next task report/documentation touch; this overstatement does not block the distinct-vertex contract delivered here.

## Finding R1 — P2: Nonconsecutive duplicate vertices are published

Location: `backend/app/services/vision/overlay.py:113-146`.

The helper removes only consecutive duplicate points and a duplicate closing point. Its final `distinct_set` check requires merely **three** unique points, not that every returned point be unique. For example, a five-point contour with `[A, B, C, A, D]` passes and returns both copies of A. The public contract in this task says every emitted polygon contains 3–128 **distinct** points. Repeated nonconsecutive points can also make the displayed path self-touch or look like two loops.

Reject an outline containing any nonconsecutive duplicate vertex after normalization and return a specific overlay warning, or use a geometry-preserving normalization that demonstrably yields one valid ordered outer polygon. Do not silently delete a repeated vertex if doing so changes the contour's shape. Keep DETECTED status and diagnostic observations unchanged when an outline is omitted. Add a unit regression with at least three unique points and one nonconsecutive repeat; verify null outline and warning (or a validated single polygon). Retain existing point-cap, offset, and real-image API checks.

## Evidence reviewed

- Exact commit `6782ca0db0fb3c889686658fa248dcea8d6019f7` on `backend-database`; diff is confined to the task's allowed paths and includes the accepted DLK-M3-033 review.
- The API adds geometry only for current-image regions and propagates unavailable-overlay warnings to the top-level response.
- MISSING/UNASSESSED regions are filtered before contour processing; current numeric measurements and classifier logic were not changed.
- Tests cover nonzero window offset, resolution scaling, point cap, missing/unassessed, invalid simple contours, and a real off-center synthetic image.
- Gemini reports 48 focused tests, 539 backend tests, and task validator VALID. Reviewer inspected the code/tests and verified the committed whitespace diff; tests were not independently rerun under the PROJECT.md role split.
- The implementation report says QUEUE.md was set to implemented, but the committed queue still says `in_progress`. This review sets the queue to `changes_requested`; Gemini should synchronize the lifecycle entry with its next correction commit.

## Follow-up

R1 is resolved. No further DLK-M3-034 correction is required. Carry the limited documentation clarification above into the next task, alongside the deferred frontend overlay work. No new feature task was generated. No push, merge, PR, or change to main is authorized by this review request.
