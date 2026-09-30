---
task_id: DLK-M3-034
reviewed_commit: 6782ca0db0fb3c889686658fa248dcea8d6019f7
decision: changes_requested
reviewed_by: ChatGPT planner/reviewer
---

# Review: DLK-M3-034

## Decision

Changes requested. The core outline path is in place, but the final polygon validity check does not enforce the task's requirement that all published points be distinct. One bounded correction is needed before dependent overlay work.

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

Correct R1 in this task's scope, update the implementation report and queue, run the focused and full checks, and commit locally. No new feature task was generated. No push, merge, PR, or change to main is authorized by this review request.
