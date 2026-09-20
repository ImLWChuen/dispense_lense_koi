# Dispense Lens - Database Entity-Relationship Specification

## Overview

Dispense Lens uses PostgreSQL with SQLAlchemy 2.x and Alembic migrations for relational persistence.
Schema evolution is strictly governed by Alembic (`backend/alembic/versions/`).

The persistence foundation establishes relational storage for:
1. **Diagnostic cases** (`cases`);
2. **Structured observations with provenance** (`case_observations`);
3. **Append-only immutable analysis revisions** (`analysis_revisions`);
4. **Technician question-answer history** (`case_question_answers`, added in DLK-M3-011);
5. **Technician troubleshooting check-result history** (`case_check_results`, added in DLK-M3-013);
6. **Technician root-cause confirmation history** (`case_cause_confirmations`, added in DLK-M3-017);
7. **Technician lifecycle transition events** (`case_lifecycle_events`, added in DLK-M3-019).

---

## Entity Relationship Diagram

```mermaid
erDiagram
    CASES ||--o{ CASE_OBSERVATIONS : "has"
    CASES ||--o{ ANALYSIS_REVISIONS : "has"
    CASES ||--o{ CASE_QUESTION_ANSWERS : "has"
    CASES ||--o{ CASE_CHECK_RESULTS : "has"
    CASES ||--o{ CASE_CAUSE_CONFIRMATIONS : "has"
    CASES ||--o{ CASE_LIFECYCLE_EVENTS : "has"

    CASES {
        uuid case_id PK "UUID-compatible identifier"
        text description "Original technician description"
        text material "Dispensing fluid material"
        text method "Dispensing method"
        jsonb machine_context "Equipment parameters"
        varchar defect_code "Identified defect category"
        text defect_name "Defect title"
        varchar issue_condition "Lifecycle condition"
        timestamptz created_at "Timezone-aware creation timestamp"
    }

    CASE_OBSERVATIONS {
        serial id PK "Surrogate primary key"
        uuid case_id FK "Owning case reference"
        text observation_id "Domain observation identifier"
        varchar observation_type "Observation category"
        text value "Normalized observation value"
        text original_text "Extracted source phrasing"
        varchar statement_type "Statement category"
        varchar source "Provenance source"
        float confidence "Confidence score"
        timestamptz created_at "Timezone-aware timestamp"
        int first_seen_revision "First revision introducing observation"
    }

    ANALYSIS_REVISIONS {
        serial id PK "Surrogate primary key"
        uuid case_id FK "Owning case reference"
        int revision_number "1-based sequence number"
        timestamptz analyzed_at "Timezone-aware analysis timestamp"
        varchar defect_code "Defect code at revision"
        varchar issue_condition "Issue condition at revision"
        jsonb result_snapshot "Complete immutable DiagnosisResult snapshot"
    }

    CASE_QUESTION_ANSWERS {
        serial id PK "Surrogate primary key"
        uuid case_id FK "Owning case reference"
        text question_id "Diagnostic question identifier"
        text answer_value "Normalized answer value"
        text answer_text "Technician clarifying text"
        varchar source "Provenance source"
        timestamptz answered_at "Timezone-aware timestamp"
        int resulting_revision_number "Analysis revision created from answer"
    }

    CASE_CHECK_RESULTS {
        serial id PK "Surrogate primary key"
        uuid case_id FK "Owning case reference"
        text check_id "Troubleshooting check identifier"
        varchar execution_status "Execution state"
        varchar finding "Finding outcome category"
        text finding_details "Technician observations/details"
        text outcome "Action-planner outcome key"
        varchar source "Provenance source"
        timestamptz checked_at "Timezone-aware timestamp"
        int resulting_revision_number "Analysis revision created from check"
    }

    CASE_CAUSE_CONFIRMATIONS {
        serial id PK "Surrogate primary key"
        uuid case_id FK "Owning case reference"
        text cause_id "Confirmed root cause identifier"
        varchar confirmed_by "Technician identifier or role"
        text notes "Optional technician notes"
        timestamptz confirmed_at "Timezone-aware timestamp"
        int resulting_revision_number "Analysis revision created from confirmation"
    }

    CASE_LIFECYCLE_EVENTS {
        serial id PK "Surrogate primary key"
        uuid case_id FK "Owning case reference"
        varchar event_type "Lifecycle event type"
        varchar prior_issue_condition "Issue condition before event"
        varchar resulting_issue_condition "Issue condition after event"
        int resulting_revision_number "Analysis revision created from event"
        varchar actor "Actor applying action or verification"
        text details "Action or verification details"
        boolean verification_passed "Verification outcome flag"
        timestamptz created_at "Timezone-aware creation timestamp"
    }
```

