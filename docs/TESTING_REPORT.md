# HireFlow AI — End-to-End Integration & Testing Report

**Date:** 2026-11-12  
**Product:** HireFlow AI — Hiring & HR AI Agent  
**Scope Verified:** End-to-end integration across React/Vite frontend (`http://127.0.0.1:5173`), FastAPI backend (`http://127.0.0.1:8000`), PostgreSQL 16.2 (`alembic` head `20261111_0004`), LangGraph unified HR orchestrator, all 7 HR workflows, security/isolation controls, 8 error-handling modes, and all 9 Dashboard Analytics KPIs.

---

## 1. Verification Summary

| Verification Suite | Scope | Result | Key Observed Details |
| :--- | :--- | :--- | :--- |
| **Backend Automated Tests (`pytest -v`)** | Full suite across auth/RBAC, multi-tenancy RLS, all 7 workflows, intelligence/guardrails/optimization, runtime sandbox/browser/MCP, and E2E integration & error modes | **38 passed, 1 warning** (`60.48s`) | Zero failures, zero skipped assertions; includes `test_end_to_end_system_verification.py` (3 comprehensive E2E test functions) |
| **Frontend Production Build (`npm run build`)** | TypeScript (`tsc --noEmit`) + Vite production bundle (`vite build`) | **Exit code 0** (`1.45s`) | 2,106 modules transformed cleanly (`dist/index.html`, CSS, JS bundle) |
| **Playwright Headless Edge E2E (`verify_ui_e2e.py`)** | Public landing page, Sign-In, Sign-Out, all 13 authenticated routes, 9 Dashboard KPI labels, interactive UI workflows, and Employee RBAC view | **`ok: true` (`routes_verified: 13`)** | **0 console errors**, **0 page errors**, **0 server 5xx**, **0 unexpected 4xx** |
| **Database Schema & Health (`GET /health`, `alembic current`)** | Embedded PostgreSQL 16.2 + Alembic schema version | **Healthy / Connected** | `20261111_0004 (head)`, `PostgreSQL 16.2 on x86_64-pc-mingw64` |

---

## 2. Frontend & Backend End-to-End Verification (All 13 Routes)

Live headless Microsoft Edge verification (`verify_ui_e2e.py`) confirmed full React/Vite integration against live FastAPI endpoints with persistent PostgreSQL storage:

1. **Public Routes (`/`, `/signin`):**
   - Verified `HireFlow AI` branding and complete absence of `Rent-an-Agent` marketplace wording or pricing storefront pages.
   - Verified live owner sign-in (`ananya@acmecloud.io`), explicit sign-out (`POST /api/v1/auth/logout`), and employee sign-in (`maya@acmecloud.io`).
2. **All 13 Authenticated Routes Verified (`routes_verified: 13`, zero console/HTTP errors):**
   - `/dashboard` — Dashboard (`OverviewPage.tsx`) with all 9 real database-backed KPI cards.
   - `/dashboard/recruitment` — Recruitment pipeline.
   - `/dashboard/screening` — Resume Screening (live execution tested interactively).
   - `/dashboard/candidates` — Candidates management & merit profiles.
   - `/dashboard/jd-generator` — Job Description Generator (live JD synthesis tested interactively).
   - `/dashboard/interviews` — Interview Management & slot coordination.
   - `/dashboard/onboarding` — Employee Onboarding workflows & HITL checklists.
   - `/dashboard/assistant` — HR Assistant multi-turn chat (`POST /api/v1/hr-agent/conversations/{id}/messages` returned `201 Created`).
   - `/dashboard/analytics` — HR Analytics charts & SQL metrics (`Run Analytics` clicked interactively).
   - `/dashboard/monitor` — Agent Execution Monitor (`GET /api/v1/hr-agent/monitor?limit=30`, `GET /api/v1/hr-agent/runtimes`).
   - `/dashboard/knowledge-base` — Knowledge Base uploads & Knowledge Graph (`GET /api/v1/hr-agent/knowledge-graph`).
   - `/dashboard/integrations` — Tools & Integrations + MCP server management (`GET /api/v1/hr-agent/tools?core_only=true`, `GET /api/v1/hr-agent/mcp/servers`).
   - `/dashboard/settings` — Workspace guardrails, quotas, routing tier, and member settings.

