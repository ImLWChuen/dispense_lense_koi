from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "validate_task.py"
SPEC = importlib.util.spec_from_file_location("validate_task", SCRIPT_PATH)
assert SPEC and SPEC.loader
VALIDATE_TASK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATE_TASK)


VALID_TASK = """---
task_id: SAMPLE-001
title: Add a bounded example
status: ready
created_by: planner
assigned_to: implementer
depends_on: []
feature_branch: feature/sample
base_branch: main
---

# SAMPLE-001: Add a bounded example

## Objective
Deliver one observable outcome.

## Current evidence
The relevant component has been inspected.

## Requirements
- Preserve existing behavior.

## Interfaces and data contracts
None.

## Allowed paths
- `src/example.py`

## Prohibited scope
- Unrelated files.

## Implementation guidance
1. Implement the smallest complete behavior.

## Acceptance criteria
- [ ] The behavior is covered by a focused test.

## Verification
1. `python -m unittest`

## Planner decision boundaries
Return material contract changes to the planner.

## Git instructions
Create one local commit. Do not push, merge, or modify main.

## Implementation report
Pending until implementation.
"""


class ValidateTaskTests(unittest.TestCase):
    def validate_text(self, text: str) -> list[str]:
        with tempfile.TemporaryDirectory() as temp_directory:
            path = Path(temp_directory) / "task.md"
            path.write_text(text, encoding="utf-8")
            return VALIDATE_TASK.validate(path)

    def test_accepts_complete_task_packet(self) -> None:
        self.assertEqual(self.validate_text(VALID_TASK), [])

    def test_rejects_missing_required_heading(self) -> None:
        task = VALID_TASK.replace("## Current evidence", "## Repository notes")

        errors = self.validate_text(task)

        self.assertTrue(any("## Current evidence" in error for error in errors))

    def test_rejects_unknown_status(self) -> None:
        task = VALID_TASK.replace("status: ready", "status: finished")

        errors = self.validate_text(task)

        self.assertTrue(any("Invalid status" in error for error in errors))

    def test_rejects_task_without_explicit_no_push_rule(self) -> None:
        task = VALID_TASK.replace("Do not push", "Remote actions are unspecified")

        errors = self.validate_text(task)

        self.assertTrue(any("Do not push" in error for error in errors))

    def test_accepts_fully_checked_checklist(self) -> None:
        task = VALID_TASK.replace(
            "- [ ] The behavior is covered by a focused test.",
            "- [x] The behavior is covered by a focused test.\n- [X] Upper-case checked item.",
        )

        self.assertEqual(self.validate_text(task), [])

    def test_rejects_missing_acceptance_checklist(self) -> None:
        task = VALID_TASK.replace(
            "- [ ] The behavior is covered by a focused test.",
            "No checklist items are present.",
        )

        errors = self.validate_text(task)

        self.assertTrue(
            any(
                "Acceptance criteria must contain at least one checklist item." in error
                for error in errors
            )
        )

    def test_rejects_checklist_item_outside_acceptance_section(self) -> None:
        task = VALID_TASK.replace(
            "## Requirements\n- Preserve existing behavior.",
            "## Requirements\n- [x] Preserve existing behavior.",
        ).replace(
            "- [ ] The behavior is covered by a focused test.",
            "Acceptance criteria provided in prose without checklist items.",
        )

        errors = self.validate_text(task)

        self.assertTrue(
            any(
                "Acceptance criteria must contain at least one checklist item." in error
                for error in errors
            )
        )


if __name__ == "__main__":
    unittest.main()

