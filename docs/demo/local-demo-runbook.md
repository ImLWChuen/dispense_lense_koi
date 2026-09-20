# DispenseIQ Competition Demo and Operator Runbook

This runbook guides operators and narrators through a structured, repeatable 6–10 minute competition demonstration of **DispenseIQ (DispenseLens)**. It provides pre-demo readiness verification, an exact timed script, failure fallbacks, truthful boundary statements, and rehearsal tracking records.

---

## 1. Pre-Demo Verification Checklist

Run these steps in Windows PowerShell 15 minutes before the demonstration:

- [ ] **Docker Engine Status:** Ensure Docker Desktop is running and its Linux container icon is green.
- [ ] **Run Preflight:**
  ```powershell
  powershell -ExecutionPolicy Bypass -File .\scripts\demo-preflight.ps1
  ```
  *Ensure all checks PASS and no conflicting services occupy ports 8000 or 3001.*
- [ ] **Start Persistent Database:**
  ```powershell
  powershell -ExecutionPolicy Bypass -File .\scripts\start-db.ps1
  ```
  *Ensure `dispenselens-postgres` reports `healthy`.*
- [ ] **Confirm Database Target:** Verify migrations apply to the development database (`dispenselens`), **never** the automated test database (`dispenselens_test`):
  ```powershell
  cd backend
  $env:DATABASE_URL = "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens"
  .\.venv\Scripts\python.exe -m alembic upgrade heads
  cd ..
  ```
- [ ] **Start Backend API:**
  ```powershell
  cd backend
  $env:DATABASE_URL = "postgresql+psycopg://dispenselens_user:dispenselens_dev_password@localhost:5432/dispenselens"
  .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
  ```
- [ ] **Start Frontend Server:** (in a separate terminal)
  ```powershell
  cd frontend
  npm run dev -- -p 3001
  ```
- [ ] **Run Identity Verification:**
  ```powershell
  powershell -ExecutionPolicy Bypass -File .\scripts\verify-demo.ps1
  ```
  *Ensure both backend API and frontend on port 3001 are positively identified as DispenseIQ.*
- [ ] **Open Browser:** Navigate to `http://localhost:3001`. Do **not** use port 3000.

---

## 2. Timed Demonstration Walkthrough (6–10 Minutes)

### Phase 1: Problem Framing & Solution Overview (0:00 – 1:30)
- **Narrative:**
  - "In high-precision industrial electronics manufacturing, fluid dispensing defects—such as inconsistent volume, nozzle clogging, or deposit tailing—lead to costly scrap and line stoppages."
  - "Junior technicians frequently lack the years of experience needed to isolate root causes when multiple variables (fluid viscosity, air pressure, nozzle wear, temperature) interact."
  - "DispenseIQ provides structured decision support by fusing three evidence sources: visual inspection, process context, and guided physical troubleshooting."
- **Action on Screen:** Display the DispenseIQ Dashboard (`/dashboard`). Point out recent defect trends, active cases, and root cause distributions.

---

### Phase 2: Process Context & Initial Case Creation (1:30 – 3:30)
- **Narrative:**
  - "Let's create a new diagnostic case for a manufacturing line experiencing undersized adhesive deposits."
- **Action on Screen:**
  1. Click **New Diagnosis** in the navigation bar (`/diagnosis/new`).
  2. Select Defect Category: **Too Little Material (D01)**.
  3. Fill in the Process Context:
     - **Equipment / Line:** `SYNTHETIC-LINE-04` *(Clearly labeled synthetic demo input)*
     - **Dispensing Method:** `Pneumatic Syringe`
     - **Fluid Material:** `Loctite 384 Epoxy`
     - **Target Deposit Diameter:** `1.5 mm`
     - **Dispense Pressure:** `28.0 psi`
     - **Nozzle Gauge:** `25G`
  4. Problem Description:
     - *"Deposits on PCB board #402 are visibly smaller than nominal 1.5mm spec after 45 minutes of continuous production. Temperature is nominal at 22C."*
  5. Click **Create Case**.
- **Result:** Case is persisted atomically to PostgreSQL with `Case ID` (UUID) at **Revision 1**.

---

### Phase 3: Calibrated Image Analysis Evidence (Optional / Flow A) (3:30 – 4:45)
- **Narrative:**
  - "When automated optical inspection images are available under calibrated conditions, DispenseIQ extracts quantitative measurements without relying on black-box visual guesses."
