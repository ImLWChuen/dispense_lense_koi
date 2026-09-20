# DispenseIQ Competition Demo and Operator Runbook

This runbook guides operators and narrators through a structured, repeatable 6–10 minute competition demonstration of **DispenseIQ (DispenseLens)** using only the controls, labels, and workflows that exist in the checked-in user interface.

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
  - "In precision industrial fluid dispensing, defect symptoms—such as undersized deposits, line clogs, or deposit tailing—lead to costly manufacturing scrap and line downtime."
  - "Junior technicians often struggle to isolate root causes when multiple physical variables (viscosity, pneumatic pressure, nozzle wear, ambient temperature) interact."
  - "DispenseIQ provides structured decision support by fusing optical inspection evidence, process context, and guided troubleshooting into a deterministic evidence-support assessment."
- **Action on Screen:** Display the DispenseIQ Dashboard (`/dashboard`). Point out recent defect trends, active cases, and root cause distributions.

---

### Phase 2: Process Context & Image Evidence Setup (1:30 – 3:45)
- **Narrative:**
  - "Let's create a new diagnostic case on the factory floor. Notice that optical inspection evidence, process context, and manual observations are assembled directly on the New Diagnosis screen before launching evaluation."
- **Action on Screen:**
  1. Click **New Diagnosis** in the sidebar navigation (`/diagnosis/new`).
  2. Fill in the **Problem Description** card (left column):
     - **Symptom Description** (textarea):
       *"[SYNTHETIC DEMO] Dispensed adhesive deposits are visibly smaller than target after 45 minutes of continuous production run. Temperature is nominal at 22C."*
     - **Equipment / Line** (select): Select `Dispensing Line A` *(or any available line A–D)*.
     - **Material Type** (input): `[SYNTHETIC DEMO] Synthetic Epoxy Adhesive Lot-A1`.
  3. Select the **Observed Defect Type**:
     - Click the card for **Too Little Material** (Defect code `D01_TOO_LITTLE`).
  4. Provide **Manual Observations** (optional selects):
     - **Deposit Size**: `Undersized (smaller than target)`.
     - **Frequency Pattern**: `Consistent (occurs steadily / every shot)`.
     - **Location Pattern**: `All dispensing points (systemic)`.
  5. **Optional Image Inspection Evidence (Right Column):**
     - In the **Image Upload** panel on the right, drop or browse a test image (JPEG/PNG).
     - In the **Analysis Mode & Calibration** panel:
       - To demonstrate calibrated evidence: Select `Process Limits`, configure process thresholds (e.g. Min Coverage Ratio `0.15`, Max Coverage Ratio `0.35`), and click `Analyze`. Once analyzed with status `CALIBRATED`, the resulting optical observation is automatically captured in the active case snapshot.
       - To demonstrate uncalibrated neutrality: Select `Features Only` and click `Analyze`. Note that status returns `UNCALIBRATED` and issues an advisory notice without generating score-bearing evidence.
     - *Note for Narrator: State the actual measurements and status returned on screen rather than assuming fixed numbers.*
  6. Click **Start Diagnosis** at the bottom of the form.
- **Result:** The case is persisted atomically to PostgreSQL with a unique `Case ID` at **Revision 1**, and the browser navigates directly to `/diagnosis/{case_id}`.

---

### Phase 3: Deterministic Evidence Support Evaluation (3:45 – 5:15)
- **Narrative:**
  - "DispenseIQ immediately evaluates the initial symptom and optical observations against deterministic diagnostic rules. Causes are ranked strictly by cumulative Evidence Support on a 0 to 100 scale."
  - "These scores are evidence-support metrics, not statistical probabilities, and they do not sum to 100 across candidate causes."
- **Action on Screen:**
  1. View the **Ranked Candidate Causes** list on `/diagnosis/{id}`:
     - Point out the **REVISION 1** badge.
     - Point out the top-ranked cause (e.g. `Nozzle Restriction` or whichever cause is ranked first by the engine for the chosen inputs).
     - Highlight the `Evidence Support /100` progress bar and score for each candidate cause.
     - Note the supporting and contradicting evidence counts (`X supports`, `Y contradicts`).
  2. Highlight the **Evidence** card: Show the itemized list of manual context and image-derived observations linked to the top cause.

---