---

## Table Schemas & Constraints

### 1. `cases`
Stores the top-level investigation record.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `case_id` | `UUID` | No | Primary key, preserving the domain UUID string. |
| `description` | `TEXT` | No | Technician's natural-language symptom description. |
| `material` | `TEXT` | Yes | Dispensing fluid name / chemistry (unrestricted domain string). |
| `method` | `TEXT` | Yes | Dispensing method (e.g. `time_pressure`, `jetting`) (unrestricted domain string). |
| `machine_context` | `JSONB` | Yes | Machine telemetry, parameters, and equipment details. |
| `defect_code` | `VARCHAR(64)` | Yes | Enum-backed defect code (e.g. `D03_INCONSISTENT_SIZE`). |
| `defect_name` | `TEXT` | Yes | Defect title (unrestricted domain string). |
| `issue_condition` | `VARCHAR(64)` | No | State: `UNRESOLVED`, `RECOVERY_PENDING_VERIFICATION`, `RESOLVED`, `RECURRED`. |
| `created_at` | `TIMESTAMPTZ` | No | Timezone-aware case creation timestamp. |

**Constraints:**
- Primary Key: `pk_cases` (`case_id`)

---

### 2. `case_observations`
Stores individual structured observations extracted from user descriptions or provided directly, retaining provenance.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `SERIAL` | No | Surrogate integer primary key. |
| `case_id` | `UUID` | No | Foreign key referencing `cases.case_id`. |
| `observation_id` | `TEXT` | No | Domain observation identifier (unrestricted domain string). |
| `observation_type` | `VARCHAR(64)` | No | Enum-backed category (e.g. `runtime_pattern`, `deposit_size`). |
| `value` | `TEXT` | No | Normalized value (unrestricted domain string). |
| `original_text` | `TEXT` | Yes | Verbatim phrasing from technician or user input. |
| `statement_type` | `VARCHAR(64)` | No | Enum-backed: `USER_OBSERVATION`, `USER_INTERPRETATION`, `AI_INFERENCE`. |
| `source` | `VARCHAR(64)` | No | Enum-backed provenance: `USER`, `MEASUREMENT`, `IMAGE`, `SYSTEM`, `HISTORICAL_CASE`. |
| `confidence` | `FLOAT` | Yes | Optional inference confidence score. |
| `created_at` | `TIMESTAMPTZ` | No | Timezone-aware timestamp. |
| `first_seen_revision` | `INTEGER` | No | The analysis revision number where this observation first appeared (default `1`). |

**Constraints:**
- Primary Key: `pk_case_observations` (`id`)
- Foreign Key: `fk_case_observations_case_id_cases` (`case_id` -> `cases.case_id` `ON DELETE CASCADE`)
- Unique Constraint: `uq_case_observations_case_id_obs_id` (`case_id`, `observation_id`)
- Check Constraint: `ck_case_observations_first_seen_rev_pos` (`first_seen_revision > 0`)
- Index: `ix_case_observations_case_id` (`case_id`)

---

### 3. `analysis_revisions`
Stores append-only, immutable diagnostic evaluation snapshots.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `SERIAL` | No | Surrogate integer primary key. |
| `case_id` | `UUID` | No | Foreign key referencing `cases.case_id`. |
| `revision_number` | `INTEGER` | No | 1-based revision sequence number. |
| `analyzed_at` | `TIMESTAMPTZ` | No | Timezone-aware timestamp of analysis pass. |
| `defect_code` | `VARCHAR(64)` | Yes | Defect code assessed at this revision. |
| `issue_condition` | `VARCHAR(64)` | No | Condition state at this revision. |
| `result_snapshot` | `JSONB` | No | Complete immutable `DiagnosisResult` serialized via `model_dump(mode="json")`. |

