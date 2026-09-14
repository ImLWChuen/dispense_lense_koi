---
task_id: DLK-M3-003
title: Accept completed handoff checklists
status: implemented
created_by: ChatGPT planner
assigned_to: Gemini implementer
depends_on: [DLK-M3-002]
feature_branch: cskee-branch
base_branch: main
---

# DLK-M3-003: Accept completed handoff checklists

## Objective

Correct the implementation-handoff validator so a task packet remains structurally valid after its acceptance checklist has been completed. The validator must continue requiring at least one checklist item, while accepting unchecked, checked, or mixed checklist states.

## Current evidence

DLK-M3-002 is accepted at commit `b825500cdd4253bcbc302ac6c3baad4114bcafa3`, and its review identifies this validator defect. The current regular expression in `.agents/skills/implementation-handoff/scripts/validate_task.py` only recognizes lines beginning with `- [ ]`. As a result, changing every acceptance item to `- [x]` makes an otherwise complete task invalid and forced the prior implementation report to leave completed criteria visually unchecked.

Existing tests in `.agents/skills/implementation-handoff/tests/test_validate_task.py` cover a valid unchecked checklist, missing headings, invalid status, and the no-push rule. They do not cover completed or absent acceptance checklists. The current branch is `cskee-branch`; it tracks `origin/cskee-branch`. The only expected uncommitted planner changes at release are this packet and `QUEUE.md`.

This tooling correction is independent of teammate product branches. `origin/main` contains Member 1's frontend work. Member 2's candidate diagnosis engine is present at `origin/ai-diagnosis-engine` but is not merged into `main`; do not integrate or modify either teammate's work in this task.

## Requirements

- Treat `- [ ]`, `- [x]`, and `- [X]` as valid acceptance checklist items.
- Require at least one checklist item under the `## Acceptance criteria` section. Checklist-looking lines elsewhere in the packet must not satisfy this requirement.
- Preserve all existing frontmatter, heading, status, and explicit `Do not push` validation behavior.
- Change the validation message so it describes a required checklist item without incorrectly requiring an unchecked item.
- Add focused regression tests proving that a fully checked checklist is accepted and that a packet without an acceptance checklist is rejected.
- Add a boundary test proving that a checklist item outside the acceptance section does not satisfy the acceptance requirement.

## Interfaces and data contracts

The public Python interface remains `validate(path: Path) -> list[str]`, and the command-line exit behavior remains unchanged: exit `0` with `VALID:` for a valid packet and exit `1` with `INVALID:` plus errors for an invalid packet. This task changes only what counts as a structurally present acceptance checklist.

## Allowed paths

- `.agents/skills/implementation-handoff/scripts/validate_task.py`
- `.agents/skills/implementation-handoff/tests/test_validate_task.py`
- `.agents/skills/implementation-handoff/references/task-template.md` only if wording must be clarified to match the corrected validator
- `.agents/handoff/QUEUE.md`
- `.agents/handoff/tasks/DLK-M3-003-accept-completed-checklists.md`

## Prohibited scope

- Do not change backend or frontend product code, dependencies, product contracts, diagnostic knowledge, scoring logic, or teammate branches.
- Do not redesign task lifecycle states or add a new parser/dependency for this bounded correction.
- Do not edit previous task packets or review records.
- Do not merge, rebase, pull teammate changes, push, update a pull request, or modify `main`.

## Implementation guidance

1. Perform the implementation-handoff preflight checks and change this packet and `QUEUE.md` to `in_progress` before editing the validator.
2. Scope checklist detection to the text between `## Acceptance criteria` and the next level-two heading. A small private helper or bounded regular expression is sufficient; do not add a Markdown parser dependency.
3. Recognize both unchecked and checked checkbox markers case-insensitively for `x`.
4. Add focused unit tests using the existing `VALID_TASK` fixture and `validate_text` helper. Ensure the negative test removes the checklist only from the acceptance section.
5. Run the focused validator tests, all implementation-handoff skill tests, validate this task packet after checking its completed criteria, then inspect the staged diff before the local commit.

## Acceptance criteria

