# DispenseLens API Specification

## Overview

The DispenseLens Backend provides REST APIs for automated troubleshooting and diagnostic intelligence in precision dispensing systems.

- **Base URL:** `/api/v1`
- **Format:** JSON (`application/json`)
- **Interactive Documentation:** `/docs` (Swagger UI), `/redoc` (ReDoc), `/openapi.json` (OpenAPI 3.1)

---

## Endpoints

### 1. Service Health Check

- **Method / Path:** `GET /api/v1/health`
- **Description:** Returns the operational status and version of the API service process.
- **Request:** None.
- **Response (200 OK):**
  ```json
  {
    "status": "ok",
    "service": "dispense-lens-api",
    "version": "0.1.0"
  }
  ```
- **Scope & Limitations:** Confirms that the web process is running and accepting HTTP requests. Does not verify database connectivity or external services.

---

### 2. Initial Diagnosis

- **Method / Path:** `POST /api/v1/diagnoses`
- **Description:** Submits an initial dispensing defect report and returns the diagnostic engine's structured assessment, including defect classification, ranked hypotheses, recommended next diagnostic question, next troubleshooting check, and evidence breakdown.

#### Statelessness & Lifecycle Contract

- **Stateless Operation:** This endpoint does not write to a database or cache state in shared memory.
- **Client Restrictions:** The caller cannot supply a `case_id`, revision numbers, prior question answers, or prior check results. The request model strictly forbids extra top-level fields (`extra = "forbid"`).
- **Transient Case ID:** The `case_id` returned in the response is a server-generated UUID (UUIDv4) that uniquely identifies that specific execution run. It is **not** currently persistent or retrievable. Repeated calls with identical inputs will generate distinct case IDs and be processed independently.
- **Follow-up Submissions:** Interactive follow-up flows (answering questions, recording check results, and updating revisions) will be introduced in subsequent persistence tasks.

#### Request Schema (`InitialDiagnosisRequest`)

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `description` | `string` | No | `""` | Free-text problem description from technician or operator. |
| `material` | `string` \| `null` | No | `null` | Dispensed fluid / material name or category (e.g. `"epoxy"`, `"solder_paste"`). |
| `method` | `string` \| `null` | No | `null` | Dispensing technology/method (e.g. `"time_pressure"`, `"jetting"`). |
| `machine_context` | `object` \| `null` | No | `null` | Machine state, parameters, or environment context. |
| `defect_code` | `string` \| `null` | No | `null` | Optional defect code (e.g. `"D01_TOO_LITTLE"`). Must match a valid defect code in the knowledge base. |
| `observations` | `array[Observation]` | No | `[]` | List of structured observations. |

##### Observation Object

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `id` | `string` | No | Auto-generated UUIDv4 | Unique identifier for this observation. If omitted by the caller, the server generates a UUIDv4. |
| `observation_type` | `string` | **Yes** | — | Category of observation. Valid values: `deposit_size`, `deposit_count`, `deposit_shape`, `deposit_presence`, `time_pattern`, `runtime_pattern`, `location_pattern`, `frequency_pattern`, `material_state`, `temperature`, `pressure`, `nozzle_condition`, `equipment_condition`, `process_parameter`, `visual_appearance`, `bubble_presence`, `spreading_behaviour`, `other`. |
| `value` | `string` | **Yes** | — | Observed descriptor or state (e.g. `"undersized"`, `"worsens_over_time"`). |
| `original_text` | `string` \| `null` | No | `null` | Original text snippet from which observation was derived. |
| `statement_type` | `string` | No | `"USER_OBSERVATION"` | Nature of statement: `USER_OBSERVATION`, `USER_INTERPRETATION`, or `AI_INFERENCE`. |
| `source` | `string` | No | `"USER"` | Evidence provenance: `USER`, `MEASUREMENT`, `IMAGE`, `SYSTEM`, `HISTORICAL_CASE`. |
| `confidence` | `float` \| `null` | No | `null` | Confidence score between `0.0` and `1.0`. |
| `timestamp` | `string` (ISO 8601) | No | Auto-generated UTC time | Timestamp when observation was created or recorded. Defaults to current UTC time. |

#### Input Validation Rules (HTTP 422)

The endpoint validates:
1. **Empty Evidence:** Submitting a blank/whitespace description with no observations returns `422 Unprocessable Entity`.
2. **Defect Code Alone:** Supplying a `defect_code` without any description or observations is considered insufficient evidence and returns `422 Unprocessable Entity`.
3. **Observations Allowed Without Description:** Submitting structured `observations` with an empty `description` is valid and accepted.
4. **Unknown Defect Code:** If `defect_code` is provided, it is checked against the knowledge base (`app.knowledge.get_defect_by_code`). Unrecognized codes return `422 Unprocessable Entity`.
5. **Forbidden Fields:** Supplying forbidden top-level fields (e.g., `case_id`, `previous_answers`, `analysis_revision`, `extra_property`) returns `422 Unprocessable Entity`.

#### Representative Execution Example

> [!NOTE]
> The following request and response demonstrate an actual diagnostic run for a nozzle restriction scenario. Generated UUIDs (such as the top-level `case_id` and the generated `observation_id`) and timestamps are distinct and independently generated on each execution run.

##### Request Payload (`POST /api/v1/diagnoses`)
```json
{
  "description": "Dispense needle drips fluid after dispensing stops",
  "material": "epoxy",
  "method": "time_pressure",
  "observations": [
    {
      "observation_type": "deposit_size",
      "value": "undersized",
      "confidence": 0.9
    }
  ]
}
```

##### Response Payload (`200 OK`)
```json
{
  "case_id": "834965ca-4d2e-462a-a6f7-8c3a32789d89",
  "defect": "D01_TOO_LITTLE",
  "defect_name": "Too Little Material",
  "ranked_causes": [
    {
      "cause_id": "nozzle_restriction",
      "cause_name": "Nozzle Restriction",
      "score": 40.0,
      "conclusion": "SUSPECTED",
      "supporting_evidence": [
        {
          "observation_id": "5c5600d8-2b33-47ca-9be5-c60c2038c2a6",
          "cause_id": "nozzle_restriction",
          "relation": "SUPPORTS",
          "strength": "STRONG",
          "source": "USER",
          "explanation": "A restricted nozzle directly reduces the amount of material that can pass through.",
          "is_duplicate": false,
          "duplicate_of": null,
          "score_contribution": 20.0
        }
      ],
      "contradicting_evidence": [],
      "neutral_evidence": [],
      "missing_evidence": [
        "deposit_size=inconsistent has not been observed.",
        "runtime_pattern=worsens_over_time has not been observed.",
        "frequency_pattern=consistent has not been observed.",
        "location_pattern=specific_nozzle has not been observed.",
        "deposit_presence=missing has not been observed."
      ],
      "score_breakdown": {
        "base": 30.0,
        "positive_evidence": 20.0,
        "contradiction_penalty": 0.0,
        "duplicate_ignored": 0.0,
        "missing_penalty": 10.0
      }
    },
    {
      "cause_id": "pressure_instability",
      "cause_name": "Pressure Instability",
      "score": 34.0,
      "conclusion": "SUSPECTED",
      "supporting_evidence": [
        {
          "observation_id": "5c5600d8-2b33-47ca-9be5-c60c2038c2a6",
          "cause_id": "pressure_instability",
          "relation": "SUPPORTS",
          "strength": "MODERATE",
          "source": "USER",
          "explanation": "Low or dropping pressure reduces dispensed volume.",
          "is_duplicate": false,
          "duplicate_of": null,
          "score_contribution": 12.0
        }
      ],
      "contradicting_evidence": [],
      "neutral_evidence": [],
      "missing_evidence": [
        "deposit_size=inconsistent has not been observed.",
        "frequency_pattern=intermittent has not been observed.",
        "location_pattern=all_points has not been observed.",
        "pressure=fluctuating has not been observed."
      ],
      "score_breakdown": {
        "base": 30.0,
        "positive_evidence": 12.0,
        "contradiction_penalty": 0.0,
        "duplicate_ignored": 0.0,
        "missing_penalty": 8.0
      }
    },
    {
      "cause_id": "air_supply_issue",
      "cause_name": "Air / Supply Issue",
      "score": 28.0,
      "conclusion": "SUSPECTED",
      "supporting_evidence": [
        {
          "observation_id": "5c5600d8-2b33-47ca-9be5-c60c2038c2a6",
          "cause_id": "air_supply_issue",
          "relation": "SUPPORTS",
          "strength": "MODERATE",
          "source": "USER",
          "explanation": "Undersized deposits can result from air displacing material volume in the supply path.",
          "is_duplicate": false,
          "duplicate_of": null,
          "score_contribution": 12.0
        }
      ],
      "contradicting_evidence": [],
      "neutral_evidence": [],
      "missing_evidence": [
        "deposit_size=inconsistent has not been observed.",
        "runtime_pattern=after_prolonged_operation has not been observed.",
        "runtime_pattern=worsens_over_time has not been observed.",
        "frequency_pattern=intermittent has not been observed.",
        "location_pattern=all_points has not been observed.",
        "bubble_presence=visible_bubbles has not been observed.",
        "deposit_presence=missing has not been observed."
      ],
      "score_breakdown": {
        "base": 30.0,
        "positive_evidence": 12.0,
        "contradiction_penalty": 0.0,
        "duplicate_ignored": 0.0,
        "missing_penalty": 14.0
      }
    },
    {
      "cause_id": "equipment_condition",
      "cause_name": "Equipment Condition",
      "score": 28.0,
      "conclusion": "SUSPECTED",
      "supporting_evidence": [],
      "contradicting_evidence": [],
      "neutral_evidence": [
        {
          "observation_id": "5c5600d8-2b33-47ca-9be5-c60c2038c2a6",
          "cause_id": "equipment_condition",
          "relation": "NEUTRAL",
          "strength": "WEAK",
          "source": "USER",
          "explanation": "No evidence rule links 'deposit_size=undersized' to 'Equipment Condition'.",
          "is_duplicate": false,
          "duplicate_of": null,
          "score_contribution": 0.0
        }
      ],
      "missing_evidence": [
        "equipment_condition=worn has not been observed."
      ],
      "score_breakdown": {
        "base": 30.0,
        "positive_evidence": 0.0,
        "contradiction_penalty": 0.0,
        "duplicate_ignored": 0.0,
        "missing_penalty": 2.0
      }
    },
    {
      "cause_id": "material_condition",
      "cause_name": "Material Condition",
      "score": 20.0,
      "conclusion": "SUSPECTED",
      "supporting_evidence": [
        {
          "observation_id": "5c5600d8-2b33-47ca-9be5-c60c2038c2a6",
          "cause_id": "material_condition",
          "relation": "SUPPORTS",
          "strength": "WEAK",
          "source": "USER",
          "explanation": "Degraded or thickened material may reduce flow through the nozzle.",
          "is_duplicate": false,
          "duplicate_of": null,
          "score_contribution": 5.0
        }
      ],
      "contradicting_evidence": [],
      "neutral_evidence": [],
      "missing_evidence": [
        "deposit_size=inconsistent has not been observed.",
        "runtime_pattern=after_prolonged_operation has not been observed.",
        "runtime_pattern=worsens_over_time has not been observed.",
        "location_pattern=all_points has not been observed.",
        "bubble_presence=visible_bubbles has not been observed.",
        "spreading_behaviour=excessive_spread has not been observed.",
        "material_state=separated has not been observed.",
        "material_state=low_viscosity has not been observed.",
        "material_state=high_viscosity has not been observed."
      ],
      "score_breakdown": {
        "base": 30.0,
        "positive_evidence": 5.0,
        "contradiction_penalty": 0.0,
        "duplicate_ignored": 0.0,
        "missing_penalty": 15.0
      }
    },
    {
      "cause_id": "parameter_issue",
      "cause_name": "Parameter Issue",
      "score": 20.0,
      "conclusion": "SUSPECTED",
      "supporting_evidence": [],
      "contradicting_evidence": [],
      "neutral_evidence": [
        {
          "observation_id": "5c5600d8-2b33-47ca-9be5-c60c2038c2a6",
          "cause_id": "parameter_issue",
          "relation": "NEUTRAL",
          "strength": "WEAK",
          "source": "USER",
          "explanation": "No evidence rule links 'deposit_size=undersized' to 'Parameter Issue'.",
          "is_duplicate": false,
          "duplicate_of": null,
          "score_contribution": 0.0
        }
      ],
      "missing_evidence": [
        "deposit_size=oversized has not been observed.",
        "frequency_pattern=consistent has not been observed.",
        "spreading_behaviour=excessive_spread has not been observed.",
        "deposit_shape=abnormal has not been observed.",
        "deposit_shape=satellite_dots has not been observed."
      ],
      "score_breakdown": {
        "base": 30.0,
        "positive_evidence": 0.0,
        "contradiction_penalty": 0.0,
        "duplicate_ignored": 0.0,
        "missing_penalty": 10.0
      }
    }
  ],
  "next_question": {
    "question_id": "Q01",
    "text": "Does the problem occur immediately after startup or only after the machine has been running for a while?",
    "purpose": "Distinguishes thermal/time-related causes (air expansion, material viscosity change) from static issues.",
    "usefulness_score": 19.5,
    "target_causes": [
      "air_supply_issue",
      "material_condition",
      "pressure_instability",
      "temperature_issue"
    ],
    "already_answered": false
  },
  "next_check": {
    "check_id": "ACT04",
    "name": "Check Dispensing Pressure",
    "description": "Verify the dispensing pressure reading and stability over a period of operation.",
    "procedure": "1. Record the pressure setpoint.\n2. Monitor the actual pressure gauge reading during dispensing.\n3. Record pressure over 5-10 minute window.\n4. Note any fluctuations, drift, or spikes.\n5. Compare actual vs setpoint.\n6. Check for pneumatic leaks in the supply line.\n7. Document findings.",
    "priority_score": 12.3,
    "target_causes": [
      "pressure_instability",
      "air_supply_issue",
      "equipment_condition"
    ],
    "reasoning": "Addresses 3 applicable cause(s). Can produce 3.0 distinct evidence outcome(s).",
    "required_access": "pressure_system",
    "effort_level": "low"
  },
  "explanation": "Nozzle Restriction is currently the highest-supported hypothesis with evidence support 40/100.\nIt is supported by 1 observation(s).\n\nRecommended Action: Run troubleshooting check 'Check Dispensing Pressure' (ACT04, effort: low).",
  "analysis_revision": {
    "revision_number": 1,
    "timestamp": "2026-09-12T06:39:30.404285Z",
    "defect_code": "D01_TOO_LITTLE",
    "ranked_causes": [
      {
        "cause_id": "nozzle_restriction",
        "cause_name": "Nozzle Restriction",
        "score": 40.0,
        "conclusion": "SUSPECTED",
        "supporting_evidence": [
          {
            "observation_id": "5c5600d8-2b33-47ca-9be5-c60c2038c2a6",
            "cause_id": "nozzle_restriction",
            "relation": "SUPPORTS",
            "strength": "STRONG",
            "source": "USER",
            "explanation": "A restricted nozzle directly reduces the amount of material that can pass through.",
            "is_duplicate": false,
            "duplicate_of": null,
            "score_contribution": 20.0
          }
        ],
        "contradicting_evidence": [],
        "neutral_evidence": [],
        "missing_evidence": [
          "deposit_size=inconsistent has not been observed.",
          "runtime_pattern=worsens_over_time has not been observed.",
          "frequency_pattern=consistent has not been observed.",
          "location_pattern=specific_nozzle has not been observed.",
          "deposit_presence=missing has not been observed."
        ],
        "score_breakdown": {
          "base": 30.0,
          "positive_evidence": 20.0,
          "contradiction_penalty": 0.0,
          "duplicate_ignored": 0.0,
          "missing_penalty": 10.0
        }
      },
      {
        "cause_id": "pressure_instability",
        "cause_name": "Pressure Instability",
        "score": 34.0,
        "conclusion": "SUSPECTED",
        "supporting_evidence": [
          {
            "observation_id": "5c5600d8-2b33-47ca-9be5-c60c2038c2a6",
            "cause_id": "pressure_instability",
            "relation": "SUPPORTS",
            "strength": "MODERATE",
            "source": "USER",
            "explanation": "Low or dropping pressure reduces dispensed volume.",
            "is_duplicate": false,
            "duplicate_of": null,
            "score_contribution": 12.0
          }
        ],
        "contradicting_evidence": [],
        "neutral_evidence": [],
        "missing_evidence": [
          "deposit_size=inconsistent has not been observed.",
          "frequency_pattern=intermittent has not been observed.",
          "location_pattern=all_points has not been observed.",
          "pressure=fluctuating has not been observed."
        ],
        "score_breakdown": {
          "base": 30.0,
          "positive_evidence": 12.0,
          "contradiction_penalty": 0.0,
          "duplicate_ignored": 0.0,
          "missing_penalty": 8.0
        }
      },
      {
        "cause_id": "air_supply_issue",
        "cause_name": "Air / Supply Issue",
        "score": 28.0,
        "conclusion": "SUSPECTED",
        "supporting_evidence": [
          {
            "observation_id": "5c5600d8-2b33-47ca-9be5-c60c2038c2a6",
            "cause_id": "air_supply_issue",
            "relation": "SUPPORTS",
            "strength": "MODERATE",
            "source": "USER",
            "explanation": "Undersized deposits can result from air displacing material volume in the supply path.",
            "is_duplicate": false,
            "duplicate_of": null,
            "score_contribution": 12.0
          }
        ],
        "contradicting_evidence": [],
        "neutral_evidence": [],
        "missing_evidence": [
          "deposit_size=inconsistent has not been observed.",
          "runtime_pattern=after_prolonged_operation has not been observed.",
          "runtime_pattern=worsens_over_time has not been observed.",
          "frequency_pattern=intermittent has not been observed.",
          "location_pattern=all_points has not been observed.",
          "bubble_presence=visible_bubbles has not been observed.",
          "deposit_presence=missing has not been observed."
        ],
        "score_breakdown": {
          "base": 30.0,
          "positive_evidence": 12.0,
          "contradiction_penalty": 0.0,
          "duplicate_ignored": 0.0,
          "missing_penalty": 14.0
        }
      },
      {
        "cause_id": "equipment_condition",
        "cause_name": "Equipment Condition",
        "score": 28.0,
        "conclusion": "SUSPECTED",
        "supporting_evidence": [],
        "contradicting_evidence": [],
        "neutral_evidence": [
          {
            "observation_id": "5c5600d8-2b33-47ca-9be5-c60c2038c2a6",
            "cause_id": "equipment_condition",
            "relation": "NEUTRAL",
            "strength": "WEAK",
            "source": "USER",
            "explanation": "No evidence rule links 'deposit_size=undersized' to 'Equipment Condition'.",
            "is_duplicate": false,
            "duplicate_of": null,
            "score_contribution": 0.0
          }
        ],
        "missing_evidence": [
          "equipment_condition=worn has not been observed."
        ],
        "score_breakdown": {
          "base": 30.0,
          "positive_evidence": 0.0,
          "contradiction_penalty": 0.0,
          "duplicate_ignored": 0.0,
          "missing_penalty": 2.0
        }
      },
      {
        "cause_id": "material_condition",
        "cause_name": "Material Condition",
        "score": 20.0,
        "conclusion": "SUSPECTED",
        "supporting_evidence": [
          {
            "observation_id": "5c5600d8-2b33-47ca-9be5-c60c2038c2a6",
            "cause_id": "material_condition",
            "relation": "SUPPORTS",
            "strength": "WEAK",
            "source": "USER",
            "explanation": "Degraded or thickened material may reduce flow through the nozzle.",
            "is_duplicate": false,
            "duplicate_of": null,
            "score_contribution": 5.0
          }
        ],
        "contradicting_evidence": [],
        "neutral_evidence": [],
        "missing_evidence": [
          "deposit_size=inconsistent has not been observed.",
          "runtime_pattern=after_prolonged_operation has not been observed.",
          "runtime_pattern=worsens_over_time has not been observed.",
          "location_pattern=all_points has not been observed.",
          "bubble_presence=visible_bubbles has not been observed.",
          "spreading_behaviour=excessive_spread has not been observed.",
          "material_state=separated has not been observed.",
          "material_state=low_viscosity has not been observed.",
          "material_state=high_viscosity has not been observed."
        ],
        "score_breakdown": {
          "base": 30.0,
          "positive_evidence": 5.0,
          "contradiction_penalty": 0.0,
          "duplicate_ignored": 0.0,
          "missing_penalty": 15.0
        }
      },
      {
        "cause_id": "parameter_issue",
        "cause_name": "Parameter Issue",
        "score": 20.0,
        "conclusion": "SUSPECTED",
        "supporting_evidence": [],
        "contradicting_evidence": [],
        "neutral_evidence": [
          {
            "observation_id": "5c5600d8-2b33-47ca-9be5-c60c2038c2a6",
            "cause_id": "parameter_issue",
            "relation": "NEUTRAL",
            "strength": "WEAK",
            "source": "USER",
            "explanation": "No evidence rule links 'deposit_size=undersized' to 'Parameter Issue'.",
            "is_duplicate": false,
            "duplicate_of": null,
            "score_contribution": 0.0
          }
        ],
        "missing_evidence": [
          "deposit_size=oversized has not been observed.",
          "frequency_pattern=consistent has not been observed.",
          "spreading_behaviour=excessive_spread has not been observed.",
          "deposit_shape=abnormal has not been observed.",
          "deposit_shape=satellite_dots has not been observed."
        ],
        "score_breakdown": {
          "base": 30.0,
          "positive_evidence": 0.0,
          "contradiction_penalty": 0.0,
          "duplicate_ignored": 0.0,
          "missing_penalty": 10.0
        }
      }
    ],
    "new_evidence_summary": "Initial diagnostic assessment.",
    "changes_from_previous": []
  },
  "issue_condition": "UNRESOLVED",
  "warnings": []
}
```

