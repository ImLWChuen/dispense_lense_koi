# Dispense Lens Frontend-Backend Contract Matrix

**Document Purpose:** Defines the integration contract between Member 3 (Backend & Persistence) and Member 1 (Frontend UI) for the Dispense Lens / Dispense Lens competition MVP.
**Authoritative Reference:** FastAPI OpenAPI specification (`/openapi.json`), accepted Member 3 backend implementations (commit `53cc609` / task `DLK-M3-024`), and image analysis endpoint (commit `6e52628f4e6e192a5044dc9de07b0f01b9cdc213` / task `DLK-M3-026`).

---

## 1. Executive Contract Summary

| Category | Count | Description |
|---|---|---|
| **Supported & Wired** | 15 | Frontend actively calls backend with matching routes, schemas, and parameters (cases, checks, lifecycle, images, reports, analytics). |
| **Available but Not Wired** | 2 | Backend endpoints fully operational; service probe and stateless diagnosis. |
| **Call / Type Mismatch (Member 1 Action)** | 0 | Fully aligned; all frontend client methods, parameters, and return types match accepted backend schemas. |
| **Deferred / Optional UI Features** | 5 | Features intentionally excluded from core MVP (e.g., vector search, LLM narration, auth). |

---

## 2. Comprehensive Endpoint Contract Matrix