---

## 3. All 7 HR Workflows Grounded Testing

Verified in both automated `TestClient` API integration tests (`backend/tests/test_end_to_end_system_verification.py`, `test_unified_hr_agent_and_governance.py`, `test_agent_1..7`) and live Playwright UI checks:

1. **Recruitment & Resume Screening (`recruitment-screening`):**
   - Tested uploaded document resume (`vikram_deshmukh_cv.txt`) via `attachments` ID resolution (`validate_structured_input` merging `attachments` -> `document_ids`) and inline resume screening in blind-screening mode. Verified extracted Python/FastAPI/PostgreSQL skills and blind-mode PII redaction (`blind_screening_applied: true`).
2. **Job Description Generator (`jd-generator`):**
   - Generated structured job descriptions (summary, responsibilities, qualifications) plus inclusive-language lint checks; persisted new `JobDescription` records to PostgreSQL.
3. **Candidate Shortlisting (`candidate-shortlisting`):**
   - Ranked stored candidates on merit while blocking protected attributes/discriminatory ranking prompts.
4. **Interview Scheduling (`interview-scheduling`):**
   - Proposed/scheduled candidate interview slots, persisted `InterviewRecord` rows (`scheduled`), and created HITL approval gates where configured.
5. **Employee Onboarding (`employee-onboarding`):**
   - Triggered onboarding workflows for hires, verified compliance checklist/document generation, and persisted pending onboarding state + HITL approvals until resolved (`resume -> 100%` verified in `test_agent_5_onboarding.py`).
6. **Employee Policy Support (`hr-policy-support`):**
   - Uploaded policy handbook (`ergonomics_benefits_2026.txt`), queried policy allowance (`$1,200 reimbursement every 24 months`), verified RAG chunk retrieval grounded in uploaded text, and confirmed employee RBAC access.
7. **HR Analytics (`hr-analytics`):**
   - Aggregated live PostgreSQL funnel metrics and `sqlglot`-validated analytics charts across candidates, jobs, interviews, onboarding, and token optimization stats.

---

## 4. Agent Behavior Verification

- **Correct Workflow Routing:** Verified automatic intent routing across all 7 HR workflows without mandatory `workflow_hint` (`test_unified_hr_agent_routes_all_7_workflows_without_hint`) as well as cross-workflow switching within multi-turn conversations.
- **Ambiguity Clarification (`needs_clarification`):** Underspecified input `"help"` triggered `classifier_result == "needs_clarification"` with structured `clarification_questions`.
- **Domain Restriction (`rejected_out_of_domain`):** Requests outside HR (e.g., `"Write a crypto trading bot for Bitcoin arbitrage and prescribe aspirin dosage."`) returned `execution_status == "rejected"` and executed zero tools (`execute_tools` absent from `trace_steps`).
- **Corrupted Inline Input Resilience:** Submitting corrupted inline resume payloads alongside valid candidates surfaced explicit warnings in `invalid_resumes`, `summary`, and `explanation` without failing valid candidate extraction.
- **Human-in-the-Loop (HITL) Governance:** Sensitive actions create pending `HitlApproval` records and MCP server actions require explicit admin approval (`403` before approval).

---

## 5. Security, Tenant Isolation & Runtime Hardening