---

### 3. Durable Case Management

Durable case endpoints persist diagnostic cases and their full assessment history in PostgreSQL. This allows cases to be uniquely identified, retrieved across sessions, and extended in future revision workflows.

#### Stateless vs. Durable Endpoints Comparison

| Characteristic | Stateless Endpoint (`POST /api/v1/diagnoses`) | Durable Endpoint (`POST /api/v1/cases`, `GET /api/v1/cases/{case_id}`) |
|---|---|---|
| **Persistence** | None. No database writes or reads. | Persistent. Writes case, observations, and revision 1 snapshot to PostgreSQL. |
| **Database Requirement** | Completely independent; operates without `DATABASE_URL` or DB service. | Requires active PostgreSQL database connection. |
| **Case ID Nature** | Ephemeral UUID identifying a single execution run. Not retrievable. | Canonical persistent UUID. Persisted in database and permanently queryable. |
| **Retrieval** | Cannot be retrieved (`GET` returns 404). | Queryable via `GET /api/v1/cases/{case_id}`. |
| **Recalculation on Read** | N/A (no read endpoint). | Guaranteed zero recalculation. Reads persisted state; never invokes `DiagnosticEngine`. |
| **Inconclusive Diagnosis Handling** | Accepts input and returns `200 OK` with `defect: null` and `analysis_revision: null`. | Rejects with `422 Unprocessable Entity`; no case or revision is persisted. *(Note: Current persistence contract requires Revision 1 for initial case storage; records current behavior, not permanent product approval.)* |
| **Primary Use Case** | Ad-hoc one-off checks, lightweight validation, automated smoke tests. | Durable diagnostic troubleshooting sessions requiring historical tracking. |

---

#### 3.1 Create Durable Case

- **Method / Path:** `POST /api/v1/cases`
- **Description:** Submits a diagnostic case, runs the deterministic `DiagnosticEngine`, and atomically stores the case record, all observations (with provenance), and the complete immutable revision-1 diagnosis snapshot in PostgreSQL.
- **Status Code:** `201 Created`

> [!NOTE]
> **Inconclusive Diagnosis Limitation (HTTP 422):**
> When valid input does not provide enough evidence for the diagnostic engine to classify a defect, no `analysis_revision` is formed. Because the initial persistence contract strictly requires Revision 1 to store a case, `POST /api/v1/cases` returns `422 Unprocessable Entity` (`"Diagnostic evaluation could not identify a defect category from the provided evidence."`) and commits no rows to the database. By contrast, the stateless `POST /api/v1/diagnoses` endpoint returns `200 OK` with `defect: null` and `analysis_revision: null`. This documents current milestone behavior, not approval of a permanent product restriction.

##### Request Schema (`CreateCaseRequest`)

Accepts identical diagnostic input semantics to `POST /api/v1/diagnoses`:

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `description` | `string` | No | `""` | Problem description from technician or operator. (Also accepts `problem_description`). |
| `material` | `string` \| `null` | No | `null` | Dispensed fluid / material name (e.g. `"epoxy"`, `"solder_paste"`). |
| `method` | `string` \| `null` | No | `null` | Dispensing technology/method (e.g. `"time_pressure"`, `"jetting"`). |
| `machine_context` | `object` \| `null` | No | `null` | Machine state, parameters, or environment context. |
| `defect_code` | `string` \| `null` | No | `null` | Optional defect code (e.g. `"D01_TOO_LITTLE"`). Must match a valid defect code in knowledge base. |
| `observations` | `array[Observation]` | No | `[]` | List of structured observations. |

*Note: Extra top-level fields (e.g., caller-supplied `case_id`, `created_at`, `revision_number`) are strictly forbidden (`extra = "forbid"`).*


##### Response Schema (`DurableCaseResponse`)

| Field | Type | Description |
|---|---|---|
| `case_id` | `string` (UUID) | Canonical persistent case identifier. |
| `description` | `string` | Stored problem description. |
| `material` | `string` \| `null` | Stored material name. |
| `method` | `string` \| `null` | Stored dispensing method. |
| `machine_context` | `object` \| `null` | Stored machine context dictionary. |
| `defect_code` | `string` \| `null` | Classified or specified defect code. |
| `defect_name` | `string` \| `null` | Human-readable defect title. |
| `issue_condition` | `string` | Current resolution state (`UNRESOLVED`). |
| `created_at` | `string` (ISO 8601) | UTC timestamp of case creation. |
| `observations` | `array[CaseObservationResponse]` | List of persisted observations with provenance metadata. |
| `initial_diagnosis` | `DiagnosisResult` | Complete immutable snapshot of the revision-1 diagnostic assessment. |
| `diagnosis` | `DiagnosisResult` | Mirror alias of `initial_diagnosis`. |

##### CaseObservationResponse Schema

| Field | Type | Description |
|---|---|---|
| `id` | `string` | Persistent observation identifier. |
| `observation_id` | `string` | Alias of `id`. |
| `observation_type` | `string` | Category of observation. |
| `value` | `string` | Observed state or descriptor. |
| `original_text` | `string` \| `null` | Source text snippet (if extracted). |
| `statement_type` | `string` | `USER_OBSERVATION`, `USER_INTERPRETATION`, or `AI_INFERENCE`. |
| `source` | `string` | Evidence provenance: `USER`, `MEASUREMENT`, `IMAGE`, `SYSTEM`, `HISTORICAL_CASE`. |
| `confidence` | `float` \| `null` | Confidence score between 0.0 and 1.0. |
| `timestamp` | `string` (ISO 8601) | Observation timestamp. |
| `created_at` | `string` (ISO 8601) | Alias of `timestamp`. |
| `first_seen_revision` | `integer` | First revision where observation appeared (1 for initial). |

---

#### 3.2 Retrieve Durable Case

- **Method / Path:** `GET /api/v1/cases/{case_id}`
- **Description:** Retrieves the persisted state of a diagnostic case and its immutable initial revision-1 diagnosis by case UUID.
- **Status Code:** `200 OK`
- **Guarantees:**
  - **Zero Recalculation:** The endpoint loads stored relational data and the serialized diagnosis snapshot; `DiagnosticEngine.diagnose()` is never invoked.
  - **Idempotent & Read-Only:** Repeated requests produce identical responses and do not create revisions or mutate state.
  - **Missing Case (404):** If the case UUID does not exist in the database, returns `404 Not Found`.
  - **Malformed UUID (422):** If the path parameter is not a valid UUID string, returns `422 Unprocessable Entity`.

---

#### 3.3 Representative Execution Example

> [!NOTE]
> The following payloads demonstrate a real executable run against PostgreSQL 16. The case was created via `POST /api/v1/cases` and subsequently fetched via `GET /api/v1/cases/{case_id}`.

##### Request Payload (`POST /api/v1/cases`)
```json
{
  "description": "The dispensing dots become smaller after the machine has been running for around 20 minutes.",
  "material": "epoxy",
  "method": "time_pressure",
  "machine_context": {
    "nozzle_id": "NZ-01",
    "pressure_bar": 2.4
  },
  "observations": [
    {
      "observation_type": "deposit_size",
      "value": "undersized",
      "confidence": 0.95
    }
  ]
}
```

