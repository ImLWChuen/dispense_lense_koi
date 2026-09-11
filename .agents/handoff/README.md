# Planner-to-implementer handoff

This directory coordinates sequential work between ChatGPT in Codex and Gemini in Antigravity.

## Everyday cycle

1. In ChatGPT, ask: `Create the next Gemini implementation task.`
2. Review the generated task under `tasks/` and its entry in `QUEUE.md`.
3. In Antigravity, run the workspace workflow `/implement-next-task`. If the workflow is not shown, use: `Run the next ready implementation task using the implementation-handoff skill.`
4. Gemini implements, verifies, updates the task report, and creates one local commit.
5. Return to ChatGPT and ask: `Review Gemini's completed task and local commit.`
6. ChatGPT either accepts it and prepares the next task or creates a bounded correction task.

The detailed task does not need to be copied between applications because both agents use this repository as the same workspace.

## Files

- `PROJECT.md` records project-specific roles, branch policy, commands, and decision boundaries.
- `QUEUE.md` identifies the one current task.
- `tasks/` contains planner-authored task packets and Gemini's implementation reports.
- `reviews/` contains ChatGPT's review decisions.
- `../skills/implementation-handoff/` contains the reusable cross-project workflow.

## Git boundary

Gemini may create atomic local commits on the configured feature branch after successful verification. Neither agent may push, merge, create a pull request, or modify the base branch without explicit human authorization.