- **Authentication & Token Revocation:** JWT access tokens bound strictly to `(user_id, tenant_id, role)`; logout writes token `jti` into `revoked_tokens` (`test_business_register_login_and_logout_revocation`).
- **Role-Based Access Control (RBAC):** Confirmed `business_employee` users (e.g., `maya@acmecloud.io`) can access Dashboard overview and HR Assistant without unauthorized calls to admin-only `GET /api/v1/audit-logs`, while admin/owner-only mutations enforce `403`.
- **Multi-Tenant PostgreSQL RLS Isolation:** Database sessions execute `SET LOCAL ROLE rent_agent_app` and `SET LOCAL app.current_tenant` (`get_tenant_db`); Company A cannot access Company B's candidates, interviews, KB documents, tool credentials, runtimes, or execution logs.
- **Prompt Injection & Secret Redaction:** Malicious instructions in inline/uploaded resumes are neutralized; leaked API keys (`AIza...`) and database URLs are redacted from HTTP responses and runtime logs.
- **Browser SSRF & Sandbox Allowlist:** `POST /api/v1/hr-agent/browser/inspect` rejects link-local metadata URLs (`http://169.254.169.254/latest/meta-data/` -> `403`); sandbox execution rejects disallowed tasks (`"sh"` -> `403`).

---

## 6. Error Handling Verification (All 8 Modes)

All 8 error-handling categories are covered in `backend/tests/test_end_to_end_system_verification.py`:

| # | Failure Mode | Expected Behavior Verified | Code Location(s) |
| :-: | :--- | :--- | :--- |
| **a** | **LLM provider failure** | Live provider exception caught cleanly; switches to `llm_provider_used == "deterministic_fallback_on_error"`, flags `llm_provider_fallback`, redacts leaked API keys | `backend/agents/framework/llm_provider.py` |
| **b** | **Database errors** | `OperationalError` -> sanitized `HTTP 503` (`database_unavailable`); `SQLAlchemyError` -> sanitized `HTTP 500` (`database_error`); no PostgreSQL credentials/DSN leaked | `backend/app/main.py` |
| **c** | **Corrupted / empty uploads** | Corrupt PDF, empty ZIP/DOCX (`word/document.xml` blank), whitespace TXT, binary NUL TXT rejected with `HTTP 400` + audit log (`POST /api/v1/hr-agent/knowledge` and `/api/v1/rentals/{id}/documents`) | `backend/agents/framework/rag.py`, `backend/app/runtime/document_security.py`, `backend/app/api/v1/hr_agent.py`, `backend/app/api/v1/rentals.py` |
| **d** | **Browser failures & timeouts** | SSRF target -> `403`; Playwright timeout -> `504`; browser crash -> `502` with URL credentials redacted | `backend/app/api/v1/hr_agent.py`, `backend/app/runtime/playwright_browser.py` |
| **e** | **Sandbox failures** | Disallowed task -> `403`; unknown runtime -> `404`; `SandboxTimeoutError` -> `504`; invalid payload `ValueError` -> `400`; runtime crash `RuntimeError` -> `502` | `backend/app/api/v1/hr_agent.py`, `backend/app/runtime/docker_sandbox.py` |
| **f** | **MCP disconnections & timeouts** | Unapproved server -> `403`; unreachable discovery -> `ok: false, connection_status: "unreachable"`; tool timeout -> `504`; broken pipe -> `502` | `backend/app/api/v1/hr_agent.py`, `backend/app/runtime/mcp_client.py` |
| **g** | **Tool execution errors** | Tool failure caught in workflow engine (`node_execute_tools`), flagged `tool_execution_error` in `guardrail_flags` without crashing HTTP execution | `backend/agents/framework/workflow.py` |
| **h** | **Request / execution timeouts** | Workflow timeout budget (`perf_counter`) cleanly halts runaway graph steps and flags `execution_timeout_enforced` | `backend/agents/framework/workflow.py` |

---

## 7. Real Dashboard Analytics (9 Database-Backed KPIs)

`GET /api/v1/hr-agent/workspace` queries live PostgreSQL tenant tables (`JobDescription`, `CandidateProfile`, `InterviewRecord`, `OnboardingWorkflow`, `ExecutionLog`, `TokenUsage`), and `frontend/src/pages/dashboard/OverviewPage.tsx` renders all 9 KPI cards.

**Observed Live Acme Cloud Tenant Snapshot (`http://127.0.0.1:8000/api/v1/hr-agent/workspace`, post-E2E):**