##### Response Payload (`201 Created` and subsequent `GET 200 OK`)
```json
{
  "case_id": "4e158104-60d1-477c-a20a-62ae77e8a6e2",
  "description": "The dispensing dots become smaller after the machine has been running for around 20 minutes.",
  "material": "epoxy",
  "method": "time_pressure",
  "machine_context": {
    "nozzle_id": "NZ-01",
    "pressure_bar": 2.4
  },
  "defect_code": "D01_TOO_LITTLE",
  "defect_name": "Too Little Material",
  "issue_condition": "UNRESOLVED",
  "created_at": "2026-09-12T16:43:28.127120Z",
  "observations": [
    {
      "id": "2438f77b-8498-4aa5-95fe-834aa859731e",
      "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
      "observation_type": "deposit_size",
      "value": "undersized",
      "original_text": null,
      "statement_type": "USER_OBSERVATION",
      "source": "USER",
      "confidence": 0.95,
      "timestamp": "2026-09-12T16:43:28.126944Z",
      "created_at": "2026-09-12T16:43:28.126944Z",
      "first_seen_revision": 1
    }
  ],
  "initial_diagnosis": {
    "case_id": "4e158104-60d1-477c-a20a-62ae77e8a6e2",
    "defect": "D01_TOO_LITTLE",
    "defect_name": "Too Little Material",
    "ranked_causes": [
      {
        "cause_id": "nozzle_restriction",
        "cause_name": "Nozzle Restriction",
        "score": 40.0,
        "conclusion": "SUSPECTED",
        "supporting_evidence": [
          {
            "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
            "cause_id": "nozzle_restriction",
            "relation": "SUPPORTS",
            "strength": "STRONG",
            "source": "USER",
            "explanation": "A restricted nozzle directly reduces the amount of material that can pass through.",
            "is_duplicate": false,
            "duplicate_of": null,
            "score_contribution": 20.0
          }
        ],
        "contradicting_evidence": [],
        "neutral_evidence": [],
        "missing_evidence": [
          "deposit_size=inconsistent has not been observed.",
          "runtime_pattern=worsens_over_time has not been observed.",
          "frequency_pattern=consistent has not been observed.",
          "location_pattern=specific_nozzle has not been observed.",
          "deposit_presence=missing has not been observed."
        ],
        "score_breakdown": {
          "base": 30.0,
          "positive_evidence": 20.0,
          "contradiction_penalty": 0.0,
          "duplicate_ignored": 0.0,
          "missing_penalty": 10.0
        }
      },
      {
        "cause_id": "pressure_instability",
        "cause_name": "Pressure Instability",
        "score": 34.0,
        "conclusion": "SUSPECTED",
        "supporting_evidence": [
          {
            "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
            "cause_id": "pressure_instability",
            "relation": "SUPPORTS",
            "strength": "MODERATE",
            "source": "USER",
            "explanation": "Low or dropping pressure reduces dispensed volume.",
            "is_duplicate": false,
            "duplicate_of": null,
            "score_contribution": 12.0
          }
        ],
        "contradicting_evidence": [],
        "neutral_evidence": [],
        "missing_evidence": [
          "deposit_size=inconsistent has not been observed.",
          "frequency_pattern=intermittent has not been observed.",
          "location_pattern=all_points has not been observed.",
          "pressure=fluctuating has not been observed."
        ],
        "score_breakdown": {
          "base": 30.0,
          "positive_evidence": 12.0,
          "contradiction_penalty": 0.0,
          "duplicate_ignored": 0.0,
          "missing_penalty": 8.0
        }
      },
      {
        "cause_id": "air_supply_issue",
        "cause_name": "Air / Supply Issue",
        "score": 28.0,
        "conclusion": "SUSPECTED",
        "supporting_evidence": [
          {
            "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
            "cause_id": "air_supply_issue",
            "relation": "SUPPORTS",
            "strength": "MODERATE",
            "source": "USER",
            "explanation": "Undersized deposits can result from air displacing material volume in the supply path.",
            "is_duplicate": false,
            "duplicate_of": null,
            "score_contribution": 12.0
          }
        ],
        "contradicting_evidence": [],
        "neutral_evidence": [],
        "missing_evidence": [
          "deposit_size=inconsistent has not been observed.",
          "runtime_pattern=after_prolonged_operation has not been observed.",
          "runtime_pattern=worsens_over_time has not been observed.",
          "frequency_pattern=intermittent has not been observed.",
          "location_pattern=all_points has not been observed.",
          "bubble_presence=visible_bubbles has not been observed.",
          "deposit_presence=missing has not been observed."
        ],
        "score_breakdown": {
          "base": 30.0,
          "positive_evidence": 12.0,
          "contradiction_penalty": 0.0,
          "duplicate_ignored": 0.0,
          "missing_penalty": 14.0
        }
      },
      {
        "cause_id": "equipment_condition",
        "cause_name": "Equipment Condition",
        "score": 28.0,
        "conclusion": "SUSPECTED",
        "supporting_evidence": [],
        "contradicting_evidence": [],
        "neutral_evidence": [
          {
            "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
            "cause_id": "equipment_condition",
            "relation": "NEUTRAL",
            "strength": "WEAK",
            "source": "USER",
            "explanation": "No evidence rule links 'deposit_size=undersized' to 'Equipment Condition'.",
            "is_duplicate": false,
            "duplicate_of": null,
            "score_contribution": 0.0
          }
        ],
        "missing_evidence": [
          "equipment_condition=worn has not been observed."
        ],
        "score_breakdown": {
          "base": 30.0,
          "positive_evidence": 0.0,
          "contradiction_penalty": 0.0,
          "duplicate_ignored": 0.0,
          "missing_penalty": 2.0
        }
      },
      {
        "cause_id": "material_condition",
        "cause_name": "Material Condition",
        "score": 20.0,
        "conclusion": "SUSPECTED",
        "supporting_evidence": [
          {
            "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
            "cause_id": "material_condition",
            "relation": "SUPPORTS",
            "strength": "WEAK",
            "source": "USER",
            "explanation": "Degraded or thickened material may reduce flow through the nozzle.",
            "is_duplicate": false,
            "duplicate_of": null,
            "score_contribution": 5.0
          }
        ],
        "contradicting_evidence": [],
        "neutral_evidence": [],
        "missing_evidence": [
          "deposit_size=inconsistent has not been observed.",
          "runtime_pattern=after_prolonged_operation has not been observed.",
          "runtime_pattern=worsens_over_time has not been observed.",
          "location_pattern=all_points has not been observed.",
          "bubble_presence=visible_bubbles has not been observed.",
          "spreading_behaviour=excessive_spread has not been observed.",
          "material_state=separated has not been observed.",
          "material_state=low_viscosity has not been observed.",
          "material_state=high_viscosity has not been observed."
        ],
        "score_breakdown": {
          "base": 30.0,
          "positive_evidence": 5.0,
          "contradiction_penalty": 0.0,
          "duplicate_ignored": 0.0,
          "missing_penalty": 15.0
        }
      },
      {
        "cause_id": "parameter_issue",
        "cause_name": "Parameter Issue",
        "score": 20.0,
        "conclusion": "SUSPECTED",
        "supporting_evidence": [],
        "contradicting_evidence": [],
        "neutral_evidence": [
          {
            "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
            "cause_id": "parameter_issue",
            "relation": "NEUTRAL",
            "strength": "WEAK",
            "source": "USER",
            "explanation": "No evidence rule links 'deposit_size=undersized' to 'Parameter Issue'.",
            "is_duplicate": false,
            "duplicate_of": null,
            "score_contribution": 0.0
          }
        ],
        "missing_evidence": [
          "deposit_size=oversized has not been observed.",
          "frequency_pattern=consistent has not been observed.",
          "spreading_behaviour=excessive_spread has not been observed.",
          "deposit_shape=abnormal has not been observed.",
          "deposit_shape=satellite_dots has not been observed."
        ],
        "score_breakdown": {
          "base": 30.0,
          "positive_evidence": 0.0,
          "contradiction_penalty": 0.0,
          "duplicate_ignored": 0.0,
          "missing_penalty": 10.0
        }
      }
    ],
    "next_question": {
      "question_id": "Q01",
      "text": "Does the problem occur immediately after startup or only after the machine has been running for a while?",
      "purpose": "Distinguishes thermal/time-related causes (air expansion, material viscosity change) from static issues.",
      "usefulness_score": 19.5,
      "target_causes": [
        "air_supply_issue",
        "material_condition",
        "pressure_instability",
        "temperature_issue"
      ],
      "already_answered": false
    },
    "next_check": {
      "check_id": "ACT04",
      "name": "Check Dispensing Pressure",
      "description": "Verify the dispensing pressure reading and stability over a period of operation.",
      "procedure": "1. Record the pressure setpoint.\n2. Monitor the actual pressure gauge reading during dispensing.\n3. Record pressure over 5-10 minute window.\n4. Note any fluctuations, drift, or spikes.\n5. Compare actual vs setpoint.\n6. Check for pneumatic leaks in the supply line.\n7. Document findings.",
      "priority_score": 12.3,
      "target_causes": [
        "pressure_instability",
        "air_supply_issue",
        "equipment_condition"
      ],
      "reasoning": "Addresses 3 applicable cause(s). Can produce 3.0 distinct evidence outcome(s).",
      "required_access": "pressure_system",
      "effort_level": "low"
    },
    "explanation": "Nozzle Restriction is currently the highest-supported hypothesis with evidence support 40/100.\nIt is supported by 1 observation(s).\n\nRecommended Action: Run troubleshooting check 'Check Dispensing Pressure' (ACT04, effort: low).",
    "analysis_revision": {
      "revision_number": 1,
      "timestamp": "2026-09-12T16:43:28.129140Z",
      "defect_code": "D01_TOO_LITTLE",
      "ranked_causes": [
        {
          "cause_id": "nozzle_restriction",
          "cause_name": "Nozzle Restriction",
          "score": 40.0,
          "conclusion": "SUSPECTED",
          "supporting_evidence": [
            {
              "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
              "cause_id": "nozzle_restriction",
              "relation": "SUPPORTS",
              "strength": "STRONG",
              "source": "USER",
              "explanation": "A restricted nozzle directly reduces the amount of material that can pass through.",
              "is_duplicate": false,
              "duplicate_of": null,
              "score_contribution": 20.0
            }
          ],
          "contradicting_evidence": [],
          "neutral_evidence": [],
          "missing_evidence": [
            "deposit_size=inconsistent has not been observed.",
            "runtime_pattern=worsens_over_time has not been observed.",
            "frequency_pattern=consistent has not been observed.",
            "location_pattern=specific_nozzle has not been observed.",
            "deposit_presence=missing has not been observed."
          ],
          "score_breakdown": {
            "base": 30.0,
            "positive_evidence": 20.0,
            "contradiction_penalty": 0.0,
            "duplicate_ignored": 0.0,
            "missing_penalty": 10.0
          }
        },
        {
          "cause_id": "pressure_instability",
          "cause_name": "Pressure Instability",
          "score": 34.0,
          "conclusion": "SUSPECTED",
          "supporting_evidence": [
            {
              "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
              "cause_id": "pressure_instability",
              "relation": "SUPPORTS",
              "strength": "MODERATE",
              "source": "USER",
              "explanation": "Low or dropping pressure reduces dispensed volume.",
              "is_duplicate": false,
              "duplicate_of": null,
              "score_contribution": 12.0
            }
          ],
          "contradicting_evidence": [],
          "neutral_evidence": [],
          "missing_evidence": [
            "deposit_size=inconsistent has not been observed.",
            "frequency_pattern=intermittent has not been observed.",
            "location_pattern=all_points has not been observed.",
            "pressure=fluctuating has not been observed."
          ],
          "score_breakdown": {
            "base": 30.0,
            "positive_evidence": 12.0,
            "contradiction_penalty": 0.0,
            "duplicate_ignored": 0.0,
            "missing_penalty": 8.0
          }
        },
        {
          "cause_id": "air_supply_issue",
          "cause_name": "Air / Supply Issue",
          "score": 28.0,
          "conclusion": "SUSPECTED",
          "supporting_evidence": [
            {
              "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
              "cause_id": "air_supply_issue",
              "relation": "SUPPORTS",
              "strength": "MODERATE",
              "source": "USER",
              "explanation": "Undersized deposits can result from air displacing material volume in the supply path.",
              "is_duplicate": false,
              "duplicate_of": null,
              "score_contribution": 12.0
            }
          ],
          "contradicting_evidence": [],
          "neutral_evidence": [],
          "missing_evidence": [
            "deposit_size=inconsistent has not been observed.",
            "runtime_pattern=after_prolonged_operation has not been observed.",
            "runtime_pattern=worsens_over_time has not been observed.",
            "frequency_pattern=intermittent has not been observed.",
            "location_pattern=all_points has not been observed.",
            "bubble_presence=visible_bubbles has not been observed.",
            "deposit_presence=missing has not been observed."
          ],
          "score_breakdown": {
            "base": 30.0,
            "positive_evidence": 12.0,
            "contradiction_penalty": 0.0,
            "duplicate_ignored": 0.0,
            "missing_penalty": 14.0
          }
        },
        {
          "cause_id": "equipment_condition",
          "cause_name": "Equipment Condition",
          "score": 28.0,
          "conclusion": "SUSPECTED",
          "supporting_evidence": [],
          "contradicting_evidence": [],
          "neutral_evidence": [
            {
              "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
              "cause_id": "equipment_condition",
              "relation": "NEUTRAL",
              "strength": "WEAK",
              "source": "USER",
              "explanation": "No evidence rule links 'deposit_size=undersized' to 'Equipment Condition'.",
              "is_duplicate": false,
              "duplicate_of": null,
              "score_contribution": 0.0
            }
          ],
          "missing_evidence": [
            "equipment_condition=worn has not been observed."
          ],
          "score_breakdown": {
            "base": 30.0,
            "positive_evidence": 0.0,
            "contradiction_penalty": 0.0,
            "duplicate_ignored": 0.0,
            "missing_penalty": 2.0
          }
        },
        {
          "cause_id": "material_condition",
          "cause_name": "Material Condition",
          "score": 20.0,
          "conclusion": "SUSPECTED",
          "supporting_evidence": [
            {
              "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
              "cause_id": "material_condition",
              "relation": "SUPPORTS",
              "strength": "WEAK",
              "source": "USER",
              "explanation": "Degraded or thickened material may reduce flow through the nozzle.",
              "is_duplicate": false,
              "duplicate_of": null,
              "score_contribution": 5.0
            }
          ],
          "contradicting_evidence": [],
          "neutral_evidence": [],
          "missing_evidence": [
            "deposit_size=inconsistent has not been observed.",
            "runtime_pattern=after_prolonged_operation has not been observed.",
            "runtime_pattern=worsens_over_time has not been observed.",
            "location_pattern=all_points has not been observed.",
            "bubble_presence=visible_bubbles has not been observed.",
            "spreading_behaviour=excessive_spread has not been observed.",
            "material_state=separated has not been observed.",
            "material_state=low_viscosity has not been observed.",
            "material_state=high_viscosity has not been observed."
          ],
          "score_breakdown": {
            "base": 30.0,
            "positive_evidence": 5.0,
            "contradiction_penalty": 0.0,
            "duplicate_ignored": 0.0,
            "missing_penalty": 15.0
          }
        },
        {
          "cause_id": "parameter_issue",
          "cause_name": "Parameter Issue",
          "score": 20.0,
          "conclusion": "SUSPECTED",
          "supporting_evidence": [],
          "contradicting_evidence": [],
          "neutral_evidence": [
            {
              "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
              "cause_id": "parameter_issue",
              "relation": "NEUTRAL",
              "strength": "WEAK",
              "source": "USER",
              "explanation": "No evidence rule links 'deposit_size=undersized' to 'Parameter Issue'.",
              "is_duplicate": false,
              "duplicate_of": null,
              "score_contribution": 0.0
            }
          ],
          "missing_evidence": [
            "deposit_size=oversized has not been observed.",
            "frequency_pattern=consistent has not been observed.",
            "spreading_behaviour=excessive_spread has not been observed.",
            "deposit_shape=abnormal has not been observed.",
            "deposit_shape=satellite_dots has not been observed."
          ],
          "score_breakdown": {
            "base": 30.0,
            "positive_evidence": 0.0,
            "contradiction_penalty": 0.0,
            "duplicate_ignored": 0.0,
            "missing_penalty": 10.0
          }
        }
      ],
      "new_evidence_summary": "Initial diagnostic assessment.",
      "changes_from_previous": []
    },
    "issue_condition": "UNRESOLVED",
    "warnings": []
  },
  "diagnosis": {
    "case_id": "4e158104-60d1-477c-a20a-62ae77e8a6e2",
    "defect": "D01_TOO_LITTLE",
    "defect_name": "Too Little Material",
    "ranked_causes": [
      {
        "cause_id": "nozzle_restriction",
        "cause_name": "Nozzle Restriction",
        "score": 40.0,
        "conclusion": "SUSPECTED",
        "supporting_evidence": [
          {
            "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
            "cause_id": "nozzle_restriction",
            "relation": "SUPPORTS",
            "strength": "STRONG",
            "source": "USER",
            "explanation": "A restricted nozzle directly reduces the amount of material that can pass through.",
            "is_duplicate": false,
            "duplicate_of": null,
            "score_contribution": 20.0
          }
        ],
        "contradicting_evidence": [],
        "neutral_evidence": [],
        "missing_evidence": [
          "deposit_size=inconsistent has not been observed.",
          "runtime_pattern=worsens_over_time has not been observed.",
          "frequency_pattern=consistent has not been observed.",
          "location_pattern=specific_nozzle has not been observed.",
          "deposit_presence=missing has not been observed."
        ],
        "score_breakdown": {
          "base": 30.0,
          "positive_evidence": 20.0,
          "contradiction_penalty": 0.0,
          "duplicate_ignored": 0.0,
          "missing_penalty": 10.0
        }
      },
      {
        "cause_id": "pressure_instability",
        "cause_name": "Pressure Instability",
        "score": 34.0,
        "conclusion": "SUSPECTED",
        "supporting_evidence": [
          {
            "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
            "cause_id": "pressure_instability",
            "relation": "SUPPORTS",
            "strength": "MODERATE",
            "source": "USER",
            "explanation": "Low or dropping pressure reduces dispensed volume.",
            "is_duplicate": false,
            "duplicate_of": null,
            "score_contribution": 12.0
          }
        ],
        "contradicting_evidence": [],
        "neutral_evidence": [],
        "missing_evidence": [
          "deposit_size=inconsistent has not been observed.",
          "frequency_pattern=intermittent has not been observed.",
          "location_pattern=all_points has not been observed.",
          "pressure=fluctuating has not been observed."
        ],
        "score_breakdown": {
          "base": 30.0,
          "positive_evidence": 12.0,
          "contradiction_penalty": 0.0,
          "duplicate_ignored": 0.0,
          "missing_penalty": 8.0
        }
      },
      {
        "cause_id": "air_supply_issue",
        "cause_name": "Air / Supply Issue",
        "score": 28.0,
        "conclusion": "SUSPECTED",
        "supporting_evidence": [
          {
            "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
            "cause_id": "air_supply_issue",
            "relation": "SUPPORTS",
            "strength": "MODERATE",
            "source": "USER",
            "explanation": "Undersized deposits can result from air displacing material volume in the supply path.",
            "is_duplicate": false,
            "duplicate_of": null,
            "score_contribution": 12.0
          }
        ],
        "contradicting_evidence": [],
        "neutral_evidence": [],
        "missing_evidence": [
          "deposit_size=inconsistent has not been observed.",
          "runtime_pattern=after_prolonged_operation has not been observed.",
          "runtime_pattern=worsens_over_time has not been observed.",
          "frequency_pattern=intermittent has not been observed.",
          "location_pattern=all_points has not been observed.",
          "bubble_presence=visible_bubbles has not been observed.",
          "deposit_presence=missing has not been observed."
        ],
        "score_breakdown": {
          "base": 30.0,
          "positive_evidence": 12.0,
          "contradiction_penalty": 0.0,
          "duplicate_ignored": 0.0,
          "missing_penalty": 14.0
        }
      },
      {
        "cause_id": "equipment_condition",
        "cause_name": "Equipment Condition",
        "score": 28.0,
        "conclusion": "SUSPECTED",
        "supporting_evidence": [],
        "contradicting_evidence": [],
        "neutral_evidence": [
          {
            "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
            "cause_id": "equipment_condition",
            "relation": "NEUTRAL",
            "strength": "WEAK",
            "source": "USER",
            "explanation": "No evidence rule links 'deposit_size=undersized' to 'Equipment Condition'.",
            "is_duplicate": false,
            "duplicate_of": null,
            "score_contribution": 0.0
          }
        ],
        "missing_evidence": [
          "equipment_condition=worn has not been observed."
        ],
        "score_breakdown": {
          "base": 30.0,
          "positive_evidence": 0.0,
          "contradiction_penalty": 0.0,
          "duplicate_ignored": 0.0,
          "missing_penalty": 2.0
        }
      },
      {
        "cause_id": "material_condition",
        "cause_name": "Material Condition",
        "score": 20.0,
        "conclusion": "SUSPECTED",
        "supporting_evidence": [
          {
            "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
            "cause_id": "material_condition",
            "relation": "SUPPORTS",
            "strength": "WEAK",
            "source": "USER",
            "explanation": "Degraded or thickened material may reduce flow through the nozzle.",
            "is_duplicate": false,
            "duplicate_of": null,
            "score_contribution": 5.0
          }
        ],
        "contradicting_evidence": [],
        "neutral_evidence": [],
        "missing_evidence": [
          "deposit_size=inconsistent has not been observed.",
          "runtime_pattern=after_prolonged_operation has not been observed.",
          "runtime_pattern=worsens_over_time has not been observed.",
          "location_pattern=all_points has not been observed.",
          "bubble_presence=visible_bubbles has not been observed.",
          "spreading_behaviour=excessive_spread has not been observed.",
          "material_state=separated has not been observed.",
          "material_state=low_viscosity has not been observed.",
          "material_state=high_viscosity has not been observed."
        ],
        "score_breakdown": {
          "base": 30.0,
          "positive_evidence": 5.0,
          "contradiction_penalty": 0.0,
          "duplicate_ignored": 0.0,
          "missing_penalty": 15.0
        }
      },
      {
        "cause_id": "parameter_issue",
        "cause_name": "Parameter Issue",
        "score": 20.0,
        "conclusion": "SUSPECTED",
        "supporting_evidence": [],
        "contradicting_evidence": [],
        "neutral_evidence": [
          {
            "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
            "cause_id": "parameter_issue",
            "relation": "NEUTRAL",
            "strength": "WEAK",
            "source": "USER",
            "explanation": "No evidence rule links 'deposit_size=undersized' to 'Parameter Issue'.",
            "is_duplicate": false,
            "duplicate_of": null,
            "score_contribution": 0.0
          }
        ],
        "missing_evidence": [
          "deposit_size=oversized has not been observed.",
          "frequency_pattern=consistent has not been observed.",
          "spreading_behaviour=excessive_spread has not been observed.",
          "deposit_shape=abnormal has not been observed.",
          "deposit_shape=satellite_dots has not been observed."
        ],
        "score_breakdown": {
          "base": 30.0,
          "positive_evidence": 0.0,
          "contradiction_penalty": 0.0,
          "duplicate_ignored": 0.0,
          "missing_penalty": 10.0
        }
      }
    ],
    "next_question": {
      "question_id": "Q01",
      "text": "Does the problem occur immediately after startup or only after the machine has been running for a while?",
      "purpose": "Distinguishes thermal/time-related causes (air expansion, material viscosity change) from static issues.",
      "usefulness_score": 19.5,
      "target_causes": [
        "air_supply_issue",
        "material_condition",
        "pressure_instability",
        "temperature_issue"
      ],
      "already_answered": false
    },
    "next_check": {
      "check_id": "ACT04",
      "name": "Check Dispensing Pressure",
      "description": "Verify the dispensing pressure reading and stability over a period of operation.",
      "procedure": "1. Record the pressure setpoint.\n2. Monitor the actual pressure gauge reading during dispensing.\n3. Record pressure over 5-10 minute window.\n4. Note any fluctuations, drift, or spikes.\n5. Compare actual vs setpoint.\n6. Check for pneumatic leaks in the supply line.\n7. Document findings.",
      "priority_score": 12.3,
      "target_causes": [
        "pressure_instability",
        "air_supply_issue",
        "equipment_condition"
      ],
      "reasoning": "Addresses 3 applicable cause(s). Can produce 3.0 distinct evidence outcome(s).",
      "required_access": "pressure_system",
      "effort_level": "low"
    },
    "explanation": "Nozzle Restriction is currently the highest-supported hypothesis with evidence support 40/100.\nIt is supported by 1 observation(s).\n\nRecommended Action: Run troubleshooting check 'Check Dispensing Pressure' (ACT04, effort: low).",
    "analysis_revision": {
      "revision_number": 1,
      "timestamp": "2026-09-12T16:43:28.129140Z",
      "defect_code": "D01_TOO_LITTLE",
      "ranked_causes": [
        {
          "cause_id": "nozzle_restriction",
          "cause_name": "Nozzle Restriction",
          "score": 40.0,
          "conclusion": "SUSPECTED",
          "supporting_evidence": [
            {
              "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
              "cause_id": "nozzle_restriction",
              "relation": "SUPPORTS",
              "strength": "STRONG",
              "source": "USER",
              "explanation": "A restricted nozzle directly reduces the amount of material that can pass through.",
              "is_duplicate": false,
              "duplicate_of": null,
              "score_contribution": 20.0
            }
          ],
          "contradicting_evidence": [],
          "neutral_evidence": [],
          "missing_evidence": [
            "deposit_size=inconsistent has not been observed.",
            "runtime_pattern=worsens_over_time has not been observed.",
            "frequency_pattern=consistent has not been observed.",
            "location_pattern=specific_nozzle has not been observed.",
            "deposit_presence=missing has not been observed."
          ],
          "score_breakdown": {
            "base": 30.0,
            "positive_evidence": 20.0,
            "contradiction_penalty": 0.0,
            "duplicate_ignored": 0.0,
            "missing_penalty": 10.0
          }
        },
        {
          "cause_id": "pressure_instability",
          "cause_name": "Pressure Instability",
          "score": 34.0,
          "conclusion": "SUSPECTED",
          "supporting_evidence": [
            {
              "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
              "cause_id": "pressure_instability",
              "relation": "SUPPORTS",
              "strength": "MODERATE",
              "source": "USER",
              "explanation": "Low or dropping pressure reduces dispensed volume.",
              "is_duplicate": false,
              "duplicate_of": null,
              "score_contribution": 12.0
            }
          ],
          "contradicting_evidence": [],
          "neutral_evidence": [],
          "missing_evidence": [
            "deposit_size=inconsistent has not been observed.",
            "frequency_pattern=intermittent has not been observed.",
            "location_pattern=all_points has not been observed.",
            "pressure=fluctuating has not been observed."
          ],
          "score_breakdown": {
            "base": 30.0,
            "positive_evidence": 12.0,
            "contradiction_penalty": 0.0,
            "duplicate_ignored": 0.0,
            "missing_penalty": 8.0
          }
        },
        {
          "cause_id": "air_supply_issue",
          "cause_name": "Air / Supply Issue",
          "score": 28.0,
          "conclusion": "SUSPECTED",
          "supporting_evidence": [
            {
              "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
              "cause_id": "air_supply_issue",
              "relation": "SUPPORTS",
              "strength": "MODERATE",
              "source": "USER",
              "explanation": "Undersized deposits can result from air displacing material volume in the supply path.",
              "is_duplicate": false,
              "duplicate_of": null,
              "score_contribution": 12.0
            }
          ],
          "contradicting_evidence": [],
          "neutral_evidence": [],
          "missing_evidence": [
            "deposit_size=inconsistent has not been observed.",
            "runtime_pattern=after_prolonged_operation has not been observed.",
            "runtime_pattern=worsens_over_time has not been observed.",
            "frequency_pattern=intermittent has not been observed.",
            "location_pattern=all_points has not been observed.",
            "bubble_presence=visible_bubbles has not been observed.",
            "deposit_presence=missing has not been observed."
          ],
          "score_breakdown": {
            "base": 30.0,
            "positive_evidence": 12.0,
            "contradiction_penalty": 0.0,
            "duplicate_ignored": 0.0,
            "missing_penalty": 14.0
          }
        },
        {
          "cause_id": "equipment_condition",
          "cause_name": "Equipment Condition",
          "score": 28.0,
          "conclusion": "SUSPECTED",
          "supporting_evidence": [],
          "contradicting_evidence": [],
          "neutral_evidence": [
            {
              "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
              "cause_id": "equipment_condition",
              "relation": "NEUTRAL",
              "strength": "WEAK",
              "source": "USER",
              "explanation": "No evidence rule links 'deposit_size=undersized' to 'Equipment Condition'.",
              "is_duplicate": false,
              "duplicate_of": null,
              "score_contribution": 0.0
            }
          ],
          "missing_evidence": [
            "equipment_condition=worn has not been observed."
          ],
          "score_breakdown": {
            "base": 30.0,
            "positive_evidence": 0.0,
            "contradiction_penalty": 0.0,
            "duplicate_ignored": 0.0,
            "missing_penalty": 2.0
          }
        },
        {
          "cause_id": "material_condition",
          "cause_name": "Material Condition",
          "score": 20.0,
          "conclusion": "SUSPECTED",
          "supporting_evidence": [
            {
              "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
              "cause_id": "material_condition",
              "relation": "SUPPORTS",
              "strength": "WEAK",
              "source": "USER",
              "explanation": "Degraded or thickened material may reduce flow through the nozzle.",
              "is_duplicate": false,
              "duplicate_of": null,
              "score_contribution": 5.0
            }
          ],
          "contradicting_evidence": [],
          "neutral_evidence": [],
          "missing_evidence": [
            "deposit_size=inconsistent has not been observed.",
            "runtime_pattern=after_prolonged_operation has not been observed.",
            "runtime_pattern=worsens_over_time has not been observed.",
            "location_pattern=all_points has not been observed.",
            "bubble_presence=visible_bubbles has not been observed.",
            "spreading_behaviour=excessive_spread has not been observed.",
            "material_state=separated has not been observed.",
            "material_state=low_viscosity has not been observed.",
            "material_state=high_viscosity has not been observed."
          ],
          "score_breakdown": {
            "base": 30.0,
            "positive_evidence": 5.0,
            "contradiction_penalty": 0.0,
            "duplicate_ignored": 0.0,
            "missing_penalty": 15.0
          }
        },
        {
          "cause_id": "parameter_issue",
          "cause_name": "Parameter Issue",
          "score": 20.0,
          "conclusion": "SUSPECTED",
          "supporting_evidence": [],
          "contradicting_evidence": [],
          "neutral_evidence": [
            {
              "observation_id": "2438f77b-8498-4aa5-95fe-834aa859731e",
              "cause_id": "parameter_issue",
              "relation": "NEUTRAL",
              "strength": "WEAK",
              "source": "USER",
              "explanation": "No evidence rule links 'deposit_size=undersized' to 'Parameter Issue'.",
              "is_duplicate": false,
              "duplicate_of": null,
              "score_contribution": 0.0
            }
          ],
          "missing_evidence": [
            "deposit_size=oversized has not been observed.",
            "frequency_pattern=consistent has not been observed.",
            "spreading_behaviour=excessive_spread has not been observed.",
            "deposit_shape=abnormal has not been observed.",
            "deposit_shape=satellite_dots has not been observed."
          ],
          "score_breakdown": {
            "base": 30.0,
            "positive_evidence": 0.0,
            "contradiction_penalty": 0.0,
            "duplicate_ignored": 0.0,
            "missing_penalty": 10.0
          }
        }
      ],
      "new_evidence_summary": "Initial diagnostic assessment.",
      "changes_from_previous": []
    },
    "issue_condition": "UNRESOLVED",
    "warnings": []
  }
}
```

