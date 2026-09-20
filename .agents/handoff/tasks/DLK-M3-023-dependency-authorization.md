# DLK-M3-023 Dependency Authorization

## Planner decision

DLK-M3-023 may resume. No replacement task is required.

Authorized dependencies:

- Production PDF renderer: `reportlab==5.0.1`
- PDF parser / extraction verifier: `pypdf==6.18.1`

If the repository separates runtime and test/dev dependencies, keep `pypdf` test/dev-only.
If the repository has a single backend dependency manifest, add both there but do not import `pypdf` from production application code.

Follow the repository's existing dependency/lock-file convention. Do not introduce a second package manager or new manifest format.

## Why these dependencies

### ReportLab 5.0.1

Authorized for production PDF generation.

Use only its standard Python PDF-generation capability required by this task. Do not add optional rendering extras unless separately authorized.

DLK-M3-023 must continue to render exclusively from the accepted DLK-M3-022 pinned report model.

### pypdf 6.18.1

Authorized for test verification of:

- PDF parseability;
- page count;
- extracted case/revision text;
- required section headings;
- rich-history content.

It is not a second renderer and must not become part of the production report-data path.

## Explicitly not selected

Do not use WeasyPrint for DLK-M3-023.

Do not add native rendering binaries or system packages.

Do not add another PDF renderer/parser without returning to the planner.

## Scope now authorized

Gemini may edit the existing dependency manifest and lock file(s) only as required to add the two authorized packages, in addition to the paths already permitted by DLK-M3-023.

No database migration or schema change is authorized.

No new report persistence is authorized.

## Resume requirements

Continue the existing task:

`DLK-M3-023 - Deterministic downloadable PDF case report`

Implement:

`GET /api/v1/cases/{case_id}/report.pdf`

Preserve all original DLK-M3-023 acceptance criteria, especially:

- reuse the DLK-M3-022 pinned report model;
- no diagnostic recalculation;
- no independent report-data path;
- no durable mutation;
- deterministic logical content;
- concurrent-write consistency;
- sanitized failure behavior;
- parseable PDF;
- multi-page handling;
- read-only proof.

## Required dependency verification

Record:

- exact dependency files changed;
- installed/resolved versions;
- ReportLab import/version check;
- pypdf import/version check;
- whether pypdf is runtime or test/dev only under the repository's existing convention.

Then run the full verification required by DLK-M3-023.

## Git boundary

After implementation and all tests pass, create the originally required single local implementation commit:

`feat(api): add downloadable PDF case report`

Do not push, merge, rebase, create/update a PR, or modify `main`.