### Phase 4: Guided Physical Troubleshooting Checks (5:15 – 6:45)
- **Narrative:**
  - "Rather than leaving the technician to guess, DispenseIQ recommends high-yield physical troubleshooting checks to confirm or eliminate suspected causes."
- **Action on Screen:**
  1. Click the **Troubleshooting Checks** workflow step (`/diagnosis/{id}/troubleshooting`).
  2. Locate the active check recommended by the engine:
     - For example, if `ACT01 - Inspect Nozzle` is recommended, expand its accordion to review the Standard Operating Procedure and Target Causes Evaluated.
  3. Under **Record Physical Check Result**:
     - **Check Execution Status**: Click `Completed` *(or another status if blocked/skipped)*.
     - **Evidence Finding**: Click `SUPPORTS`.
     - **Canonical Outcome Key**: Select the applicable canonical outcome from the rendered radio options (for `ACT01`, select `blockage_found`).
     - **Technician Notes** (textarea): *"[SYNTHETIC DEMO] Cured epoxy deposit observed at nozzle orifice tip."*
  4. Click **Submit Check Result**.
- **Result:** The check result is atomically recorded. The case advances to **Revision 2**, recalculates evidence support scores, and updates cause rankings dynamically based on the verified finding.

---

### Phase 5: Root Cause Confirmation & Recovery Verification (6:45 – 8:30)
- **Narrative:**
  - "DispenseIQ enforces strict semantic separation: confirming a root cause is an engineering assessment, executing a corrective action is a physical recovery, and verifying recovery determines whether the issue is resolved."
- **Action on Screen:**
  1. Click the **Engineer Verification** workflow step (`/diagnosis/{id}/verification`).
  2. **Step A — Confirm Candidate Root Cause (Optional):**
     - Click to select the top candidate cause card from the list.
     - In the **Confirm Cause Assessment** textarea, enter technician notes:
       *"[SYNTHETIC DEMO] Visual nozzle inspection confirmed partial cured epoxy restriction."*
     - Click **Confirm Selected Cause**.
     - Point out: The confirmed cause record is saved, but the issue condition remains `Unresolved`.
  3. **Step B — Record Corrective / Recovery Action:**
     - In the **Record Corrective / Recovery Action** card, enter free-text action details in the textarea:
       *"[SYNTHETIC DEMO] Replaced 25G dispensing tip with clean lot #8841 and executed 3 fluid purge test cycles."*
     - Click **Record Recovery Action**.
     - Point out: The issue condition transitions to `Recovery Pending Verification`.
  4. **Step C — Recovery Verification:**
     - In the **Recovery Verification** card, click the **Verification Passed** button.
     - In the **Verification Details / Test Observations** textarea, enter:
       *"[SYNTHETIC DEMO] Dispensed 10 test dots; measured diameters are within nominal process tolerance."*
     - Click **Submit Passed Verification** *(if demonstrating an unsuccessful verification branch where Verification Failed was clicked, the button renders as **Submit Failed Verification**)*.
     - Point out: The issue condition transitions to **Resolved**.

---

### Phase 6: Case History, Reports, & Analytics (8:30 – 10:00)
- **Narrative:**
  - "Every action, observation, check result, and recovery verification forms an immutable, audit-ready history for factory quality records."
- **Action on Screen:**
  1. Open Case Details (`/cases/{id}`): Show the deterministic chronological timeline displaying all lifecycle events (Case Created → Check Completed → Cause Confirmed → Recovery Performed → Recovery Verified).
  2. Navigate to Reports (`/reports`): Open the structured JSON case report and download the PDF report.
  3. *(Optional)* View the AI-generated narrative summary:
     - Explain: *"When an OpenAI API key is configured, an optional narrative summary is generated (`source='llm'`). When offline or without a key, the system provides a structured deterministic summary (`source='deterministic'`). In both cases, evidence support scores and conclusions remain 100% deterministic."*
  4. Return to Dashboard (`/dashboard`): Demonstrate that the resolved case is reflected in platform quality metrics.

---

## 3. Truthful Claims and System Boundaries

During demonstrations and technical reviews, state these boundaries truthfully:

1. **Technician Decision Support:** DispenseIQ is designed as an advisory tool for factory technicians and quality engineers. It is **not** an autonomous closed-loop machine controller.
2. **Deterministic Diagnostic Authority:** All cause rankings, evidence evaluations, question/check recommendations, and lifecycle transitions are governed by Member 2's deterministic expert rules. The platform uses an **Evidence Support** score on a 0–100 scale, **not** statistical probabilities or a Bayesian model. Scores do not sum to 100.
3. **Optional LLM Explanations:** The AI summary endpoint produces narrative explanations (`source="llm"` or fallback `source="deterministic"`). The LLM has zero authority to alter diagnostic scores, cause rankings, or case states.
4. **Calibrated Vision Scope:** Computer vision is bounded to optical feature extraction under controlled conditions (`PROCESS_LIMITS` or `REFERENCE_IMAGE`). Uncalibrated images generate advisory notices and emit no score-bearing observations.
5. **No Production Hardware Claims:** The prototype demonstrates software architecture and algorithmic workflows. It does not claim live PLC machine-bus integration or field-validated cycle-time compliance.
6. **Explicitly Deferred Scope:** Vector/semantic similarity search, multi-tenant RBAC authentication, and deferred hardware integrations are not implemented in this prototype.

---

## 4. Failure Fallback Procedures

| Component | Failure Scenario | Fallback / Immediate Action |
| :--- | :--- | :--- |
| **Docker / PostgreSQL** | Container stops or health check times out. | Run `powershell .\scripts\start-db.ps1`. The development volume `postgres_data` preserves existing cases. If needed, restart container with `docker compose restart postgres`. |
| **Backend Service** | FastAPI process exits or port 8000 drops. | Re-run `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000` in the backend terminal. Startup takes < 2 seconds. |
| **Frontend Service** | Next.js server drops on port 3001. | Re-run `npm run dev -- -p 3001` in the frontend terminal. Browser auto-reconnects with Turbopack. |
| **Wrong Local Service** | Browser loads Open-WebUI or other tool on port 3000. | Re-orient browser to `http://localhost:3001`. Run `.\scripts\verify-demo.ps1` to confirm service identity. |
| **Image Input Issue** | Test image file is corrupted or camera unavailable. | Skip image upload. The diagnostic engine operates fully on problem description and process context inputs. |
| **OpenAI Timeout / Missing Key** | `OPENAI_API_KEY` is unset or network times out. | System automatically falls back to `source="deterministic"` and renders the rule-based summary. Point out that deterministic operation is an intentional reliability design. |

---

## 5. Reset-Free Rehearsal Policy

- **Preserve Development Records:** Do **not** wipe the PostgreSQL database between rehearsal runs. Retaining prior cases demonstrates search, filtering, and dashboard trend charts realistically.
- **Use Synthetic Demo Data Tags:** Mark all entered free-text demonstration inputs with synthetic identifiers (e.g. prefixing symptom descriptions, material descriptions, check findings, cause confirmation notes, recovery actions, and verification observations with `[SYNTHETIC DEMO]`). Note that the checked-in UI exposes a fixed dropdown for line selection (`Dispensing Line A–D`) and does not expose an editable operator-identity field; the current prototype records a generic technician actor in the audit timeline.
- **Never Test Against Development DB:** Never run automated pytest integration suites with `$env:DATABASE_URL` pointing to `dispenselens`. Automated tests require `$env:TEST_DATABASE_URL` pointing to the disposable `dispenselens_test` database.

---

## 6. Three-Run Rehearsal Record

Use this table to record dry-run rehearsals before official presentation:

| Rehearsal Run | Operator | Narrator | Target Time | Elapsed Time | Expected Outcome | Issues Observed / Actions Taken |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Rehearsal #1** | Team Member | Lead Narrator | 8m 00s | _Recorded in rehearsal_ | Full end-to-end case creation, cause confirmation, recovery, and PDF download. | _Verified port 3001, confirmed PostgreSQL health check._ |
| **Rehearsal #2** | Team Member | Lead Narrator | 7m 30s | _Recorded in rehearsal_ | Calibrated image analysis with diameter measurement and deterministic ranking. | _Confirmed uncalibrated image neutrality warning._ |
| **Rehearsal #3** | Team Member | Lead Narrator | 7m 00s | _Recorded in rehearsal_ | Full timed run with intentional offline deterministic summary fallback. | _Confirmed source='deterministic' rendered gracefully._ |