---

### 4. Technician Question-Answer Submission

- **Method / Path:** `POST /api/v1/cases/{case_id}/answers`
- **Description:** Submits a technician answer for an active durable case, executes Member 2's `QuestionAnswerHandler` and diagnostic engine answer workflow, evaluates the next immutable analysis revision, and atomically persists the answer history, any newly derived observations, and the revision snapshot in PostgreSQL.

#### Lifecycle & Concurrency Contract

- **Atomic Revision Advance:** Each accepted answer atomically appends one `QuestionAnswer` history record, any newly generated observations (with `first_seen_revision = N + 1` and `source = USER`), and one new immutable `AnalysisRevision` snapshot (`revision_number = N + 1`).
- **Optimistic Concurrency Control:** The client must provide `expected_revision`. The update succeeds only if `expected_revision` matches the case's current persisted revision at transaction execution time.
- **Stale Revisions (409 Conflict):** If `expected_revision` does not match the latest persisted revision (e.g. concurrent answer submissions or replays), the transaction is rejected with `409 Conflict` and no partial rows are committed.
- **Member 2 Diagnostic Authority:** Question and answer semantics are validated by Member 2's `QuestionAnswerHandler`:
  - Questions are restricted to supported registry IDs (`Q01`–`Q15`). Unknown IDs return `422 Unprocessable Entity`.
  - Allowed options for each question are validated against registry rules. Invalid answers return `422 Unprocessable Entity`.
  - **`UNKNOWN`:** Recorded in answer history and advances the revision, but generates zero observations (no fabricated evidence).
  - **`NOT_APPLICABLE`:** Recorded in answer history and advances the revision, but generates zero observations (no false contradictions).
  - **Hypotheses:** User hypotheses are stored as observations but are never converted to confirmed causes by technician submission.