- **Action on Screen:**
  1. Upload synthetic demo image with known calibration circle or reference fiducials.
  2. Select Mode: `PROCESS_LIMITS` or `REFERENCE_IMAGE`.
  3. Specify Comparison Basis: `1.5 mm target ± 0.1 mm tolerance`.
  4. Click **Analyze Image**.
  5. Point out the extracted measurements:
     - Calculated Diameter: `1.18 mm` (under minimum threshold)
     - Coverage Ratio: `0.78`
     - Classification: `UNDERSIZED`
  6. Point out that a canonical `IMAGE` observation is generated and linked to the case evidence.
  7. Explain: "If an image lacks calibration scale (`FEATURES_ONLY`), DispenseIQ issues a warning and emits zero score-bearing evidence, ensuring uncalibrated images never pollute deterministic diagnostic scoring."

---

### Phase 4: Deterministic Cause Ranking & Evidence Evaluation (4:45 – 6:00)
- **Narrative:**
  - "DispenseIQ's diagnostic engine immediately evaluates the process context and visual evidence, ranking potential root causes with numeric confidence percentages and transparent evidence links."
- **Action on Screen:**
  1. View the **Candidate Causes** ranking on the diagnosis view (`/diagnosis/{id}`):
     - **Rank 1:** `RC01 - Nozzle Partial Restriction / Clogging` (e.g. 74% confidence)
       - Supporting: Measured diameter 1.18mm < 1.5mm nominal; pressure normal.
     - **Rank 2:** `RC04 - Dispense Pressure Instability / Drop` (e.g. 18% confidence)
     - **Rank 3:** `RC03 - High Material Viscosity` (e.g. 8% confidence)
  2. Highlight the **Evidence Panel**: Show how each observation explicitly supports or contradicts each candidate cause.

---

### Phase 5: Guided Troubleshooting & Lifecycle Revision (6:00 – 7:30)
- **Narrative:**
  - "Rather than leaving the technician guessing, DispenseIQ recommends the next highest-yield troubleshooting questions and physical checks."
- **Action on Screen:**
  1. Answer follow-up question or perform physical check:
     - Check: `CHK01 - Inspect Nozzle Tip under Microscope`.
     - Result: `RESTRICTION_OBSERVED` (cured adhesive ring at orifice tip).
     - Technician Notes: *"Partial dried epoxy ring observed inside 25G nozzle tip."*
  2. Click **Submit Check Result**.
  3. Observe **Revision Increment**: The case advances to **Revision 2**.
  4. Point out the updated ranking: `RC01 - Nozzle Partial Restriction` confidence increases (e.g. to 92%).

---

### Phase 6: Root Cause Confirmation & Recovery Verification (7:30 – 8:45)
- **Narrative:**
  - "DispenseIQ enforces strict semantic independence: confirming a root cause is separate from executing a recovery, and executing a recovery is separate from verifying the issue is resolved."
- **Action on Screen:**
  1. Click **Confirm Cause**: Confirm `RC01 - Nozzle Partial Restriction`.
     - Actor: `Lead Technician #104`
     - Status: Cause confirmed.
  2. Click **Record Recovery Action**:
     - Action: `ACT01 - Replace Dispensing Tip & Flush Syringe Adapter`.
     - Notes: *"Replaced 25G tip with clean lot #8841. Flushed 3 test purge shots."*
  3. Click **Submit Recovery Verification**:
     - Verification: `VERIFY01 - Dispense 5 Calibration Dots`.
     - Result: `PASSED` (measured diameter 1.49mm).
     - Case Status transitions to **RESOLVED**.

---

### Phase 7: Historical Case Detail, PDF Report, & Analytics (8:45 – 10:00)
- **Narrative:**
  - "All actions, revisions, measurements, and timestamps form an immutable audit trail for quality assurance and engineering root-cause analysis."
- **Action on Screen:**
  1. Open Case Details (`/cases/{id}`): Show the complete deterministic timeline (Case Created → Check Completed → Cause Confirmed → Recovery Performed → Recovery Verified).
  2. Navigate to Reports (`/reports`): View structured JSON case report and click **Download PDF Report**.
  3. (Optional) Show the AI-generated narrative summary:
     - Explain: *"When OpenAI is enabled, an optional plain-text narrative is generated. Notice that the deterministic scores and conclusions remain 100% authoritative—the LLM provides an explanation, not the diagnosis."*
  4. Return to Dashboard (`/dashboard`): Show the newly resolved case counted in quality metrics.

