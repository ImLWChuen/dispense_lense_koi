# DispenseIQ Software Engineering Documentation

**AI Dispensing Troubleshooting & Defect Intelligence Platform**  
*Comprehensive System Reverse-Engineering, Architecture, Verification, and Engineering Manual*

---

## 1. Executive Summary

**DispenseIQ** (developed under the internal project name `DispenseLens` / `dispense_lense_koi`) is an industrial fluid dispensing defect intelligence and troubleshooting decision-support platform. The platform is designed for precision electronics and cleanroom manufacturing environments (e.g., surface-mount technology [SMT], optical adhesive bonding, semiconductor packaging, and LED encapsulation) where liquid adhesives, epoxies, and underfills are dispensed via automated jetting valves, auger screws, pneumatic needles, or piston pumps.

### Primary Operational Purpose
In precision electronics manufacturing, fluid dispensing failures (e.g., undersized dots, line clogs, deposit tailing, or fluid spreading) lead directly to component scrap, optical occlusion, electrical bridging, and unscheduled line downtime. Floor technicians and quality engineers often face high-stress troubleshooting scenarios where multiple physical variables interact: material viscosity, pneumatic supply pressure, nozzle tip wear, valve open time, ambient temperature, and syringe pot life. Junior operators frequently resort to unsystematic trial-and-error adjustments (e.g., cranking up pressure when a nozzle is partially obstructed), exacerbating process instability. 

DispenseIQ solves this by introducing a **deterministic, evidence-driven, explainable diagnostic engine** paired with **bounded computer vision** and an **audit-ready case management lifecycle**. Rather than relying on a probabilistic "black-box" model or hallucination-prone generative AI, the platform evaluates physical observations against a codified engineering knowledge base, computes cumulative **Evidence Support Scores (`Evidence Support /100`)**, preserves an immutable sequence of diagnostic revisions, and tracks independent corrective recovery verifications.

### Architectural Reality & Maturity Overview
The codebase represents a mature, hardened competition prototype transitioning toward an industrial minimum viable product (MVP). As of the accepted milestones `DLK-M3-030` and `DLK-M3-031`:
- **Backend**: Implemented in **Python 3.11+ / FastAPI** backed by **PostgreSQL 16** via **SQLAlchemy 2.0** and **psycopg 3**. Authoritative schema evolution is managed via **Alembic** (10 migrations). The backend features 491 automated tests (unit and integration) validating persistence safety, deterministic ranking, optimistic concurrency control (`StaleRevisionError`), ReportLab PDF rendering, and image preprocessing.
- **Frontend**: Implemented in **Next.js 16.3.4 (App Router)** and **React 19.2.8** using **TailwindCSS v4**, **TypeScript 5**, and **Recharts**. The frontend incorporates dedicated state controllers (`case-detail-state.ts`, `diagnostic-workflow-state.ts`, `image-upload-state.ts`, `reports-state.ts`) with standalone regression suites executed directly via Node.js.
- **Computer Vision**: Utilizes **OpenCV (`opencv-python-headless 5.0+`)** to segment user-defined Regions of Interest (ROIs), extract resolution-independent features (coverage ratio, overflow ratio, circularity, solidity), and convert calibrated deviations into canonical diagnostic observations.
- **AI Integration**: The LLM (OpenAI `gpt-4o-mini`) is strictly **bounded and non-authoritative**. It is restricted to natural-language symptom extraction and plain-text summarization. It is strictly prohibited from computing scores, altering rankings, or asserting issue resolution. The system degrades gracefully to deterministic text when the LLM is offline.
- **Key Divergences from Intended Design**: As confirmed in `.agents/handoff/QUEUE.md`, vector/semantic embeddings (`pgvector`) were explicitly deferred in favor of deterministic multi-attribute relational matching; authentication/authorization is implemented for user management and admin screens but standard operational diagnostic routes remain unauthenticated; and the Knowledge Base UI relies on hardcoded constants rather than fetching the live backend knowledge endpoints.

---

## 2. System Purpose

### The Engineering Problem
Industrial dispensing of fluids (such as Norland NOA-68 optical adhesive, Loctite 382 cyanoacrylate, EPO-TEK 353ND thermal epoxy, and Dow Corning OE-6630 silicone) requires volumetric repeatability often down to nanoliter or microliter tolerances. When dispensing deviates from nominal tolerances, operators face three compounding challenges:
1. **Symptom Equifinality**: Multiple distinct root causes manifest as identical symptoms. For example, an undersized adhesive dot can be caused by partial nozzle tip clogging (`nozzle_restriction`), a drop in main fluid line pressure (`pressure_instability`), material thickening due to expired pot life (`material_condition`), or an incorrect valve pulse time parameter (`parameter_issue`).
2. **Destructive Trial-and-Error**: Technicians frequently alter machine recipe parameters to compensate for physical degradation (e.g., increasing pulse time to force material through a clogged nozzle). When the clog eventually clears or the nozzle is swapped, the altered parameters cause massive over-dispensing (`D02_TOO_MUCH`) and substrate contamination.
3. **Loss of Provenance & Tribal Knowledge**: Root-cause discoveries and corrective actions are rarely documented in real time. Historical resolutions remain locked in senior engineers' heads rather than accessible on the factory floor.

### Intended Product Concept vs. Current Implementation
- **Intended Concept**: *"From dispensing symptom to probable cause and next action — faster."* A unified edge/cloud platform that ingests live camera feeds, continuously monitors line sensors, runs vector similarity search across plant-wide defect databases, and auto-generates compliance reports.
- **Current Implementation**: A structured, interactive desktop web application where technicians:
  1. Record symptoms, fluid material, and equipment line context manually or attach inspection images via client-side ROI calibration (`/diagnosis/new`).
  2. Receive a deterministically ranked candidate cause list with explicit `Evidence Support /100` scores and an itemized breakdown of supporting and contradicting evidence.
  3. Answer discriminating diagnostic questions (`/diagnosis/{id}/questions`) or execute recommended physical checks (`/diagnosis/{id}/troubleshooting`).
  4. Advance through immutable analysis revisions ($R_1 \to R_2 \to \dots \to R_n$) governed by optimistic locking.
  5. Formally confirm the root cause and document corrective action and verification test shots (`/diagnosis/{id}/verification`).
  6. Generate and download audit-ready standard PDF case reports or AIAG/VDA-compliant 8D Problem Solving quality dossiers (`/reports/{id}`).

---

## 3. Problem Domain

### Industrial Manufacturing Context
Precision fluid dispensing operates across four primary machine dispenser architectures:
1. **Jetting Valves (e.g., Line A / Asymtek)**: High-speed, non-contact pneumatic or piezo-actuated valves that drop discrete fluid dots on the fly. Susceptible to satellite droplets, fluid tailing, and nozzle seat wear.
2. **Auger Screw Dispenser (e.g., Line B / Camalot)**: Rotary displacement mechanisms used for highly filled or abrasive materials. Susceptible to shear-thinning variation, motor stall, and screw clearance wear.
3. **Pneumatic Time-Pressure Needles (e.g., Line C / Nordson)**: Syringe-mounted dispensing needles pulsed with regulated compressed air. Highly sensitive to air pressure fluctuations, fluid level drop inside the barrel, and temperature-induced viscosity drift.
4. **Positive Displacement Piston Pumps (e.g., Line D / PVA)**: Mechanical displacement pumps delivering fixed volumetric shots. Highly accurate but susceptible to air cavitation and seal leakage.

### Defect Taxonomy
The platform codifies the dispensing domain into six standard manufacturing defect categories (defined in `backend/app/knowledge/defects.json`):

| Defect Code | Defect Name | Description | Key Physical Indicators |
| :--- | :--- | :--- | :--- |
| **D01_TOO_LITTLE** | Too Little Material | Dispensed volume is consistently less than target. | Undersized dot diameter, thin bead, insufficient coverage. |
| **D02_TOO_MUCH** | Too Much Material | Dispensed volume consistently exceeds specification. | Oversized dot diameter, tall bulging deposit, adhesive tailing. |
| **D03_INCONSISTENT_SIZE** | Inconsistent Size | Shot-to-shot volume variation across consecutive cycles. | Intermittent dot diameter, high standard deviation, drift over shift. |
| **D04_MISSING_DOTS** | Missing Material | One or more target dispense points receive zero material. | Complete void, dry shot, nozzle completely blocked or starved. |
| **D05_SPREADING** | Excessive Spreading | Material wets out and flows beyond designated boundaries. | Deposit bleeding, boundary overflow, flat aspect ratio. |
| **D06_BUBBLES_ABNORMAL_SHAPE**| Bubbles / Abnormal Shape | Trapped air pockets, voids, or non-circular deposit geometries. | Internal voids, asymmetrical edges, donut shapes, cavitation tails. |

### Materials and Consumables Handled
The domain encompasses light-curable acrylics, cyanoacrylates, two-part optical epoxies, and thermal silicone gels. The cleanroom telemetry subsystem (`backend/app/services/telemetry/telemetry_service.py`) specifically models four real-world industrial adhesive profiles:
- **Norland NOA-68**: UV-cure optical acrylic (8-hour pot life, 45 min thaw from $-40^\circ\text{C}$).
- **Loctite 382 TakPak Prism**: Cyanoacrylate surface-cure adhesive (12-hour pot life, 30 min thaw).
- **EPO-TEK 353ND**: High-temperature semiconductor epoxy (4-hour pot life, 60 min thaw).
- **Dow Corning OE-6630**: Dual-part LED optical encapsulation silicone (6-hour pot life, 40 min thaw).

---

## 4. Users and Roles

The system models user identities in `backend/app/models/user.py` and implements role-based access control (RBAC) in `backend/app/api/admin.py` and `frontend/components/providers/AuthContext.tsx`.

### Role Matrix

| Role | Responsibilities | Permissions & Route Access | Implemented Status |
| :--- | :--- | :--- | :--- |
| **Technician (`technician`)** | First-line floor response, defect logging, executing troubleshooting actions, recording test shots, thaw/mount syringes. | Full access to `/dashboard`, `/diagnosis/*`, `/cases/*`, `/telemetry`, `/reports`. Cannot access `/admin/*`. | ✅ Fully implemented in UI and Admin API. |
| **Engineer (`engineer`)** | Process optimization, root cause confirmation, recovery action approval, SPC capability analysis. | Same as Technician plus authority to sign off on 8D quality steps and review multi-line SPC charts. | 🟡 Distinct role in DB/Admin, but permission gates currently treat Engineer identically to Technician. |
| **Administrator (`admin`)** | System oversight, employee onboarding, password resets, role assignment, account deactivation. | Access to all application routes, including `/admin` and all `POST/PUT/DELETE /api/v1/admin/users/*` endpoints. | ✅ Fully implemented and enforced via `require_admin` dependency. |
| **Viewer / Auditor (`viewer`)** | Read-only compliance audit, customer quality report inspection. | View reports, inspection summaries, and analytics. Read-only permissions. | 🟡 Seeded in DB (`0009_user_roles_admin.py`) and UI dropdown, but API endpoints do not yet restrict write operations for viewers. |

### Authentication & Authorization Constraints
- Authentication is handled via OAuth2 Password Bearer flow issuing **HS256 JWT tokens** with an 8-day expiration (`ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 8`).
- Backend enforcement: The dependency `require_admin` in `backend/app/api/dependencies.py` enforces `current_user.role == "admin"`.
- Operational routes (`/cases`, `/diagnoses`, `/images`, `/telemetry`, `/analytics`): Currently **unauthenticated** at the API layer to facilitate rapid competition demo execution without login friction.

---

## 5. System Scope

### In-Scope (Implemented and Functional)
1. **Interactive Diagnostic Intake**: Symptom entry with structured natural language extraction and equipment context (`/diagnosis/new`).
2. **Calibrated Computer Vision**: Uploading PNG/JPEG images, defining normalized ROIs, executing OpenCV segmentation, extracting area/diameter/coverage, and emitting `Observation` objects (`/images/analyze`).
3. **Deterministic Diagnostic Reasoner**: Evaluating observation evidence against 76 domain rules, computing independent `Evidence Support /100` scores, selecting discriminating questions and troubleshooting checks.
4. **Durable Case Lifecycle Persistence**: PostgreSQL storage of cases, structured observations, append-only revisions, question answers, check executions, cause confirmations, and recovery verifications.
5. **Optimistic Concurrency Control**: Rejection of stale client mutations via `StaleRevisionError` when `expected_revision` does not match the database head.
6. **Downloadable PDF Reporting**: Standard case report PDF generation and AIAG/VDA 8D Problem Solving Dossier generation via ReportLab 5.0.1.
7. **Production Analytics & Live SSE**: Aggregated KPI metrics, defect/cause distributions, resolution duration histograms, and real-time Server-Sent Events (`/api/v1/analytics/events`).
8. **Statistical Process Control (SPC)**: $I\text{-}MR$ control charts, capability metrics ($C_p, C_{pk}, P_p, P_{pk}$), frequency histograms, and Nelson out-of-control rule evaluation.
9. **Cleanroom Telemetry & Syringe Pot Life**: Ambient environmental monitoring, line sensor tracking, and state-machine-driven syringe thaw, mount, purge, and scrap lifecycles.
10. **Multi-Attribute Case Similarity**: Relational retrieval matching past resolved cases across defect taxonomy, fluid material, dispense method, equipment line, and symptom overlap.