- **Idempotency & Replay:** Re-submitting the same payload with an outdated `expected_revision` safely fails with `409 Conflict`.

#### Request Schema (`SubmitAnswerRequest`)

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `question_id` | `string` | **Yes** | — | Identifier of the diagnostic question being answered (e.g. `"Q01"`). Must match a supported question. |
| `answer` | `string` | **Yes** | — | Technician answer value or key (e.g. `"after_prolonged_operation"`, `"UNKNOWN"`, `"NOT_APPLICABLE"`). Alias `"answer_value"` is accepted. |
| `expected_revision` | `integer` | **Yes** | — | Optimistic locking token matching the current persisted revision number (must be >= 1). |
| `answer_text` | `string` \| `null` | No | `null` | Optional technician description or supplemental statement. |

#### Input Validation Rules (HTTP 422)

1. **Unknown Question:** Supplying an unsupported question ID returns `422 Unprocessable Entity` (`"Unknown question_id: 'Q99'..."`).
2. **Invalid Answer Value:** Supplying an answer string outside the allowed options for that question returns `422 Unprocessable Entity` (`"Invalid answer '...' for question Q01..."`).
3. **Empty Fields:** Submitting an empty or whitespace-only `question_id` or `answer` returns `422 Unprocessable Entity`.
4. **Invalid Revision Number:** Submitting `expected_revision < 1` returns `422 Unprocessable Entity`.
5. **Malformed Case ID:** Path parameter that is not a valid UUID returns `422 Unprocessable Entity`.

#### Status and Error Codes

- `200 OK` — Answer accepted and revision N+1 committed.
- `404 Not Found` — Case ID does not exist in the database.
- `409 Conflict` — `expected_revision` is stale or does not match the current persisted revision.
- `422 Unprocessable Entity` — Invalid input schema, unsupported question ID, or invalid answer value.
- `500 Internal Server Error` — Persistence or diagnostic engine failure; internal error details and credentials are sanitized.

#### Representative Execution Example

> [!NOTE]
> The following request and response demonstrate real execution against PostgreSQL 16 using the implemented API.

##### Request Payload (`POST /api/v1/cases/{case_id}/answers`)
```json
{
  "question_id": "Q01",
  "answer": "after_prolonged_operation",
  "expected_revision": 1,
  "answer_text": "Dots decrease in volume after 20 minutes of continuous operation"
}
```

##### Response Payload (`200 OK`)
```json
{
  "case_id": "e1b68f9a-1175-4189-aedf-24a6cd637f97",
  "description": "Dispensing dots become smaller after running for 20 minutes",
  "material": "solder_paste",
  "method": "jetting",
  "machine_context": null,
  "defect_code": "D03_INCONSISTENT_SIZE",
  "defect_name": "Inconsistent Dot Size",
  "issue_condition": "UNRESOLVED",
  "created_at": "2026-09-13T07:48:20.123456Z",
  "observations": [
    {
      "id": "885b26eb-9f61-4ec7-a49b-a6e101876861",
      "observation_id": "885b26eb-9f61-4ec7-a49b-a6e101876861",
      "observation_type": "deposit_size",
      "value": "undersized",
      "original_text": "Dots become smaller",
      "statement_type": "USER_OBSERVATION",
      "source": "USER",
      "confidence": null,
      "timestamp": "2026-09-13T07:48:20.123456Z",
      "created_at": "2026-09-13T07:48:20.123456Z",
      "first_seen_revision": 1
    },
    {
      "id": "3c7ccb4e-c8ac-4ccf-a821-e695fa84016c",
      "observation_id": "3c7ccb4e-c8ac-4ccf-a821-e695fa84016c",
      "observation_type": "runtime_pattern",
      "value": "after_prolonged_operation",
      "original_text": "Q01: after_prolonged_operation",
      "statement_type": "USER_OBSERVATION",
      "source": "USER",
      "confidence": null,
      "timestamp": "2026-09-13T07:48:20.447108Z",
      "created_at": "2026-09-13T07:48:20.447108Z",
      "first_seen_revision": 2
    },
    {
      "id": "f98959fb-7ba5-4c0f-8514-e832822d5824",
      "observation_id": "f98959fb-7ba5-4c0f-8514-e832822d5824",
      "observation_type": "question_answer",
      "value": "Q01:after_prolonged_operation",
      "original_text": "Q01: after_prolonged_operation",
      "statement_type": "USER_OBSERVATION",
      "source": "USER",
      "confidence": null,
      "timestamp": "2026-09-13T07:48:20.447108Z",
      "created_at": "2026-09-13T07:48:20.447108Z",
      "first_seen_revision": 2
    }
  ],
  "initial_diagnosis": {
    "case_id": "e1b68f9a-1175-4189-aedf-24a6cd637f97",
    "defect": "D03_INCONSISTENT_SIZE",
    "defect_name": "Inconsistent Dot Size",
    "analysis_revision": {
      "revision_number": 1,
      "timestamp": "2026-09-13T07:48:20.123456Z",
      "defect_code": "D03_INCONSISTENT_SIZE",
      "new_evidence_summary": "Initial diagnostic assessment.",
      "changes_from_previous": []
    },
    "issue_condition": "UNRESOLVED",
    "warnings": []
  },
  "diagnosis": {
    "case_id": "e1b68f9a-1175-4189-aedf-24a6cd637f97",
    "defect": "D03_INCONSISTENT_SIZE",
    "defect_name": "Inconsistent Dot Size",
    "ranked_causes": [
      {
        "cause_id": "air_supply_issue",
        "cause_name": "Air / Supply Issue",
        "score": 70.0,
        "conclusion": "SUSPECTED",
        "supporting_evidence": [
          {
            "observation_id": "3c7ccb4e-c8ac-4ccf-a821-e695fa84016c",
            "cause_id": "air_supply_issue",
            "relation": "SUPPORTS",
            "strength": "STRONG",
            "source": "USER",
            "explanation": "Air supply depletion or compressor duty cycle issues manifest after prolonged operation.",
            "is_duplicate": false,
            "duplicate_of": null,
            "score_contribution": 20.0
          }
        ],
        "contradicting_evidence": [],
        "neutral_evidence": []
      }
    ],
    "analysis_revision": {
      "revision_number": 2,
      "timestamp": "2026-09-13T07:48:20.447108Z",
      "defect_code": "D03_INCONSISTENT_SIZE",
      "new_evidence_summary": "Updated with 4 observations and 0 check results.",
      "changes_from_previous": [
        "Air / Supply Issue increased from 50 to 70 (+20 pts).",
        "Pressure Instability increased from 34 to 46 (+12 pts).",
        "Material Condition increased from 32 to 44 (+12 pts)."
      ]
    },
    "issue_condition": "UNRESOLVED",
    "warnings": []
  },
  "current_revision": 2,
  "submitted_answer": {
    "question_id": "Q01",
    "answer_value": "after_prolonged_operation",
    "answer_text": "Dots decrease in volume after 20 minutes of continuous operation",
    "source": "USER",
    "answered_at": "2026-09-13T07:48:20.447108Z",
    "resulting_revision_number": 2
  },
  "previous_answers": [
    {
      "question_id": "Q01",
      "answer_value": "after_prolonged_operation",
      "answer_text": "Dots decrease in volume after 20 minutes of continuous operation",
      "source": "USER",
      "answered_at": "2026-09-13T07:48:20.447108Z",
      "resulting_revision_number": 2
    }
  ],
  "next_question": {
    "question_id": "Q02",
    "text": "Does the defect occur across all dispensing points or only at specific nozzles/locations?",
    "purpose": "Distinguishes system-wide causes (pressure, material) from localized causes (nozzle blockage, valve).",
    "usefulness_score": 18.5,
    "target_causes": [
      "nozzle_restriction",
      "air_supply_issue",
      "pressure_instability"
    ],
    "already_answered": false
  },
  "next_check": {
    "check_id": "ACT05",
    "name": "Perform Purge Cycle",
    "description": "Execute a material purge to clear trapped air and evaluate whether it improves dispensing.",
    "priority_score": 13.58,
    "target_causes": [
      "air_supply_issue",
      "nozzle_restriction"
    ],
    "effort_level": "low"
  }
}
```

---

### 5. Technician Troubleshooting Check-Result Submission

- **Method / Path:** `POST /api/v1/cases/{case_id}/check-results`
- **Description:** Submits a technician troubleshooting check execution and finding for an active durable case, executes Member 2's `CheckResultHandler` and diagnostic engine check-result workflow, evaluates the next immutable analysis revision, and atomically persists the check-result history, any newly derived observations, and the revision snapshot in PostgreSQL.

#### Lifecycle & Concurrency Contract

