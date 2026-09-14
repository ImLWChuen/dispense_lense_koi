# Implementation Queue

## Current milestone

Adaptive investigation — durable troubleshooting-check result workflow

## Accepted prerequisites

- `DLK-M3-010` — durable case API closeout — **accepted**
- `DLK-M3-011` — question-answer persistence and immutable revision append — **accepted**

- `DLK-M3-012` — technician question-answer submission API — **accepted**
  - accepted commit: `17756205b7299037b5c23a6b97209ac5f594f749`
  - review: `.agents/handoff/reviews/DLK-M3-012-review.md`

Member 2's merged check-result implementation has passed the major readiness checks for execution/finding separation, explicit cause confirmation, and non-executed/inconclusive handling. DLK-M3-013 contains a tightly bounded planner-approved semantic closeout for the remaining ACT03 mapping defect and semantic-test import namespace issue before the API phase may begin.

## Ready

- `DLK-M3-013` — Check-result semantic closeout and durable troubleshooting-check result API — **implemented**
  - task: `.agents/handoff/tasks/DLK-M3-013-troubleshooting-check-result-api.md`
  - branch: `backend-database`
  - depends on: `DLK-M3-012`
  - Phase B is gated on all Phase A semantic suites passing

## Not released

Blocked until DLK-M3-013 is implemented and accepted:

- explicit cause-confirmation API and durable confirmation record
- issue recovery / verification API
- corrective-action / recovery workflow
- report generation
- image/CV integration
- LLM integration
- historical-case retrieval
- frontend check-result integration

Only DLK-M3-013 is authorized for implementation.