| # | HTTP Method & Path | Backend Schema / Status | Frontend Caller / Location | Contract Status | Notes & Action Required |
|---|---|---|---|---|---|
| 1 | `GET /api/v1/health` | `HealthResponse` (`200 OK`) | None directly in `casesApi` | **Available (Not Wired)** | Service health probe. Ready for UI status bar / health check polling. |
| 2 | `POST /api/v1/diagnoses` | `InitialDiagnosisRequest` &rarr; `DiagnosisResult` (`200 OK`, `422`) | None in `casesApi` | **Available (Not Wired)** | Stateless one-shot diagnostic evaluation. Frontend prefers durable case creation (`POST /cases`). |
| 3 | `POST /api/v1/cases` | `CreateCaseRequest` &rarr; `DurableCaseResponse` (`201 Created`, `422`, `500`) | `casesApi.createCase` (`frontend/lib/api/cases.ts`) | **Supported & Wired** | Used by `frontend/app/(dashboard)/diagnosis/new/page.tsx`. Submits canonical manual and calibrated image observations. Fully aligned. |
| 4 | `GET /api/v1/cases` | `list[DurableCaseResponse]` (`200 OK`, `500`) | `casesApi.listCases` (`frontend/lib/api/cases.ts`) | **Supported & Wired** | Used by `frontend/app/(dashboard)/cases/page.tsx`. Fully aligned. Returns all persisted cases. Equipment falls back to `Not recorded`. |
| 5 | `GET /api/v1/cases/{case_id}` | `DurableCaseResponse` (`200 OK`, `404`, `422`, `500`) | `casesApi.getCase` (`frontend/lib/api/cases.ts`) | **Supported & Wired** | Authority: `DLK-M3-029`. Hydrates `previous_confirmations` and `lifecycle_events` ordered ascending by revision number for restart-safe resume without engine re-computation. |
| 6 | `POST /api/v1/cases/{case_id}/answers` | `SubmitAnswerRequest` &rarr; `CaseAnswerResponse` (`200 OK`, `404`, `409`, `422`, `500`) | `casesApi.submitAnswer` (`frontend/lib/api/cases.ts`) | **Supported & Wired** | Authority: `DLK-M3-029`. Returns typed `CaseAnswerResponse`. Mutually exclusive question view handles initial errors, stale mutation errors, and neutral completion. |
| 7 | `POST /api/v1/cases/{case_id}/check-results` | `SubmitCheckResultRequest` &rarr; `CaseCheckResultResponse` (`200 OK`, `404`, `409`, `422`, `500`) | `casesApi.submitCheckResult` (`frontend/lib/api/cases.ts`) | **Supported & Wired** | Authority: `DLK-M3-029`. Fully aligned: returns `Promise<CaseCheckResultResponse>`, submits canonical `outcome` keys from `actions.json` (e.g. `blockage_found`), explicit findings (`SUPPORTS`, `CONTRADICTS`, `INCONCLUSIVE`, `UNKNOWN`), un-optimistic UI state awaiting API response. |
| 8 | `POST /api/v1/cases/{case_id}/cause-confirmations` | `SubmitCauseConfirmationRequest` &rarr; `CaseCauseConfirmationResponse` (`200 OK`, `404`, `409`, `422`, `500`) | `casesApi.submitCauseConfirmation` (`frontend/lib/api/cases.ts`) | **Supported & Wired** | Authority: `DLK-M3-029`. Returns typed `CaseCauseConfirmationResponse`. Independent from resolution; confirms candidate cause with technician notes. |
| 9 | `POST /api/v1/cases/{case_id}/recovery-actions` | `SubmitRecoveryActionRequest` &rarr; `CaseRecoveryActionResponse` (`200 OK`, `404`, `409`, `422`, `500`) | `casesApi.submitRecoveryAction` (`frontend/lib/api/cases.ts`) | **Supported & Wired** | Authority: `DLK-M3-029`. Returns typed `CaseRecoveryActionResponse`. Transitions issue condition to `RECOVERY_PENDING_VERIFICATION` with real technician text. Does not require prior cause confirmation. |
| 10 | `POST /api/v1/cases/{case_id}/recovery-verifications` | `SubmitRecoveryVerificationRequest` &rarr; `CaseRecoveryVerificationResponse` (`200 OK`, `404`, `409`, `422`, `500`) | `casesApi.verifyCase` (`frontend/lib/api/cases.ts`) | **Supported & Wired** | Authority: `DLK-M3-029`. Fully aligned: returns `Promise<CaseRecoveryVerificationResponse>`. Supports passed (transitions to `RESOLVED`) and failed (returns to `UNRESOLVED`) verifications with entered details. |
| 11 | `POST /api/v1/cases/{case_id}/recurrences` | `SubmitRecurrenceRequest` &rarr; `CaseRecurrenceResponse` (`200 OK`, `404`, `409`, `422`, `500`) | `casesApi.submitRecurrence` (`frontend/lib/api/cases.ts`) | **Supported & Wired** | Authority: `DLK-M3-029`. Fully wired in client and UI (`EngineerVerification.tsx`). Transitions resolved case to `RECURRED` with technician details. |
| 12 | `GET /api/v1/cases/{case_id}/report` | `CaseReportResponse` (`200 OK`, `404`, `422`, `500`) | `reportsApi.getCaseReport` (`frontend/lib/api/reports.ts:18`) | **Supported & Wired** | Used by `frontend/app/(dashboard)/reports/[id]/page.tsx` and `ReportPreview.tsx`. Strictly renders persisted case facts without mock reports. |
| 13 | `GET /api/v1/cases/{case_id}/report.pdf` | `application/pdf` binary stream (`200 OK`, `404`, `422`, `500`) | `reportsApi.downloadReportPdf` (`frontend/lib/api/reports.ts:24`) | **Supported & Wired** | Wired in `ReportPreview.tsx` and `ReportActions.tsx`. Downloads dynamic PDF binary directly from backend endpoint. |
| 14 | `POST /api/v1/images/analyze` | Multipart Form Data &rarr; `ImageAnalysisResponse` (`200 OK`, `400`, `413`, `422`, `500`) | `imagesApi.analyze` (`frontend/lib/api/images.ts:25`) | **Supported & Wired** | Authority: `DLK-M3-026` / commit `6e52628f4e6e192a5044dc9de07b0f01b9cdc213`. Wired via `ImageUpload.tsx`. Analyzes ROIs across `FEATURES_ONLY`, `PROCESS_LIMITS`, and `REFERENCE_IMAGE` modes. |
| 15 | `GET /api/v1/analytics/dashboard` | `DashboardAnalyticsResponse` (`200 OK`, `500`) | `analyticsApi.getDashboard` (`frontend/lib/api/analytics.ts:21`) | **Supported & Wired** | Authority: `DLK-M3-028`. Wired in `app/(dashboard)/dashboard/page.tsx`. Truthful KPI metrics, recent cases with evidence support, and confirmed-cause insights. |
| 16 | `GET /api/v1/analytics/performance` | `AnalyticsPerformanceResponse` (`200 OK`, `500`) | `analyticsApi.getPerformance` (`frontend/lib/api/analytics.ts:26`) | **Supported & Wired** | Authority: `DLK-M3-028`. Wired in `app/(dashboard)/analytics/page.tsx`. Parameterized by period (`7d`, `30d`, `90d`, `1y`). Dynamic distributions and truthful trends. |
| 17 | `GET /api/v1/analytics/events` | `text/event-stream` SSE (`200 OK`) | `analyticsApi.subscribeToEvents` (`frontend/lib/api/analytics.ts:31`) | **Supported & Wired** | Server-Sent Events stream for real-time dashboard refresh. |

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
    - `rois`: `list[NormalizedROI]` where each ROI has `{ roi_id: string, x: number, y: number, width: number, height: number }` with normalized coordinates in `[0.0, 1.0]`, non-blank `roi_id`, and `x + width <= 1.0`, `y + height <= 1.0`.
    - `process_limits`: Optional `ProcessLimits` (`{ min_coverage_ratio?: number, max_coverage_ratio?: number, max_overflow_ratio?: number, max_size_cv?: number, min_presence_ratio?: number }`). Required when `mode == "PROCESS_LIMITS"`.
    - `reference_limits`: Optional `ReferenceLimits` (`{ min_reference_ratio?: number, max_reference_ratio?: number, tolerance_ratio?: number }`). Required when `mode == "REFERENCE_IMAGE"`.
    - `mm_per_pixel`: Optional `number` (> 0.0). Calibrated physical scale factor.
  - `reference_file`: Optional `UploadFile`. Required when `mode == "REFERENCE_IMAGE"`. Subject to identical 10 MiB and JPEG/PNG constraints.
