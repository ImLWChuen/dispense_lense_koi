# DispenseLens Frontend-Backend Contract Matrix

**Document Purpose:** Defines the integration contract between Member 3 (Backend & Persistence) and Member 1 (Frontend UI) for the DispenseLens / DispenseIQ competition MVP.
**Authoritative Reference:** FastAPI OpenAPI specification (`/openapi.json`), accepted Member 3 backend implementations (commit `53cc609` / task `DLK-M3-024`), and image analysis endpoint (commit `6e52628f4e6e192a5044dc9de07b0f01b9cdc213` / task `DLK-M3-026`).

---

## 1. Executive Contract Summary

| Category | Count | Description |
|---|---|---|
| **Supported & Wired** | 7 | Frontend actively calls backend with matching routes and parameters (including image analysis). |
| **Available but Not Wired** | 5 | Backend endpoints fully operational; frontend has placeholders or direct UI flows yet to wire. |
| **Call / Type Mismatch (Member 1 Action)** | 2 | Frontend types or request field names differ slightly from accepted backend schema. |
| **Deferred / Optional UI Features** | 5 | Features intentionally excluded from core MVP (e.g., vector search, LLM narration, auth). |

---

## 2. Comprehensive Endpoint Contract Matrix

| # | HTTP Method & Path | Backend Schema / Status | Frontend Caller / Location | Contract Status | Notes & Action Required |
|---|---|---|---|---|---|
| 1 | `GET /api/v1/health` | `HealthResponse` (`200 OK`) | None directly in `casesApi` | **Available (Not Wired)** | Service health probe. Ready for UI status bar / health check polling. |
| 2 | `POST /api/v1/diagnoses` | `InitialDiagnosisRequest` &rarr; `DiagnosisResult` (`200 OK`, `422`) | None in `casesApi` | **Available (Not Wired)** | Stateless one-shot diagnostic evaluation. Frontend prefers durable case creation (`POST /cases`). |
| 3 | `POST /api/v1/cases` | `CreateCaseRequest` &rarr; `DurableCaseResponse` (`201 Created`, `422`, `500`) | `casesApi.createCase` (`frontend/lib/api/cases.ts:9`) | **Supported & Wired** | Used by `frontend/app/(dashboard)/diagnosis/new/page.tsx`. Submits canonical manual and calibrated image observations. Fully aligned. |
| 4 | `GET /api/v1/cases` | `list[DurableCaseResponse]` (`200 OK`, `500`) | `casesApi.listCases` (`frontend/lib/api/cases.ts:5`) | **Supported & Wired** | Used by `frontend/app/(dashboard)/cases/page.tsx:35`. Fully aligned. Returns all persisted cases. |
| 5 | `GET /api/v1/cases/{case_id}` | `DurableCaseResponse` (`200 OK`, `404`, `422`, `500`) | `casesApi.getCase` (`frontend/lib/api/cases.ts:13`) | **Supported & Wired** | Used by diagnosis analysis, verification, questions, and troubleshooting pages. Fully aligned. |
| 6 | `POST /api/v1/cases/{case_id}/answers` | `SubmitAnswerRequest` &rarr; `CaseAnswerResponse` (`200 OK`, `404`, `409`, `422`, `500`) | `casesApi.submitAnswer` (`frontend/lib/api/cases.ts:17`) | **Supported & Wired** | Used by `questions/page.tsx:46`. Advances case revision atomically. |
| 7 | `POST /api/v1/cases/{case_id}/check-results` | `SubmitCheckResultRequest` &rarr; `CaseCheckResultResponse` (`200 OK`, `404`, `409`, `422`, `500`) | `casesApi.submitCheckResult` (`frontend/lib/api/cases.ts:26`) | **Type Mismatch** | **Member 1 Action (Phase 3 Audit):**<br>1. Return type in frontend is typed as `Promise<DiagnosisResult>`, but backend returns `CaseCheckResultResponse` (which embeds `diagnosis`, `current_revision`, `check_result`).<br>2. Frontend sends `finding_text?: string`, but backend `SubmitCheckResultRequest` configures `extra="forbid"`. Supplying `finding_text` causes backend validation to fail with **HTTP 422 Unprocessable Entity** (`extra_forbidden`); extra fields are **not** ignored. Member 1 must remove `finding_text` (or pass it as `finding_details`) and supply `outcome` for structured evidence evaluation.<br>3. **Check Outcome Value Mismatch:** In `backend/app/knowledge/actions.json`, actions expect specific outcome keys mapping to evidence rules (e.g., ACT01 expects `blockage_found`, `no_blockage`, or `damage_found`). In `frontend/components/diagnosis/TroubleshootingChecklist.tsx`, lines 80-85 map outcomes to `"CONTRADICTS"` or `"SUPPORTS"`. Member 1 must align the frontend checklist outcome buttons with the action's configured evidence outcomes in Phase 3. |
| 8 | `POST /api/v1/cases/{case_id}/cause-confirmations` | `SubmitCauseConfirmationRequest` &rarr; `CaseCauseConfirmationResponse` (`200 OK`, `404`, `409`, `422`, `500`) | `casesApi.submitCauseConfirmation` (`frontend/lib/api/cases.ts:59`) | **Supported & Wired** | Used by `verification/page.tsx:46`. Confirms candidate root cause. |
| 9 | `POST /api/v1/cases/{case_id}/recovery-actions` | `SubmitRecoveryActionRequest` &rarr; `CaseRecoveryActionResponse` (`200 OK`, `404`, `409`, `422`, `500`) | `casesApi.submitRecoveryAction` (`frontend/lib/api/cases.ts:68`) | **Supported & Wired** | Used by `verification/page.tsx:57`. Transitions issue condition to `RECOVERY_PENDING_VERIFICATION`. |
| 10 | `POST /api/v1/cases/{case_id}/recovery-verifications` | `SubmitRecoveryVerificationRequest` &rarr; `CaseRecoveryVerificationResponse` (`200 OK`, `404`, `409`, `422`, `500`) | `casesApi.verifyCase` (`frontend/lib/api/cases.ts:45`) | **Type Mismatch** | **Member 1 Action:**<br>1. Frontend method name is `verifyCase(caseId, status, notes, expectedRevision)` (`frontend/lib/api/cases.ts:45`).<br>2. Frontend declares return type `Promise<DiagnosisResult>`, but backend returns `CaseRecoveryVerificationResponse` (which extends `DurableCaseResponse` with `current_revision`, `submitted_event: LifecycleEventRecord`, and `lifecycle_events: list[LifecycleEventRecord]`). Frontend callers should consume `response.diagnosis` or update the return type to `Promise<CaseRecoveryVerificationResponse>`.<br>3. Frontend passes `{ verification_passed: status === 'RESOLVED', verification_details: notes, expected_revision: expectedRevision }`, matching backend schema. Optional `verified_by` defaults to `"technician"` (max 64 chars). |
| 11 | `POST /api/v1/cases/{case_id}/recurrences` | `SubmitRecurrenceRequest` &rarr; `CaseRecurrenceResponse` (`200 OK`, `404`, `409`, `422`, `500`) | Not wired in `cases.ts` | **Available (Not Wired)** | **Member 1 Action:** Add `submitRecurrence(caseId, details, expectedRevision, reportedBy)` to `casesApi` to support re-opening resolved cases when defects recur. |
| 12 | `GET /api/v1/cases/{case_id}/report` | `CaseReportResponse` (`200 OK`, `404`, `422`, `500`) | `reports.ts` is 0 bytes | **Available (Not Wired)** | **Member 1 Action:** Wire `getCaseReport(caseId)` in `frontend/lib/api/reports.ts` and replace mock report data in `frontend/app/(dashboard)/reports/page.tsx`. |
| 13 | `GET /api/v1/cases/{case_id}/report.pdf` | `application/pdf` binary stream (`200 OK`, `404`, `422`, `500`) | Not wired in `reports.ts` | **Available (Not Wired)** | **Member 1 Action:** Wire `downloadReportPdf(caseId)` in `frontend/lib/api/reports.ts` using `window.open` or blob download triggering attachment download. |
| 14 | `POST /api/v1/images/analyze` | Multipart Form Data &rarr; `ImageAnalysisResponse` (`200 OK`, `400`, `413`, `422`, `500`) | `imagesApi.analyze` (`frontend/lib/api/images.ts:25`) | **Supported & Wired** | Authority: `DLK-M3-026` / commit `6e52628f4e6e192a5044dc9de07b0f01b9cdc213`. Wired via `ImageUpload.tsx`. Analyzes ROIs across `FEATURES_ONLY`, `PROCESS_LIMITS`, and `REFERENCE_IMAGE` modes. |

