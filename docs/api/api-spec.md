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

## Error Handling

### HTTP 422 Unprocessable Entity
Returned when request input fails validation rules. Validation errors are returned as a structured array in the `detail` field.

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
Returned when the internal diagnostic engine encounters an unhandled exception.

Example response:
```json
{
  "detail": "An unexpected error occurred during diagnosis evaluation."
}
```
*Note: Exception details, stack traces, file system paths, and submitted user data are sanitized and never exposed in the response.*

---

## Integration Notes for Member 1 (Frontend)

1. **Evidence-Support Scores vs Calibrated Probabilities:**
   - The `score` field (0.0 to 100.0) on each `CandidateCause` represents an **engine evidence-support score** computed from baseline priors, positive rule matches, contradiction penalties, and missing observation penalties.
   - It is **not** a calibrated statistical probability. Do not display it as an absolute percentage chance that the cause is true. Instead, display it as a relative ranking score (e.g. "Evidence Score: 40/100" or a relative confidence bar).

2. **Deterministic Extraction:**
   - Symptom extraction in this increment relies on deterministic keyword mapping and rule matching. No live external LLM calls are made.

3. **Stateless Flow:**
   - At this stage, each submission to `POST /api/v1/diagnoses` is an independent initial diagnosis.
   - Do not attempt to pass `case_id` back to the server in this initial endpoint. Subsequent milestones will introduce persistent cases and revision submission endpoints.