### Out-of-Scope / Deferred (Explicitly Verified in Repository)
1. **Vector / Semantic Embeddings**: `pgvector` or OpenAI embedding retrieval was deferred per `QUEUE.md`. Case similarity uses deterministic multi-attribute scoring.
2. **Deep Learning Vision Models**: YOLOv8 or semantic segmentation neural networks are not implemented; OpenCV classical edge/contour segmentation is used exclusively.
3. **Score-Bearing D06 Vision Metrics**: Fully implemented. Classical OpenCV pipeline calculates contour aspect ratio ($w/h$), circularity ($4\pi\text{Area}/\text{Perimeter}^2$), convexity ($P_{\text{hull}}/P_{\text{contour}}$), solidity ($\text{Area}/\text{Area}_{\text{hull}}$), and interior bubble/void detection via Hough Circle & Blob Detection. Calibrated shape and bubble limits generate score-bearing observations (`deposit_shape=tailing`, `deposit_shape=abnormal`, `bubble_presence=visible_bubbles`) feeding directly into `DiagnosticEngine` cause ranking.
4. **Automated Machine Actuation**: The platform is an advisory decision-support system; it does not write recipe parameters directly to PLC/SCADA controllers.

---

## 6. Functional Requirements

The following requirements have been reverse-engineered and verified directly against the implementation:

| ID | Module | Requirement Description | Current Status | Evidence (Source File & Symbol) | Technical Notes |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **FR-001** | Auth | User registration with email, bcrypt password hashing, and role assignment. | ✅ Fully implemented | `backend/app/api/auth.py:register_user` | Passwords hashed via `bcrypt` (72-byte truncation enforced). |
| **FR-002** | Auth | OAuth2 JWT login issuing bearer tokens. | ✅ Fully implemented | `backend/app/api/auth.py:login_access_token` | Tokens encoded with `python-jose`, 8-day expiration. |
| **FR-003** | Auth | Current user profile retrieval and password change. | ✅ Fully implemented | `backend/app/api/auth.py:read_user_me`, `change_user_password` | Requires active user authentication. |
| **FR-004** | Admin | Admin user management (list, create, update, reset password, delete). | ✅ Fully implemented | `backend/app/api/admin.py` | Enforced by `Depends(require_admin)`. |
| **FR-005** | Diagnosis | Natural language symptom extraction into structured observations. | ✅ Fully implemented | `backend/app/services/diagnosis/symptom_extractor.py:SymptomExtractor` | Regex extraction fallback when OpenAI API key is unset. |
| **FR-006** | Diagnosis | Defect taxonomy identification from observation patterns. | ✅ Fully implemented | `backend/app/services/diagnosis/defect_identifier.py:identify_defect` | Matches observation tuples against `defects.json`. |
| **FR-007** | Diagnosis | Evidence evaluation against codified knowledge base rules. | ✅ Fully implemented | `backend/app/services/diagnosis/evidence_engine.py:EvidenceEngine` | Evaluates SUPPORTS, CONTRADICTS, and duplicate grouping. |
| **FR-008** | Diagnosis | Deterministic cause ranking with cumulative `Evidence Support /100` scores. | ✅ Fully implemented | `backend/app/services/diagnosis/cause_ranker.py:CauseRanker` | Bounded $[0, 100]$; does not sum to 100 across causes. |
| **FR-009** | Diagnosis | Optimal discriminating question selection. | ✅ Fully implemented | `backend/app/services/diagnosis/question_engine.py:QuestionEngine` | Calculates information gain across top-ranked candidate causes. |
| **FR-010** | Diagnosis | Troubleshooting check selection with effort/information weighting. | ✅ Fully implemented | `backend/app/services/diagnosis/action_planner.py:ActionPlanner` | Penalizes high-effort checks; skips already attempted checks. |
| **FR-011** | Vision | Multipart image upload with format validation and memory-bounded streaming. | ✅ Fully implemented | `backend/app/api/images.py:analyze_image` | Rejects non-PNG/JPEG; chunks uploads to prevent memory exhaustion (max 10MB). |
| **FR-012** | Vision | Localized ROI contour segmentation and geometric measurement. | ✅ Fully implemented | `backend/app/services/vision/segmentation.py`, `measurement.py` | OpenCV thresholding, contour extraction, area/diameter/circularity. |
| **FR-013** | Vision | Process limit classification converting measurements to canonical observations. | ✅ Fully implemented | `backend/app/services/vision/defect_classifier.py` | Emits `deposit_size`, `deposit_presence`, or `spreading_behaviour`. |
| **FR-014** | Case Mgmt | Atomic persistence of initial diagnostic case and Revision 1 snapshot. | ✅ Fully implemented | `backend/app/db/repository.py:save_initial_case` | Saves case context, observations, and revision JSON atomically. |
| **FR-015** | Case Mgmt | Submitting question answers and triggering re-ranking to Revision $N+1$. | ✅ Fully implemented | `backend/app/api/cases.py:submit_case_answer` | Appends answer record and creates new analysis revision. |
| **FR-016** | Case Mgmt | Submitting physical check findings with non-completed execution rules. | ✅ Fully implemented | `backend/app/api/cases.py:submit_case_check_result` | BLOCKED checks forced to UNKNOWN; never emit negative evidence. |
| **FR-017** | Case Mgmt | Optimistic concurrency control via `expected_revision`. | ✅ Fully implemented | `backend/app/db/repository.py:append_check_result` | Raises HTTP 409 Conflict upon revision mismatch. |
| **FR-018** | Case Mgmt | Explicit technician root cause confirmation. | ✅ Fully implemented | `backend/app/api/cases.py:submit_case_cause_confirmation` | Independent operation: checks never auto-confirm causes. |
| **FR-019** | Case Mgmt | Two-step issue recovery and independent verification tracking. | ✅ Fully implemented | `backend/app/api/cases.py:submit_case_recovery_action`, `..._verification` | Issue condition state machine strictly enforces verification before RESOLVED. |
| **FR-020** | Case Mgmt | Documenting recurrence of previously resolved cases. | ✅ Fully implemented | `backend/app/api/cases.py:submit_case_recurrence` | Transitions condition to RECURRED and advances revision. |
| **FR-021** | Reports | Structured case report data model generation. | ✅ Fully implemented | `backend/app/services/reporting/report_generator.py:build_case_report` | Aggregates all revision histories and lifecycle events. |
| **FR-022** | Reports | Standard multi-page PDF case report download. | ✅ Fully implemented | `backend/app/services/reporting/pdf_generator.py:render_case_report_pdf` | ReportLab canvas with dynamic page count ("Page X of Y"). |
| **FR-023** | Reports | AIAG/VDA Standard 8D Problem Solving quality report generation. | ✅ Fully implemented | `backend/app/services/reporting/eight_d_service.py:build_8d_report` | Generates D1 through D8 sections, 5-Whys, and Ishikawa categories. |
| **FR-024** | Reports | Downloadable 8D Quality Compliance PDF. | ✅ Fully implemented | `backend/app/services/reporting/eight_d_pdf_generator.py` | Formal industrial layout with running compliance header. |
| **FR-025** | AI Engine | Bounded natural language explanation of diagnostic changes. | ✅ Fully implemented | `backend/app/services/ai/explanation_service.py` | LLM generation with strict guardrails and deterministic fallback. |
| **FR-026** | AI Engine | Case report executive summary generation. | ✅ Fully implemented | `backend/app/api/cases.py:generate_case_ai_summary` | Uses projected safe observations; falls back to template text. |
| **FR-027** | Retrieval | Multi-attribute historical case similarity ranking. | ✅ Fully implemented | `backend/app/services/retrieval/similarity.py:calculate_case_similarity` | Multi-attribute scoring across 6 weighted dimensions. |
| **FR-028** | Analytics | Real-time global analytics event streaming via SSE. | ✅ Fully implemented | `backend/app/api/analytics.py:sse_events` | Server-Sent Events with keepalive ping broadcasting updates. |
| **FR-029** | Analytics | Aggregated dashboard KPI overview. | ✅ Fully implemented | `backend/app/api/analytics.py:get_dashboard_analytics` | Computes active cases, defect distributions, and trend insights. |
| **FR-030** | Analytics | Performance analytics with dynamic period filtering. | ✅ Fully implemented | `backend/app/api/analytics.py:get_performance_analytics` | Computes MTTR, first-time resolution rate, and cause confirmation rate. |
| **FR-031** | SPC | Statistical process control capability analysis. | ✅ Fully implemented | `backend/app/services/spc/spc_service.py:generate_spc_analysis` | Computes $C_p, C_{pk}, P_p, P_{pk}$, control limits, and Nelson rules. |
| **FR-032** | Telemetry | Cleanroom ambient and line sensor monitoring. | ✅ Fully implemented | `backend/app/services/telemetry/telemetry_service.py` | Generates live readings for temp, humidity, pressure, particles. |
| **FR-033** | Telemetry | Syringe pot life, defrosting, mounting, and scrap tracking. | ✅ Fully implemented | `backend/app/services/telemetry/telemetry_service.py` | State machine governing syringe defrost countdown and work life. |
| **FR-034** | Knowledge | Live knowledge base inspection via REST API. | ⚠️ Implemented but disconnected | `backend/app/api/defects.py`, `causes.py`, `actions.py`, `questions.py` | Backend endpoints work; frontend page uses hardcoded static arrays. |

---

## 7. Non-Functional Requirements

### Implemented vs. Recommended Matrix

| Quality Attribute | Implemented Baseline (Current Code) | Recommended Production Target | Evaluation & Evidence |
| :--- | :--- | :--- | :--- |
| **Performance** | In-memory OpenCV execution in worker threads (`anyio.to_thread.run_sync`). Image analysis completes in $<150\text{ ms}$ for typical $1\text{ MB}$ crops. | Dedicated Celery/Redis background task worker pool for large image batches. | Currently synchronous from client perspective; bounded to 10 MB. |
| **Scalability** | Single FastAPI instance with connection pooling. In-memory SSE queues (`_sse_subscribers: list[asyncio.Queue]`). | Distributed Redis Pub/Sub backplane for SSE broadcasting across multiple API instances. | Current SSE queue will drop broadcasts across multi-worker deployments. |
| **Security** | Passwords hashed with bcrypt; JWT auth for admin routes; secret-safe logging; upload chunking and dimension caps. | Enforce JWT auth across all operational `/cases` endpoints; implement HTTPS and rate limiting. | Operational API routes currently open to local network. |
| **Reliability** | Strict PostgreSQL transactions; optimistic revision checks (`StaleRevisionError`); offline LLM fallbacks. | Database read replicas; automated database disaster recovery snapshots. | Zero data corruption observed under concurrency tests. |
| **Maintainability** | Clean separation of schemas, models, services, and repositories. Zero circular dependencies. | Modular monorepo tooling (e.g. Turborepo, Poetry/uv workspaces). | High code readability and strict typing across Python and TypeScript. |
| **Data Integrity** | Foreign key cascades; database check constraints (`resulting_revision_number > 1`); unique constraints on `(case_id, revision)`. | Add audit trigger logging for tracking user IP addresses during case lifecycle updates. | Relational schema enforces append-only immutability. |
| **Observability** | Standard Python `logging`; structured JSON health check endpoint (`/api/v1/health`). | OpenTelemetry instrumentation, Prometheus metrics exporter, and centralized log shipping (Loki/Datadog). | Logs currently print to stdout/stderr. |
| **Usability** | Highly responsive UI with Tailwind v4, optimistic UI updates, clear warning alerts, and keyboard navigation. | WCAG 2.1 AA full accessibility audit, internationalization (i18n) for cleanroom plant languages. | Cleanroom operators can easily operate UI with touch/glove interfaces. |

---

## 8. Technology Stack

### Core Technologies and Rationale