- **Atomic Revision Advance:** Each accepted check result atomically appends one `CaseCheckResult` history record, any newly generated observations (with `first_seen_revision = N + 1` and `source = USER_CHECK_RESULT`), and one new immutable `AnalysisRevision` snapshot (`revision_number = N + 1`).
- **Optimistic Concurrency Control:** The client must provide `expected_revision`. The update succeeds only if `expected_revision` matches the case's current persisted revision at transaction execution time.
- **Stale Revisions (409 Conflict):** If `expected_revision` does not match the latest persisted revision (e.g. concurrent check submissions or replays), the transaction is rejected with `409 Conflict` and no partial rows are committed.
- **Member 2 Diagnostic Authority & Semantic Boundaries:**
  - Check ID is validated against `actions.json`. Unknown IDs return `422 Unprocessable Entity`.
  - Specific outcomes are validated against action definitions. Invalid outcomes return `422 Unprocessable Entity`.
  - **Unfinished Statuses Rejected (422):** Execution statuses `PENDING` and `IN_PROGRESS` are strictly rejected with `422 Unprocessable Entity` before evidence evaluation or persistence, as this is a result submission endpoint.
  - **Non-Executing Statuses:** `BLOCKED`, `FAILED`, `UNKNOWN`, `NOT_APPLICABLE`, and `SKIPPED` checks are recorded in history and advance the revision, but their finding is strictly normalized to `UNKNOWN` and they generate zero diagnostic observations.
  - **Inconclusive Findings:** Completed checks with `INCONCLUSIVE`, `UNKNOWN`, or `NOT_APPLICABLE` findings are recorded in history and advance the revision, but generate zero diagnostic observations.
  - **Non-Directional Semantic Fix (ACT03):** Completed `ACT03` with outcome `consistent_but_wrong_size` generates the structured `CHECK_RESULT` observation but generates no directional `deposit_size` observation (neither `undersized` nor `oversized`).
  - **Strict Cause and Issue Independence:** A supporting check result increases evidence scores but **never** automatically confirms a root cause (which requires explicit confirmation) and **never** transitions the issue condition to `RESOLVED` (which requires independent recovery verification).
- **Idempotency & Replay:** Re-submitting the same payload with an outdated `expected_revision` safely fails with `409 Conflict`.

#### Request Schema (`SubmitCheckResultRequest`)

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `check_id` | `string` | **Yes** | — | Identifier of the troubleshooting check (e.g. `"ACT01"`, `"ACT02"`). Must match a supported action in `actions.json`. |
| `execution_status` | `string` | **Yes** | — | Execution status: `COMPLETED`, `BLOCKED`, `FAILED`, `UNKNOWN`, `NOT_APPLICABLE`, `SKIPPED`. Note: `PENDING` and `IN_PROGRESS` are rejected with `422`. |
| `finding` | `string` | **Yes** | — | Finding: `SUPPORTS`, `CONTRADICTS`, `INCONCLUSIVE`, `UNKNOWN`, `NOT_APPLICABLE`. |
| `expected_revision` | `integer` | **Yes** | — | Optimistic locking token matching the current persisted revision number (must be >= 1). |
| `outcome` | `string` \| `null` | No | `null` | Optional action outcome key (e.g. `"no_blockage"`, `"air_bubbles_found"`). Validated against action evidence mapping. |
| `finding_details` | `string` \| `null` | No | `null` | Optional technician description, equipment readings, or inspection notes. |

#### Input Validation Rules (HTTP 422)

1. **Unknown Check:** Supplying an unsupported check ID returns `422 Unprocessable Entity` (`"Unknown check_id: 'ACT99'..."`).
2. **Invalid Outcome:** Supplying an outcome key not defined in the check's evidence mapping returns `422 Unprocessable Entity` (`"Invalid outcome '...' for check ACT01..."`).
3. **Empty Fields:** Submitting an empty or whitespace-only `check_id` returns `422 Unprocessable Entity`.
4. **Invalid Revision Number:** Submitting `expected_revision < 1` returns `422 Unprocessable Entity`.
5. **Malformed Case ID:** Path parameter that is not a valid UUID returns `422 Unprocessable Entity`.
6. **Unfinished Execution Status:** Submitting `execution_status` as `PENDING` or `IN_PROGRESS` returns `422 Unprocessable Entity` without altering case state or evaluating evidence.

#### Status and Error Codes

- `200 OK` — Check result accepted and revision N+1 committed.
- `404 Not Found` — Case ID does not exist in the database.
- `409 Conflict` — `expected_revision` is stale or does not match the current persisted revision.
- `422 Unprocessable Entity` — Invalid input schema, unsupported check ID, or invalid outcome key.
- `500 Internal Server Error` — Persistence or diagnostic engine failure; internal error details and credentials are sanitized.

#### Representative Execution Example

##### Request Payload (`POST /api/v1/cases/{case_id}/check-results`)
```json
{
  "check_id": "ACT01",
  "execution_status": "COMPLETED",
  "finding": "CONTRADICTS",
  "outcome": "no_blockage",
  "finding_details": "No visible blockage under 50x microscope",
  "expected_revision": 1
}
```

##### Response Payload (`200 OK`)
```json
{
  "case_id": "514614df-ea4c-4855-be1e-98ea73135a8d",
  "description": "Dispense dots are shrinking over time during continuous operation",
  "material": "solder_paste",
  "method": "jetting",
  "machine_context": null,
  "defect_code": "D03_INCONSISTENT_SIZE",
  "defect_name": "Inconsistent Dot Size",
  "issue_condition": "UNRESOLVED",
  "created_at": "2026-09-14T14:19:10.123456Z",
  "observations": [
    {
      "id": "obs_1",
      "observation_id": "obs_1",
      "observation_type": "deposit_size",
      "value": "undersized",
      "original_text": "Dispense dots are shrinking",
      "statement_type": "USER_OBSERVATION",
      "source": "USER",
      "confidence": null,
      "timestamp": "2026-09-14T14:19:10.123456Z",
      "created_at": "2026-09-14T14:19:10.123456Z",
      "first_seen_revision": 1
    },
    {
      "id": "obs_2",
      "observation_id": "obs_2",
      "observation_type": "check_result",
      "value": "ACT01:no_blockage",
      "original_text": "No visible blockage under 50x microscope",
      "statement_type": "USER_OBSERVATION",
      "source": "USER_CHECK_RESULT",
      "confidence": null,
      "timestamp": "2026-09-14T14:19:11.123456Z",
      "created_at": "2026-09-14T14:19:11.123456Z",
      "first_seen_revision": 2
    }
  ],
  "initial_diagnosis": { ... },
  "diagnosis": {
    "case_id": "514614df-ea4c-4855-be1e-98ea73135a8d",
    "defect": "D03_INCONSISTENT_SIZE",
    "defect_name": "Inconsistent Dot Size",
    "ranked_causes": [ ... ],
    "analysis_revision": {
      "revision_number": 2,
      "defect_code": "D03_INCONSISTENT_SIZE",
      "new_evidence_summary": "Check 'Inspect Nozzle for Physical Blockage' (ACT01) was COMPLETED with finding CONTRADICTS. Outcome: no_blockage.",
      "changes_from_previous": [
        "Nozzle Restriction decreased from 40 to 10 (-30 pts)."
      ]
    },
    "issue_condition": "UNRESOLVED",
    "warnings": []
  },
  "current_revision": 2,
  "submitted_check_result": {
    "check_id": "ACT01",
    "execution_status": "COMPLETED",
    "finding": "CONTRADICTS",
    "finding_details": "No visible blockage under 50x microscope",
    "outcome": "no_blockage",
    "source": "USER_CHECK_RESULT",
    "checked_at": "2026-09-14T14:19:11.123456Z",
    "resulting_revision_number": 2
  },
  "previous_check_results": [
    {
      "check_id": "ACT01",
      "execution_status": "COMPLETED",
      "finding": "CONTRADICTS",
      "finding_details": "No visible blockage under 50x microscope",
      "outcome": "no_blockage",
      "source": "USER_CHECK_RESULT",
      "checked_at": "2026-09-14T14:19:11.123456Z",
      "resulting_revision_number": 2
    }
  ],
  "previous_answers": [],
  "next_question": { ... },
  "next_check": { ... }
}
```

---

### 6. Technician Explicit Root-Cause Confirmation Submission

- **Method / Path:** `POST /api/v1/cases/{case_id}/cause-confirmations`
- **Description:** Submits an explicit technician root-cause confirmation for an active durable case, executes Member 2's `confirm_cause()` diagnostic engine workflow, evaluates the next immutable analysis revision, and atomically persists the cause confirmation event and the revision snapshot in PostgreSQL.

#### Lifecycle & Concurrency Contract

- **Atomic Revision Advance:** Each accepted cause confirmation atomically appends one `CaseCauseConfirmation` history record and one new immutable `AnalysisRevision` snapshot (`revision_number = N + 1`).
- **Optimistic Concurrency Control:** The client must provide `expected_revision`. The update succeeds only if `expected_revision` matches the case's current persisted revision at transaction execution time.
- **Stale Revisions (409 Conflict):** If `expected_revision` does not match the latest persisted revision (e.g. concurrent submissions or replays), the transaction is rejected with `409 Conflict` and no rows or revisions are committed.
- **Member 2 Diagnostic Authority & Semantic Boundaries:**
  - `cause_id` is validated against candidate causes for the defect. Unknown or domain-invalid causes return `422 Unprocessable Entity` before persistence.
  - **Supporting Checks Do Not Confirm a Cause Automatically:** A supporting check result or high evidence score increases hypothesis ranking, but **never** confirms a cause automatically. Cause confirmation requires an explicit technician submission.
  - **Cause Confirmation Does Not Resolve the Issue:** Explicitly confirming a cause sets the candidate cause conclusion to `CONFIRMED`, but **never** transitions the overall `issue_condition` to `RESOLVED`. Issue resolution requires independent post-correction recovery verification.
  - **No Recovery Verification State:** The endpoint preserves issue resolution independently and never invents recovery or resolution state.
- **Idempotency & Replay:** Re-submitting the same payload with an outdated `expected_revision` safely fails with `409 Conflict`.

#### Request Schema (`SubmitCauseConfirmationRequest`)

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `cause_id` | `string` | **Yes** | — | Identifier of the candidate cause being confirmed as root cause (e.g. `"nozzle_restriction"`, `"pressure_instability"`). |
| `expected_revision` | `integer` | **Yes** | — | Optimistic locking token matching the current persisted revision number (must be >= 1). |
| `confirmed_by` | `string` | No | `"technician"` | Identifier or role of the user confirming the cause (maximum length 64 characters). |
| `notes` | `string` \| `null` | No | `null` | Optional technician notes or observations explaining the confirmation. |

#### Input Validation Rules (HTTP 422)

1. **Unknown or Invalid Cause:** Supplying a `cause_id` not found among candidate causes for the defect returns `422 Unprocessable Entity` (`"Cannot confirm cause '...'..."`).
2. **Performer Length Exceeded:** Submitting `confirmed_by` longer than 64 characters returns `422 Unprocessable Entity` before persistence.
3. **Empty Cause ID:** Submitting an empty or whitespace-only `cause_id` returns `422 Unprocessable Entity` (`"cause_id must be a non-empty string."`).
4. **Invalid Revision Number:** Submitting `expected_revision < 1` returns `422 Unprocessable Entity` (`"expected_revision must be >= 1."`).
5. **Malformed Case ID:** Path parameter that is not a valid UUID returns `422 Unprocessable Entity`.
6. **Extra Forbidden Fields:** Supplying forbidden top-level fields returns `422 Unprocessable Entity`.

#### Status and Error Codes

- `200 OK` — Cause confirmation accepted and revision N+1 committed.
- `404 Not Found` — Case ID does not exist in the database.
- `409 Conflict` — `expected_revision` is stale or does not match the current persisted revision.
- `422 Unprocessable Entity` — Invalid input schema, empty cause, invalid/unrecognized cause ID, or `confirmed_by` exceeding 64 characters.
- `500 Internal Server Error` — Unexpected internal diagnostic engine or database failure. Error responses are sanitized and do not echo internal exception details, stack traces, paths, or credentials.

#### Representative Execution Example

##### Request Payload (`POST /api/v1/cases/{case_id}/cause-confirmations`)
```json
{
  "cause_id": "nozzle_restriction",
  "expected_revision": 3,
  "confirmed_by": "technician",
  "notes": "Direct microscopic bore inspection confirms solder paste restriction."
}
```

##### Response Payload (`200 OK`)
```json
{
  "case_id": "514614df-ea4c-4855-be1e-98ea73135a8d",
  "description": "Dispense dots are shrinking over time during continuous operation",
  "material": "solder_paste",
  "method": "jetting",
  "machine_context": null,
  "defect_code": "D03_INCONSISTENT_SIZE",
  "defect_name": "Inconsistent Dot Size",
  "issue_condition": "UNRESOLVED",
  "created_at": "2026-09-14T14:19:10.123456Z",
  "observations": [ ... ],
  "initial_diagnosis": { ... },
  "diagnosis": {
    "case_id": "514614df-ea4c-4855-be1e-98ea73135a8d",
    "defect": "D03_INCONSISTENT_SIZE",
    "defect_name": "Inconsistent Dot Size",
    "ranked_causes": [
      {
        "cause_id": "nozzle_restriction",
        "cause_name": "Nozzle Restriction",
        "score": 40.0,
        "conclusion": "CONFIRMED",
        "supporting_evidence": [ ... ],
        "contradicting_evidence": [],
        "neutral_evidence": []
      }
    ],
    "analysis_revision": {
      "revision_number": 4,
      "defect_code": "D03_INCONSISTENT_SIZE",
      "new_evidence_summary": "Cause 'nozzle_restriction' explicitly confirmed by technician.",
      "changes_from_previous": []
    },
    "issue_condition": "UNRESOLVED",
    "warnings": []
  },
  "current_revision": 4,
  "submitted_confirmation": {
    "cause_id": "nozzle_restriction",
    "confirmed_by": "technician",
    "notes": "Direct microscopic bore inspection confirms solder paste restriction.",
    "confirmed_at": "2026-09-14T14:21:00.123456Z",
    "resulting_revision_number": 4
  },
  "previous_confirmations": [
    {
      "cause_id": "nozzle_restriction",
      "confirmed_by": "technician",
      "notes": "Direct microscopic bore inspection confirms solder paste restriction.",
      "confirmed_at": "2026-09-14T14:21:00.123456Z",
      "resulting_revision_number": 4
    }
  ],
  "previous_check_results": [
    {
      "check_id": "ACT02",
      "execution_status": "COMPLETED",
      "finding": "SUPPORTS",
      "outcome": "air_bubbles_found",
      "resulting_revision_number": 3
    }
  ],
  "previous_answers": [
    {
      "question_id": "Q01",
      "answer_value": "after_prolonged_operation",
      "resulting_revision_number": 2
    }
  ],
  "confirmed_cause": "nozzle_restriction",
  "selected_cause_conclusion": "CONFIRMED",
  "next_question": { ... },
  "next_check": { ... }
}
```