- **Responses:**
  - `200 OK`: `ImageAnalysisResponse`
    - `status`: `"CALIBRATED"` | `"UNCALIBRATED"` | `"UNRELIABLE"`
    - `mode`: `ImageAnalysisMode` (`"FEATURES_ONLY"` | `"PROCESS_LIMITS"` | `"REFERENCE_IMAGE"`)
    - `image_dimensions`: `{ width: number, height: number, channels: number }`
    - `roi_measurements`: `list[RoiMeasurement]` (each containing `roi_id`, `deposit_area_px`, `target_area_px`, `coverage_ratio`, `overflow_ratio`, `equivalent_diameter_px`, `calibrated_diameter_mm`, `circularity`, `solidity`, `aspect_ratio`, `hole_void_ratio`, `segmentation_quality`, `is_missing`)
    - `aggregate_measurements`: `AggregateMeasurements` (`mean_coverage`, `size_cv`, `missing_roi_ids`, `warnings`)
    - `observations`: `list[Observation]` (structured observations with `id`, `observation_type`, `value`, `confidence`, `source: "IMAGE"`, `statement_type: "AI_INFERENCE"`, `original_text`, and `metadata`; note that `observation_id` is reserved for `CaseObservationResponse` in durable case responses)
    - `warnings`: `list[str]`
  - `400 Bad Request`: Missing `reference_file` when required, or malformed `profile` JSON.
  - `413 Payload Too Large`: Uploaded file exceeds 10 MiB limit.
  - `422 Unprocessable Entity`: Invalid file type, invalid ROI boundary values, or contradictory numeric limits.
  - `500 Internal Server Error`: Sanitized unhandled analysis pipeline failure.
- **Non-Persistence of Raw Images:**
  - Raw image bytes, base64 strings, or object URLs are strictly transient client-side artifacts. They are **never** persisted to the database or stored on the backend filesystem.
  - When a case is created (`POST /api/v1/cases`), only the extracted canonical `Observation` records (with `source: "IMAGE"` and structured `metadata`) are transmitted and persisted.
- **Evidence Gating:**
  - Only `CALIBRATED` analysis results may contribute observations to case creation. If status is `UNCALIBRATED` (e.g. `FEATURES_ONLY` mode) or `UNRELIABLE` (ambiguous/uniform frames), results produce 0 diagnostic observations and must never be submitted as case evidence.
- **Request Cancellation & Stale-Result Lifecycle:**
  - The client provides an `AbortSignal` for every analyze request.
  - If an upload is removed or its configuration/ROIs change, in-flight requests are synchronously invalidated and aborted immediately, generated object URLs are revoked (`URL.revokeObjectURL`), and late responses are rejected so they cannot commit stale calibrated evidence or recreate removed uploads.

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