```mermaid
mindmap
  root((DispenseIQ Stack))
    Frontend
      Next.js 16.3.4 (App Router)
      React 19.2.8
      TypeScript 5
      TailwindCSS v4
      Recharts 3.10
      Lucide React
    Backend
      Python 3.11+
      FastAPI 0.115+
      SQLAlchemy 2.0
      Alembic 1.13+
      psycopg 3 (Binary)
      Pydantic v2
    Data & Storage
      PostgreSQL 16
      Docker Compose
      JSONB Semi-structured Storage
    AI & Vision
      OpenCV (Headless 5.0+)
      OpenAI Python SDK (gpt-4o-mini)
      Deterministic Rule Reasoner
    Document Generation
      ReportLab 5.0.1 (Flowables & Canvas)
      PyPDF (Test verification)
```

### Detailed Component Analysis

#### Frontend Layer
- **Framework**: **Next.js 16.3.4** utilizing React Server Components where appropriate and `"use client"` for dynamic stateful forms.
- **Language**: **TypeScript 5** with strict null-checking enabled in `tsconfig.json`.
- **Styling**: **TailwindCSS v4** via `@tailwindcss/postcss`. No arbitrary utility bloat; modern layout tokens and clean responsive breakpoints.
- **Data Visualization**: **Recharts 3.10.1** used in `DefectChart.tsx`, `CauseChart.tsx`, `ResolutionChart.tsx`, and `SpcControlChart.tsx`.
- **Icons**: **Lucide React 1.44.0**.

#### Backend Layer
- **Framework**: **FastAPI 0.115.0** running on **Uvicorn 0.30.0**. Native ASGI asynchronous request routing.
- **ORM & Database Driver**: **SQLAlchemy 2.0** utilizing `Mapped` and `mapped_column` type annotations paired with **psycopg 3** (`psycopg[binary] >= 3.1`).
- **Data Validation**: **Pydantic v2** (`BaseModel`, `Field`, `model_validate`).
- **Database Migrations**: **Alembic 1.13.0**.

#### Image Processing & Document Generation
- **Computer Vision**: **OpenCV (`opencv-python-headless >= 5.0.0.93`)** for NumPy image array manipulation, adaptive thresholding, morphological noise filtering, and contour geometry extraction.
- **PDF Generation**: **ReportLab 5.0.1** utilizing custom `NumberedCanvas` implementations for precise, multi-page vector document generation.

---

## 9. System Architecture

DispenseIQ is architected as a **decoupled, multi-tier industrial intelligence platform**. The architecture separates user interaction, API routing, deterministic diagnostic orchestration, computer vision processing, bounded LLM reasoning, and durable relational persistence.

```mermaid
flowchart TD
    subgraph Client["Presentation Tier (Frontend)"]
        UI["Next.js 16 Web Application (Port 3001)"]
        AuthCtx["AuthContext & Providers"]
        StateCtrls["Workflow & Image State Controllers"]
        ApiClient["Fetch API Client (localStorage JWT)"]
    end

    subgraph API["Application Tier (FastAPI Backend - Port 8000)"]
        Router["APIRouter (/api/v1)"]
        AuthModule["Auth & Admin Subsystem"]
        CasesModule["Cases & Lifecycle Subsystem"]
        VisionModule["Images API & Offload Thread"]
        AnalyticsModule["Analytics, SPC & SSE Stream"]
        TelemetryModule["Telemetry & Pot Life Service"]
    end

    subgraph Engine["Reasoning & Processing Tier"]
        DiagEngine["DiagnosticEngine (Orchestrator)"]
        SymptomExt["SymptomExtractor (Regex / LLM)"]
        EvidenceEng["EvidenceEngine (Codified Rules)"]
        CauseRank["CauseRanker (Evidence Support /100)"]
        VisionPipe["OpenCV Segmentation & Measurement"]
        ReportLabGen["ReportLab PDF Generators (Standard & 8D)"]
        LLMBounded["Bounded LLM Service (OpenAI gpt-4o-mini)"]
    end

    subgraph Data["Persistence Tier"]
        PG[(PostgreSQL 16 Database)]
        CasesTab["cases / revisions / observations"]
        EventsTab["check_results / confirmations / lifecycle"]
        UsersTab["users (RBAC)"]
    end

    %% Client to Backend
    UI --> StateCtrls
    StateCtrls --> ApiClient
    AuthCtx --> ApiClient
    ApiClient -->|HTTP REST / SSE| Router

    %% Backend Routing
    Router --> AuthModule
    Router --> CasesModule
    Router --> VisionModule
    Router --> AnalyticsModule
    Router --> TelemetryModule

    %% Processing Calls
    CasesModule --> DiagEngine
    CasesModule --> ReportLabGen
    VisionModule --> VisionPipe
    DiagEngine --> SymptomExt
    DiagEngine --> EvidenceEng
    DiagEngine --> CauseRank
    DiagEngine --> LLMBounded

    %% Persistence Calls
    AuthModule --> UsersTab
    CasesModule --> CasesTab
    CasesModule --> EventsTab
    AnalyticsModule --> CasesTab
    AnalyticsModule --> EventsTab
    CasesTab --- PG
    EventsTab --- PG
    UsersTab --- PG
```

### Architectural Highlights
1. **Zero Diagnostic Recalculation on Report Generation**: The PDF generator and report read models consume already-accepted, persisted diagnostic revisions directly from the database; they never execute diagnostic algorithms during rendering.
2. **Stateless Processing with Durable Snapshots**: Every diagnostic evaluation produces an immutable JSON snapshot (`result_snapshot` in `analysis_revisions`), ensuring past reasoning can be audited years later even if underlying knowledge rules evolve.
3. **Optimistic Locking Guard**: Clients must pass their local `expected_revision` when appending answers, check results, or confirmations. The backend verifies this against the persisted revision number, preventing lost updates in multi-operator cleanroom lines.

---

## 10. Architecture Diagrams

### 10.1 High-Level Component Interactions

```mermaid
sequenceDiagram
    autonumber
    actor Tech as Cleanroom Technician
    participant FE as Next.js Frontend
    participant API as FastAPI Backend
    participant CV as OpenCV Vision Pipeline
    participant ENG as Diagnostic Engine
    participant DB as PostgreSQL 16
    participant LLM as OpenAI (Optional)

    Tech->>FE: Upload Defect Image & Set ROI
    FE->>API: POST /images/analyze (Multipart + Profile)
    API->>CV: Execute segmentation & feature extraction
    CV-->>API: Return RoiMeasurements & Defect Observations
    API-->>FE: Return Calibrated Observations

    Tech->>FE: Enter Problem Description & Submit
    FE->>API: POST /cases (CreateCaseRequest + Obs)
    API->>ENG: prepare_case() & diagnose()
    ENG->>ENG: identify_defect()
    ENG->>ENG: evaluate_evidence() & rank_causes()
    ENG->>LLM: generate_text() (Bounded Explanation)
    Note over ENG,LLM: Graceful fallback to deterministic text if offline
    ENG-->>API: DiagnosisResult (Revision 1)
    API->>DB: Atomically persist CaseModel, Obs, & AnalysisRevisionModel
    DB-->>API: Persisted (Commit)
    API-->>FE: DurableCaseResponse (Revision 1)
    FE-->>Tech: Render Ranked Causes & Next Recommended Action
```

### 10.2 Database Entity Relationship Diagram (ERD)

```mermaid
erDiagram
    users {
        string id PK
        string email UK
        string hashed_password
        string first_name
        string last_name
        boolean is_active
        string role
        string department
        datetime created_at
        datetime last_login
    }

    cases {
        uuid case_id PK
        text description
        text material
        text method
        jsonb machine_context
        string defect_code
        text defect_name
        string issue_condition
        datetime created_at
    }

    case_observations {
        int id PK
        uuid case_id FK
        text observation_id
        string observation_type
        text value
        text original_text
        string statement_type
        string source
        float confidence
        datetime created_at
        int first_seen_revision
        jsonb metadata
    }

    analysis_revisions {
        int id PK
        uuid case_id FK
        int revision_number
        datetime analyzed_at
        string defect_code
        string issue_condition
        jsonb result_snapshot
    }

    case_question_answers {
        int id PK
        uuid case_id FK
        text question_id
        text answer_value
        text answer_text
        string source
        datetime answered_at
        int resulting_revision_number
    }

    case_check_results {
        int id PK
        uuid case_id FK
        text check_id
        string execution_status
        string finding
        text finding_details
        text outcome
        string source
        datetime checked_at
        int resulting_revision_number
    }

    case_check_executions {
        int id PK
        uuid case_id FK
        text check_id
        string status
        string finding
        text notes
        datetime executed_at
        int resulting_revision_number
    }

    case_cause_confirmations {
        int id PK
        uuid case_id FK
        text cause_id
        string confirmed_by
        text notes
        datetime confirmed_at
        int resulting_revision_number
    }

    case_lifecycle_events {
        int id PK
        uuid case_id FK
        string event_type
        string prior_issue_condition
        string resulting_issue_condition
        int resulting_revision_number
        string actor
        text details
        boolean verification_passed
        datetime created_at
    }

    cases ||--o{ case_observations : "has many"
    cases ||--o{ analysis_revisions : "has many (ordered)"
    cases ||--o{ case_question_answers : "records"
    cases ||--o{ case_check_results : "records"
    cases ||--o{ case_check_executions : "tracks"
    cases ||--o{ case_cause_confirmations : "confirms"
    cases ||--o{ case_lifecycle_events : "transitions"
```

---

## 11. Frontend Architecture

### Routing and Layout Structure
The frontend application lives in `frontend/app/` and utilizes Next.js App Router route grouping:
- **`app/page.tsx`**: Automatic redirect to `/dashboard`.
- **`app/(auth)/`**: Unauthenticated authentication group containing:
  - `login/page.tsx`: Credential login form storing JWT in `localStorage`.
  - `register/page.tsx`: User registration form with department and role selection.
- **`app/(dashboard)/`**: Protected application shell group wrapped with `DashboardShell` (sidebar, top header, command palette):
  - `dashboard/page.tsx`: Main overview with KPIs, live line ribbon, recent cases, and SSE connection.
  - `diagnosis/new/page.tsx`: Intake form integrating `ProblemForm` and `ImageUpload`.
  - `diagnosis/[id]/page.tsx`: Diagnostic assessment hub showing ranked causes and evidence.
  - `diagnosis/[id]/questions/page.tsx`: Interactive question refinement screen.
  - `diagnosis/[id]/troubleshooting/page.tsx`: Action checklist for physical tests.
  - `diagnosis/[id]/verification/page.tsx`: Root cause confirmation and recovery verification.
  - `diagnosis/[id]/analysis/page.tsx`: Deep-dive scoring breakdown and revision history.
  - `cases/page.tsx`: Filterable, searchable case list table.
  - `cases/[id]/page.tsx`: Case detail timeline and historical similar case matches.
  - `reports/page.tsx`: Quality reporting hub.
  - `reports/[id]/page.tsx`: Split view for Standard PDF reports and AIAG/VDA 8D reports.
  - `analytics/page.tsx`: Toggleable performance metrics and Statistical Process Control (SPC).
  - `telemetry/page.tsx`: Live sensor gauges, ambient conditions, and syringe pot life management.
  - `knowledge-base/page.tsx`: Browsable catalog of defects, causes, actions, and rules.
  - `admin/page.tsx`: Administrative employee and user management interface.
  - `settings/page.tsx`: User profile, password change, and appearance settings.

### State Management & Controllers
Rather than relying on heavyweight global stores like Redux, state is managed through scoped, testable controller modules in `frontend/lib/`:
1. **`diagnostic-workflow-state.ts`**: Coordinates optimistic question answers, check result payloads, cause confirmations, recovery actions, and handles HTTP 409 stale revision retries.
2. **`image-upload-state.ts`**: Manages drag-and-drop uploads, ROI coordinate validation, concurrent analysis request cancellation (`AbortController`), and result aggregation.
3. **`case-detail-state.ts`**: Chronologically merges the 7 distinct lifecycle collections (`observations`, `revisions`, `answers`, `check_results`, `executions`, `confirmations`, `events`) into a unified, inspectable audit timeline.
4. **`reports-state.ts`**: Handles format selection (`standard` vs `8d`), loading indicators, and PDF blob downloads.

---

## 12. Backend Architecture

The backend follows a **layered, clean architecture** pattern with strict dependency injection via FastAPI:

```text
HTTP Request
     │
     ▼
[API Route Handlers] (backend/app/api/*.py)
  ├── Parses request schemas (Pydantic v2)
  ├── Injects DB Session (app.db.session.get_db)
  └── Injects Business Services
     │
     ▼
[Domain Services] (backend/app/services/*)
  ├── DiagnosticEngine (app.services.diagnosis.engine)
  ├── EvidenceEngine & CauseRanker
  ├── Vision Pipeline (app.services.vision.*)
  ├── Reporting & PDF Services (app.services.reporting.*)
  └── TelemetryService (app.services.telemetry.*)
     │
     ▼
[Persistence Layer] (backend/app/db/repository.py)
  ├── Atomic transactional commits
  ├── Optimistic revision enforcement
  └── Query optimization (selectinload)
     │
     ▼
[Relational Database] (PostgreSQL 16 via psycopg 3)
```

