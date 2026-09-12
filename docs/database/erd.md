# DispenseIQ — Database Entity-Relationship Specification

## Overview

DispenseIQ uses PostgreSQL with SQLAlchemy 2.x and Alembic migrations for relational persistence.
Schema evolution is strictly governed by Alembic (`backend/alembic/versions/`).

The initial persistence foundation (DLK-M3-006) establishes minimal relational storage for:
1. **Diagnostic cases** (`cases`);
2. **Structured observations with provenance** (`case_observations`);
3. **Append-only immutable analysis revisions** (`analysis_revisions`).

---

## Entity Relationship Diagram

```mermaid
erDiagram
    CASES ||--o{ CASE_OBSERVATIONS : "has"
    CASES ||--o{ ANALYSIS_REVISIONS : "has"

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
In accordance with DispenseIQ diagnostic principles:
- Completing troubleshooting checks does NOT automatically confirm a root cause.
- Confirming a root cause does NOT automatically mean the dispensing defect is resolved.
- Resolving an issue requires independent recovery verification.
- Root cause confirmation and recovery verification remain separate deferred entities in later tasks and are intentionally not coupled into a boolean flag on the case.