---

## 3. Detailed Contract Specifications

### 3.1 `GET /api/v1/cases` (Case List)
- **Method:** `GET`
- **Path:** `/api/v1/cases`
- **Query Parameters:** None in MVP. (Pagination, search, and sorting are intentionally unspecified in core MVP contract).
- **Responses:**
  - `200 OK`: `list[DurableCaseResponse]`
    - Each item contains `case_id`, `description`, `material`, `method`, `machine_context`, `defect_code`, `defect_name`, `issue_condition`, `created_at`, `observations`, `initial_diagnosis`, `diagnosis` (latest revision).
  - `500 Internal Server Error`: `{"detail": "An unexpected error occurred while retrieving cases."}` (Sanitized).
- **Semantics:** Read-only transaction. Exposes latest persisted diagnosis without re-running diagnostic engine. Revisions are never advanced by listing.

### 3.2 Concurrency & Optimistic Locking Contract
- Mutating endpoints (`/answers`, `/check-results`, `/cause-confirmations`, `/recovery-actions`, `/recovery-verifications`, `/recurrences`) require `expected_revision: int` in the request body.
- **Mismatch Behavior:** If `expected_revision != current_durable_revision`, backend aborts atomically with `409 Conflict`:
  ```json
  {
    "detail": "Case revision conflict: expected revision X, but current revision is Y."
  }
  ```
