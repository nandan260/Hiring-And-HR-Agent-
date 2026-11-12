# HireFlow AI — Hiring & HR AI Agent

An enterprise-grade, multi-tenant AI SaaS control plane and intelligent assistant purpose-built for **Hiring & Human Resources operations**. HireFlow AI unifies seven specialized HR workflows inside a single governed LangGraph orchestration engine backed by PostgreSQL (`pgvector` + Row-Level Security), isolated execution runtimes, Playwright web inspection, MCP tool integrations, human-in-the-loop (HITL) approvals, and a modern React/Tailwind CSS dashboard.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Features](#features)
3. [System Architecture](#system-architecture)
4. [Technology Stack](#technology-stack)
5. [Installation Instructions](#installation-instructions)
6. [Environment Configuration](#environment-configuration)
7. [Database Setup](#database-setup)
8. [Docker Setup](#docker-setup)
9. [Backend Startup](#backend-startup)
10. [Frontend Startup](#frontend-startup)
11. [HR Agent Workflows](#hr-agent-workflows)
12. [Browser & MCP Configuration](#browser--mcp-configuration)
13. [API Documentation](#api-documentation)
14. [Testing Instructions](#testing-instructions)
15. [Known Limitations](#known-limitations)

---

## Project Overview

HireFlow AI provides organizations with a unified, tenant-isolated Hiring & HR AI workspace (`http://localhost:5173`) paired with a strict FastAPI backend (`http://localhost:8000`). Rather than functioning as an unguarded general chatbot, every incoming request passes through deterministic and model-assisted **intent & domain classification**, **workspace/RBAC policy enforcement**, **prompt-injection & PII guardrails**, **token optimization**, and **structured schema validation** before running grounded HR tools.

---

## Features

- **Unified 13-View Enterprise UI:** Public landing and authentication views plus 13 authenticated workspace views (`Dashboard`, `Recruitment`, `Resume Screening`, `Candidates`, `Job Description Generator`, `Interview Management`, `Employee Onboarding`, `HR Assistant`, `HR Analytics`, `Agent Execution Monitor`, `Knowledge Base`, `Tools and Integrations`, and `Settings`).
- **7 Specialized HR Workflows:** Resume screening, job description generation, merit-based candidate shortlisting, interview coordination, employee onboarding checklists, HR policy RAG Q&A, and hiring analytics.
- **Strict Multi-Tenancy & PostgreSQL RLS:** Tenant ownership derived solely from verified JWT claims; sessions set `SET LOCAL ROLE rent_agent_app` and `SET LOCAL app.current_tenant` (`FORCE ROW LEVEL SECURITY` in PostgreSQL).
- **Role-Based Access Control (RBAC):** Supports `platform_admin`, `business_owner`, `business_admin`, and `business_employee` with token revocation on logout.
- **Security & Guardrails:**
  - Out-of-domain rejection (`rejected_out_of_domain`) and ambiguity clarification (`needs_clarification`).
  - XML boundary tagging and neutralization for uploaded/inline resumes against prompt injection.
  - Blind screening mode and strict output scrubbing for emails, phones, SSNs, and API secrets.
  - Per-tenant Fernet-encrypted tool credentials (`CREDENTIALS_ENCRYPTION_KEY`) and file-signature validation (rejecting binary/corrupted/empty PDF, DOCX, and TXT uploads).
- **Human-in-the-Loop (HITL) Governance:** Configurable approval gates for sensitive actions (e.g., shortlist signoff, interview invites, account provisioning, and MCP server activation).
- **Token & Context Optimization:** Prompt compression, KV prefix cache tagging, tiered model cascade (`tier_0_rule`, `tier_1_fast`, `tier_2_reasoning`, `auto_cascade`), exact tenant response cache, and live A/B comparison telemetry.
- **Real-Time PostgreSQL Analytics:** 9 live dashboard KPIs (`Total Jobs`, `Total Candidates`, `Resumes Analyzed`, `Interviews Scheduled`, `Pending Onboarding`, `Completed Executions`, `Failed Executions`, `Token Consumption`, `Estimated AI Costs`), SQLGlot-validated charts, knowledge graph visualization, Markdown export, and immutable audit logs.
- **Resilient Error Handling:** Standardized handling for upstream LLM failures (automatic fallback + secret redaction), database unavailability (`503`/`500` sanitized responses), corrupted uploads (`400`), browser SSRF/timeouts (`403`/`504`/`502`), sandbox limits (`400`/`403`/`404`/`504`/`502`), MCP disconnects (`403`/`502`/`504`), tool errors, and workflow timeout caps.

---

## System Architecture

```text
+-----------------------------------------------------------------------------+
|                        React + Vite + Tailwind Frontend                     |
|  13 Authenticated Views | AppContext Auth & RBAC | HireFlowApiClient (REST) |
+--------------------------------------+--------------------------------------+
                                       | HTTPS / JSON + Bearer JWT
                                       v
+-----------------------------------------------------------------------------+
|                           FastAPI Control Plane                             |
|  Auth & Token Revocation | PostgreSQL RLS Session | Rate Limiter & Quotas   |
+--------------------------------------+--------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|                     Unified LangGraph Workflow Engine                       |
|  1. Classify Intent & Domain (allow HR workflows / clarify / reject OOD)    |
|  2. Load Context (Tenant Workspace Settings, KB Vector Chunks, Memory)      |
|  3. Execute Allowed Tools (Sandbox OCR, Blind Masker, Rubric, SQL, etc.)    |
|  4. Synthesize Output (Gemini / OpenAI / Anthropic / Offline Deterministic) |
|  5. Validate Guardrails & Scrub PII/Secrets -> 6. Persist Execution & Usage |
+-----------------+--------------------+--------------------+-----------------+
                  |                    |                    |
                  v                    v                    v
      +-------------------+  +-------------------+  +-------------------+
      | Sandbox Manager   |  | Playwright Browser|  | MCP Bridge Client |
      | Non-root Docker   |  | Allowlisted Hosts |  | Admin HITL Gate   |
      | or Dev Subprocess |  | SSRF Protection   |  | STDIO / HTTP MCP  |
      +---------+---------+  +-------------------+  +-------------------+
                |
                v
+-----------------------------------------------------------------------------+
|                    PostgreSQL 16 + pgvector + Tenant Storage                |
|  FORCE RLS Multi-Tenant Tables | Fernet Credentials | Tenant Sandboxes      |
+-----------------------------------------------------------------------------+
```

For deeper design specifications and test evidence, see:
- [`docs/SYSTEM_DESIGN.md`](docs/SYSTEM_DESIGN.md)
- [`docs/AGENT_ARCHITECTURE.md`](docs/AGENT_ARCHITECTURE.md)
- [`docs/DATABASE_DESIGN.md`](docs/DATABASE_DESIGN.md)
- [`docs/SECURITY_AND_GUARDRAILS.md`](docs/SECURITY_AND_GUARDRAILS.md)
- [`docs/RUNTIME_INFRASTRUCTURE_REPORT.md`](docs/RUNTIME_INFRASTRUCTURE_REPORT.md)
- [`docs/INTELLIGENCE_GUARDRAILS_AND_OPTIMIZATION.md`](docs/INTELLIGENCE_GUARDRAILS_AND_OPTIMIZATION.md)
- [`docs/TESTING_REPORT.md`](docs/TESTING_REPORT.md)

---

## Technology Stack

- **Frontend:** React 19, TypeScript 7, Vite 8, Tailwind CSS v4 (`@tailwindcss/vite`), React Router v7, Lucide icons (`lucide-react`).
- **Backend:** Python 3.12+, FastAPI, Uvicorn, Pydantic v2 & `pydantic-settings`, SQLAlchemy 2.0, Alembic.
- **AI Orchestration & Document Processing:** LangGraph, `google-genai`, `openai`, `anthropic`, `pypdf`, `python-docx`, `sqlglot`, `jsonschema`.
- **Database & Security:** PostgreSQL 16 (`psycopg[binary]`, embedded `pgserver` for local dev), `pgvector`, PyJWT, `argon2-cffi`, `cryptography` (Fernet).
- **Runtime & Automation:** Docker CLI (optional non-root container isolation), Playwright (headless Chromium/Edge isolated sessions), MCP Python SDK, `psutil`.
- **Testing:** `pytest`, `httpx` (`FastAPI TestClient`), headless Playwright browser E2E.

---

## Installation Instructions

### Prerequisites

- **Python** 3.12 or higher
- **Node.js** 20+ and **npm**
- **Optional:** Docker Desktop / Docker Engine (for Linux container sandbox mode and `docker-compose`)
- **Optional:** Playwright browser binaries or Microsoft Edge on Windows

### 1. Clone the Repository

```bash
git clone https://github.com/nandan260/Hiring-And-HR-Agent-.git
cd Hiring-And-HR-Agent-
```

### 2. Backend Setup

```bash
cd backend
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# Linux / macOS
# source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

# Optional: install Playwright Chromium runtime for headless web inspection
playwright install chromium
```

### 3. Frontend Setup

```bash
cd ../frontend
npm install
```

---

## Environment Configuration

Copy `.env.example` files before customizing configuration (never commit real `.env` files or API keys):

```bash
# Backend
cp backend/.env.example backend/.env

# Frontend
cp frontend/.env.example frontend/.env.local
```

### Key Backend Environment Variables (`backend/app/config.py`)

| Variable | Default / Example | Description |
| :--- | :--- | :--- |
| `APP_ENV` | `development` | Set `production` in deployed environments (`CREDENTIALS_ENCRYPTION_KEY` required in production) |
| `DATABASE_URL` | `""` (empty) | PostgreSQL DSN (e.g., `postgresql+psycopg://postgres:password@localhost:5432/rent_an_agent`). Leave empty in local dev to auto-launch embedded `pgserver` PostgreSQL in `backend/.pgdata` |
| `JWT_SECRET_KEY` | Dev key | Set a strong 32+ char random secret in production |
| `CREDENTIALS_ENCRYPTION_KEY` | Auto-generated dev key | Base64 url-safe 32-byte Fernet key (`Fernet.generate_key()`) |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Allowed frontend origins |
| `AUTO_SEED_CATALOG` | `true` | Automatically seeds workflow specs and sample demo tenants on startup |
| `LLM_PROVIDER` | `auto` | `auto`, `gemini`, `openai`, `anthropic`, or `deterministic` |
| `GEMINI_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | `""` | External LLM API keys; when unset, `deterministic-hr-synthesizer-v1` runs offline cleanly |
| `SANDBOX_DOCKER_IMAGE` | `hireflow-hr-sandbox:latest` | Non-root Docker image built from `backend/Dockerfile.sandbox` |
| `PLAYWRIGHT_HEADLESS` | `true` | Runs isolated Playwright browser contexts headlessly |
| `PLAYWRIGHT_DEFAULT_ALLOWLIST` | `github.com,linkedin.com,greenhouse.io,...` | Host allowlist enforced alongside private/loopback IP SSRF checks |
| `RATE_LIMIT_ENABLED` | `true` | Enables per-tenant execution & token rate limits |

### Key Frontend Environment Variables (`frontend/.env.example`)

| Variable | Default | Description |
| :--- | :--- | :--- |
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | FastAPI base URL |
| `VITE_ENABLE_LIVE_API` | `false` | Set `"true"` in `.env.local` if desired (live mode is active by default in `apiClient.ts`) |

---

## Database Setup

HireFlow AI uses PostgreSQL 16 + Alembic migrations (`backend/alembic/versions/20261111_0001` through `20261111_0004`).

```bash
cd backend

# Apply all schema migrations and RLS policies
alembic upgrade head

# (Optional) Verify current migration revision -> 20261111_0004 (head)
alembic current

# Seed sample HR workflows, tools, and multi-tenant demo organizations
python -m app.db.seed
```

> **Note for local development:** If `DATABASE_URL` is left empty, SQLAlchemy/Alembic automatically manages an embedded PostgreSQL 16 instance inside `backend/.pgdata/`. Note that running `alembic` CLI concurrently against the same `.pgdata/` directory while `uvicorn` owns it is unsupported; stop `uvicorn` before running CLI migrations in embedded mode.

### Seeded Demo Accounts (Fictional Sample Data)

| Organization | Role | Email | Password |
| :--- | :--- | :--- | :--- |
| Acme Cloud Corp | `business_owner` | `ananya@acmecloud.io` | `AcmeOwner!2026` |
| Acme Cloud Corp | `business_admin` | `vikram@acmecloud.io` | `AcmeAdmin!2026` |
| Acme Cloud Corp | `business_employee` | `maya@acmecloud.io` | `AcmeUser!2026` |
| NovaBio HealthTech | `business_owner` | `priya@novabio.io` | `NovaOwner!2026` |

---

## Docker Setup

### Run PostgreSQL & Backend with Docker Compose

From the repository root:

```bash
docker compose up --build -d
```

This starts:
- `postgres:16-alpine` on port `5432` (`rent_an_agent` database with persistent volume `rent_agent_pgdata`)
- `backend` built from [`backend/Dockerfile`](backend/Dockerfile) running `alembic upgrade head && python -m app.db.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000`

### Build the Hardened Non-Root Sandbox Image (Optional)

```bash
cd backend
docker build -f Dockerfile.sandbox -t hireflow-hr-sandbox:latest .
```

The sandbox image executes `app/runtime/sandbox_worker.py` under unprivileged user `10001:10001` with `python -I`, CPU/memory caps, `--network=none`, and execution timeouts.

---

## Backend Startup

```bash
cd backend
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000
```

Verify health:

```bash
curl http://127.0.0.1:8000/health
```

Expected JSON:

```json
{
  "status": "ok",
  "service": "HireFlow AI — Hiring & HR AI Agent",
  "database": "connected",
  "postgres_version": "PostgreSQL 16.2 on ..."
}
```

---

## Frontend Startup

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173` (or `http://localhost:5173`) in your browser.

To create a production bundle and type-check:

```bash
cd frontend
npm run build
```

---

## HR Agent Workflows

| Slug | Workflow | Capabilities | Key Guardrails / Tools |
| :--- | :--- | :--- | :--- |
| `recruitment-screening` | **Recruitment & Resume Screening** | Extracts resume text, parses skills/experience, evaluates candidates against JDs | `sandbox_ocr_extract`, `pii_blind_masker`, `rubric_scorer`, `playwright_verify_portfolio`, `ats_post_scorecard` |
| `jd-generator` | **Job Description Generator** | Synthesizes structured JDs (role overview, responsibilities, requirements) | `kb_search_leveling_guide`, `inclusive_language_linter`, `playwright_careers_style_check`, `ats_create_draft_req` |
| `candidate-shortlisting` | **Candidate Shortlisting** | Ranks screened candidates objectively using weighted merit criteria | `query_screened_pool`, `sandbox_weighted_ranker`, `citation_grounding_check`, `hitl_shortlist_signoff`, protected-attribute filtering |
| `interview-scheduling` | **Interview Scheduling** | Solves multi-interviewer timezones, proposes/books interview slots | `gcal_free_busy`, `timezone_slot_solver`, `playwright_legacy_portal`, `gcal_create_interview_event` (HITL gated) |
| `employee-onboarding` | **Employee Onboarding** | Orchestrates pre-boarding checks, KYC verification, IT & SSO provisioning | `sandbox_kyc_ocr_verify`, `scim_provision_account` (HITL), `jira_create_hardware_ticket` (HITL) |
| `hr-policy-support` | **Employee Policy Support** | Answers employee leave/benefits/compliance questions with KB citations | Tenant `pgvector` RAG retrieval, RBAC access checks, deterministic fast-path classification |
| `hr-analytics` | **HR Analytics** | Computes recruiting funnel KPIs, pipeline conversion charts, and token ROI | `sqlglot` AST read-only query validation, live PostgreSQL tenant aggregations |

---

## Browser & MCP Configuration

### Playwright Isolated Browser Runtime

- Each tenant inspection runs inside a dedicated ephemeral browser workspace under `BROWSER_ROOT/<tenant_id>/<browser_id>/` (`screenshot.png` + extracted text).
- Requests to `POST /api/v1/hr-agent/browser/inspect` enforce domain allowlisting (`PLAYWRIGHT_DEFAULT_ALLOWLIST`), block private/loopback/link-local SSRF targets (e.g., `127.0.0.1`, `169.254.169.254`), and map timeouts to HTTP `504` and crashed sessions to HTTP `502` with secret redaction.

### Model Context Protocol (MCP) Servers

- Register STDIO or HTTP MCP integrations via `POST /api/v1/hr-agent/mcp/servers` (configured with command/URL & `MCP_EXECUTION_TIMEOUT_SEC`).
- **Security Gate:** Unapproved MCP servers cannot discover tools or execute calls (`HTTP 403`). Owners/admins must approve a server via `POST /api/v1/hr-agent/mcp/servers/{server_id}/approval`, run tool discovery (`/discover`), and optionally scope per-tool permissions (`/permissions`) before `/execute`.

---

## API Documentation

Interactive OpenAPI documentation is available while the backend is running:
- **Swagger UI:** `http://127.0.0.1:8000/docs`
- **ReDoc:** `http://127.0.0.1:8000/redoc`

### Core Route Groups (`/api/v1`)

- **Authentication (`/auth`):** `POST /register`, `POST /login`, `POST /logout`, `GET /me`
- **Organizations (`/organizations`):** `GET /current`, `GET /members`, `POST /members`, `PATCH /members/{member_id}/role`
- **Unified HR Agent (`/hr-agent`):**
  - Workspace & Settings: `GET /workspace`, `PATCH /settings`
  - Execution & Classification: `POST /classify`, `POST /execute`, `GET /executions`, `GET /usage`, `POST /optimization/compare`
  - Conversations: `GET|POST /conversations`, `GET|POST /conversations/{conversation_id}/messages`
  - Knowledge Base & Graph: `GET|POST /knowledge`, `GET /knowledge/{doc_id}/download`, `DELETE /knowledge/{doc_id}`, `GET /knowledge/{doc_id}/markdown`, `GET /knowledge-graph`
  - Integrations & Runtimes: `GET /integrations`, `PATCH /integrations/{permission_id}`, `POST /integrations/{permission_id}/credentials`, `GET /monitor`, `GET|POST /runtimes`, `POST /runtimes/{id}/start|stop|restart|execute`, `DELETE /runtimes/{id}`, `GET /tools`, `POST /tools/{tool_id}/execute`
  - Browser & MCP: `POST /browser/inspect`, `GET|POST /mcp/servers`, `POST /mcp/servers/{id}/approval|discover|execute`, `PATCH /mcp/servers/{id}/permissions`
- **HR Domain Entities & Governance:** `GET /agents/specs`, `GET|POST /hitl/approvals` (`/{id}/resolve`), `GET /candidates`, `GET /interviews`, `GET /onboarding`, `GET /audit-logs`, `GET /execution-logs`, `GET /usage/summary`

---

## Testing Instructions

### Backend Integration & Security Suite

Tests run inside isolated temporary `pgserver` PostgreSQL instances (automatically managed by `backend/tests/conftest.py`):

```bash
cd backend
.\.venv\Scripts\pytest.exe -v
```

Covers 38 end-to-end tests across:
- Multi-tenant RLS isolation & JWT RBAC (`test_auth_and_rbac.py`, `test_multi_tenancy_and_rls.py`)
- All 7 specialized HR workflows (`test_agent_1..7*.py`, `test_end_to_end_agents_api.py`, `test_unified_hr_agent_and_governance.py`)
- Intelligence classifier, guardrails, injection defense & token optimizer (`test_intelligence_guardrails_optimization.py`)
- Sandbox, Playwright SSRF, MCP approvals & monitor (`test_runtime_infrastructure.py`)
- Full E2E integration, 8 error-handling modes & all 9 Dashboard KPIs (`test_end_to_end_system_verification.py`)

### Frontend Type Check & Production Build

```bash
cd frontend
npm run build
```

---

## Known Limitations

- **Docker Fallback on Hosts Without Docker CLI:** When Docker is unavailable (`docker_available: false`), `SandboxManager` automatically runs in `development_fallback` (`is_container_isolated: false`) using isolated Python child subprocesses and per-tenant temp directories rather than Linux container namespaces.
- **Deterministic Offline LLM Mode:** With `GEMINI_API_KEY`, `OPENAI_API_KEY`, and `ANTHROPIC_API_KEY` unset, agent responses synthesize via the local `deterministic-hr-synthesizer-v1` engine (`$0.00` incremental LLM spend) rather than live external foundation model calls.
- **In-Process Rate Limiter & Cache:** `rate_limiter` and `tenant_response_cache` use in-memory state scoped to a single backend worker process; multi-replica horizontal deployments should back these with Redis.
- **Backend Compatibility Modules:** Legacy `marketplace.py` and `rentals.py` routers remain mounted internally on FastAPI for API/test backward compatibility, while user-facing marketplace concepts are removed from the UI and HireFlow unified workspace.