**Constraints:**
- Primary Key: `pk_analysis_revisions` (`id`)
- Foreign Key: `fk_analysis_revisions_case_id_cases` (`case_id` -> `cases.case_id` `ON DELETE CASCADE`)
- Unique Constraint: `uq_analysis_revisions_case_id_revision_number` (`case_id`, `revision_number`)
- Check Constraint: `ck_analysis_revisions_revision_number_pos` (`revision_number > 0`)
- Index: `ix_analysis_revisions_case_id` (`case_id`)

---

### 4. `case_question_answers`
Stores technician responses to diagnostic questions associated with diagnostic revisions.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `SERIAL` | No | Surrogate integer primary key. |
| `case_id` | `UUID` | No | Foreign key referencing `cases.case_id`. |
| `question_id` | `TEXT` | No | Diagnostic question identifier (unrestricted domain text). |
| `answer_value` | `TEXT` | No | Normalized answer value (unrestricted domain text, e.g. `after_prolonged_operation`, `YES`, `UNKNOWN`). |
| `answer_text` | `TEXT` | Yes | Technician clarifying comments or verbatim notes. |
| `source` | `VARCHAR(64)` | No | Provenance source (e.g. `USER`). |
| `answered_at` | `TIMESTAMPTZ` | No | Timezone-aware timestamp of the answer submission. |
| `resulting_revision_number` | `INTEGER` | No | Analysis revision number produced by this answer event (> 1). |

**Constraints:**
- Primary Key: `pk_case_question_answers` (`id`)
- Foreign Key: `fk_case_question_answers_case_id_cases` (`case_id` -> `cases.case_id` `ON DELETE CASCADE`)
- Unique Constraint: `uq_case_question_answers_case_id_rev` (`case_id`, `resulting_revision_number`)
- Check Constraint: `ck_case_question_answers_rev_gt_1` (`resulting_revision_number > 1`)
- Index: `ix_case_question_answers_case_id` (`case_id`)

---

### 5. `case_check_results`
Stores technician troubleshooting check executions and findings associated with diagnostic revisions.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `SERIAL` | No | Surrogate integer primary key. |
| `case_id` | `UUID` | No | Foreign key referencing `cases.case_id`. |
| `check_id` | `TEXT` | No | Troubleshooting check identifier (unrestricted domain text, e.g. `ACT01`, `ACT02`). |
| `execution_status` | `VARCHAR(64)` | No | Execution state: `COMPLETED`, `BLOCKED`, `FAILED`, `UNKNOWN`, `NOT_APPLICABLE`, `SKIPPED`. |
| `finding` | `VARCHAR(64)` | No | Normalized finding: `SUPPORTS`, `CONTRADICTS`, `INCONCLUSIVE`, `UNKNOWN`, `NOT_APPLICABLE`. |
| `finding_details` | `TEXT` | Yes | Technician observation details, notes, or equipment readings (unrestricted domain text). |
| `outcome` | `TEXT` | Yes | Specific action outcome key (e.g. `no_blockage`, `air_bubbles_found`, `consistent_but_wrong_size`). |
| `source` | `VARCHAR(64)` | No | Provenance source (always `USER_CHECK_RESULT` for technician submissions). |
| `checked_at` | `TIMESTAMPTZ` | No | Timezone-aware timestamp of the check submission. |
| `resulting_revision_number` | `INTEGER` | No | Analysis revision number produced by this check event (> 1). |

**Constraints:**
- Primary Key: `pk_case_check_results` (`id`)
- Foreign Key: `fk_case_check_results_case_id_cases` (`case_id` -> `cases.case_id` `ON DELETE CASCADE`)
- Unique Constraint: `uq_case_check_results_case_id_rev` (`case_id`, `resulting_revision_number`)
- Check Constraint: `ck_case_check_results_rev_gt_1` (`resulting_revision_number > 1`)
- Index: `ix_case_check_results_case_id` (`case_id`)

---