### Key Architectural Patterns
- **Dependency Injection**: Dependencies like `get_db`, `get_case_repository`, `get_diagnosis_engine`, and `get_current_user` are injected at route definitions, allowing seamless mocking in automated tests.
- **Repository Pattern**: `CaseRepository` in `backend/app/db/repository.py` encapsulates all raw SQLAlchemy queries, ensuring route handlers do not construct direct SQL expressions.
- **Optimistic Concurrency Control**: Mutating operations enforce revision sequencing. If an operator submits an action expecting Revision 2, but another technician advanced the case to Revision 3, the repository raises `StaleRevisionError`, which maps to an HTTP 409 Conflict.

---

## 13. Database Architecture

### Technology & Driver Configuration
- **Database Engine**: **PostgreSQL 16-alpine** executed in a persistent Docker container (`dispenselens-postgres`).
- **Driver**: **`psycopg` (Version 3.1+)** using SQLAlchemy's async/sync binary interface (`postgresql+psycopg://`).
- **Schema Management**: Managed exclusively through **Alembic**. The database schema is identical between development and production.

### Entity Relationships & Constraints
- **`cases` Table**: Stores the root domain entity. The primary key is a native PostgreSQL `UUID` (`as_uuid=False`).
- **`case_observations` Table**: Stores structured observations. Features a composite unique constraint `uq_case_observations_case_id_obs_id` and check constraint `ck_case_observations_first_seen_rev_pos` (`first_seen_revision > 0`). Metadata is stored as native PostgreSQL `JSONB`.
- **`analysis_revisions` Table**: Append-only snapshots. Constrained by `uq_analysis_revisions_case_id_revision_number` and `ck_analysis_revisions_revision_number_pos` (`revision_number > 0`). The complete evaluation is serialized in `result_snapshot (JSONB)`.
- **`case_question_answers`, `case_check_results`, `case_check_executions`, `case_cause_confirmations`, `case_lifecycle_events`**: All maintain foreign key cascades (`ondelete="CASCADE"`) to `cases.case_id`, unique constraints on `(case_id, resulting_revision_number)`, and check constraints enforcing `resulting_revision_number > 1`.
- **`users` Table**: Stores system operators, roles, bcrypt password hashes, and department assignments.

---

## 14. API Documentation

### Complete Endpoint Directory

| Method | Endpoint | Summary / Purpose | Request Body | Response Model | Auth | DB Ops | Status |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| `GET` | `/api/v1/health` | Service liveness & DB check | None | `HealthResponse` | None | Read | ✅ |
| `POST` | `/api/v1/auth/register` | Register new employee | `UserCreate` | `UserRead` | None | Write | ✅ |
| `POST` | `/api/v1/auth/login` | OAuth2 access token login | `OAuth2PasswordRequestForm` | `Token` | None | Read | ✅ |
| `GET` | `/api/v1/auth/me` | Get current user profile | None | `UserRead` | Bearer | Read | ✅ |
| `PATCH` | `/api/v1/auth/me` | Update profile fields | `UserProfileUpdate` | `UserRead` | Bearer | Write | ✅ |
| `POST` | `/api/v1/auth/me/change-password` | Change user password | `ChangePasswordRequest` | `dict` | Bearer | Write | ✅ |
| `POST` | `/api/v1/cases` | Create & evaluate initial case | `CreateCaseRequest` | `DurableCaseResponse` | None | Write | ✅ |
| `GET` | `/api/v1/cases` | List all diagnostic cases | Query: `skip`, `limit` | `list[DurableCaseResponse]` | None | Read | ✅ |
| `GET` | `/api/v1/cases/{id}` | Get complete case detail | None | `DurableCaseResponse` | None | Read | ✅ |
| `POST` | `/api/v1/cases/{id}/answers` | Submit question answer | `SubmitAnswerRequest` | `CaseAnswerResponse` | None | Write | ✅ |
| `POST` | `/api/v1/cases/{id}/check-results` | Submit check result | `SubmitCheckResultRequest` | `CaseCheckResultResponse` | None | Write | ✅ |
| `POST` | `/api/v1/cases/{id}/checks` | Record check execution | `SubmitCheckRequest` | `CaseCheckResponse` | None | Write | ✅ |
| `POST` | `/api/v1/cases/{id}/confirmations` | Confirm root cause | `SubmitCauseConfirmationRequest` | `CaseCauseConfirmationResponse` | None | Write | ✅ |
| `POST` | `/api/v1/cases/{id}/recovery-actions`| Record corrective action | `SubmitRecoveryActionRequest` | `CaseRecoveryActionResponse` | None | Write | ✅ |
| `POST` | `/api/v1/cases/{id}/recovery-verifications`| Verify issue resolution | `SubmitRecoveryVerificationRequest` | `CaseRecoveryVerificationResponse` | None | Write | ✅ |
| `POST` | `/api/v1/cases/{id}/recurrences` | Record defect recurrence | `SubmitRecurrenceRequest` | `CaseRecurrenceResponse` | None | Write | ✅ |
| `GET` | `/api/v1/cases/{id}/report` | Get case report read model | None | `CaseReportResponse` | None | Read | ✅ |
| `GET` | `/api/v1/cases/{id}/report.pdf` | Download standard PDF report | None | Binary PDF Stream | None | Read | ✅ |
| `GET` | `/api/v1/cases/{id}/8d` | Get 8D quality dossier | None | `EightDReportResponse` | None | Read | ✅ |
| `GET` | `/api/v1/cases/{id}/8d.pdf` | Download 8D compliance PDF | None | Binary PDF Stream | None | Read | ✅ |
| `POST` | `/api/v1/cases/{id}/ai-summary` | Generate AI executive summary | None | `CaseAiSummaryResponse` | None | Read | ✅ |
| `GET` | `/api/v1/cases/{id}/similar` | Find similar historical cases| Query: `limit`, `min_score` | `SimilarCasesResponse` | None | Read | ✅ |
| `POST` | `/api/v1/images/analyze` | Analyze image with ROIs | Multipart: file, profile | `ImageAnalysisResponse` | None | None | ✅ |
| `GET` | `/api/v1/analytics/dashboard` | Main dashboard statistics | None | `DashboardAnalyticsResponse` | None | Read | ✅ |
| `GET` | `/api/v1/analytics/performance`| Performance metrics & trends | Query: `period` | `AnalyticsPerformanceResponse` | None | Read | ✅ |
| `GET` | `/api/v1/analytics/spc` | Statistical process control | Query: `parameter`, `line` | `SpcAnalysisResponse` | None | None | ✅ |
| `GET` | `/api/v1/analytics/events` | Real-time SSE event stream | None | `text/event-stream` | None | None | ✅ |
| `GET` | `/api/v1/telemetry/overview` | Cleanroom ambient & lines | None | `TelemetryOverviewResponse` | None | None | ✅ |
| `GET` | `/api/v1/telemetry/lines/{id}`| Live line sensor snapshot | None | `LineTelemetrySnapshot` | None | None | ✅ |
| `GET` | `/api/v1/telemetry/consumables`| List active adhesive syringes| None | `list[ConsumableItem]` | None | None | ✅ |
| `POST` | `/api/v1/telemetry/consumables/thaw`| Start defrost countdown | `ThawRequest` | `ConsumableItem` | None | None | ✅ |
| `POST` | `/api/v1/telemetry/consumables/{id}/mount`| Mount syringe to line | `MountRequest` | `ConsumableItem` | None | None | ✅ |
| `POST` | `/api/v1/telemetry/consumables/{id}/purge`| Record nozzle purge shot | `PurgeRequest` | `ConsumableItem` | None | None | ✅ |
| `POST` | `/api/v1/telemetry/consumables/{id}/scrap`| Retire/scrap expired syringe| `ScrapRequest` | `ConsumableItem` | None | None | ✅ |
| `GET` | `/api/v1/admin/overview` | Admin system metrics | None | `AdminOverviewStats` | Admin | Read | ✅ |
| `GET` | `/api/v1/admin/users` | List employee directory | None | `list[EmployeeSummary]` | Admin | Read | ✅ |
| `POST` | `/api/v1/admin/users` | Admin create employee | `CreateEmployeeRequest` | `UserRead` | Admin | Write | ✅ |
| `PUT` | `/api/v1/admin/users/{id}` | Admin update employee | `UpdateEmployeeRequest` | `UserRead` | Admin | Write | ✅ |
| `POST` | `/api/v1/admin/users/{id}/reset-password`| Force password reset | `AdminResetPasswordRequest`| `dict` | Admin | Write | ✅ |
| `DELETE`| `/api/v1/admin/users/{id}` | Deactivate/delete employee | None | `dict` (200 OK) | Admin | Write | ✅ |
| `GET` | `/api/v1/defects` | Get defect taxonomy | None | `list[DefectDefinition]` | None | None | ⚠️ |
| `GET` | `/api/v1/causes` | Get root causes catalog | None | `list[CauseDefinition]` | None | None | ⚠️ |
| `GET` | `/api/v1/actions` | Get troubleshooting actions | None | `list[ActionDefinition]` | None | None | ⚠️ |
| `GET` | `/api/v1/questions` | Get diagnostic questions | None | `list[QuestionDefinition]`| None | None | ⚠️ |

---

## 15. Authentication & Authorization

### Implementation Architecture
```mermaid
sequenceDiagram
    autonumber
    actor User as Operator / Admin
    participant FE as Next.js Frontend
    participant API as FastAPI Backend (/api/v1/auth)
    participant DB as PostgreSQL (users table)

    User->>FE: Enter Email & Password
    FE->>API: POST /auth/login (form-urlencoded)
    API->>DB: Query user by email
    DB-->>API: UserModel record
    API->>API: bcrypt.checkpw(password, hashed_password)
    alt Password Valid & User Active
        API->>API: jwt.encode(sub=user.id, exp=8 days)
        API->>DB: Update user.last_login
        API-->>FE: 200 OK {"access_token": "...", "token_type": "bearer"}
        FE->>FE: Save token to localStorage
        FE->>API: GET /auth/me (Authorization: Bearer ...)
        API-->>FE: 200 OK UserRead {id, email, role, department}
        FE->>FE: Update AuthContext state
    else Invalid Credentials
        API-->>FE: 400 Bad Request ("Incorrect email or password")
    end
```

### Security Details
- **Password Hashing**: Utilizes standard `bcrypt` with salt generation (`bcrypt.gensalt()`). Passwords are truncated to 72 bytes before hashing to prevent DoS attacks on bcrypt implementations.
- **Client Storage**: Tokens are stored in `localStorage` under the key `"token"`. The frontend `apiClient` automatically injects `Authorization: Bearer <token>` into outgoing request headers if present.
- **Admin RBAC Enforcement**: Handled via `Depends(require_admin)` in `backend/app/api/admin.py`. If `current_user.role != "admin"`, an HTTP 403 Forbidden exception is returned.

---

## 16. Diagnosis Engine

The diagnostic engine (`backend/app/services/diagnosis/engine.py`) is the central orchestrator of the entire platform. It evaluates structured physical observations against a codified engineering knowledge base, computes cumulative evidence support scores, and manages diagnostic revisions.

```mermaid
flowchart LR
    Input["Intake: Problem Text, Line Context, Image Observations"] --> Extractor["SymptomExtractor"]
    Extractor --> DefectID["Defect Identifier"]
    DefectID --> EvidenceEng["EvidenceEngine (76 Rules)"]
    EvidenceEng --> Ranker["CauseRanker (Evidence Support /100)"]
    Ranker --> StateCheck["StateManager (4-Dimension Independence)"]
    StateCheck --> NextSteps["QuestionEngine & ActionPlanner"]
    NextSteps --> Snapshot["AnalysisRevision Snapshot (PostgreSQL)"]
```

### Core Diagnostic Lifecycle Phases
1. **Intake & Preparation (`prepare_case`)**: Unifies `DiagnosisRequest` or `StructuredCase`, normalizes incoming manual observations, and attaches metadata.
2. **Symptom Extraction (`SymptomExtractor`)**: Extracts deposit size, location, frequency, and material state.
3. **Defect Identification (`identify_defect`)**: Evaluates observation tuples against defect patterns in `defects.json`. If ambiguous, issues an advisory warning.
4. **Evidence Evaluation (`EvidenceEngine`)**: Matches observations against candidate causes using 76 codified rules. Flags duplicates using semantic group deduplication.
5. **Deterministic Cause Ranking (`CauseRanker`)**: Computes cumulative `Evidence Support /100` scores.
6. **State Independence Validation (`StateManager`)**: Strictly separates step execution, step finding, cause conclusion, and issue condition.
7. **Revision Sequencing**: Compares the new ranking with prior revisions, logs score deltas, and appends Revision $N+1$.
8. **Next Question & Check Selection**: Evaluates maximum information gain across remaining candidate causes.