---

## 3. Truthful Claims and System Boundaries

During demonstrations and Q&A, state these engineering boundaries truthfully:

1. **Technician Decision Support:** DispenseIQ is designed as an assistant for factory floor technicians and quality engineers. It is **not** an autonomous closed-loop machine control system.
2. **Deterministic Diagnostic Authority:** All cause ranking, confidence calculations, question recommendations, and lifecycle transitions are governed by Member 2's deterministic expert rules and Bayesian scoring model. The LLM does not calculate scores.
3. **Optional LLM Explanations:** The AI summary endpoint produces narrative explanations (`source="llm"` or fallback `source="deterministic"`). It has zero mutation authority over case state, diagnostic scores, or rankings.
4. **Calibrated Vision Scope:** Image analysis performs bounded optical measurements on standardized circular/oval deposits under controlled camera setups (`PROCESS_LIMITS` or `REFERENCE_IMAGE`). Uncalibrated images generate warnings and no score-bearing observations.
5. **No Production Hardware Claims:** The prototype demonstrates software architecture and algorithmic workflows. It does not claim field-validated micro-dispensing cycle time or hardware camera synchronization.
6. **Explicitly Deferred Features:** Vector similarity search, multi-tenant RBAC authentication, and real-time PLC bus integration are out of scope for this competition prototype.

---

## 4. Failure Fallback Procedures

| Component | Failure Scenario | Fallback / Immediate Action |
| :--- | :--- | :--- |
| **Docker / PostgreSQL** | Container stops or health check times out. | Run `powershell .\scripts\start-db.ps1`. The development volume `postgres_data` preserves existing cases. If needed, restart container with `docker compose restart postgres`. |
| **Backend Service** | FastAPI crashes or port 8000 drops. | Re-run `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000` in the backend terminal. Recovery takes < 2 seconds. |
| **Frontend Service** | Next.js server drops on port 3001. | Re-run `npm run dev -- -p 3001` in the frontend terminal. Browser auto-reconnects with Turbopack. |
| **Wrong Local Service** | Browser loads Open-WebUI or other tool on port 3000. | Re-orient browser to `http://localhost:3001`. Run `.\scripts\verify-demo.ps1` to confirm service identity. |
| **Image Input Issue** | Test image file is corrupted or camera unavailable. | Skip image upload. Proceed with manual problem description and process parameter inputs; the diagnostic engine operates fully on process context. |
| **OpenAI Timeout / Missing Key** | `OPENAI_API_KEY` is not set or OpenAI API fails. | System automatically falls back to `source="deterministic"` and displays structured rule-based summary. Point out that deterministic operation is an intentional reliability feature! |

---

## 5. Reset-Free Rehearsal Policy

- **Preserve Development Records:** Do **not** wipe the PostgreSQL database between rehearsal runs. Retaining prior cases demonstrates search, filtering, and dashboard trend charts realistically.
- **Use Synthetic Input Tags:** Prefix demonstration lines and operators with synthetic identifiers (e.g. `SYNTHETIC-LINE-01`, `TECH-DEMO-A`).
- **Never Test Against Development DB:** Never run automated pytest integration suites with `$env:DATABASE_URL` pointing to `dispenselens`. Automated tests require `$env:TEST_DATABASE_URL` pointing to the disposable `dispenselens_test` database.

---

## 6. Three-Run Rehearsal Record

Use this table to record dry-run rehearsals before official presentation:

| Rehearsal Run | Operator | Narrator | Target Time | Elapsed Time | Expected Outcome | Issues Observed / Actions Taken |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Rehearsal #1** | Team Member | Lead Narrator | 8m 00s | _Recorded in rehearsal_ | Full end-to-end case creation, cause confirmation, recovery, and PDF download. | _Verified port 3001, confirmed PostgreSQL health check._ |
| **Rehearsal #2** | Team Member | Lead Narrator | 7m 30s | _Recorded in rehearsal_ | Calibrated image analysis with diameter measurement and deterministic ranking. | _Confirmed uncalibrated image neutrality warning._ |
| **Rehearsal #3** | Team Member | Lead Narrator | 7m 00s | _Recorded in rehearsal_ | Full timed run with intentional offline deterministic summary fallback. | _Confirmed source='deterministic' rendered gracefully._ |