### 3.6 Physical Checks & Canonical Outcome Alignment (DLK-M3-029)
- **Resolved in DLK-M3-029:** The frontend adapter (`casesApi.submitCheckResult`) and checklist component (`TroubleshootingChecklist.tsx`) submit canonical outcome keys defined in `backend/app/knowledge/actions.json` (e.g. `blockage_found`, `no_blockage`, `damage_found` for ACT01) mapped to human-readable technician labels.
- **Canonical Payloads:**
  - For `COMPLETED` checks with `SUPPORTS` or `CONTRADICTS` findings, an explicit canonical `outcome` string is required and submitted.
  - For `INCONCLUSIVE` completed checks, `outcome` is omitted (`null`).
  - For non-completed checks (`BLOCKED`, `FAILED`, `SKIPPED`, `UNKNOWN`, `NOT_APPLICABLE`), `finding` is forced to `"UNKNOWN"` and `outcome` is omitted (`null`), preserving the technician's notes without claiming evidence support or diagnostic score shifts.
- **Safe UI State:** Check results are un-optimistic; the UI awaits API resolution and reconciles state from the durable response rather than marking checks saved prematurely.

### 3.7 Analytics, Reports & Truthful Evidence-Support Contract
- **Authoritative Reference:** `DLK-M3-028`.
- **No Diagnostic or Calibrated AI Accuracy:**
  - Neither the backend nor the diagnostic engine calculates calibrated probability, statistical precision, or model accuracy.
  - The previous synthetic `ai_accuracy_rate` and `diagnostic_accuracy_rate` metrics are replaced by `cause_confirmation_rate: Optional[float]`.
- **`cause_confirmation_rate` Definition & Semantics:**
  - Plainly named workflow coverage metric: defined strictly as `(unique cases with at least one persisted cause confirmation / total cases in the applicable population) * 100`.
  - When the population denominator is zero, the endpoint returns `null`.
  - The frontend renders `"Not available"` (or neutral state) when `null`. It must **never** be labeled as accuracy, precision, or model correctness.
- **`evidence_support` Definition & Semantics:**
  - Replaces previous synthetic recent-case `confidence`.
  - Derived strictly from the latest persisted analysis revision's top-ranked candidate cause score (`CandidateCause.score`).
  - Score is a deterministic 0–100 evidence-support metric evaluated by rule weights. It does **not** sum to 100 across candidate causes and is **not** a probability.
  - Must be labeled `"Evidence Support"` or `"Evidence Support /100"`, never confidence, probability, or accuracy.
  - When no ranked causes exist, `evidence_support` is `null`, and frontend surfaces display `"N/A"`.
  - A score of `0` is a valid score and must be displayed (`0/100`), not treated as missing. Only the visual bar is clamped to `[0, 100]`.
- **Nullable Period-over-Period Trends & Population Comparability (R1):**
  - All trend fields (`active_diagnoses_trend`, `open_defects_trend`, `resolved_cases_trend`, `avg_time_trend`, `total_cases_trend`, `avg_resolution_trend`, `first_time_resolution_trend`, `cause_confirmation_trend`) are nullable (`Optional[str] = None`).
  - Dashboard trends return `null` because all-time current operational states (`active_diagnoses`, `open_defects`, `resolved_cases`) cannot be reconstructed truthfully into past point-in-time cohorts without historical snapshots. Comparing all-time counts with a 30-day creation cohort is prohibited.
  - In performance analytics, trends are computed strictly between comparable creation cohorts (`[cutoff, now]` vs `[prev_cutoff, cutoff]`). If no comparable prior population exists (>0 records), trends return `null`.
  - The frontend renders no trend badge or a neutral state; it must **never** substitute synthetic trends such as `+100%`, `-15%`, `+5%`, `+2%`, or `0%`.
- **First-Time Resolution Rate Semantics (R2):**
  - Replaces arbitrary `revision_count <= 2` heuristics.
  - Derived strictly from explicit persisted lifecycle events (`CaseLifecycleEventModel`): a resolved case is first-time resolved if it has at least one passed verification event (`event_type in ("RECOVERY_VERIFICATION", "VERIFICATION")` with `verification_passed is True`), zero failed verifications (`verification_passed is False`), and zero recurrence events (`resulting_issue_condition == "RECURRED"` or `event_type == "RECURRENCE"`).
  - Revisions produced by questions, checks, or cause confirmations do not penalize first-time resolution.
  - If any resolved case in the population lacks verification lifecycle evidence, the metric returns `null` (unsupported evidence).