---

### 7. Recovery Action and Post-Correction Verification Submission

#### 7.1 Record Recovery Action

- **Method / Path:** `POST /api/v1/cases/{case_id}/recovery-actions`
- **Description:** Records that a corrective or recovery action has been applied by a technician or engineer. Transitions the issue condition from `UNRESOLVED` to `RECOVERY_PENDING_VERIFICATION` via the domain `StateManager`. Does **not** resolve the issue.

##### Lifecycle & Concurrency Contract
- **Atomic Revision Advance:** Each accepted recovery action atomically appends one `CaseLifecycleEvent` record (event_type: `RECOVERY_ACTION`), advances `cases.issue_condition` to `RECOVERY_PENDING_VERIFICATION`, and appends one new immutable `AnalysisRevision` snapshot (`revision_number = N + 1`).
- **Optimistic Concurrency Control:** Requires `expected_revision`. Stale revisions return `409 Conflict` and commit no changes.
- **State Machine Enforcement:** Uses `StateManager.transition_issue_condition(...)`. Transitions are valid from `UNRESOLVED`. Attempting a recovery action from `RESOLVED` returns `422 Unprocessable Entity`.
- **Independence from Cause Confirmation:** An issue may undergo recovery whether a root cause has been confirmed or not. Root cause conclusions are preserved unchanged.

##### Request Schema (`SubmitRecoveryActionRequest`)

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `expected_revision` | `integer` | **Yes** | — | Optimistic locking token matching current revision (must be >= 1). |
| `recovery_details` | `string` | **Yes** | — | Description of corrective action applied (unrestricted text). |
| `performed_by` | `string` | No | `"technician"` | Identifier or role of actor performing the recovery (max length 64 characters). |

##### Status and Error Codes
- `200 OK` — Recovery action accepted and committed.
- `404 Not Found` — Case ID does not exist.
- `409 Conflict` — `expected_revision` is stale or does not match current persisted revision.
- `422 Unprocessable Entity` — Illegal transition (e.g. attempting recovery action from `RESOLVED`), empty details, `performed_by` exceeding 64 characters, or malformed UUID.
- `500 Internal Server Error` — Sanitized unexpected error (e.g. unexpected internal transition or persistence failure); raw exception details or internal paths are never reflected.

##### Representative Request Example
```json
{
  "expected_revision": 4,
  "recovery_details": "Replaced worn dispensing nozzle with 0.25mm gauge needle and purged fluid line.",
  "performed_by": "technician"
}
```

##### Representative Response Example (`200 OK`)
```json
{
  "case_id": "514614df-ea4c-4855-be1e-98ea73135a8d",
  "issue_condition": "RECOVERY_PENDING_VERIFICATION",
  "current_revision": 5,
  "submitted_recovery_action": {
    "event_type": "RECOVERY_ACTION",
    "prior_issue_condition": "UNRESOLVED",
    "resulting_issue_condition": "RECOVERY_PENDING_VERIFICATION",
    "resulting_revision_number": 5,
    "actor": "technician",
    "details": "Replaced worn dispensing nozzle with 0.25mm gauge needle and purged fluid line.",
    "verification_passed": null,
    "created_at": "2026-09-14T14:22:00.123456Z"
  },
  "lifecycle_events": [ ... ],
  "diagnosis": {
    "issue_condition": "RECOVERY_PENDING_VERIFICATION",
    "analysis_revision": {
      "revision_number": 5
    }
  }
}
```

---

#### 7.2 Record Recovery Verification

- **Method / Path:** `POST /api/v1/cases/{case_id}/recovery-verifications`
- **Description:** Records an explicit post-correction verification outcome (e.g. test shots or inspection). If `verification_passed = true`, transitions the issue condition to `RESOLVED`. If `verification_passed = false`, reverts the issue condition to `UNRESOLVED`.

##### Lifecycle & Concurrency Contract
- **Atomic Revision Advance:** Each accepted verification atomically appends one `CaseLifecycleEvent` record (event_type: `RECOVERY_VERIFICATION`), updates `cases.issue_condition`, and appends one new immutable `AnalysisRevision` snapshot (`revision_number = N + 1`).
- **Optimistic Concurrency Control:** Requires `expected_revision`. Stale revisions return `409 Conflict`.
- **Precondition & State Machine Enforcement:** Recovery verification is accepted **only** when the current persisted issue condition is `RECOVERY_PENDING_VERIFICATION`. Verification submitted from `UNRESOLVED` or `RESOLVED` (for both `verification_passed=true` and `verification_passed=false`) returns controlled `422 Unprocessable Entity` before any lifecycle mutation.
- **Independence from Cause Confirmation:** An issue can be resolved with or without a confirmed root cause. A confirmed cause remains confirmed even if recovery verification fails.
- **No Recurrence API:** Recurrence transitions (`RECURRED`) are not supported by this endpoint.

##### Request Schema (`SubmitRecoveryVerificationRequest`)

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `expected_revision` | `integer` | **Yes** | — | Optimistic locking token matching current revision (must be >= 1). |
| `verification_passed` | `boolean` | **Yes** | — | Outcome: `true` transitions to `RESOLVED`, `false` transitions to `UNRESOLVED`. |
| `verification_details` | `string` | **Yes** | — | Verification test results, observations, or measurement details (unrestricted text). |
| `verified_by` | `string` | No | `"technician"` | Identifier or role of actor verifying the recovery (max length 64 characters). |

##### Status and Error Codes
- `200 OK` — Verification accepted and committed.
- `404 Not Found` — Case ID does not exist.
- `409 Conflict` — `expected_revision` is stale or replayed.
- `422 Unprocessable Entity` — Precondition or illegal transition failure (verification requested when current condition is not `RECOVERY_PENDING_VERIFICATION`, such as from `UNRESOLVED` or `RESOLVED`), empty details, `verified_by` exceeding 64 characters, or malformed UUID.
- `500 Internal Server Error` — Sanitized unexpected error (e.g. unexpected internal state manager or persistence failure); raw internal exception details or paths are never reflected.

##### Representative Request Example
```json
{
  "expected_revision": 5,
  "verification_passed": true,
  "verification_details": "Ran 50 test dot shots; dot diameter measured at 0.45mm +/- 0.02mm, well within tolerance.",
  "verified_by": "qa_engineer"
}
```

##### Representative Response Example (`200 OK`)
```json
{
  "case_id": "514614df-ea4c-4855-be1e-98ea73135a8d",
  "issue_condition": "RESOLVED",
  "current_revision": 6,
  "submitted_recovery_verification": {
    "event_type": "RECOVERY_VERIFICATION",
    "prior_issue_condition": "RECOVERY_PENDING_VERIFICATION",
    "resulting_issue_condition": "RESOLVED",
    "resulting_revision_number": 6,
    "actor": "qa_engineer",
    "details": "Ran 50 test dot shots; dot diameter measured at 0.45mm +/- 0.02mm, well within tolerance.",
    "verification_passed": true,
    "created_at": "2026-09-14T14:25:00.123456Z"
  },
  "lifecycle_events": [ ... ],
  "diagnosis": {
    "issue_condition": "RESOLVED",
    "analysis_revision": {
      "revision_number": 6
    }
  }
}
```

---

### 8. Resolved-Issue Recurrence Reporting

#### 8.1 Report Recurrence of a Resolved Issue

- **Method / Path:** `POST /api/v1/cases/{case_id}/recurrences`
- **Description:** Records explicit reporting that a previously verified `RESOLVED` issue has recurred. Transitions the case issue condition from `RESOLVED` to `RECURRED` via the domain `StateManager`. Does **not** automatically start a new recovery cycle and does **not** alter cause confirmation conclusions.

##### Lifecycle & Concurrency Contract
- **Atomic Revision Advance:** Each accepted recurrence submission atomically appends one `CaseLifecycleEvent` record (event_type: `RECURRENCE`), advances `cases.issue_condition` to `RECURRED`, and appends one new immutable `AnalysisRevision` snapshot (`revision_number = N + 1`).
- **Optimistic Concurrency Control:** Requires `expected_revision`. Stale or replayed revisions return `409 Conflict` and commit zero mutations.
- **Precondition & State Machine Enforcement:** Recurrence reporting is accepted **only** when the current persisted issue condition is `RESOLVED`. Recurrence requested from `UNRESOLVED`, `RECOVERY_PENDING_VERIFICATION`, or `RECURRED` returns controlled `422 Unprocessable Entity` before any lifecycle mutation.
- **Independence from Cause Conclusions:** A recurrence report leaves existing cause conclusions unchanged. A previously confirmed cause remains confirmed; an unconfirmed cause does not become confirmed merely because recurrence was reported.
- **No Automatic Recovery or Report Generation:** Does not automatically start a new recovery cycle, enter `RECOVERY_PENDING_VERIFICATION`, or generate reports/exports.

##### Request Schema (`SubmitRecurrenceRequest`)

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `expected_revision` | `integer` | **Yes** | — | Optimistic locking token matching current revision (must be >= 1). |
| `recurrence_details` | `string` | **Yes** | — | Description of recurred defect observations or symptoms (unrestricted non-empty text). |
| `reported_by` | `string` | No | `"technician"` | Identifier or role of actor reporting the recurrence (max length 64 characters). |

##### Status and Error Codes
- `200 OK` — Recurrence accepted and revision N+1 committed.
- `404 Not Found` — Case ID does not exist.
- `409 Conflict` — `expected_revision` is stale or replayed.
- `422 Unprocessable Entity` — Precondition or validation failure (issue condition not `RESOLVED`, e.g. `UNRESOLVED`, `RECOVERY_PENDING_VERIFICATION`, or `RECURRED`; empty details; `reported_by` exceeding 64 characters; or malformed UUID).
- `500 Internal Server Error` — Sanitized unexpected error (e.g. unexpected internal state manager or persistence failure); raw internal exception details or paths are never reflected.

##### Representative Request Example
```json
{
  "expected_revision": 6,
  "recurrence_details": "Dot size variation observed again after 2 hours of continuous dispensing.",
  "reported_by": "technician_dan"
}
```

##### Representative Response Example (`200 OK`)
```json
{
  "case_id": "514614df-ea4c-4855-be1e-98ea73135a8d",
  "issue_condition": "RECURRED",
  "current_revision": 7,
  "submitted_recurrence": {
    "event_type": "RECURRENCE",
    "prior_issue_condition": "RESOLVED",
    "resulting_issue_condition": "RECURRED",
    "resulting_revision_number": 7,
    "actor": "technician_dan",
    "details": "Dot size variation observed again after 2 hours of continuous dispensing.",
    "verification_passed": null,
    "created_at": "2026-09-14T16:00:00.123456Z"
  },
  "submitted_event": {
    "event_type": "RECURRENCE",
    "prior_issue_condition": "RESOLVED",
    "resulting_issue_condition": "RECURRED",
    "resulting_revision_number": 7,
    "actor": "technician_dan",
    "details": "Dot size variation observed again after 2 hours of continuous dispensing.",
    "verification_passed": null,
    "created_at": "2026-09-14T16:00:00.123456Z"
  },
  "lifecycle_events": [ ... ],
  "confirmed_cause": "nozzle_restriction",
  "diagnosis": {
    "issue_condition": "RECURRED",
    "analysis_revision": {
      "revision_number": 7
    }
  }
}
```

---

### 9. Durable Case Report Export

#### 9.1 Export Full Case Report

- **Method / Path:** `GET /api/v1/cases/{case_id}/report`
- **Description:** Returns a complete, deterministic, and durable read-model report of a troubleshooting case. Assembles the report entirely from persistent database records and audit revision history without invoking the diagnostic engine, recalculating scores, advancing state, creating revisions, or writing audit records.

##### Read-Only & Zero Recalculation Contract
- **No Diagnostic Recalculation:** Assembles the report strictly from persisted tables (`cases`, `analysis_revisions`, `question_answer_revisions`, `check_result_revisions`, `cause_confirmation_revisions`, `case_lifecycle_events`). Diagnostic engine rules and scoring logic are never invoked.
- **Zero Mutation:** Operates strictly within a read-only transaction. No database tables are inserted, updated, or deleted; no analysis revisions or lifecycle event records are generated.
- **Deterministic History Ordering:** All audit event arrays (`question_answers`, `check_results`, `cause_confirmations`, `lifecycle_events`) are guaranteed to be sorted in strict ascending chronological and revision order.
- **Empty History Handling:** Cases with no question answers, check results, cause confirmations, or lifecycle events return empty lists (`[]`) without synthetic or fabricated events.
- **Document Rendering Notice:** Returns structured JSON only. Binary PDF, Word/DOCX, or HTML document rendering is explicitly deferred to future increments.

##### Response Schema (`CaseReportResponse`)

| Field | Type | Required | Description |
|---|---|---|---|
| `case_id` | `string` | **Yes** | Unique case identifier. |
| `current_revision` | `integer` | **Yes** | Current revision number of the case. |
| `defect_code` | `string` | No | Persisted defect code identifier (e.g. 'D03_INCONSISTENT_SIZE'). |
| `defect_name` | `string` | No | Persisted human-readable defect title. |
| `description` | `string` | **Yes** | Problem description provided by technician. |
| `material` | `string` | No | Dispensed fluid material name or category. |
| `method` | `string` | No | Dispensing method (e.g. 'jetting', 'time_pressure'). |
| `machine_context` | `object` | No | Equipment/process parameters. |
| `issue_condition` | `string` | **Yes** | Current issue condition (`UNRESOLVED`, `RECOVERY_PENDING_VERIFICATION`, `RESOLVED`, `RECURRED`). |
| `created_at` | `datetime` | **Yes** | Case creation timestamp (ISO-8601). |
| `current_diagnosis` | `DiagnosisResult` | **Yes** | Current analysis snapshot from the latest analysis revision (aliased as `diagnosis`). |
| `diagnosis` | `DiagnosisResult` | **Yes** | Alias for `current_diagnosis`. |
| `question_answers` | `array[QuestionAnswerRecord]` | **Yes** | Historical question-answer submissions in ascending revision order (aliased as `question_answer_history`). |
| `question_answer_history` | `array[QuestionAnswerRecord]` | **Yes** | Alias for `question_answers`. |
| `check_results` | `array[CheckResultRecord]` | **Yes** | Historical troubleshooting check results in ascending revision order (aliased as `troubleshooting_check_history`). |
| `troubleshooting_check_history` | `array[CheckResultRecord]` | **Yes** | Alias for `check_results`. |
| `cause_confirmations` | `array[CauseConfirmationRecord]` | **Yes** | Historical cause confirmation submissions in ascending revision order (aliased as `cause_confirmation_history`). |
| `cause_confirmation_history` | `array[CauseConfirmationRecord]` | **Yes** | Alias for `cause_confirmations`. |
| `lifecycle_events` | `array[LifecycleEventRecord]` | **Yes** | Complete audit log of lifecycle transitions in ascending revision order (aliased as `issue_lifecycle_history`). |
| `issue_lifecycle_history` | `array[LifecycleEventRecord]` | **Yes** | Alias for `lifecycle_events`. |
| `outcome_summary` | `CaseOutcomeSummary` | **Yes** | Compact summary of the persisted outcome state (aliased as `current_outcome_summary`). |
| `current_outcome_summary` | `CaseOutcomeSummary` | **Yes** | Alias for `outcome_summary`. |