### 6. `case_cause_confirmations`
Stores technician root-cause confirmations associated with diagnostic revisions.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `SERIAL` | No | Surrogate integer primary key. |
| `case_id` | `UUID` | No | Foreign key referencing `cases.case_id`. |
| `cause_id` | `TEXT` | No | Identifier of the confirmed root cause (unrestricted domain text). |
| `confirmed_by` | `VARCHAR(64)` | No | Identifier or role of technician confirming the cause (default `'technician'`). |
| `notes` | `TEXT` | Yes | Optional technician explanation, equipment findings, or notes. |
| `confirmed_at` | `TIMESTAMPTZ` | No | Timezone-aware timestamp of the confirmation. |
| `resulting_revision_number` | `INTEGER` | No | Analysis revision number produced by this confirmation event (> 1). |

**Constraints:**
- Primary Key: `pk_case_cause_confirmations` (`id`)
- Foreign Key: `fk_case_cause_confirmations_case_id_cases` (`case_id` -> `cases.case_id` `ON DELETE CASCADE`)
- Unique Constraint: `uq_case_cause_confirmations_case_id_rev` (`case_id`, `resulting_revision_number`)
- Check Constraint: `ck_case_cause_confirmations_rev_gt_1` (`resulting_revision_number > 1`)
- Index: `ix_case_cause_confirmations_case_id` (`case_id`)

---

### 7. `case_lifecycle_events`
Stores append-only audit history of issue condition lifecycle transitions (recovery actions and recovery verifications).

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `SERIAL` | No | Surrogate integer primary key. |
| `case_id` | `UUID` | No | Foreign key referencing `cases.case_id`. |
| `event_type` | `VARCHAR(64)` | No | Lifecycle event type (`RECOVERY_ACTION`, `RECOVERY_VERIFICATION`). |
| `prior_issue_condition` | `VARCHAR(64)` | No | Issue condition prior to transition (e.g. `UNRESOLVED`, `RECOVERY_PENDING_VERIFICATION`). |
| `resulting_issue_condition` | `VARCHAR(64)` | No | Issue condition resulting from transition (e.g. `RECOVERY_PENDING_VERIFICATION`, `RESOLVED`, `UNRESOLVED`). |
| `resulting_revision_number` | `INTEGER` | No | Analysis revision number produced by this lifecycle transition event (> 1). |
| `actor` | `VARCHAR(64)` | No | Identifier or role of technician performing/verifying the transition (default `'technician'`). |
| `details` | `TEXT` | No | Full descriptive details of the corrective action or verification observations. |
| `verification_passed` | `BOOLEAN` | Yes | Explicit verification outcome: `True` (passed), `False` (failed), `None` for recovery actions. |
| `created_at` | `TIMESTAMPTZ` | No | Timezone-aware timestamp of the transition event. |

**Constraints:**
- Primary Key: `pk_case_lifecycle_events` (`id`)
- Foreign Key: `fk_case_lifecycle_events_case_id_cases` (`case_id` -> `cases.case_id` `ON DELETE CASCADE`)
- Unique Constraint: `uq_case_lifecycle_events_case_id_rev` (`case_id`, `resulting_revision_number`)
- Check Constraint: `ck_case_lifecycle_events_rev_gt_1` (`resulting_revision_number > 1`)
- Index: `ix_case_lifecycle_events_case_id` (`case_id`)

---

## Architectural Guarantees

### 1. JSONB Snapshot Rationale
The `result_snapshot` column stores the full output of Member 2's diagnostic engine without lossy flattening. This preserves:
- All ranked candidate causes with scores and conclusions;
- Complete supporting, contradicting, and neutral evidence traces with provenance, strength, relation, explanation, and score contribution;
- Missing evidence lists and granular score breakdowns;
- Recommended discriminating questions and troubleshooting checks;
- Detailed diagnostic explanation text and engine warnings;
- Internal analysis revision metadata.

### 2. Append-Only Revision Rule
Revisions are strictly append-only:
- `(case_id, revision_number)` is enforced as unique in the database.
- The repository provides no update or delete operations for analysis revisions.
- Attempting to overwrite an existing revision raises an integrity violation.

### 3. Separation of Cause Confirmation and Issue Recovery
In accordance with Dispense Lens diagnostic principles:
- Completing troubleshooting checks does NOT automatically confirm a root cause.
- Confirming a root cause does NOT automatically mean the dispensing defect is resolved.
- Resolving an issue requires independent recovery verification.
- Root cause confirmation and recovery verification remain separate deferred entities in later tasks and are intentionally not coupled into a boolean flag on the case.