- **Resolution Durations & Zero-Minute Exclusion (R3):**
  - Average diagnosis time (`avg_diagnosis_time_minutes`) and average resolution time (`avg_resolution_time_minutes`) are nullable (`Optional[float] = None`).
  - Measured only over resolved cases that have a persisted `CaseLifecycleEventModel` of condition `RESOLVED`.
  - Resolved cases without a persisted resolution event are excluded from duration metrics and duration buckets (`res_times_minutes`). They are **never** assigned `0.0` minutes or placed in the `< 5 min` bucket.
  - When no duration is measurable, average resolution/diagnosis time returns `null`, and frontend displays `"Not available"`.
- **Mutually Exclusive UI Loading, Error, Empty, and Data States (R4):**
  - In Dashboard, Analytics, and Reports surfaces, initial request failure renders a dedicated error state with a retry action. An initial failure must **never** render fallback `0`, `0 min`, empty charts, or `"No reports found"`.
  - When a refresh fails after data has already loaded, the previously loaded data is retained and clearly marked with a top stale warning banner ("Refresh failed: {error}. Showing last synced data from {time}.").
  - Empty states ("No reports found", empty distributions) are rendered only when requests succeed and the returned dataset is genuine zero/empty.
- **Canonical Equipment Key (R5):**
  - Case equipment context reads `equipment` as the primary canonical key, alongside compatibility fallbacks `machine_id` and `equipment_id`. When none are present, returns `"Not recorded"`.
- **Distinct Case Count in Cause Distribution (R6):**
  - Cause distributions in both dashboard and performance analytics count unique cases via `func.distinct(CaseCauseConfirmationModel.case_id)`, avoiding duplicate counts when a case undergoes multiple confirmation revisions.
- **Insight & Defect Trend Alignment (R7):**
  - Dashboard AI insight defect share is labeled `"{value}% of defect-recorded cases"` (matching the queried population of cases with recorded defects).
- **Empty Chart Arrays When No Observed Data (R8):**
  - Defect trend returns `defect_trend = []` when the six-month window contains no defect-classified cases. Once at least one case exists in that window, the full six-month series (including meaningful zero months) is returned.
  - Resolution duration distribution returns `resolution_time_distribution = []` when no case duration is measurable (`res_times_minutes` is empty). Once at least one duration is measured, the complete bucket series is returned.
- **Deterministic Defect Order & Independent Insight Aggregates (R9):**
  - Defect distribution is sorted deterministically by case count descending and defect name ascending (`order_by(func.count(CaseModel.case_id).desc(), CaseModel.defect_name.asc())`).
  - Dashboard AI insight presents separate scoped facts: `"Most recorded defect category: {top_defect.name}. Most commonly confirmed cause across all confirmed cases: {top_cause}."` (or `"Root cause investigations are currently in progress."` if no causes are confirmed).
  - Unwarranted causal claims (e.g. "primary contributing factor") and unsupported recency claims ("recent verified investigations") are strictly excluded.
- **Nullable Defect Breakdown Code (R10):**
  - `DefectTypeBreakdownItem.code` is nullable (`Optional[str] = None` in backend schema, `string | null` in frontend type).
  - Invented fallback codes such as `D00` are prohibited. The frontend uses `key={dt.code || dt.name}` to safely render items without recorded defect codes.
- **Truthful Reports Reload & Refresh State (R11):**
  - In `reports/page.tsx`, `reloadReports` preserves previously loaded reports upon refresh failure, rendering a top stale warning banner while keeping data visible.
  - Initial load failure exclusively displays a dedicated full-page error state with retry action without rendering the table or empty states.
  - A reachable `Refresh` button is provided in the reports header. Verified via dependency-free regression suite `frontend/scripts/test-reports-state.mjs`.