- **Frontend Recommendation:** Refresh case state via `GET /cases/{case_id}` on 409 and prompt user to re-evaluate with the latest diagnosis snapshot.

### 3.3 Text Length Constraints
All actor, confirmer, verifier, and reporter string fields enforce max length of 64 characters:
- `confirmed_by`: `str` (max 64)
- `performed_by`: `str` (max 64)
- `verified_by`: `str` (max 64)
- `reported_by`: `str` (max 64)

### 3.4 Image Analysis Contract (`POST /api/v1/images/analyze`)
- **Authoritative Reference:** `DLK-M3-026` (commit `6e52628f4e6e192a5044dc9de07b0f01b9cdc213`).
- **HTTP Method & Path:** `POST /api/v1/images/analyze`
- **Encoding:** `multipart/form-data`. Boundary must NOT be explicitly configured in `Content-Type` headers; the browser/client automatically generates boundaries with appropriate multipart headers.
- **Multipart Form Fields:**
  - `file`: Required `UploadFile`. Supported image MIME types: `image/jpeg`, `image/png`. Max file size: 10 MiB (10,485,760 bytes).
  - `profile`: Required `str` (JSON string serialized from `AnalysisProfile`):
    - `mode`: `"FEATURES_ONLY"` | `"PROCESS_LIMITS"` | `"REFERENCE_IMAGE"`
    - `rois`: `list[NormalizedROI]` where each ROI has `{ roi_id: string, x: number, y: number, width: number, height: number }` with normalized coordinates in `[0.0, 1.0]`. Minimum dimension: 0.01.
    - `process_limits`: Optional `{ min_coverage_ratio?: number, max_coverage_ratio?: number, max_overflow_ratio?: number, max_size_cv?: number, min_presence_ratio?: number }`. Required when `mode == "PROCESS_LIMITS"`.
    - `reference_limits`: Optional `{ min_reference_ratio?: number, max_reference_ratio?: number, tolerance_ratio?: number }`. Required when `mode == "REFERENCE_IMAGE"`.
    - `mm_per_pixel`: Optional `number` (> 0.0). Calibrated physical scale factor.
  - `reference_file`: Optional `UploadFile`. Required when `mode == "REFERENCE_IMAGE"`. Subject to identical 10 MiB and JPEG/PNG constraints.
