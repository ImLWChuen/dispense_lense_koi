# Task and review templates

## Task packet

Copy this template without removing required headings. Replace every placeholder; use `None` only when it is a meaningful, reviewed value.

```markdown
---
task_id: PROJECT-AREA-001
title: Concise outcome
status: draft
created_by: planner
assigned_to: implementer
depends_on: []
feature_branch: feature-branch
base_branch: main
---

# PROJECT-AREA-001: Concise outcome

## Objective

Describe one observable outcome and why it is the next dependency.

## Current evidence

List inspected files, current behavior, and relevant prior commit or review. Distinguish verified facts from planning assumptions.

## Requirements

- Required behavior or contract.
- Required error or unknown-state behavior.

## Interfaces and data contracts

Document inputs, outputs, persistence effects, ownership boundaries, and compatibility requirements. Write `None` only when this task has no interface effect.

## Allowed paths

- `path/that/may/change`

## Prohibited scope

- Work that belongs to later tasks or other owners.
- Remote Git operations and changes to the base branch.

## Implementation guidance

1. Ordered guidance where sequencing matters.
2. Leave private implementation details to the implementer.

## Acceptance criteria

- [ ] Observable criterion with an objective pass condition.
- [ ] Error, unknown, or boundary behavior where relevant.
- [ ] No unrelated files changed.

## Verification

Run from the stated directory:

1. `existing focused command`
2. `existing broader command`, when justified

## Planner decision boundaries

Return to the planner before changing architecture, public interfaces, database contracts, dependencies, ownership boundaries, security requirements, or task scope unless explicitly authorized above.

## Git instructions

Create one atomic local commit after all required checks pass. Do not push, merge, rebase a shared branch, create a pull request, or change the base branch.

Proposed commit message: `type(scope): explain the outcome`

## Implementation report

Complete this section before the local commit.

### Summary

Pending.

### Files changed

Pending.

### Decisions made

Pending.

### Verification results

Pending.

### Limitations and follow-up

Pending.

### Proposed commit message

Pending. Record the resulting commit hash in the Antigravity completion message; a commit cannot contain its own final hash.
```

## Review record

```markdown
---
task_id: PROJECT-AREA-001
reviewed_commit: abc1234
decision: accepted
reviewed_by: planner
---

# Review: PROJECT-AREA-001

## Decision

Accepted | Changes requested | Blocked review

## Acceptance evidence

Map each acceptance criterion to code, test, or recorded command evidence.

## Findings

List actionable findings with file locations and consequences. Write `None` for an accepted task with no findings.

## Follow-up

Name the correction task or next dependency. State that remote Git operations remain unauthorized unless the user explicitly changes that instruction.
```
