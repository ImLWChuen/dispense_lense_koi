# DispenseIQ: What We Built vs. What We Used

This document outlines the architectural boundary between **custom algorithmic engineering built by our team** and **foundational third-party open-source libraries used** in DispenseIQ (DispenseLens).

---

## 1. Summary Matrix

| Subsystem | What We Built (Custom Proprietary Logic) | What We Used (External Libraries & Frameworks) |
| :--- | :--- | :--- |
| **Diagnostic Question Discrimination** | **Custom Information-Gain `QuestionEngine`** with real-time hypothesis partitioning, top-2 cause tie-breaker bonuses, already-answered penalties, and dynamic stopping conditions. Fully addresses **NSW Step 1 Bonus**. | Python standard library (`typing`, `enum`, `dataclasses`). |
| **Evidence Evaluation & Scoring** | **Codified Expert Rule System (`EvidenceEngine`)** with 76 domain rules, semantic observation deduplication, and an inspectable 0–100 **Evidence Support** score calculator (`CauseRanker`). | Python standard library (`math`, `re`). |
| **Diagnostic State Management** | **4-Dimensional State Machine (`StateManager`)** enforcing strict independence between step execution, step findings, root cause conclusions, and issue resolution (DLK-M3-013 semantic standard). | Python standard library. |
| **Cleanroom Telemetry & Pot Life** | **Syringe Pot Life & Consumables State Machine** (`TelemetryService`) managing thaw countdowns, active work windows, volumetric depletion, purge tracking, and scrap lifecycles. | Python standard library, asyncio. |
| **Computer Vision Inspection** | **Calibrated Optical Feature Extraction Pipeline** (`cv2`-based edge detection, contour geometry, aspect ratio, circularity, area coverage ratio, and internal bubble detection). | OpenCV (`opencv-python-headless`), NumPy. |
| **Backend Service & Persistence** | **Durable Case & Revision Data Model** (`AnalysisRevision`, `ObservationModel`, `CheckResultModel`, `QuestionAnswerModel`) with atomic transactional state transitions. | FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, PostgreSQL 16. |
| **Operator Cleanroom Frontend** | **Custom Industrial UI Component Library** (Defect Cards, Active Question & Check Workflow Stepper, Live Telemetry Ribbon, 8D Timeline, Pot Life Modal). | Next.js 15 (App Router), React 19, Tailwind CSS, Lucide React icons. |
| **Quality Reporting & 8D Export** | **Deterministic 8D Root Cause Problem Solving Report Generator** and audit-ready PDF export service. | ReportLab (PDF rendering engine). |
| **AI Explanations & Summaries** | **Prompt Projection & Guardrail Engine** (`PromptManager`) bounding AI to non-authoritative explanations with deterministic offline fallbacks. | OpenAI API client (`openai`). |

---

## 2. Deep Dive: What We Built

### A. Dynamic Question Discrimination Engine (`QuestionEngine`)
- **File:** `backend/app/services/diagnosis/question_engine.py`
- **What It Does:** Rather than displaying a static, linear questionnaire, DispenseIQ's `QuestionEngine` calculates the real-time **Information Gain** across competing candidate causes:
  $$U(Q) = \text{CauseCoverage}(Q, \mathcal{C}_{top}) \times W_{cov} + \text{UncertaintyReduction}(Q, \mathcal{C}) \times W_{unc} - \text{Penalty}_{answered}(Q)$$
- **NSW Step 1 Bonus Showcase:** When an operator indicates *"inconsistent volume"*, the engine detects multiple competing hypotheses (`pressure_instability`, `air_supply_issue`, `nozzle_restriction`, `material_condition`, `temperature_issue`). Instead of asking a generic checklist, it immediately isolates **shift duration vs. ambient temperature vs. syringe pot life / thaw time**, dynamically pivoting all subsequent inquiries based on operator feedback.
- **Dynamic Stopping Conditions:** Halts inquiry when confidence reaches $\ge 75/100$, when residual information gain falls below $1.0$, or when all questions are answered.

### B. Codified Expert Rules & Cause Ranker
- **Files:** `backend/app/services/diagnosis/evidence_engine.py`, `backend/app/services/diagnosis/cause_ranker.py`, `backend/app/knowledge/`
- **What It Does:** Contains 76 codified expert rules mapping physical observations to positive, neutral, or negative evidential relations across 10 canonical root causes. Computes inspectable, deterministic `Evidence Support` scores (0–100 scale) with zero black-box statistical hallucinations.

### C. 4-Dimension Independent State Manager
- **File:** `backend/app/services/diagnosis/engine.py:StateManager`
- **What It Does:** Enforces the critical cleanroom engineering rule:
  $$\text{Check Completed} \neq \text{Check Supports Cause} \neq \text{Cause Confirmed} \neq \text{Issue Resolved}$$
  Maintains independent state tracking across:
  1. *Step Execution:* `PENDING`, `IN_PROGRESS`, `COMPLETED`, `BLOCKED`, `SKIPPED`, `FAILED`.
  2. *Step Finding:* `SUPPORTS`, `CONTRADICTS`, `INCONCLUSIVE`, `UNKNOWN`.
  3. *Cause Conclusion:* `SUSPECTED`, `CONFIRMED`, `UNRESOLVED`.
  4. *Issue Condition:* `UNRESOLVED`, `RECOVERY_PENDING_VERIFICATION`, `RESOLVED`, `RECURRED`.

### D. Cleanroom Telemetry & Syringe Pot Life State Machine
- **File:** `backend/app/services/telemetry/telemetry_service.py`
- **What It Does:** A live simulation service managing consumable epoxy lifecycles:
  - Tracks adhesive thawing from $-40^\circ\text{C}$ to room temperature (e.g. 45-min thaw for Norland NOA-68).
  - Enforces pot life expiration countdowns (4h for EPO-TEK 353ND, 8h for NOA-68, 12h for Loctite 382).
  - Emits real-time state machine events (`FROZEN_STORAGE` $\to$ `THAWING` $\to$ `READY_TO_MOUNT` $\to$ `MOUNTED_ACTIVE` $\to$ `POT_LIFE_EXPIRED`).

### E. Calibrated Optical Inspection Computer Vision
- **File:** `backend/app/services/vision/feature_extractor.py`
- **What It Does:** Computer vision analysis tailored for micro-dispensing:
  - Calibrated contour segmentation using `PROCESS_LIMITS` and `REFERENCE_IMAGE`.
  - Calculates aspect ratio, circularity, area ratio, and centroid eccentricity.
  - Detects internal voids and microbubbles within the fluid deposit.

---

## 3. What We Used (Third-Party Technologies)

We intentionally leveraged industry-standard open-source frameworks for commodity infrastructure:
- **FastAPI:** High-performance asynchronous REST API routing and OpenAPI specification generation.
- **Pydantic v2:** Rigorous contract validation and serialization between client and server.
- **PostgreSQL 16 & SQLAlchemy / Alembic:** Relational transactional persistence, audit-proof case revision history, and schema migrations.
- **Next.js 15 & React 19:** Server-side rendering, client component interactivity, and Turbopack hot module reloading.
- **Tailwind CSS:** Responsive utility styling compliant with cleanroom display guidelines.
- **OpenCV & NumPy:** Low-level image matrix operations, Gaussian blurring, and morphological contour detection.
- **ReportLab:** Vector PDF page assembly and table layout.
- **OpenAI API:** Restricted exclusively to producing natural language prose summaries from pre-computed deterministic facts (`source="llm"`, with automatic deterministic fallback if offline or unkeyed).