---

## 17. AI Architecture

### Non-Authoritative Bounded LLM Design
In industrial manufacturing, generative AI models hallucinate non-existent mechanical failure modes and output inconsistent probabilities. DispenseIQ implements a strict **bounded architectural boundary** around LLM usage:

```mermaid
flowchart TD
    subgraph DeterministicCore["Deterministic Engineering Authority (Authoritative)"]
        Engine["Diagnostic Engine"]
        Rules["Knowledge Base Rules (rules.json)"]
        Scoring["Evidence Support Math (/100)"]
        State["IssueCondition State Machine"]
    end

    subgraph LLMBoundary["Bounded AI Layer (Non-Authoritative)"]
        PromptMgr["PromptManager (Strict Injection Schemas)"]
        LLM["OpenAI gpt-4o-mini (temperature=0.2)"]
        Guard["Explanation Validation Guardrails"]
    end

    subgraph OutputTier["Output Presentation"]
        Summary["Technician Explanation"]
        Fallback["Deterministic Template Fallback"]
    end

    Engine --> Scoring
    Rules --> Engine
    Engine -->|Structured Score & Evidence Data| PromptMgr
    PromptMgr --> LLM
    LLM --> Guard
    Guard -->|Passes Guardrails| Summary
    Guard -->|Fails or Offline| Fallback
    Scoring -.->|Forbidden to Modify| LLM
    State -.->|Forbidden to Assert| LLM
```

### Prompt Engineering and Guardrails
All prompts reside in `backend/app/services/ai/prompt_manager.py`. System prompts explicitly instruct:
1. **No Score Modification**: The model is strictly prohibited from inventing or altering any numerical score.
2. **No Procedure Hallucination**: The model cannot introduce troubleshooting steps not present in the structured payload.
3. **No Autonomous Confirmation**: The model cannot declare root causes confirmed or defects resolved.
4. **Safe Observation Projection**: Method `PromptManager.project_safe_observations()` filters out raw image paths, base64 bytes, and internal server parameters, passing only clean domain tuples `(type, value, source)`.

---

## 18. Explainability & Confidence

### Mathematical Scoring Model
Unlike probabilistic systems that require cause likelihoods to sum to $100\%$, DispenseIQ models **independent evidence support**. A score represents cumulative empirical evidence supporting a hypothesis:

$$\text{Score}(c) = \text{clamp}\left(\text{Base} + \sum_{e \in E_{\text{supp}}} w^+(e) - \sum_{e \in E_{\text{cont}}} w^-(e) - \text{Penalty}_{\text{missing}} \cdot |E_{\text{miss}}|, 0, 100\right)$$

Where:
- $\text{Base} = 30.0$ (initial baseline for any applicable cause).
- $w^+(e) \in \{+20.0 \text{ (STRONG)}, +12.0 \text{ (MODERATE)}, +5.0 \text{ (WEAK)}\}$.
- $w^-(e) \in \{-18.0 \text{ (STRONG)}, -10.0 \text{ (MODERATE)}, -4.0 \text{ (WEAK)}\}$.
- $w_{\text{duplicate}} = 0.0$ (semantic deduplication prevents inflated scores).
- $\text{Penalty}_{\text{missing}} = 2.0$ per unverified diagnostic attribute.
- $\text{Threshold}_{\text{high}} \ge 75.0$, $\text{Threshold}_{\text{low}} \le 30.0$.

### Four-Level Explainability Structure
Every ranked cause provides an inspectable breakdown displayed in `frontend/components/diagnosis/CauseRanking.tsx`:
1. **Evidence Support Score**: Normalized value out of 100.
2. **Itemized Supporting Evidence**: Observations directly boosting the hypothesis, tagged with provenance (`[USER]`, `[IMAGE]`, `[USER_CHECK_RESULT]`).
3. **Itemized Contradicting Evidence**: Observations actively discounting the hypothesis.
4. **Revision Delta**: Explicit change summary (e.g., *"Nozzle Restriction decreased from 82 to 54 (-28 pts) due to Check ACT01 finding clean nozzle tip"*).

---

## 19. Image Analysis

### Vision Pipeline Architecture
The image analysis pipeline is implemented in `backend/app/services/vision/` and exposed via `POST /api/v1/images/analyze`.

```mermaid
flowchart TD
    Upload["Upload JPEG/PNG (Max 10 MB)"] --> Decode["cv2.imdecode & Magic Bytes Validation"]
    Decode --> DimCheck["Dimension Check (Max 4096px, 16M pixels)"]
    DimCheck --> ROINorm["Normalized ROI to Pixel Projection"]
    ROINorm --> PatchCrop["Analysis Window Patch Crop"]
    PatchCrop --> Segment["cv2 Adaptive Threshold & Morphological Cleanup"]
    Segment --> Features["Feature Extraction (Area, Circularity, Solidity)"]
    Features --> Calibrate["Calibration Mode Evaluation"]
    Calibrate -->|FEATURES_ONLY| Neutral["Status: UNCALIBRATED (Neutral Features)"]
    Calibrate -->|PROCESS_LIMITS| Limits["Evaluate Coverage & Overflow Ratios"]
    Calibrate -->|REFERENCE_IMAGE| Golden["Compare with Golden Template Image"]
    Limits --> Observations["Generate Canonical Observations (Source: IMAGE)"]
    Golden --> Observations
    Neutral --> Response["Return ImageAnalysisResponse"]
    Observations --> Response
```

### Analysis Modes & Calibration
1. **`FEATURES_ONLY`**: Extracts raw geometric measurements without declaring a defect. Status is `UNCALIBRATED`; emits no score-bearing observations.
2. **`PROCESS_LIMITS`**: Evaluates deposit coverage ratio against caller-specified bounds:
   - Coverage ratio $< \text{min\_coverage\_ratio} \implies \text{D01 (undersized)}$.
   - Coverage ratio $> \text{max\_coverage\_ratio} \implies \text{D02 (oversized)}$.
   - Coverage ratio $< \text{min\_presence\_ratio} \implies \text{D04 (missing)}$.
   - Overflow ratio $> \text{max\_overflow\_ratio} \implies \text{D05 (spreading)}$.
3. **`REFERENCE_IMAGE`**: Compares the target image with an uploaded reference (golden template) image.

### Storage Reality
Raw image bytes are **never written to disk or the database**. Images are decoded in memory, processed through OpenCV, and discarded. Only the lightweight numerical measurements and derived `Observation` metadata records are retained in PostgreSQL.

---

## 20. Case Management

### Issue Condition State Machine
The platform strictly decouples troubleshooting actions from issue resolution. Completing a check never automatically resolves an issue. Resolution requires independent physical verification test shots.

```mermaid
stateDiagram-v2
    [*] --> UNRESOLVED: Initial Case Creation (Revision 1)
    UNRESOLVED --> UNRESOLVED: Diagnostic Questions & Checks (Revision N+1)
    UNRESOLVED --> RECOVERY_PENDING_VERIFICATION: Apply Corrective Action
    RECOVERY_PENDING_VERIFICATION --> UNRESOLVED: Verification Failed (Test shots bad)
    RECOVERY_PENDING_VERIFICATION --> RESOLVED: Verification Passed (Nominal test shots)
    RESOLVED --> RECURRED: Defect Recurrence Observed
    RECURRED --> RECOVERY_PENDING_VERIFICATION: New Corrective Action Applied
    RECURRED --> UNRESOLVED: Reopened for Re-diagnosis
```

### Four Orthogonal State Dimensions
1. **Check Execution Status**: `PENDING`, `IN_PROGRESS`, `COMPLETED`, `BLOCKED`, `SKIPPED`, `FAILED`.
2. **Check Finding**: `SUPPORTS`, `CONTRADICTS`, `INCONCLUSIVE`, `UNKNOWN`.
3. **Cause Conclusion**: `SUSPECTED`, `CONFIRMED`, `UNRESOLVED`.
4. **Issue Condition**: `UNRESOLVED`, `RECOVERY_PENDING_VERIFICATION`, `RESOLVED`, `RECURRED`.

---

## 21. Knowledge Base & Similar Cases

### Multi-Attribute Case Similarity Engine
Case retrieval (`backend/app/services/retrieval/similarity.py`) matches historical cases across six weighted dimensions:

| Dimension | Max Weight | Matching Logic |
| :--- | :---: | :--- |
| **Defect Code Matching** | 0.35 | Exact defect code match (+0.35); token overlap across defect names (+0.18). |
| **Material Compatibility** | 0.15 | Exact material string match (+0.15); Jaccard token similarity $>0.4$ (+0.15). |
| **Method & Dispenser Model** | 0.15 | Method match (+0.10); equipment line/machine model match (+0.05). |
| **Observation Overlap** | 0.15 | Jaccard token overlap between recorded observation types. |
| **Problem Description** | 0.10 | Lexical token overlap of filtered problem descriptions. |
| **Resolution Status** | 0.10 | Prioritizes cases verified as `RESOLVED` (+0.10) or having confirmed causes (+0.05). |

Total similarity score is normalized in $[0.0, 1.0]$. The system does not use vector embeddings or pgvector.

---

## 22. Reporting & PDF Generation

### Report Types
1. **Standard Case Report (`/api/v1/cases/{id}/report.pdf`)**: A comprehensive summary including defect classification, current `Evidence Support /100` ranking, complete question answer history, check execution logs, and recovery verification signoff.
2. **AIAG / VDA 8D Quality Report (`/api/v1/cases/{id}/8d.pdf`)**: A standardized manufacturing quality compliance document structured across the Eight Disciplines:
   - **D1 (Team)**: Champion, team leader, quality members.
   - **D2 (Problem Description)**: 5W2H analysis (What, Where, When, Who, Why, How, How Many).
   - **D3 (Interim Containment)**: Quarantine lots, containment actions, effectivity ratings.
   - **D4 (Root Cause Analysis)**: 5-Whys deduction, Ishikawa fishbone category.
   - **D5 (Permanent Corrective Actions)**: Selected corrective actions.
   - **D6 (Validation)**: Verification test shot measurements and validation evidence.
   - **D7 (Prevent Recurrence)**: Process parameter standardization and SOP updates.
   - **D8 (Closure & Signoff)**: Formal signoff and case archive.

### Implementation Details
- Built with **ReportLab 5.0.1** using `NumberedCanvas` for dynamic two-pass page calculation (`"Page X of Y"`).
- Uses auto-wrapping `Paragraph` flowables inside table cells to eliminate text clipping.
- Generates zero database queries during rendering; formats purely from the accepted `CaseReportResponse` or `EightDReportResponse` models.

---

## 23. Analytics

### Implemented Subsystems
1. **Real-time Global SSE Stream (`GET /api/v1/analytics/events`)**: Asynchronous SSE endpoint that broadcasts case lifecycle transitions to connected clients, accompanied by a 15-second heartbeat ping.
2. **Performance Analytics (`GET /api/v1/analytics/performance`)**:
   - **Mean Time to Resolution (MTTR)**: Derived strictly from difference between `created_at` and the earliest `RESOLVED` lifecycle event.
   - **First-Time Resolution Rate**: Percentage of resolved cases achieving resolution with zero failed verifications and zero recurrences.
   - **Cause Confirmation Rate**: Percentage of cases with at least one confirmed root cause.
   - **Duration Histograms**: Grouped into standard manufacturing buckets (`0-5 min`, `5-10 min`, `10-15 min`, `15-20 min`, `20-30 min`, `30+ min`).
3. **Statistical Process Control (SPC) (`GET /api/v1/analytics/spc`)**:
   - Capability metrics: $C_p, C_{pk}, P_p, P_{pk}$.
   - Individual & Moving Range ($I\text{-}MR$) control chart data ($UCL, CL, LCL$).
   - Nelson Rules evaluation for detecting out-of-control runs and trends.

---

## 24. Data Flow

### End-to-End Traces

#### Trace 1: Image Analysis & Case Intake
`Technician UI (/diagnosis/new)` $\to$ `ImageUpload.tsx` $\to$ `imagesApi.analyze(file, profile)` $\to$ `POST /api/v1/images/analyze` $\to$ `anyio.to_thread.run_sync(_sync_analyze_image)` $\to$ `OpenCV segmentation` $\to$ `ImageAnalysisResponse` $\to$ `ProblemForm.handleSubmit` $\to$ `casesApi.createCase()` $\to$ `POST /api/v1/cases` $\to$ `DiagnosticEngine.prepare_case()` $\to$ `CaseRepository.save_initial_case()` $\to$ `PostgreSQL (cases, case_observations, analysis_revisions)` $\to$ `Router navigates to /diagnosis/{case_id}`.

