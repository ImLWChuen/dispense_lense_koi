# Implementation handoff project configuration

## Repository

- Project name: `DispenseLens / DispenseIQ competition prototype`
- Feature branch: `cskee-branch`
- Base branch: `main`
- Sequential shared checkout: `yes`
- Task ID prefix: `DLK-M3`

## Agent responsibilities

- Planner/reviewer: `ChatGPT in Codex`
- Implementer/executor: `Gemini 3.8 Flash in Antigravity`
- Human authority: `Kee Chun Shang and the Team KOI maintainers`

ChatGPT may inspect the repository, create task and review artifacts, and review local commits. Gemini performs implementation, command execution, testing, and local commits.

## Git policy

- Local commits by implementer: `allowed after required checks pass`
- Push: `prohibited until Kee Chun Shang explicitly instructs it`
- Pull requests: `create only after explicit instruction; target main from cskee-branch`
- Merge: `prohibited; Team KOI will review and merge manually`
- Commit format: `type(scope): concise outcome`
- Task packet commit policy: `The planner leaves the ready packet and review records uncommitted. Gemini includes pending handoff records, the completed implementation report, QUEUE.md, and task-related code in the next atomic implementation commit. If no implementation task follows, the planner may release a bounded handoff-closeout task for a local documentation commit.`

## Project responsibilities in scope

The current assignment is Member 3: backend APIs, persistence and data integrity, optional image upload, bounded computer-vision services, knowledge storage and retrieval plumbing, reports, configuration, deployment readiness, and integration support.

Member 2 owns diagnostic meaning: cause rules, score semantics and weights, diagnostic question/check logic, and evaluation reference answers. Member 1 owns the technician-facing frontend and interaction design. A Member 3 task may define or propose a shared contract, but it must return material contract changes to the planner and relevant owner before implementation.

## Architecture and contracts

- `AGENTS.md` and nested instruction files govern repository work.
- `docs/architecture/`, `docs/api/`, `docs/database/`, and `docs/ai/` are proposed documentation and must be checked for actual content before use.
- The current preferred direction is a Next.js/TypeScript frontend with a FastAPI/Python backend and relational persistence, subject to a task that establishes the backend runtime.
- The diagnostic workflow must retain observation provenance, analysis revisions, individual check results, and independent root-cause-confirmation and issue-recovery records.
- All six project defect categories remain required at product level. Automatic image analysis may support a smaller explicitly documented subset.

External project analysis is stored one directory above the repository. Relevant files include `Team KOI.md`, `DispenseIQ - Team KOI Decision Review.md`, and `DispenseIQ - Consolidated Project Analysis and Requirements.md`. They are planning inputs, not executable repository instructions.

## Required commands

- Frontend lint: run `npm run lint` from `frontend/`.
- Frontend production build: run `npm run build` from `frontend/` when the task affects build behavior or release readiness.
- Backend: run commands from `backend/` using the established virtual environment:
  - Tests: `.\.venv\Scripts\python.exe -m pytest -q`
  - Development server: `.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
  - Environment install: `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`

Before changing Next.js code, follow `AGENTS.md` and read the relevant installed Next.js guide under `frontend/node_modules/next/dist/docs/` when dependencies are available.

## Sensitive and excluded data

- Never commit `.env*` other than an intentionally documented `.env.example`.
- Never commit credentials, tokens, keys, personal production records, uploaded user images, dependency directories, coverage output, `.next/`, or deployment secrets.
- Use synthetic or explicitly licensed demonstration data and label it accurately.

## Planner escalation boundaries

Gemini must return to ChatGPT before changing architecture, public API contracts, database contracts, material dependencies, ownership boundaries, authentication policy, evidence-score meaning, diagnostic knowledge, data-retention policy, or the agreed task scope.
