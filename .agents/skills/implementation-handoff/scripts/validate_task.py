"""Validate the structural contract of an implementation handoff task."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


REQUIRED_FRONTMATTER = {
    "task_id",
    "title",
    "status",
    "created_by",
    "assigned_to",
    "depends_on",
    "feature_branch",
    "base_branch",
}

REQUIRED_HEADINGS = [
    "## Objective",
    "## Current evidence",
    "## Requirements",
    "## Interfaces and data contracts",
    "## Allowed paths",
    "## Prohibited scope",
    "## Implementation guidance",
    "## Acceptance criteria",
    "## Verification",
    "## Planner decision boundaries",
    "## Git instructions",
    "## Implementation report",
]

ALLOWED_STATUSES = {
    "draft",
    "ready",
    "in_progress",
    "blocked",
    "implemented",
    "accepted",
    "changes_requested",
}


def parse_frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        raise ValueError("Task must begin with YAML-style frontmatter between --- lines.")

    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"Invalid frontmatter line: {line!r}")
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"Cannot read {path}: {exc}"]

    try:
        fields = parse_frontmatter(text)
    except ValueError as exc:
        return [str(exc)]

    missing_fields = sorted(REQUIRED_FRONTMATTER - fields.keys())
    if missing_fields:
        errors.append("Missing frontmatter fields: " + ", ".join(missing_fields))

    status = fields.get("status")
    if status and status not in ALLOWED_STATUSES:
        errors.append(
            f"Invalid status {status!r}; expected one of: "
            + ", ".join(sorted(ALLOWED_STATUSES))
        )

    for field in REQUIRED_FRONTMATTER:
        value = fields.get(field, "")
        if value.lower() in {"", "<placeholder>", "pending", "tbd"}:
            errors.append(f"Frontmatter field {field!r} has no usable value.")

    missing_headings = [heading for heading in REQUIRED_HEADINGS if heading not in text]
    if missing_headings:
        errors.append("Missing required headings: " + ", ".join(missing_headings))

    if not re.search(r"(?m)^- \[ \] .+", text):
        errors.append("Acceptance criteria must contain at least one unchecked checklist item.")

    if "Do not push" not in text:
        errors.append("Git instructions must explicitly include 'Do not push'.")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_file", type=Path)
    args = parser.parse_args()

    errors = validate(args.task_file)
    if errors:
        print(f"INVALID: {args.task_file}")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"VALID: {args.task_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