#### Trace 2: Check Submission & Optimistic Re-ranking
`TroubleshootingChecklist.tsx` $\to$ `diagnostic-workflow-state.ts` $\to$ `casesApi.submitCheckResult(case_id, payload)` $\to$ `POST /api/v1/cases/{id}/check-results` $\to$ `CaseRepository.append_check_result()` (verifies `expected_revision == current_revision`) $\to$ `DiagnosticEngine.submit_check_result()` $\to$ `EvidenceEngine.evaluate()` $\to$ `CauseRanker.rank()` $\to$ `AnalysisRevision (Revision N+1)` $\to$ `PostgreSQL commit` $\to$ `broadcast_analytics_update()` $\to$ `SSE stream emits CASE_UPDATED` $\to$ `Frontend receives updated revision & renders re-ranked causes`.

---

## 25. State Machines

### Syringe Pot Life State Machine (`backend/app/services/telemetry/telemetry_service.py`)

```mermaid
stateDiagram-v2
    [*] --> FROZEN: Cold Storage (-40C)
    FROZEN --> THAWING: Post /consumables/thaw
    THAWING --> READY_TO_MOUNT: Defrost Countdown Elapsed
    READY_TO_MOUNT --> MOUNTED_ACTIVE: Post /consumables/{id}/mount
    MOUNTED_ACTIVE --> POT_LIFE_EXPIRED: Active Work Time > Pot Life Hours
    MOUNTED_ACTIVE --> VOLUME_DEPLETED: Shot Count Depletes Barrel
    MOUNTED_ACTIVE --> SCRAPPED: Post /consumables/{id}/scrap
    POT_LIFE_EXPIRED --> SCRAPPED: Scrap Expired Syringe
    VOLUME_DEPLETED --> SCRAPPED: Scrap Empty Syringe
    SCRAPPED --> [*]
```

---

## 26. Frontend Component Documentation

### Component Status Directory

| Component | File Path | API Connected | Mock / Static Data | Status | Description |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `ProblemForm` | `components/diagnosis/ProblemForm.tsx` | Indirect | None | ✅ Fully implemented | Symptom input, line selection, defect cards. |
| `ImageUpload` | `components/diagnosis/ImageUpload.tsx` | Yes (`/images/analyze`) | None | ✅ Fully implemented | Drag-drop, ROI drawing, calibration limits. |
| `DiagnosticStepper` | `components/diagnosis/DiagnosticStepper.tsx` | Indirect | None | ✅ Fully implemented | Visual step progress across workflow. |
| `CauseRanking` | `components/diagnosis/CauseRanking.tsx` | Indirect | None | ✅ Fully implemented | Evidence support bars, revision deltas. |
| `EvidencePanel` | `components/diagnosis/EvidencePanel.tsx` | Indirect | None | ✅ Fully implemented | Itemized supporting & contradicting list. |
| `SimilarCases` | `components/cases/SimilarCases.tsx` | Yes (`/cases/{id}/similar`) | None | ✅ Fully implemented | Historical case matching cards. |
| `TroubleshootingChecklist`| `components/diagnosis/TroubleshootingChecklist.tsx` | Yes (`/cases/{id}/check-results`)| None | ✅ Fully implemented | Action checklist with outcome selection. |
| `EngineerVerification` | `components/diagnosis/EngineerVerification.tsx` | Yes (`/cases/{id}/confirmations`)| None | ✅ Fully implemented | Root cause confirmation & verification. |
| `CaseDetails` | `components/cases/CaseDetails.tsx` | Indirect | None | ✅ Fully implemented | Chronological case audit timeline. |
| `EightDReportView` | `components/reports/EightDReportView.tsx` | Yes (`/cases/{id}/8d`) | None | ✅ Fully implemented | Full 8D compliance dossier display. |
| `LineStatusRibbon` | `components/dashboard/LineStatusRibbon.tsx` | ❌ No | Static `PRODUCTION_LINES` array | 🟣 Mocked | Hardcoded lines A-D on dashboard. |
| `LiveTelemetryRibbon` | `components/telemetry/LiveTelemetryRibbon.tsx` | Yes (`/telemetry/overview`) | None | ✅ Fully implemented | Live cleanroom environment ticker. |
| `SensorGauges` | `components/telemetry/SensorGauges.tsx` | Yes (`/telemetry/lines/{id}`)| None | ✅ Fully implemented | Real-time SVG dials for line sensors. |
| `SpcControlChart` | `components/spc/SpcControlChart.tsx` | Yes (`/analytics/spc`)| None | ✅ Fully implemented | Recharts $I\text{-}MR$ chart with UCL/LCL. |

---

## 27. Backend Module Documentation

### Module Directory & Responsibilities
- **`app.api.cases`** (`backend/app/api/cases.py`): 2,900 lines. Primary lifecycle router governing case creation, question answering, check submissions, root cause confirmation, recovery actions, verification test shots, reports, and AI summaries.
- **`app.api.images`** (`backend/app/api/images.py`): Offloads image decoding and OpenCV processing to worker threads; validates file sizes and enforces image dimension safety.
- **`app.api.analytics`** (`backend/app/api/analytics.py`): Real-time SSE broadcasting, dashboard metrics aggregation, duration histograms, and period filtering.
- **`app.api.admin`** (`backend/app/api/admin.py`): Employee management, account creation, password resets, role updates.
- **`app.api.telemetry`** (`backend/app/api/telemetry.py`): Ambient cleanroom monitoring, high-frequency line sensor queries, syringe defrost/mount/purge/scrap management.
- **`app.services.diagnosis.engine`** (`backend/app/services/diagnosis/engine.py`): Master diagnostic orchestrator coordinating symptom extraction, defect identification, rule evaluation, cause ranking, and state machine transitions.
- **`app.services.vision`**: Modular computer vision pipeline covering preprocessing, contour segmentation, resolution-independent measurement, and defect classification.
- **`app.services.reporting`**: Standard case PDF generation (`pdf_generator.py`) and AIAG/VDA 8D report generation (`eight_d_pdf_generator.py`) using ReportLab.
- **`app.db.repository`** (`backend/app/db/repository.py`): Atomic SQLAlchemy persistence operations with optimistic locking (`StaleRevisionError`).

---

## 28. Database Schema Documentation

### Complete Table Specifications

#### 1. `cases`
- `case_id` (UUID, PK): Unique case identifier.
- `description` (TEXT, NOT NULL): Initial problem description.
- `material` (TEXT, NULLABLE): Dispensed fluid material name.
- `method` (TEXT, NULLABLE): Dispensing method (e.g. `jetting`, `time_pressure`).
- `machine_context` (JSONB, NULLABLE): Machine parameters and line ID.
- `defect_code` (VARCHAR(64), NULLABLE): Defect taxonomy code.
- `defect_name` (TEXT, NULLABLE): Human-readable defect title.
- `issue_condition` (VARCHAR(64), NOT NULL): Lifecycle state.
- `created_at` (TIMESTAMPTZ, NOT NULL): Creation timestamp.

#### 2. `case_observations`
- `id` (INTEGER, PK, Autoincrement): Synthetic row ID.
- `case_id` (UUID, FK $\to$ `cases.case_id`, ON DELETE CASCADE): Owning case.
- `observation_id` (TEXT, NOT NULL): Domain identifier.
- `observation_type` (VARCHAR(64), NOT NULL): Category enum.
- `value` (TEXT, NOT NULL): Normalized value string.
- `original_text` (TEXT, NULLABLE): Source user phrasing.
- `statement_type` (VARCHAR(64), NOT NULL): `USER_OBSERVATION` or `AI_INFERENCE`.
- `source` (VARCHAR(64), NOT NULL): Provenance (`USER`, `IMAGE`, `SYSTEM`, etc.).
- `confidence` (FLOAT, NULLABLE): Inferred observation confidence.
- `created_at` (TIMESTAMPTZ, NOT NULL): Timestamp.
- `first_seen_revision` (INTEGER, NOT NULL, DEFAULT 1): Check constraint $> 0$.
- `metadata` (JSONB, NOT NULL, DEFAULT '{}'): Measurement metadata.
- *Constraints*: `uq_case_observations_case_id_obs_id` on `(case_id, observation_id)`.

#### 3. `analysis_revisions`
- `id` (INTEGER, PK, Autoincrement).
- `case_id` (UUID, FK $\to$ `cases.case_id`, ON DELETE CASCADE).
- `revision_number` (INTEGER, NOT NULL): Revision sequence number.
- `analyzed_at` (TIMESTAMPTZ, NOT NULL): Generation timestamp.
- `defect_code` (VARCHAR(64), NULLABLE): Defect code at this revision.
- `issue_condition` (VARCHAR(64), NOT NULL): Condition at this revision.
- `result_snapshot` (JSONB, NOT NULL): Complete immutable `DiagnosisResult` JSON.
- *Constraints*: `uq_analysis_revisions_case_id_revision_number`, `ck_analysis_revisions_revision_number_pos`.

#### 4. `case_question_answers`
- `id` (INTEGER, PK).
- `case_id` (UUID, FK $\to$ `cases.case_id`, ON DELETE CASCADE).
- `question_id` (TEXT, NOT NULL): Question identifier.
- `answer_value` (TEXT, NOT NULL): `YES`, `NO`, `UNKNOWN`, etc.
- `answer_text` (TEXT, NULLABLE): Verbatim technician notes.
- `source` (VARCHAR(64), NOT NULL).
- `answered_at` (TIMESTAMPTZ, NOT NULL).
- `resulting_revision_number` (INTEGER, NOT NULL): Check constraint $> 1$.
- *Constraints*: `uq_case_question_answers_case_id_rev`.

#### 5. `case_check_results`
- `id` (INTEGER, PK).
- `case_id` (UUID, FK $\to$ `cases.case_id`, ON DELETE CASCADE).
- `check_id` (TEXT, NOT NULL): Action ID (e.g. `ACT01`).
- `execution_status` (VARCHAR(64), NOT NULL): `COMPLETED`, `BLOCKED`, etc.
- `finding` (VARCHAR(64), NOT NULL): `SUPPORTS`, `CONTRADICTS`, `INCONCLUSIVE`, `UNKNOWN`.
- `finding_details` (TEXT, NULLABLE): Technician notes.
- `outcome` (TEXT, NULLABLE): Outcome key (e.g. `blockage_found`).
- `source` (VARCHAR(64), NOT NULL).
- `checked_at` (TIMESTAMPTZ, NOT NULL).
- `resulting_revision_number` (INTEGER, NOT NULL): Check constraint $> 1$.
- *Constraints*: `uq_case_check_results_case_id_rev`.

#### 6. `case_check_executions`
- Tracks granular execution attempts (`COMPLETED`, `BLOCKED`, `SKIPPED`, `FAILED`).

#### 7. `case_cause_confirmations`
- `id` (INTEGER, PK).
- `case_id` (UUID, FK $\to$ `cases.case_id`, ON DELETE CASCADE).
- `cause_id` (TEXT, NOT NULL): Root cause confirmed.
- `confirmed_by` (VARCHAR(64), NOT NULL, DEFAULT 'technician').
- `notes` (TEXT, NULLABLE): Justification notes.
- `confirmed_at` (TIMESTAMPTZ, NOT NULL).
- `resulting_revision_number` (INTEGER, NOT NULL): Check constraint $> 1$.
- *Constraints*: `uq_case_cause_confirmations_case_id_rev`.

#### 8. `case_lifecycle_events`
- `id` (INTEGER, PK).
- `case_id` (UUID, FK $\to$ `cases.case_id`, ON DELETE CASCADE).
- `event_type` (VARCHAR(64), NOT NULL): `RECOVERY_ACTION` or `RECOVERY_VERIFICATION`.
- `prior_issue_condition` (VARCHAR(64), NOT NULL).
- `resulting_issue_condition` (VARCHAR(64), NOT NULL).
- `resulting_revision_number` (INTEGER, NOT NULL): Check constraint $> 1$.
- `actor` (VARCHAR(64), NOT NULL, DEFAULT 'technician').
- `details` (TEXT, NOT NULL).
- `verification_passed` (BOOLEAN, NULLABLE).
- `created_at` (TIMESTAMPTZ, NOT NULL).
- *Constraints*: `uq_case_lifecycle_events_case_id_rev`.

#### 9. `users`
- `id` (VARCHAR, PK, indexed).
- `email` (VARCHAR, UK, indexed, NOT NULL).
- `hashed_password` (VARCHAR, NOT NULL).
- `first_name` (VARCHAR, NULLABLE).
- `last_name` (VARCHAR, NULLABLE).
- `is_active` (BOOLEAN, DEFAULT TRUE).
- `role` (VARCHAR(64), NOT NULL, DEFAULT 'technician').
- `department` (VARCHAR(128), NULLABLE).
- `created_at` (TIMESTAMPTZ, NOT NULL, DEFAULT `func.now()`).
- `last_login` (TIMESTAMPTZ, NULLABLE).

