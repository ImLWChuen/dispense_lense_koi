---
name: implementation-handoff
description: Coordinate implementation work between a planning/review agent and a separate coding agent through repository task packets. Use this skill whenever a user asks to assign, generate, execute, continue, review, or revise an implementation task for another agent; mentions a planner/implementer workflow, Antigravity, Gemini, Codex, Claude, or another coding agent; or wants agent work performed one reviewable task at a time with local commits and controlled Git boundaries.
compatibility: Requires a shared Git repository and agents that can read Markdown files and inspect Git state. The optional validator requires Python 3.11 or later.
---

# Implementation Handoff

Coordinate two agents without relying on hidden conversation context. The repository is the shared source of truth: the planner writes a bounded task, the implementer completes and commits it locally, and the planner reviews the exact commit before releasing another task.

## Select the operating mode

Infer the mode from the requested action rather than the model's identity.

- **Planner mode:** create or revise the next task.
- **Implementer mode:** implement the one task marked `ready`.
- **Reviewer mode:** assess the implementer's commit and decide whether it is accepted or needs a correction task.

If the requested action is ambiguous, report which mode appears applicable and ask one concise question. Never combine planner and implementer work in one run: separating them keeps the implementation independently reviewable.

## Load project context

From the repository root, read these files before acting:

1. Every applicable `AGENTS.md` or equivalent repository instruction file.
2. `.agents/handoff/PROJECT.md`.
3. `.agents/handoff/QUEUE.md`.
4. The active task and any task or review it references.
5. The relevant source, configuration, documentation, and tests.

Treat filenames and proposed directory trees as weak evidence. Check file contents, working behavior, and Git history before claiming that a component exists.

If `.agents/handoff/PROJECT.md` is missing, planner mode may create it from `references/project-config-template.md`. The implementer must stop and request a planner task when essential project configuration is missing.

## Shared safety rules

- Work only on the feature branch named in `PROJECT.md`. Stop before editing if the current branch differs.
- Preserve unrelated user or teammate changes. Never clean, reset, revert, stash, or overwrite them merely to obtain a clean tree.
- Never push, merge, rebase a shared branch, force-push, create or update a pull request, or modify the base branch unless the user explicitly authorizes that exact action.
- Do not expose secrets. Do not commit environment files, credentials, tokens, private keys, build output, dependency folders, or other ignored artifacts.
- Keep one task active at a time. A correction receives its own task ID and references the reviewed task.
- Use repository-relative paths in task packets so the workflow remains portable.
- Record facts and observed command output. Do not report tests as passed unless they were run successfully during the implementation.

## Task lifecycle

Use these states:

`draft → ready → in_progress → implemented → accepted`

Exceptional states are `blocked` and `changes_requested`.

- The planner is responsible for `draft`, `ready`, `accepted`, and `changes_requested` decisions.
- The implementer may change `ready` to `in_progress`, then to `implemented` or `blocked`.
- `implemented` means the scoped work was committed locally and is ready for review. It does not mean accepted or pushed.

Record the canonical state in `.agents/handoff/QUEUE.md`. The task file contains its implementation report; the reviewer records the decision under `.agents/handoff/reviews/`.

## Planner mode

### 1. Inspect before decomposing

Read the current branch, status, recent commits, previous review, and relevant implementation. Determine what is actually working and what the next dependency is. Do not assign work based only on a planning document.

If uncommitted code changes overlap the proposed task, do not write a conflicting task. Explain the overlap and select a non-conflicting next task or wait for review.

### 2. Choose one reviewable increment

A good task has one primary outcome and normally one atomic commit. It should be small enough that the reviewer can understand the entire diff and large enough to produce testable behavior.

Prefer vertical or dependency-complete increments. Examples include defining one persisted domain contract with its tests, implementing one API operation through storage, or adding one bounded image measurement with its validation. Avoid tasks such as “build the backend” or lists of unrelated endpoints.

Do not generate a new feature task while an earlier task is `implemented` and awaiting review. If review finds a defect, write a correction task before continuing the roadmap.

### 3. Write the task packet

Copy the structure in `references/task-template.md` to:

`.agents/handoff/tasks/<task-id>-<short-name>.md`

Make every instruction executable without access to the planning conversation. Include:

- objective and user-visible or system-visible outcome;
- evidence about the current repository state;
- dependencies and relevant interfaces;
- allowed paths and prohibited scope;
- ordered implementation guidance where order matters;
- acceptance criteria stated as observable outcomes;
- exact verification commands known to exist in the repository;
- decision boundaries that require returning to the planner;
- local commit requirements and expected completion report.