- [x] A packet whose acceptance section contains only `- [x]` or `- [X]` items validates successfully.
- [x] A packet with an unchecked acceptance item continues to validate successfully.
- [x] A packet with no checklist item in its acceptance section fails with an accurate checklist-related error.
- [x] A checklist item outside the acceptance section cannot make an empty acceptance section valid.
- [x] Existing frontmatter, required-heading, status, and no-push validation tests continue to pass.
- [x] The completed DLK-M3-003 packet validates after Gemini marks these acceptance items checked.
- [x] The commit contains only the allowed task, queue, validator, test, and any necessary template clarification files.

## Verification

Run from the repository root:

1. `python -m unittest discover -s .agents/skills/implementation-handoff/tests -p "test_validate_task.py"`
2. `python -m unittest discover -s .agents/skills/implementation-handoff/tests -p "test_*.py"`
3. `python .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-003-accept-completed-checklists.md`
4. `git diff --check`
5. Inspect `git status --short`, the staged file list, and the staged diff before committing.

## Planner decision boundaries

Return to the planner before changing the task format, lifecycle, public validator interface, dependency set, repository ownership rules, or any product code. Routine regex/helper design and test fixture construction are implementer decisions within this task.

## Git instructions

Create one atomic local commit after all checks pass. Include this task packet and `QUEUE.md` with the implementation. Do not push, merge, rebase a shared branch, create or update a pull request, or change `main`.

Proposed commit message: `fix(handoff): accept completed checklists`

## Implementation report

### Summary

Corrected the implementation-handoff validator so task packets remain structurally valid when acceptance criteria are completed (`- [x]` or `- [X]`), unchecked (`- [ ]`), or mixed. Scoped checklist item detection strictly to the `## Acceptance criteria` section, updated the validation error message to accurately require a checklist item rather than specifically an unchecked one, and added regression and boundary unit tests.

### Files changed

- `.agents/skills/implementation-handoff/scripts/validate_task.py`: Added private helper `_has_acceptance_checklist` scoping checklist detection to the `## Acceptance criteria` section (before the next level-two heading) and accepting `- [ ]`, `- [x]`, and `- [X]` checklist markers. Updated error message to `"Acceptance criteria must contain at least one checklist item."`.
- `.agents/skills/implementation-handoff/tests/test_validate_task.py`: Added `test_accepts_fully_checked_checklist`, `test_rejects_missing_acceptance_checklist`, and `test_rejects_checklist_item_outside_acceptance_section`.
- `.agents/handoff/QUEUE.md`: Updated active task status to `implemented`.
- `.agents/handoff/tasks/DLK-M3-003-accept-completed-checklists.md`: Marked status as `implemented`, checked off completed acceptance items, and completed implementation report.

### Decisions made

- Section-Scoped Parsing: Scoped checklist detection using regex `r"(?ms)^## Acceptance criteria\s*\n(.*?)(?=^## |\Z)"` to extract the acceptance section content, ensuring checklist items in other sections (e.g. `## Requirements`) cannot satisfy the acceptance criteria requirement.
- Case-Insensitive Checkbox Detection: Recognized checklist items using regex `r"(?m)^- \[[ xX]\] .+"` covering `- [ ]`, `- [x]`, and `- [X]`.
- Minimal Dependencies: Avoided introducing external Markdown parsing libraries, maintaining standalone compatibility with standard library `re` and `pathlib`.

### Verification results

1. Focused validator test suite:
   Command: `python -m unittest discover -s .agents/skills/implementation-handoff/tests -p "test_validate_task.py"`
   Result: `Ran 7 tests in 0.044s - OK` (Exit code 0).
2. Complete skill test suite:
   Command: `python -m unittest discover -s .agents/skills/implementation-handoff/tests -p "test_*.py"`
   Result: `Ran 11 tests in 0.024s - OK` (Exit code 0).
3. Self-validation of completed packet with checked criteria:
   Command: `python .agents/skills/implementation-handoff/scripts/validate_task.py .agents/handoff/tasks/DLK-M3-003-accept-completed-checklists.md`
   Result: `VALID: .agents\handoff\tasks\DLK-M3-003-accept-completed-checklists.md` (Exit code 0).
4. Formatting and whitespace verification:
   Command: `git diff --check`
   Result: Clean, no whitespace or formatting errors.

### Limitations and follow-up

- Validator now supports standard GitHub-flavored task checklist items (`- [ ]`, `- [x]`, `- [X]`) within the acceptance section.
- Future product tasks can now mark completed criteria without failing structural handoff validation.

### Proposed commit message

`fix(handoff): accept completed checklists`
