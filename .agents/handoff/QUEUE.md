# Implementation Queue

## Current milestone

Troubleshooting-check workflow closeout

## Review state

- `DLK-M3-013` — Check-result semantic closeout and durable troubleshooting-check result API — **changes_requested**
  - reviewed commit: `5e7cb8270762f0e0c06a0c994a0fa424f16f9c2a`
  - review: `.agents/handoff/reviews/DLK-M3-013-review.md`
  - unfinished-state rejection resolved by DLK-M3-014; remaining verification closeout is DLK-M3-015

## Changes requested

- `DLK-M3-014` — Troubleshooting-check result closeout — **changes_requested**
  - reviewed commit: `0e220344f9e96fa40a5443db9f72e9cfa5fb5ce5`
  - review: `.agents/handoff/reviews/DLK-M3-014-review.md`
  - remaining correction: assert pending-write evidence outside the handled request and compare complete preserved state
  - task: `.agents/handoff/tasks/DLK-M3-014-check-result-closeout.md`
  - branch: `backend-database`
  - depends on: `DLK-M3-013`

## Not released

Blocked until DLK-M3-015 is accepted and closes the prior review chain:

- explicit cause-confirmation persistence/API
- issue recovery verification
- report generation
- image/CV integration
- LLM integration
- historical-case retrieval
- frontend check-result integration

## Ready

- `DLK-M3-015` — Check-result verification closeout — **implemented**
  - task: `.agents/handoff/tasks/DLK-M3-015-check-result-verification-closeout.md`
  - branch: `backend-database`
  - depends on: DLK-M3-014 implementation at `0e220344f9e96fa40a5443db9f72e9cfa5fb5ce5`; acceptance is not a prerequisite for this correction

Only DLK-M3-015 is authorized for implementation.