### 4. Question-Answer History and Reconstruction Rationale
Technician question answers are stored in `case_question_answers` independently of whether an answer generates an observation:
- Answers mapping to domain observations generate structured rows in `case_observations` with `first_seen_revision = N`.
- Answers such as `UNKNOWN` or `NOT_APPLICABLE` deliberately produce no observations, but their historical record in `case_question_answers` is required so that case reconstruction via `load_structured_case` populates `previous_answers` and prevents the question selection engine from repeatedly re-asking already answered questions.
- In this milestone, exactly one answer produces one new analysis revision (`resulting_revision_number > 1`), enforced by unique constraint `(case_id, resulting_revision_number)`.
- No unique constraint is placed on `(case_id, question_id)`, leaving future capability open for re-answering or corrective workflows.

### 5. Troubleshooting Check-Result History and Reconstruction Rationale
Technician troubleshooting check results are stored in `case_check_results` independently of whether a check generates diagnostic observations:
- Completed checks with definitive findings (`SUPPORTS`, `CONTRADICTS`) generate structured rows in `case_observations` with `first_seen_revision = N` and `source = USER_CHECK_RESULT`.
- Non-executing checks (`BLOCKED`, `FAILED`, `UNKNOWN`, `NOT_APPLICABLE`, `SKIPPED`) and completed checks with non-definitive findings (`INCONCLUSIVE`, `UNKNOWN`, `NOT_APPLICABLE`) deliberately produce no observations, but their historical record in `case_check_results` is required so that case reconstruction via `load_structured_case` populates `previous_check_results` with exact fidelity.
- Each submitted check result produces one new analysis revision (`resulting_revision_number > 1`), enforced by unique constraint `(case_id, resulting_revision_number)`.
- No unique constraint is placed on `(case_id, check_id)`, allowing repeated checks across the investigation lifecycle.
- Interleaved event histories (e.g. Revision 1: initial -> Revision 2: answer -> Revision 3: check -> Revision 4: answer) are fully supported with monotonic global revision numbering.

### 6. Root-Cause Confirmation History and Semantic Separation Rationale
Technician root-cause confirmations are stored in `case_cause_confirmations` to preserve explicit, auditable confirmation events:
- In accordance with core diagnostic rules: `check completed` != `check supports cause` != `cause confirmed` != `issue resolved`.
- Troubleshooting checks and high evidence scores do **never** confirm a cause automatically.
- Confirming a cause sets the candidate cause conclusion to `CONFIRMED`, but does **never** transition the overall `issue_condition` to `RESOLVED` (which requires independent recovery verification).
- Each confirmed cause produces exactly one new analysis revision (`resulting_revision_number > 1`), enforced by unique constraint `(case_id, resulting_revision_number)`.
- During case reconstruction via `load_structured_case()`, confirmed causes are populated into `StructuredCase.confirmed_causes`, guaranteeing subsequent diagnostic evaluations preserve `CONFIRMED` cause conclusions.
- Monotonic global revision numbering is maintained across question answers, check results, and cause confirmations.

### 7. Lifecycle Transition History and Independent Verification Rationale
Technician recovery actions and post-correction verifications are stored in `case_lifecycle_events` to provide an immutable, append-only audit log of issue lifecycle transitions:
- In accordance with Dispense Lens diagnostic principles:
  - Applying a recovery action transitions the case to `RECOVERY_PENDING_VERIFICATION` through `StateManager.transition_issue_condition(...)` and does **not** directly resolve the issue.
  - Resolving an issue requires an explicit verification step (`verification_passed = True`) moving the case from `RECOVERY_PENDING_VERIFICATION` to `RESOLVED`.
  - If verification fails (`verification_passed = False`), the issue transitions back to `UNRESOLVED`, preserving prior investigation and confirmation history.
  - Cause confirmation and issue condition remain strictly independent: an unconfirmed cause can be resolved after recovery verification, and a confirmed cause remains confirmed even if recovery verification fails.
- Each accepted recovery action or verification appends exactly one new analysis revision (`resulting_revision_number > 1`), enforced by unique constraint `(case_id, resulting_revision_number)`.
- Monotonic global revision numbering is shared across all workflow event types (initial diagnosis, question answers, check results, cause confirmations, recovery actions, and recovery verifications).