##### Outcome Summary Schema (`CaseOutcomeSummary`)

| Field | Type | Required | Description |
|---|---|---|---|
| `issue_condition` | `string` | **Yes** | Current case issue condition (`UNRESOLVED`, `RECOVERY_PENDING_VERIFICATION`, `RESOLVED`, or `RECURRED`). |
| `current_revision` | `integer` | **Yes** | Current revision number of the case. |
| `confirmed_causes` | `array[string]` | **Yes** | List of confirmed root causes (aliased as `currently_confirmed_causes`). |
| `currently_confirmed_causes` | `array[string]` | **Yes** | Alias for `confirmed_causes`. |
| `is_resolved` | `boolean` | **Yes** | Whether the case is currently in `RESOLVED` condition (aliased as `resolved`). |
| `resolved` | `boolean` | **Yes** | Alias for `is_resolved`. |

##### Status and Error Codes
- `200 OK` — Complete report assembled and returned.
- `404 Not Found` — Case ID does not exist in database.
- `422 Unprocessable Entity` — Invalid case ID format (not a valid UUID).
- `500 Internal Server Error` — Sanitized unexpected error during report assembly; raw internal details and paths are never exposed.

##### Representative Request Example
```http
GET /api/v1/cases/514614df-ea4c-4855-be1e-98ea73135a8d/report HTTP/1.1
Host: localhost:8000
Accept: application/json
```

##### Representative Response Example (`200 OK`)
```json
{
  "case_id": "514614df-ea4c-4855-be1e-98ea73135a8d",
  "current_revision": 6,
  "defect_code": "D03_INCONSISTENT_SIZE",
  "defect_name": "Inconsistent Dot Size",
  "description": "Dispense dots are shrinking over time during continuous operation",
  "material": "solder_paste",
  "method": "jetting",
  "machine_context": null,
  "issue_condition": "RESOLVED",
  "created_at": "2026-09-14T10:00:00Z",
  "current_diagnosis": {
    "defect_category": "D03_INCONSISTENT_SIZE",
    "defect_name": "Inconsistent Dot Size",
    "issue_condition": "RESOLVED",
    "analysis_revision": {
      "revision_number": 6
    },
    "ranked_causes": [
      {
        "cause_id": "nozzle_restriction",
        "name": "Nozzle Restriction / Clog",
        "score": 45.0,
        "is_confirmed": true,
        "conclusion": "CONFIRMED"
      }
    ],
    "unconfirmed_causes": []
  },
  "diagnosis": {
    "defect_category": "D03_INCONSISTENT_SIZE",
    "defect_name": "Inconsistent Dot Size",
    "issue_condition": "RESOLVED",
    "analysis_revision": {
      "revision_number": 6
    },
    "ranked_causes": [
      {
        "cause_id": "nozzle_restriction",
        "name": "Nozzle Restriction / Clog",
        "score": 45.0,
        "is_confirmed": true,
        "conclusion": "CONFIRMED"
      }
    ],
    "unconfirmed_causes": []
  },
  "question_answers": [
    {
      "question_id": "Q01",
      "answer_value": "after_prolonged_operation",
      "answer_text": null,
      "source": "USER",
      "answered_at": "2026-09-14T10:05:00Z",
      "resulting_revision_number": 2
    }
  ],
  "question_answer_history": [
    {
      "question_id": "Q01",
      "answer_value": "after_prolonged_operation",
      "answer_text": null,
      "source": "USER",
      "answered_at": "2026-09-14T10:05:00Z",
      "resulting_revision_number": 2
    }
  ],
  "check_results": [
    {
      "check_id": "ACT02",
      "execution_status": "COMPLETED",
      "finding": "SUPPORTS",
      "finding_details": null,
      "outcome": "air_bubbles_found",
      "source": "USER_CHECK_RESULT",
      "checked_at": "2026-09-14T10:10:00Z",
      "resulting_revision_number": 3
    }
  ],
  "troubleshooting_check_history": [
    {
      "check_id": "ACT02",
      "execution_status": "COMPLETED",
      "finding": "SUPPORTS",
      "finding_details": null,
      "outcome": "air_bubbles_found",
      "source": "USER_CHECK_RESULT",
      "checked_at": "2026-09-14T10:10:00Z",
      "resulting_revision_number": 3
    }
  ],
  "cause_confirmations": [
    {
      "cause_id": "nozzle_restriction",
      "confirmed_by": "lead_tech",
      "notes": "Verified restriction via microscopic inspection",
      "confirmed_at": "2026-09-14T10:12:00Z",
      "resulting_revision_number": 4
    }
  ],
  "cause_confirmation_history": [
    {
      "cause_id": "nozzle_restriction",
      "confirmed_by": "lead_tech",
      "notes": "Verified restriction via microscopic inspection",
      "confirmed_at": "2026-09-14T10:12:00Z",
      "resulting_revision_number": 4
    }
  ],
  "lifecycle_events": [
    {
      "event_type": "RECOVERY_ACTION",
      "prior_issue_condition": "UNRESOLVED",
      "resulting_issue_condition": "RECOVERY_PENDING_VERIFICATION",
      "resulting_revision_number": 5,
      "actor": "technician",
      "details": "Replaced fluid syringe and cleaned nozzle",
      "verification_passed": null,
      "created_at": "2026-09-14T10:15:00Z"
    },
    {
      "event_type": "RECOVERY_VERIFICATION",
      "prior_issue_condition": "RECOVERY_PENDING_VERIFICATION",
      "resulting_issue_condition": "RESOLVED",
      "resulting_revision_number": 6,
      "actor": "qa_engineer",
      "details": "100 test shots verified within nominal dot tolerance",
      "verification_passed": true,
      "created_at": "2026-09-14T10:20:00Z"
    }
  ],
  "issue_lifecycle_history": [
    {
      "event_type": "RECOVERY_ACTION",
      "prior_issue_condition": "UNRESOLVED",
      "resulting_issue_condition": "RECOVERY_PENDING_VERIFICATION",
      "resulting_revision_number": 5,
      "actor": "technician",
      "details": "Replaced fluid syringe and cleaned nozzle",
      "verification_passed": null,
      "created_at": "2026-09-14T10:15:00Z"
    },
    {
      "event_type": "RECOVERY_VERIFICATION",
      "prior_issue_condition": "RECOVERY_PENDING_VERIFICATION",
      "resulting_issue_condition": "RESOLVED",
      "resulting_revision_number": 6,
      "actor": "qa_engineer",
      "details": "100 test shots verified within nominal dot tolerance",
      "verification_passed": true,
      "created_at": "2026-09-14T10:20:00Z"
    }
  ],
  "outcome_summary": {
    "issue_condition": "RESOLVED",
    "current_revision": 6,
    "confirmed_causes": [
      "nozzle_restriction"
    ],
    "currently_confirmed_causes": [
      "nozzle_restriction"
    ],
    "is_resolved": true,
    "resolved": true
  },
  "current_outcome_summary": {
    "issue_condition": "RESOLVED",
    "current_revision": 6,
    "confirmed_causes": [
      "nozzle_restriction"
    ],
    "currently_confirmed_causes": [
      "nozzle_restriction"
    ],
    "is_resolved": true,
    "resolved": true
  }
}
```

---

## Error Handling

### HTTP 404 Not Found
Returned when requesting a case ID that does not exist in the database.

Example (`GET /api/v1/cases/00000000-0000-0000-0000-000000000000`):
```json
{
  "detail": "Case '00000000-0000-0000-0000-000000000000' not found."
}
```

### HTTP 409 Conflict
Returned when submitting a question answer, troubleshooting check result, cause confirmation, recovery action, recovery verification, or recurrence report with an `expected_revision` that does not match the latest persisted revision of the case (optimistic concurrency violation).

Example (`POST /api/v1/cases/e1b68f9a-1175-4189-aedf-24a6cd637f97/answers` with stale `expected_revision: 1` when case is at revision 2):
```json
{
  "detail": "Stale revision for case 'e1b68f9a-1175-4189-aedf-24a6cd637f97': expected revision 1, but current revision is 2."
}
```
*Note: No partial writes, answer records, check result records, confirmation records, lifecycle event records, observation rows, or revision snapshots are committed on a 409 Conflict.*

### HTTP 422 Unprocessable Entity
Returned when request input fails validation rules. Validation errors are returned as a structured array or error detail.

Example: Malformed case ID in path:
```json
{
  "detail": "Invalid case_id format: 'not-a-valid-uuid-12345' must be a valid UUID."
}
```

Example: Insufficient evidence input (empty/whitespace description with no observations, or defect code alone):
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": [
        "body"
      ],
      "msg": "Value error, Insufficient evidence input: provide a non-empty description or at least one observation.",
      "input": {
        "description": "   "
      },
      "ctx": {
        "error": {}
      }
    }
  ]
}
```

Example: Unknown defect code:
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": [
        "body"
      ],
      "msg": "Value error, Unknown defect code: 'D99_UNKNOWN'",
      "input": {
        "description": "Dispensing dots missing",
        "defect_code": "D99_UNKNOWN"
      },
      "ctx": {
        "error": {}
      }
    }
  ]
}
```

Example: Inconclusive diagnosis evidence (no defect category identified):
```json
{
  "detail": "Diagnostic evaluation could not identify a defect category from the provided evidence."
}
```

Example: Extra forbidden field (such as caller-supplied `case_id` or `analysis_revision`):
```json
{
  "detail": [
    {
      "type": "extra_forbidden",
      "loc": [
        "body",
        "case_id"
      ],
      "msg": "Extra inputs are not permitted",
      "input": "custom-id"
    }
  ]
}
```

### HTTP 500 Internal Server Error
Returned when the internal diagnostic engine or database encounters an unhandled exception.

Example response (initial diagnosis evaluation failure):
```json
{
  "detail": "An unexpected error occurred during diagnosis evaluation."
}
```

Example response (durable case creation failure):
```json
{
  "detail": "An unexpected error occurred during case creation."
}
```

Example response (durable case retrieval failure):
```json
{
  "detail": "An unexpected error occurred while retrieving the case."
}
```

Example response (recovery action failure):
```json
{
  "detail": "An unexpected error occurred while recording the recovery action."
}
```

Example response (recovery verification failure):
```json
{
  "detail": "An unexpected error occurred while recording the recovery verification."
}
```

Example response (recurrence reporting failure):
```json
{
  "detail": "An unexpected error occurred while submitting the issue recurrence."
}
```

Example response (case report generation failure):
```json
{
  "detail": "An unexpected error occurred while generating the case report."
}
```
*Note: Exception details, stack traces, database URLs, credentials, SQL statements, file system paths, and submitted user data are sanitized and never exposed in the response.*

---

## Integration Notes for Member 1 (Frontend)

1. **Evidence-Support Scores vs Calibrated Probabilities:**
   - The `score` field (0.0 to 100.0) on each `CandidateCause` represents an **engine evidence-support score** computed from baseline priors, positive rule matches, contradiction penalties, and missing observation penalties.
   - It is **not** a calibrated statistical probability. Do not display it as an absolute percentage chance that the cause is true. Instead, display it as a relative ranking score (e.g. "Evidence Score: 40/100" or a relative confidence bar).

2. **Deterministic Extraction:**
   - Symptom extraction in this increment relies on deterministic keyword mapping and rule matching. No live external LLM calls are made.

3. **Stateless vs Persistent Flows:**
   - Use `POST /api/v1/diagnoses` for quick ad-hoc analysis or automated smoke checks where persistent state is not required.
   - Use `POST /api/v1/cases` when initiating a troubleshooting case that will be tracked, queried, or advanced across multiple steps or sessions.
   - When viewing an existing case, use `GET /api/v1/cases/{case_id}` to retrieve the stored diagnosis and observations. Retrieval is instant, idempotent, and performs no recalculation.

4. **Recovery Actions and Verification Workflow:**
   - When corrective actions are taken, submit `POST /api/v1/cases/{case_id}/recovery-actions` to mark the issue as `RECOVERY_PENDING_VERIFICATION`. Do not assume the issue is resolved.
   - After testing (e.g. test shots or inspection), submit `POST /api/v1/cases/{case_id}/recovery-verifications` with `verification_passed: true` (transitions to `RESOLVED`) or `verification_passed: false` (reverts to `UNRESOLVED`).
   - Root cause confirmation and issue resolution are independent: an issue may be resolved without a confirmed root cause, and a confirmed root cause remains confirmed even if a recovery verification fails.

5. **Recurrence Reporting Workflow:**
   - When an issue that was previously `RESOLVED` recurs in production, submit `POST /api/v1/cases/{case_id}/recurrences` with the current revision and descriptive recurrence details.
   - Recurrence reporting transitions the condition from `RESOLVED` to `RECURRED`. It is valid **only** from `RESOLVED`; calling this endpoint on an `UNRESOLVED` or `RECOVERY_PENDING_VERIFICATION` case returns HTTP 422.
   - Recurrence does not automatically initiate recovery or alter prior root-cause confirmation.

6. **Durable Case Report Export:**
   - Use `GET /api/v1/cases/{case_id}/report` to retrieve the comprehensive, deterministic read-model for a case.
   - The report contains the complete case profile, latest diagnosis snapshot, complete audit history (`question_answers`, `check_results`, `cause_confirmations`, `lifecycle_events`) in strict ascending revision order, and a compact `outcome_summary`.
   - The endpoint performs zero diagnostic recalculation and commits zero mutations.
   - Note that binary document export (PDF, Word/DOCX) is not performed by the backend in this increment; the frontend should format or render the returned JSON report as needed for display or client-side print/export.