---

## 29. Environment Configuration

### Required Environment Variables

| Variable | Purpose | Required | Used By | Example / Default |
| :--- | :--- | :---: | :--- | :--- |
| `DATABASE_URL` | Primary PostgreSQL persistence connection string | **Yes** | Backend ORM, Alembic migrations | `postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens` |
| `TEST_DATABASE_URL` | Disposable database connection for test suites | **Yes** (tests) | `pytest` test runners | `postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens_test` |
| `CORS_ORIGINS` | Comma-separated allowed HTTP origins | No | FastAPI CORS middleware | `http://localhost:3000,http://localhost:3001,http://127.0.0.1:3001` |
| `OPENAI_API_KEY` | OpenAI API key for bounded symptom extraction/summary | No | `LLMService` (falls back to offline templates) | `<redacted>` |
| `OPENAI_MODEL` | OpenAI model identifier | No | `LLMService` | `gpt-4o-mini` |
| `LLM_TIMEOUT_SECONDS`| Maximum seconds to wait for LLM before fallback | No | `LLMService` | `10.0` |
| `NEXT_PUBLIC_API_URL`| Base URL for frontend API client | No | Frontend `apiClient` | `http://localhost:8000/api/v1` |

---

## 30. Development Setup

### Step-by-Step Operator Guide

#### 1. Prerequisites
- **OS**: Windows 10/11 with PowerShell 5.1+ or 7+.
- **Docker Desktop**: Running with Linux container engine.
- **Python**: Version 3.11+ (Python 3.11, 3.12, 3.13, 3.14 supported).
- **Node.js**: Version **$\ge$ 20.9.0** (strictly enforced by Next.js 16) and `npm`.

#### 2. Environment Preparation
```powershell
# In repository root:
Copy-Item .env.example .env
```

#### 3. Backend Setup
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
cd ..
```

#### 4. Frontend Setup
```powershell
cd frontend
npm install
cd ..
```

#### 5. Verification & Service Startup
```powershell
# Step A: Run read-only preflight check
powershell -ExecutionPolicy Bypass -File .\scripts\demo-preflight.ps1

# Step B: Start Docker PostgreSQL database container
powershell -ExecutionPolicy Bypass -File .\scripts\start-db.ps1

# Step C: Apply Alembic migrations
cd backend
$env:DATABASE_URL = "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens"
.\.venv\Scripts\python.exe -m alembic upgrade heads
cd ..

# Step D: Start Backend API (Terminal 1)
cd backend
$env:DATABASE_URL = "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Step E: Start Frontend Application on Port 3001 (Terminal 2)
cd frontend
npm run dev -- -p 3001

# Step F: Verify Local Demo Health (Terminal 3)
powershell -ExecutionPolicy Bypass -File .\scripts\verify-demo.ps1
```
*Access the Web Application at `http://localhost:3001` (avoid port 3000).*

---

## 31. Testing Strategy

### Test Directory & Coverage

| Test Area | Existing Test Files | Scope & Evidence | Missing Tests / Recommended |
| :--- | :--- | :--- | :--- |
| **Backend Unit** | 29 files in `backend/tests/unit/` | Tests symptom extraction, cause ranking, evidence evaluation, action planning, question selection, OpenCV features, ReportLab PDF layout, and 8D structure. | Mock tests for physical serial hardware communication. |
| **Backend Integration** | 20 files in `backend/tests/integration/` | Full API testing: case creation, answer submissions, check results, optimistic concurrency, PDF endpoints, image uploads, and analytics. Total: 491 passing tests. | Multi-instance load tests and latency stress benchmarks. |
| **Frontend State** | 4 files in `frontend/scripts/` | Standalone Node.js regression suites verifying case detail timeline derivation, diagnostic workflow mutations, image upload controllers, and report format state. | End-to-end browser tests (Playwright or Cypress). |

---

## 32. Security Analysis

### Security Posture Findings
1. **Password Storage**: Passwords are securely hashed with `bcrypt` using cryptographic salts.
2. **SQL Injection Mitigation**: All database operations use SQLAlchemy 2.0 ORM expressions and parameterized statements. No raw string formatting or SQL concatenation exists.
3. **Upload File Safety**: Image upload endpoint (`/api/v1/images/analyze`) enforces magic byte checking (`\x89PNG` and `\xff\xd8\xff`), bounds decoded image dimensions ($\le 4096\text{ px}$ per side, $\le 16\text{M total pixels}$), and streams file bytes in 64 KB chunks to reject uploads exceeding 10 MB with HTTP 413.
4. **Information Disclosure Prevention**: Method `PromptManager.project_safe_observations()` filters out file system paths and sensitive image metadata before formatting LLM prompts.
5. **Vulnerability / Architectural Risk**: Operational API routes (`/api/v1/cases/*`, `/api/v1/telemetry/*`) are currently open without JWT authentication. While acceptable for a closed-network cleanroom demo, production deployment requires attaching `Depends(get_current_user)` to all mutating routes.

---

## 33. Performance Analysis

### Observed Latencies and Bottlenecks
- **Diagnostic Evaluation**: The deterministic diagnostic engine evaluates all 76 rules across candidate causes in **$3\text{ to }12\text{ ms}$**, eliminating algorithmic latency.
- **Computer Vision**: OpenCV morphological operations and contour extraction on typical $1\text{ to }3\text{ MB}$ cleanroom macro photographs execute in **$45\text{ to }140\text{ ms}$**. Because processing is offloaded to worker threads via `anyio.to_thread.run_sync`, the FastAPI event loop is not blocked.
- **ReportLab PDF Generation**: Generating a multi-page PDF with running headers and dynamic page calculation takes **$120\text{ to }350\text{ ms}$**.
- **Database Indexing**: Foreign keys (`case_id` on all event tables) and unique revision constraints are fully indexed. No $N+1$ query bottlenecks exist because `CaseRepository` utilizes SQLAlchemy's `selectinload` for child collections.

---

## 34. Error Handling

### Error Handling Architecture
- **Backend API**: Emits standard FastAPI `HTTPException` with structured JSON details. Standard exceptions:
  - `400 Bad Request`: Illegal issue condition state transition or invalid payload.
  - `404 Not Found`: Case ID or user ID not found in database.
  - `409 Conflict`: `StaleRevisionError` when a client submits an action based on an outdated revision number.
  - `413 Payload Too Large`: Uploaded inspection image exceeds 10 MB.
  - `422 Unprocessable Entity`: Schema validation error or uncalibrated image parameters.
  - `500 Internal Server Error`: Unhandled exceptions logged via Python `logging.exception`.
- **Frontend**: Managed via custom `ApiError` class in `frontend/lib/api/client.ts`, parsing structured FastAPI detail strings or arrays. Frontend components display user-friendly contextual alert banners (`AlertCircle`, `AlertTriangle`) with "Try Again" retry handlers.

---

## 35. Logging & Observability

### Implemented Baseline
- **Application Logging**: Python's standard `logging` module configured across services. Exceptions in image analysis, PDF generation, and LLM calls log full stack traces (`logger.exception()`).
- **Health Check Endpoint**: Exposed at `GET /api/v1/health`, returning JSON with API version, status, and live database connectivity status:
  ```json
  {
    "status": "ok",
    "version": "0.1.0",
    "database": "connected"
  }
  ```
- **Real-Time Telemetry Logging**: SSE events stream continuous connectivity status (`CONNECTED`, `PING`, `CASE_UPDATED`).

---

## 36. Deployment Architecture

### Current Local Deployment Model
- **Containerized Database**: PostgreSQL 16 Alpine running in Docker with persistent named volume `postgres_data`.
- **Host Processes**: Backend running via Uvicorn on port 8000; Frontend running via Next.js Node dev server on port 3001.

### Recommended Production Architecture

```mermaid
flowchart TD
    subgraph Edge["Factory Cleanroom Floor"]
        Terminals["Cleanroom Operator Tablets & Line Terminals"]
    end

    subgraph Ingress["Reverse Proxy & Gateway"]
        Nginx["Nginx / Traefik (TLS Termination & Rate Limiting)"]
    end

    subgraph AppCluster["Production Application Cluster (Docker / K8s)"]
        FE1["Next.js Container 1"]
        FE2["Next.js Container 2"]
        BE1["FastAPI Worker 1"]
        BE2["FastAPI Worker 2"]
        CeleryWorkers["Celery Workers (Async Heavy CV & Batch PDF)"]
        RedisNode[("Redis 7 (SSE Backplane & Task Broker)")]
    end

    subgraph DataTier["Managed Industrial Storage"]
        PGPrimary[("PostgreSQL 16 (Primary)")]
        PGReplica[("PostgreSQL 16 (Read Replica)")]
        S3Storage[("MinIO / AWS S3 (Permanent Inspection Image Storage)")]
    end

    Terminals -->|HTTPS:443| Nginx
    Nginx --> FE1 & FE2
    Nginx --> BE1 & BE2
    BE1 & BE2 --> RedisNode
    BE1 & BE2 --> PGPrimary
    BE1 & BE2 --> CeleryWorkers
    CeleryWorkers --> S3Storage
    PGPrimary --> PGReplica
```

---

## 37. CI/CD

### Current Repository Automation
- Continuous integration is driven locally by automated test runner scripts:
  - PowerShell Preflight: `scripts/demo-preflight.ps1`.
  - Identity Verification: `scripts/verify-demo.ps1`.
  - Backend Suite: `python -m pytest -q` (491 passing tests).
  - Frontend Verification: `npm run lint`, `npm run build`, and `node frontend/scripts/test-*.mjs`.

### Recommended GitHub Actions Workflow
```yaml
name: CI/CD Pipeline
on: [push, pull_request]
jobs:
  backend-test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: dispenselens_test
          POSTGRES_USER: dispenselens_user
          POSTGRES_PASSWORD: dispenselens_dev_password
        ports: [5432:5432]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e "backend[dev]"
      - run: pytest backend/tests/ -q
        env:
          DATABASE_URL: postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens_test

  frontend-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20.9.0" }
      - run: cd frontend && npm ci
      - run: cd frontend && npm run lint
      - run: cd frontend && npm run build
      - run: node frontend/scripts/test-case-detail-state.mjs
```

---

## 38. Mock Data & Placeholder Analysis

### Comprehensive Mock Data Register

| Location | Mock / Placeholder | Used By | Should Be Replaced With | Priority |
| :--- | :--- | :--- | :--- | :---: |
| `frontend/components/dashboard/LineStatusRibbon.tsx:15` | Hardcoded `PRODUCTION_LINES` array (Asymtek 1, Camalot 2, etc.) | Dashboard overview | Fetch from `GET /api/v1/telemetry/overview` | Medium |
| `frontend/app/(dashboard)/knowledge-base/page.tsx:18` | Hardcoded arrays for `defects`, `causes`, `actions`, `evidenceRules` | Knowledge Base screen | Fetch from `GET /api/v1/defects`, `/causes`, `/actions` | Medium |
| `backend/app/services/telemetry/telemetry_service.py:100` | Pseudo-random Gaussian noise for ambient cleanroom temperature | Cleanroom Telemetry | Real-world MQTT / OPC-UA IoT industrial gateway | Low |
| `frontend/scripts/test-*.mjs` | Synthetic case fixtures | Node test runner | Retain as regression fixtures | N/A (Test) |

---

## 39. Incomplete Features

### Technical Backlog
1. **Unauthenticated Operational Routes**: Endpoints under `/cases`, `/diagnoses`, `/images`, and `/telemetry` do not enforce `get_current_user`, meaning any client on the network can create cases.
2. **Disconnected Knowledge Base Endpoints**: Backend API routes `/defects`, `/causes`, `/actions`, and `/questions` are fully implemented and tested, but the frontend Knowledge Base page renders static in-page constants.
3. **Viewer Role Enforcement**: The `viewer` role exists in the database and UI, but write endpoints do not yet check user permissions to block viewers from creating cases.
4. **Persistent Image Archival**: Uploaded images are processed in memory and discarded; production deployment requires streaming raw images to an S3/MinIO bucket.

---

## 40. Feature Connectivity Matrix