| Dashboard KPI Card | Backend Field | Observed Live Value |
| :--- | :--- | :--- |
| **1. Total Jobs** | `metrics.total_jobs_count` | `6` |
| **2. Total Candidates** | `metrics.candidate_count` | `4` |
| **3. Resumes Analyzed** | `metrics.resumes_analyzed_count` | `4` |
| **4. Interviews Scheduled** | `metrics.scheduled_interviews_count` (of `interview_count: 2`) | `1` |
| **5. Pending Onboarding** | `metrics.pending_onboarding_count` (of `onboarding_count: 2`) | `2` |
| **6. Completed Executions** | `metrics.completed_executions` (of `total_executions: 35`) | `30` |
| **7. Failed Executions** | `metrics.failed_executions` | `0` |
| **8. Token Consumption** | `quota.tokens_used_this_month` (limit `1,000,000`, `3.6%`) | `36,132` |
| **9. Estimated AI Costs** | `metrics.estimated_ai_cost_usd` | `$0.00133` |

*(Automated test `test_all_7_hr_workflows_grounded_data_and_9_dashboard_metrics` additionally verifies `failed_executions` increments accurately when a `status="failed"` `ExecutionLog` record exists in PostgreSQL.)*

---

## 8. Key Bugs Identified & Resolved During Integration Testing

1. **Classifier False Positive on Benefits/Stipend Policy (`classifier.py`):** Query `"What is our home office ergonomics allowance amount and renewal cycle?"` initially triggered out-of-domain rejection; expanded `hr-policy-support` domain vocabulary with workplace benefits terms (`home office`, `ergonomics`, `stipend`, `allowance`, `health insurance`, `probation`, etc.).
2. **Resume Screening Attachment Resolution (`base_agent.py`):** Frontend `ResumeScreeningPage.tsx` submitted selected uploads via `attachments` while `RecruitmentInput` checked `document_ids`; normalized `validate_structured_input` to merge `attachments` into `document_ids`.
3. **Raw Corrupt Resume Filtering Before XML Wrapping (`recruitment_agent.py`):** `_tool_sandbox_ocr_extract` now validates raw resume strings before `_sanitize_resume_text` wraps XML boundaries, preventing malformed/short inputs from looking valid and exposing `invalid_resumes` warnings on `RecruitmentOutput`.
4. **React Render-Cycle Token Overwrite & Employee Audit Log Call (`AppContext.tsx`, `index.html`):**
   - `AppProvider` previously called `loadStoredAuth()` directly in the render body, overwriting `apiClient.config.authToken` with stale `localStorage` data during `setLoadingWorkspace(true)` re-renders and causing a `401` on `GET /api/v1/audit-logs`. Fixed via lazy initialization `useState(() => loadStoredAuth())`.
   - Gated `apiClient.listAuditLogs()` to `["business_owner", "business_admin", "platform_admin"]` to eliminate `403` console noise for `business_employee` sessions.
   - Added inline SVG `<link rel="icon">` in `frontend/index.html` to eliminate `/favicon.ico` `404` console noise.

---

## 9. Verified Environment Limitations

- **No Host Docker Daemon Installed (`development_fallback`):** On the current Windows host, Docker CLI is unavailable (`docker_available: false`). `SandboxManager` cleanly reports `backend_mode: "development_fallback"` and `is_container_isolated: false` and runs tenant-scoped isolated Python child subprocesses with temporary workspace directories rather than Linux container namespaces.
- **Offline Deterministic LLM Mode by Default:** Because external API keys (e.g., Gemini/OpenAI) are unset in the local `.env`, workflow synthesis runs via `deterministic-hr-synthesizer-v1` (with `cost_usd = $0.00` per deterministic run); live provider error handling & redaction are verified using `monkeypatch` on `llm_provider._invoke_live_provider`.
- **Single-Process In-Memory Limiter & Cache:** `rate_limiter` and `tenant_response_cache` operate in process memory for single-worker local deployments.