Do not invent commands for an environment that has not been configured. If setup itself is the task, acceptance criteria should verify the setup and document the commands it establishes.

### 4. Validate and release

Run:

`python .agents/skills/implementation-handoff/scripts/validate_task.py <task-file>`

Resolve validation failures, set the packet status to `ready`, and update `QUEUE.md`. Leave the packet uncommitted for the implementer to include with the implementation commit unless `PROJECT.md` specifies a different handoff policy.

Tell the user the task ID, purpose, major boundaries, and the short Antigravity instruction:

`Run the next ready implementation task using the implementation-handoff skill.`

## Implementer mode

### 1. Perform preflight checks

Read the task referenced as `ready` in `QUEUE.md`. Confirm:

- the current branch matches `PROJECT.md`;
- there is exactly one ready task;
- its dependencies are accepted or otherwise satisfied;
- existing uncommitted changes are limited to handoff artifacts or explicitly acknowledged files;
- its verification commands exist, or the task explicitly creates them.

If any check fails, do not guess. Mark the task `blocked` only when editing the task packet is safe, and record the exact observed condition and the smallest decision needed.

### 2. Implement within the packet

Change the task to `in_progress`, then implement only its stated outcome. Follow repository instructions and read relevant framework documentation required by those instructions.

Make reasonable, reversible choices within the assigned contracts. Stop and report before proceeding if implementation would require any of the following unless the packet already authorizes it:

- changing architecture or public interfaces;
- redesigning the database contract;
- selecting or replacing a material dependency;
- expanding into another owner's area;
- weakening security, validation, or acceptance criteria;
- deleting or migrating data;
- broadening the task substantially.

Routine error recovery, local naming, private helper design, and test fixture details are implementer decisions when they stay within scope.

### 3. Verify honestly

Run the packet's focused checks and any repository-required checks affected by the change. Inspect the final diff, including staged files, for unintended changes and secrets.

If a required check cannot run, do not substitute “should pass.” Record the command, output summary, reason, and practical consequence. A task with an unmet acceptance criterion is `blocked`, not `implemented`, unless the packet explicitly permits that limitation.

### 4. Report and commit locally

Complete the task packet's Implementation report with:

- files changed and behavior delivered;
- decisions made within scope;
- verification commands and actual outcomes;
- limitations or follow-up considerations;
- proposed commit message.

Set the task to `implemented`, update `QUEUE.md`, stage only task-related files, and create one atomic local commit using the message format in `PROJECT.md`. Do not push it.

Finish by reporting the task ID, local commit hash, test evidence, and review concerns. If blocked, do not create a success commit; return the evidence and required decision to the planner.

## Reviewer mode

### 1. Review the exact implementation

Read the task packet, implementation report, local commit, diff, relevant contracts, and reported check output. Verify:

- all acceptance criteria are met by evidence in the commit;
- implementation stayed within allowed paths and scope;
- tests meaningfully exercise behavior rather than mirror the implementation;
- error and unknown states are handled where required;
- no secrets, generated output, or unrelated changes were committed;
- documentation and reports describe actual behavior.

The reviewer may inspect Git and files. Under a planner/reviewer-only policy, leave execution and code changes to the implementer.

### 2. Record one decision

Write `.agents/handoff/reviews/<task-id>-review.md` using the review template in `references/task-template.md`.

- **Accepted:** cite the commit and evidence for the acceptance criteria, set `QUEUE.md` to `accepted`, and then prepare the next task if requested.
- **Changes requested:** identify concrete findings with file locations and consequences, set `QUEUE.md` to `changes_requested`, and create one bounded correction task referencing the original.
- **Blocked review:** state which evidence is unavailable. Do not accept based on assumption.

Do not amend the implementer's commit or implement corrections in reviewer mode.

## Reusable project setup

For a new repository:

1. Copy this skill directory to `.agents/skills/implementation-handoff/`.
2. Copy `references/project-config-template.md` to `.agents/handoff/PROJECT.md` and fill every required field.
3. Create `.agents/handoff/tasks/` and `.agents/handoff/reviews/`.
4. Create `QUEUE.md` with no active task and the next task ID.
5. Add an Antigravity workspace workflow that invokes implementer mode.
6. Confirm both agents can see the same repository and feature branch.

Use one checkout when planner and implementer operate sequentially. Use separate Git worktrees and branches if they will edit concurrently.

## Completion standard

The handoff is successful when an unfamiliar implementation agent can complete the packet without the planning conversation, produce a bounded local commit, and give the reviewer enough evidence to accept it or request a precise correction.