| Feature | Frontend Component | API Client Method | Backend Route | Domain Service | Database Model | AI/CV Layer | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **Authentication** | `login/page.tsx` | `authApi.login` | `POST /auth/login` | `security.py` | `UserModel` | None | ✅ Fully Connected |
| **Case Intake** | `ProblemForm.tsx` | `casesApi.createCase` | `POST /cases` | `DiagnosticEngine` | `CaseModel` | SymptomExtractor | ✅ Fully Connected |
| **Image Analysis** | `ImageUpload.tsx` | `imagesApi.analyze` | `POST /images/analyze`| `vision/*` | In-memory | OpenCV Pipeline | ✅ Fully Connected |
| **Question Answer**| `DiagnosticQuestion.tsx`| `casesApi.submitAnswer`| `POST /cases/{id}/answers`| `DiagnosticEngine`| `QuestionAnswerModel`| Deterministic Engine | ✅ Fully Connected |
| **Check Execution**| `TroubleshootingChecklist`| `casesApi.submitCheckResult`| `POST /cases/{id}/check-results`| `DiagnosticEngine`| `CaseCheckResultModel`| Deterministic Engine | ✅ Fully Connected |
| **Root Cause Confirm**| `EngineerVerification.tsx`| `casesApi.submitCauseConfirmation`| `POST /cases/{id}/confirmations`| `DiagnosticEngine`| `CaseCauseConfirmationModel`| None | ✅ Fully Connected |
| **Resolution Verify**| `EngineerVerification.tsx`| `casesApi.verifyCase` | `POST /cases/{id}/recovery-verifications`| `DiagnosticEngine`| `CaseLifecycleEventModel`| None | ✅ Fully Connected |
| **Standard PDF Report**| `ReportPreview.tsx` | `reportsApi.downloadPdf`| `GET /cases/{id}/report.pdf`| `pdf_generator.py`| Read Model | ReportLab 5.0 | ✅ Fully Connected |
| **8D Quality Report**| `EightDReportView.tsx`| `reportsApi.download8DPdf`| `GET /cases/{id}/8d.pdf`| `eight_d_pdf_generator.py`| Read Model | ReportLab 5.0 | ✅ Fully Connected |
| **Case Similarity** | `SimilarCases.tsx` | `casesApi.getSimilarCases`| `GET /cases/{id}/similar`| `CaseRetriever` | `CaseModel` | Similarity Engine | ✅ Fully Connected |
| **SPC Analytics** | `SpcControlChart.tsx`| `spcApi.getAnalysis` | `GET /analytics/spc` | `spc_service.py` | Simulated / Cases | Statistical Math | ✅ Fully Connected |
| **Cleanroom Telemetry**| `LiveTelemetryRibbon.tsx`| `telemetryApi.getOverview`| `GET /telemetry/overview`| `telemetry_service.py`| In-memory State | Simulation Math | ✅ Fully Connected |
| **Knowledge Base** | `knowledge-base/page.tsx`| None (Static constants) | `GET /defects, /causes` | `knowledge/__init__.py`| None (JSON files) | None | ⚠️ Disconnected |

---

## 41. Technical Debt

| ID | Issue Description | Location | Impact | Risk | Recommended Action |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **TD-001** | Open operational endpoints lack JWT authentication | `backend/app/api/cases.py` | Any network client can mutate cases | High | Add `Depends(get_current_user)` to all `/cases/*` routes. |
| **TD-002** | Knowledge Base UI uses hardcoded static arrays | `frontend/app/(dashboard)/knowledge-base/page.tsx` | UI diverges from backend knowledge JSONs | Medium | Connect page to `GET /api/v1/defects`, `/causes`, etc. |
| **TD-003** | In-memory SSE queues do not scale across multi-worker servers | `backend/app/api/analytics.py` | Events lost if multiple Uvicorn workers run | Medium | Introduce Redis Pub/Sub backplane for SSE broadcasting. |
| **TD-004** | Monolithic `cases.py` API file exceeds 2,900 lines | `backend/app/api/cases.py` | High cognitive overhead for maintainers | Low | Split into sub-routers (`case_lifecycle.py`, `case_reports.py`). |
| **TD-005** | Dashboard Line Status Ribbon uses hardcoded mock line status | `frontend/components/dashboard/LineStatusRibbon.tsx` | UI shows static yield rate rather than live telemetry | Low | Wire component to `telemetryApi.getOverview()`. |

---

## 42. Bugs & Risks

### Static Analysis & Risk Audit
1. **CONFIRMED FINDING — Knowledge Base Disconnection**:
   - *Problem*: `frontend/app/(dashboard)/knowledge-base/page.tsx` defines static in-line arrays (`const defects = [...]`, `const causes = [...]`).
   - *Consequence*: Any update made by process engineers to `backend/app/knowledge/rules.json` or `defects.json` will not appear in the Knowledge Base UI.
   - *Fix*: Replace static arrays with `useEffect` fetch calls to `/api/v1/defects`, `/api/v1/causes`, `/api/v1/actions`.
2. **POTENTIAL RISK — SSE Connection Leaks**:
   - *Problem*: If clients disconnect uncleanly without triggering `request.is_disconnected()`, queues in `_sse_subscribers` could accumulate over prolonged runtimes.
   - *Mitigation*: Implemented 15s keepalive ping clears dead queues upon write error, but active connection tracking should be bounded.
3. **CONFIRMED BEHAVIOR — BLOCKED Check Safety Enforcement**:
   - *Verification*: `CheckResultHandler.handle()` enforces that non-completed checks (`BLOCKED`, `FAILED`, `UNKNOWN`) force `finding = CheckFinding.UNKNOWN` and emit zero observations, ensuring blocked actions never corrupt cause scores.

---

## 43. Requirements Traceability

| Requirement | Frontend Component | Backend API Route | DB Entity | Test Suite | Status |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **Defect Diagnosis** | `ProblemForm.tsx` | `POST /api/v1/cases` | `cases`, `analysis_revisions` | `test_diagnosis_engine.py` | ✅ Verified |
| **Image Feature Extraction**| `ImageUpload.tsx` | `POST /api/v1/images/analyze`| In-memory | `test_vision_measurement.py`| ✅ Verified |
| **Check Results & Revision**| `TroubleshootingChecklist`| `POST /api/v1/cases/{id}/check-results`| `case_check_results` | `test_check_result_api.py` | ✅ Verified |
| **Root Cause Confirmation** | `EngineerVerification.tsx`| `POST /api/v1/cases/{id}/confirmations`| `case_cause_confirmations` | `test_cause_confirmation_api.py`| ✅ Verified |
| **Recovery Verification** | `EngineerVerification.tsx`| `POST /api/v1/cases/{id}/recovery-verifications`| `case_lifecycle_events` | `test_recovery_verification_api.py`| ✅ Verified |
| **8D Dossier Generation** | `EightDReportView.tsx` | `GET /api/v1/cases/{id}/8d.pdf` | Read Model | `test_eight_d_report.py` | ✅ Verified |
| **Historical Similarity** | `SimilarCases.tsx` | `GET /api/v1/cases/{id}/similar` | `cases` | `test_case_retrieval.py` | ✅ Verified |

---

## 44. Recommended Engineering Roadmap

```mermaid
gantt
    title DispenseIQ Engineering Roadmap
    dateFormat  YYYY-MM-DD
    section Phase 1: Security & Correctness
    Wire Auth to All Operational Endpoints        :p1_1, 2026-10-01, 7d
    Connect Knowledge Base UI to Backend APIs     :p1_2, after p1_1, 5d
    Wire Dashboard Line Ribbon to Telemetry API   :p1_3, after p1_2, 3d

    section Phase 2: Production Hardening
    Split cases.py into Modular Sub-routers       :p2_1, 2026-10-16, 6d
    Introduce Redis Pub/Sub for SSE Scaling       :p2_2, after p2_1, 7d
    Playwright End-to-End Test Automation Suite   :p2_3, after p2_2, 8d

    section Phase 3: Advanced Intelligence
    Persistent MinIO / S3 Image Storage           :p3_1, 2026-11-05, 10d
    YOLOv8 Edge Model for Satellite Droplets      :p3_2, after p3_1, 14d
    OPC-UA / MQTT IoT Hardware Connector          :p3_3, after p3_2, 14d
```

### Phase Details
- **Phase 1 (Correctness & Security)**: Enforce JWT authentication on all mutating endpoints; eliminate remaining static mock data on Knowledge Base and Dashboard Line Status ribbon.
- **Phase 2 (Architecture Hardening)**: Decompose the 2,900-line `cases.py` router; add Redis Pub/Sub backplane for multi-worker SSE scaling; implement Playwright E2E browser automation.
- **Phase 3 (Industrial Edge Integration)**: Connect physical cleanroom cameras and PLCs via OPC-UA / MQTT protocols; archive raw inspection images to S3/MinIO.

---

## 45. Final System Maturity Summary

### Implementation Summary
- **✅ Implemented & Production-Ready**:
  - Deterministic diagnostic reasoning with 76 engineering rules.
  - Relational case persistence with append-only revisions and optimistic revision safety.
  - ReportLab standard and 8D PDF compliance generation.
  - OpenCV image segmentation, feature extraction, and process limit classification.
  - Real-time SSE analytics and statistical process control ($I\text{-}MR$ charts, $C_{pk}$).
  - Cleanroom ambient telemetry and syringe pot life state machine.
- **🟡 Partially Implemented**:
  - Role-based authorization: User roles exist in DB and admin UI, but operational routes treat all authenticated users identically.
  - Performance period trend analysis: Trends require historical baseline data; returns null if prior period has no cases.
- **🟣 Mocked / Simulated**:
  - `LineStatusRibbon.tsx` on the dashboard uses a static array rather than the live telemetry endpoint.
  - Physical cleanroom environmental sensors simulate realistic Gaussian fluctuations in software rather than connecting to live OPC-UA hardware.
- **⚠️ Disconnected**:
  - `/api/v1/defects`, `/causes`, `/actions` REST endpoints exist in backend, but `knowledge-base/page.tsx` renders static in-line arrays.
- **🔴 Missing / Explicitly Deferred**:
  - `pgvector` semantic vector similarity (deferred in favor of multi-attribute relational scoring).
  - Deep learning object detection models (YOLO).
  - Score-bearing vision semantics for Defect D06 (bubbles / abnormal shapes) — **Resolved & Implemented**: Delivered via classical OpenCV aspect ratio, circularity, solidity/convexity checks and interior Hough Circle / Blob detection.

---

## 46. Appendix

### A. Repository Directory Structure Reference
```text
dispense_lense_koi/
├── .agents/                    # Multi-agent handoff records, task packets, reviews
├── backend/
│   ├── alembic/                # Database migrations (10 versions)
│   ├── app/
│   │   ├── api/                # FastAPI route controllers (cases, images, analytics, etc.)
│   │   ├── core/               # Configuration (config.py) and security (security.py)
│   │   ├── db/                 # Database engine, session, and CaseRepository
│   │   ├── knowledge/          # Codified JSON engineering knowledge (rules, defects, etc.)
│   │   ├── models/             # SQLAlchemy ORM models (case.py, user.py)
│   │   ├── schemas/            # Pydantic v2 validation contracts
│   │   ├── services/
│   │   │   ├── ai/             # Bounded LLM service & PromptManager
│   │   │   ├── diagnosis/      # DiagnosticEngine, CauseRanker, EvidenceEngine
│   │   │   ├── reporting/      # ReportLab PDF & 8D Quality generators
│   │   │   ├── retrieval/      # Multi-attribute similarity engine
│   │   │   ├── spc/            # Statistical Process Control engine
│   │   │   ├── telemetry/      # Cleanroom sensor & syringe pot life tracker
│   │   │   └── vision/         # OpenCV segmentation, measurement, & classification
│   │   └── utils/              # ScoringConfig & mathematical helpers
│   └── tests/                  # 491 passing unit & integration tests
├── frontend/
│   ├── app/                    # Next.js 16 App Router pages & layouts
│   ├── components/             # Reusable UI components (diagnosis, cases, reports, spc)
│   ├── lib/                    # API clients and deterministic state controllers
│   ├── scripts/                # Node.js regression test runners
│   └── types/                  # TypeScript contract definitions
├── docs/                       # Architectural specifications, contracts, and demo runbook
├── scripts/                    # PowerShell automation (preflight, start-db, verify-demo)
├── compose.yaml                # Docker Compose specification (PostgreSQL 16)
└── README.md                   # Complete local startup and onboarding guide
```

### B. Verification Evidence Log
- **Backend Tests**: 491 passed in `backend/tests/` (`test_phases_1_5.py`, `test_phases_6_8.py`, `test_phases_9_11.py`, `unit/*`, `integration/*`).
- **Frontend Regression**: Passed in `frontend/scripts/` (`test-case-detail-state.mjs`, `test-diagnostic-workflow-state.mjs`, `test-image-upload-state.mjs`, `test-reports-state.mjs`).
- **Preflight & Verification**: Passed via `scripts/demo-preflight.ps1` and `scripts/verify-demo.ps1`.