- **Responses:**
  - `200 OK`: `ImageAnalysisResponse`
    - `status`: `"CALIBRATED"` | `"UNRELIABLE"` | `"PROCESSING_FAILED"`
    - `mode`: `ImageAnalysisMode`
    - `image_dimensions`: `{ width: number, height: number }`
    - `roi_measurements`: `list[RoiMeasurement]` (each containing `roi_index`, `label`, `bounding_box`, `area_pixels`, `equivalent_diameter_pixels`, `calibrated_diameter_mm`, `circularity`, `mean_intensity`, `aspect_ratio`, `presence_ratio`, `similarity_ratio`)
    - `aggregate_measurements`: `AggregateMeasurements` (`deposit_count`, `mean_diameter_pixels`, `mean_calibrated_diameter_mm`, `mean_circularity`, `diameter_std_dev_pixels`)
    - `observations`: `list[DiagnosticObservation]` (structured observations with `source: "IMAGE"`, `evidence_type: "AI_INFERENCE"`, `category: "IMAGE"`, and metadata)
    - `warnings`: `list[str]`
  - `400 Bad Request`: Missing `reference_file` when required, or malformed `profile_json`.
  - `413 Payload Too Large`: Uploaded file exceeds 10 MiB.
  - `422 Unprocessable Entity`: Invalid file type or invalid ROI boundary values.
  - `500 Internal Server Error`: Unhandled analysis pipeline failure.
- **Non-Persistence of Raw Images:**
  - Raw image bytes, base64 strings, or object URLs are strictly transient client-side artifacts. They are **never** persisted to the database or stored on the backend filesystem.
  - When a case is created (`POST /api/v1/cases`), only the extracted `DiagnosticObservation` records (with `source: "IMAGE"` and structured `metadata`) are transmitted and persisted.
- **Evidence Gating:**
  - Only `CALIBRATED` analysis results may contribute observations to case creation. If status is `UNRELIABLE` or `PROCESSING_FAILED`, observations must not be submitted as case evidence.
- **Request Cancellation & Cache Lifecycle:**
  - The client provides an `AbortSignal` for every analyze request.
  - If an upload is removed or its configuration/ROIs change, in-flight requests are aborted immediately, generated object URLs are revoked (`URL.revokeObjectURL`), and any cached observations are cleared to prevent stale state.

### 3.5 Canonical Form Values for Manual Case Observations
When creating a case (`POST /api/v1/cases`), manual observations submitted from the initial problem form must conform strictly to canonical knowledge base values:
- **Material:** Controlled text field (`material`), e.g. `"Loctite 3542"`, `"Epoxy 301"`. Max length 64 chars.
- **Defect Code:**
  - `D01_TOO_LITTLE` (Too Little Material)
  - `D02_TOO_MUCH` (Too Much Material)
  - `D03_INCONSISTENT_SIZE` (Inconsistent Size)
  - `D04_MISSING_DOTS` (Missing Dots)
  - `D05_SPREADING` (Spreading)
  - `D06_BUBBLES_ABNORMAL_SHAPE` (Bubbles / Abnormal Shape)
- **Deposit Size (D04):**
  - `undersized`
  - `oversized`
  - `inconsistent`
- **Frequency (D05):**
  - `consistent`
  - `intermittent`
- **Location (D06):**
  - `all_points`
  - `specific_nozzle`
  - `random_locations`
  - `varies_across_points`

### 3.6 Phase 3 Action & Check Outcomes Audit
- **Issue:** In `backend/app/knowledge/actions.json`, troubleshooting actions map observations through action-specific outcome keys (e.g. ACT01 maps `blockage_found`, `no_blockage`, `damage_found`).
- **Frontend Deviation:** `frontend/components/diagnosis/TroubleshootingChecklist.tsx` lines 80-85 currently maps user selection to generic strings `"CONTRADICTS"` or `"SUPPORTS"`.
- **Status:** Audited follow-up action for Member 1 in Phase 3. No edits were made to `TroubleshootingChecklist.tsx` in `DLK-M3-027` to preserve Phase 3 file boundaries.

---

## 4. Deferred Features (No MVP Backend Requirement)

The following capabilities are explicitly documented as post-competition or deferred items. Their absence does **not** constitute an MVP defect:

1. **Historical Case Similarity & Vector Search:** Embedding generation, vector database indexing (e.g. pgvector), and nearest-neighbor search are deferred.
2. **Bounded LLM Integration:** LLM-assisted narration, conversational troubleshooting, and automated report summarization are deferred.
3. **Authentication & Multi-Tenancy:** JWT/OAuth authentication, role-based access control, and organization tenancy are deferred; all endpoints operate under default engineer context.
4. **Background Workers & Job Queues:** Async report rendering or heavy Celery/Redis workers are unnecessary as in-memory PDF rendering executes in < 25ms.
5. **Machine Hardware Telemetry / Automation:** Direct integration with dispensing robots or PLC controllers via OPC-UA/MQTT is deferred.