- **Report Data Integrity:**
  - `GET /api/v1/cases/{case_id}/report` and `ReportPreview` render only real persisted case data and lifecycle events.
  - Mock fallback reports (`mockFallbackReports`), synthetic defect descriptions ("A particle or debris..."), invented measurements, and canned recommendations are forbidden. Missing sections explicitly state "Not recorded" or display neutral empty states.

### 3.8 Restart-Safe Technician Troubleshooting and Lifecycle Workflow (DLK-M3-029)
- **Authoritative Reference:** `DLK-M3-029`.
- **Additive GET-Case History Fields:**
  - `GET /api/v1/cases/{case_id}` includes `previous_confirmations: list[CauseConfirmationRecord]` and `lifecycle_events: list[LifecycleEventRecord]` populated from repository reads at the latest revision boundary.
  - Sorted deterministically in ascending revision/creation order.
  - Operation is strictly read-only: no diagnostic recalculation, no state mutation, and returns `[]` when no history exists.
- **Typed Mutation Responses:**
  - `POST /cases/{id}/answers` &rarr; `CaseAnswerResponse`
  - `POST /cases/{id}/check-results` &rarr; `CaseCheckResultResponse`
  - `POST /cases/{id}/cause-confirmations` &rarr; `CaseCauseConfirmationResponse`
  - `POST /cases/{id}/recovery-actions` &rarr; `CaseRecoveryActionResponse`
  - `POST /cases/{id}/recovery-verifications` &rarr; `CaseRecoveryVerificationResponse`
  - `POST /cases/{id}/recurrences` &rarr; `CaseRecurrenceResponse`
  - All responses extend `DurableCaseResponse` and contain `current_revision`, the submitted record, and updated history.
- **Truthful Workflow Views & Mutex States:**
  - Questions and Troubleshooting views enforce mutual exclusion: initial loading, initial error, active question/check, and completion.
  - Initial load failure renders a dedicated error card with retry; it **never** renders completion or empty lists.
  - When no additional questions or checks are available, neutral completion text is displayed. The UI must **never** claim "The engine has gathered sufficient evidence" or that a root cause is proven.
- **Lifecycle Transitions & Legal Actions:**
  - Transitions adhere strictly to:
    ```text
    UNRESOLVED or RECURRED --recovery action--> RECOVERY_PENDING_VERIFICATION
    RECOVERY_PENDING_VERIFICATION --verification passed--> RESOLVED
    RECOVERY_PENDING_VERIFICATION --verification failed--> UNRESOLVED
    RESOLVED --recurrence--> RECURRED
    ```
  - `UNRESOLVED` or `RECURRED`: Cause confirmation and/or recovery action are permitted. Cause confirmation is an independent record and does not transition issue condition.
  - `RECOVERY_PENDING_VERIFICATION`: Pass or fail recovery verification is permitted.
  - `RESOLVED`: Recurrence reporting is permitted.
- **Independent Operations & No Fake Rejection:**
  - The chained one-click flow is eliminated. Each action is performed and persisted independently.
  - Cause confirmation is optional; cases may be recovered and resolved directly without a confirmed cause.
  - The backend provides no cause-rejection endpoint. Controls implying persisted cause rejection are removed, replaced by an informative note that technicians can continue gathering evidence or perform recovery directly.
- **Stale Concurrency & Error Recovery:**
  - On `409 Conflict` or mutation error, the UI preserves the last persisted state with a top warning banner and automatically re-synchronizes with the latest server revision. Mutations are **never** automatically replayed.

---

## 4. Deferred Features (No MVP Backend Requirement)

The following capabilities are explicitly documented as post-competition or deferred items. Their absence does **not** constitute an MVP defect:

1. **Historical Case Similarity & Vector Search:** Embedding generation, vector database indexing (e.g. pgvector), and nearest-neighbor search are deferred.
2. **Bounded LLM Integration:** LLM-assisted narration, conversational troubleshooting, and automated report summarization are deferred.
3. **Authentication & Multi-Tenancy:** JWT/OAuth authentication, role-based access control, and organization tenancy are deferred; all endpoints operate under default engineer context.
4. **Background Workers & Job Queues:** Async report rendering or heavy Celery/Redis workers are unnecessary as in-memory PDF rendering executes in < 25ms.
5. **Machine Hardware Telemetry / Automation:** Direct integration with dispensing robots or PLC controllers via OPC-UA/MQTT is deferred.
