# HireFlow AI — Secure Agent Runtime Infrastructure Report

**Date:** 2026-11-11  
**Project:** HireFlow AI — Hiring & HR AI Agent (`Hiring-And-HR Agent`)  
**Migration Head:** `20261111_0003` (`Secure agent runtime infrastructure tables and telemetry`)

---

## 1. Executive Summary

We extended the existing **HireFlow AI** platform with multi-tenant, security-hardened agent runtime infrastructure across five subsystems without replacing existing agent workflows or PostgreSQL Row-Level Security (`FORCE ROW LEVEL SECURITY`) guarantees:

1. **Docker Sandbox & Honest Development Fallback** (`backend/app/runtime/docker_sandbox.py`, `backend/app/runtime/sandbox_worker.py`, `backend/Dockerfile`, `backend/Dockerfile.sandbox`)
2. **SSRF-Hardened Isolated Playwright Browser** (`backend/app/runtime/playwright_browser.py`)
3. **Structured HR Tool Registry (10 Explicit Core Tools + Workflow Tools)** (`backend/app/runtime/tool_registry.py`)
4. **MCP Protocol Client Manager & Governance** (`backend/app/runtime/mcp_client.py`)
5. **Real-Time & Persisted Execution Telemetry Monitor & UI** (`backend/app/runtime/monitor.py`, `frontend/src/pages/dashboard/ExecutionHistoryPage.tsx`, `frontend/src/pages/dashboard/ToolsIntegrationsPage.tsx`)

> **Honest Local Host Notice:** Docker CLI is **not installed** on this Windows development host (`docker_available: false`). The runtime manager detects this cleanly, reports `"Docker CLI is not installed on host; using development_fallback"`, and executes tasks inside isolated child Python subprocesses with `is_container_isolated = false` instead of simulating or claiming container isolation.

---

## 2. Subsystem Architecture & Security Controls

### 2.1 Sandbox Runtime Manager (`DockerSandboxManager` / `sandbox_manager`)
- **Per-Tenant Workspace Isolation:** Assigns each tenant runtime an isolated directory under `SANDBOX_ROOT/<tenant_id>/<runtime_id>`, plus persistent state in PostgreSQL table `agent_sandbox_runtimes` (`AgentSandboxRuntime` with RLS).
- **Lifecycle API:** Implements `create_runtime`, `start_runtime`, `stop_runtime`, `restart_runtime`, `destroy_runtime`, `get_runtime_status`, `list_runtimes`, and `execute_in_runtime` (exposed under `/api/v1/hr-agent/runtimes*`).
- **Hardened Container Flags (Docker mode):** Builds least-privilege Docker commands with `--network=none`, `--read-only`, `--cap-drop=ALL`, `--security-opt=no-new-privileges:true`, `--user=10001:10001`, `--cpus`, `--memory`, `--pids-limit`, and zero Docker socket mount (`/var/run/docker.sock` is never mounted or exposed to the LLM).
- **Whitelisted Worker Execution (`sandbox_worker.py`):** Accepts JSON payloads over `stdin` for whitelisted tasks (`noop_ping`, `probe_delay`, `parse_pdf_resume`, `parse_docx_resume`, `rank_candidates_weighted`, `verify_kyc_document`, `compute_analytics_charts`) rather than arbitrary shell execution; path-traversal attempts fail with exit code `3` and raise `SandboxSecurityError` (HTTP `403`).
- **Resource Monitoring & Secret Redaction (`redaction.py`):** Samples CPU/memory via `psutil` and scrubs secret patterns (`redact_secrets_in_text`, `sanitize_structured_payload`) from execution logs. Enforces execution timeouts (`SandboxTimeoutError`, HTTP `504`).

### 2.2 Isolated Playwright Browser (`BrowserSessionManager` / `browser_manager`)
- **Ephemeral Per-Run Contexts:** Uses `playwright-1.65.0` with Chromium/Edge fallback and creates a clean ephemeral `BrowserContext` per inspection (`accept_downloads=False`, zero cookie persistence).
- **SSRF & Redirect Protection (`validate_browser_url` + subresource routing):** Blocks `localhost`, loopback (`127.0.0.1`), RFC1918 private ranges, link-local / cloud metadata IP `169.254.0.0/16`, and non-HTTP schemes (`file://`), validates DNS resolution results against private networks, intercepts subresources/redirects via `context.route("**/*", ...)`, and restricts hosts against tenant/default domain allowlists.
- **Content Safety:** Extracts visible text wrapped inside `<untrusted_webpage_content>` delimiters (`strip_untrusted_webpage_text`), supports optional PNG screenshot capture, and powers `browser_search`, `playwright_verify_portfolio`, `playwright_careers_style_check`, `playwright_legacy_portal`, and `POST /api/v1/hr-agent/browser/inspect`.

### 2.3 Structured HR Tool Registry (`StructuredHRToolRegistry` / `hr_tool_registry`)
- Schema-documented (Pydantic input/output schemas), RBAC-enforced, `ToolPermission`-aware, and timeout-protected registry implementing all **10 core HR tools** plus existing workflow tools (`GET /api/v1/hr-agent/tools?core_only=true`, `POST /api/v1/hr-agent/tools/{tool_id}/execute`):
  1. `resume_pdf_parser`
  2. `resume_docx_parser`
  3. `candidate_database_search`
  4. `job_database_search`
  5. `hr_document_retriever`
  6. `job_description_generator`
  7. `email_draft_generator`
  8. `calendar_availability_checker`
  9. `browser_search`
  10. `onboarding_checklist_manager`

### 2.4 MCP Client Manager (`McpClientManager` / `mcp_manager`)
- **Real MCP 2.3.0 Protocol Support:** Connects over `stdio` (`stdio_client`) and `sse` (`sse_client`) transports using `mcp.ClientSession`.
- **Untrusted-by-Default & Governance:** Newly registered servers (`POST /api/v1/hr-agent/mcp/servers`) default to `is_approved = False` (`approval_status = "pending_approval"`). Shell wrapper binaries and SSRF URLs are rejected on registration (`McpSecurityError`, HTTP `403`).
- **Approval, Discovery & Schema Validation:** Admins/Owners approve servers (`POST /api/v1/hr-agent/mcp/servers/{server_id}/approval`), discover remote tool schemas (`POST .../discover`), configure per-tool RBAC & HITL gates (`PATCH .../permissions`), and execute tools (`POST .../execute`) validated with `jsonschema-4.26.0` (HTTP `422` on invalid args).
- **Credential & Audit Hygiene:** Resolves tenant secrets from `ToolPermission.encrypted_secret` without leaking values and logs all invocations in `mcp_execution_logs` (`McpExecutionLog`) and `audit_logs` (`AuditLog`).

### 2.5 Execution Monitor & Dashboard UI (`ExecutionMonitorTracker` / `monitor_tracker`)
- **Honest Execution Telemetry (`GET /api/v1/hr-agent/monitor`):** Tracks active runs (`active_runs`), `current_task`, `current_workflow`, `tool_calls`, `sandbox_status`, `execution_duration_ms`, and `token_usage` (`input_tokens`, `cached_tokens`, `output_tokens`, `total_tokens`, `estimated_cost_usd`). `browser_activity.status` defaults to `"not_used"` when no browser tool ran (replacing earlier static `"idle"` placeholders).
- **Dashboard Views Updated:**
  - `frontend/src/pages/dashboard/ExecutionHistoryPage.tsx`: Displays sandbox runtime controls (create, start, stop, restart, destroy), honest Docker/fallback isolation status badges, active & completed runs, tool call telemetry, browser inspection status, and token/cost breakdowns.
  - `frontend/src/pages/dashboard/ToolsIntegrationsPage.tsx`: Surfaces the 10 core HR tools, JSON schemas, URL isolated browser inspector test panel, MCP server registration, approval toggle, tool discovery, permission toggles, and execution log audit trail.

---

## 3. Database Migration & Files Modified

- **Migration:** `backend/alembic/versions/20261111_0003_secure_agent_runtime_infrastructure.py`
  - Added `execution_logs.runtime_telemetry_json`
  - Created RLS-enforced tables `agent_sandbox_runtimes`, `mcp_servers`, and `mcp_execution_logs` (`FORCE ROW LEVEL SECURITY`, `GRANT ... TO rent_agent_app`)
- **Backend Files Added / Updated:**
  - `backend/requirements.txt`, `backend/Dockerfile`, `backend/Dockerfile.sandbox`, `backend/app/config.py`
  - `backend/app/db/models.py`, `backend/app/db/seed.py`
  - `backend/app/runtime/{__init__.py,redaction.py,sandbox_worker.py,docker_sandbox.py,playwright_browser.py,mcp_client.py,monitor.py,tool_registry.py}`
  - `backend/agents/framework/{rag.py,tools.py,workflow.py}` and agents (`recruitment_agent.py`, `jd_generator_agent.py`, `candidate_shortlisting_agent.py`, `interview_scheduling_agent.py`, `employee_onboarding_agent.py`, `hr_analytics_agent.py`)
  - `backend/app/api/v1/hr_agent.py`
  - `backend/tests/{conftest.py,test_runtime_infrastructure.py}`
- **Frontend Files Updated:**
  - `frontend/src/types/agent.ts`, `frontend/src/services/apiClient.ts`, `frontend/src/context/AppContext.tsx`
  - `frontend/src/pages/dashboard/{ExecutionHistoryPage.tsx,ToolsIntegrationsPage.tsx}`
- **Documentation Updated:**
  - `docs/CURRENT_IMPLEMENTATION_STATUS.md`, `docs/RUNTIME_INFRASTRUCTURE_REPORT.md`

---

## 4. Verification Results

All checks below ran after all code edits and against migrated database state:

| Check | Command / Target | Observed Result |
|---|---|---|
| Alembic Migration | `alembic upgrade head` (`backend/.pgdata`) | Exited `0`; upgraded `20261111_0002 -> 20261111_0003` |
| Seed Script | `python -m app.db.seed` | Exited `0`; `{'plans': 3, 'tools': 37, 'agents': 7}` |
| Backend Test Suite | `backend\.venv\Scripts\pytest.exe -v` | Exited `0`; **`28 passed, 1 warning in 28.28s`** (all 6 tests in `test_runtime_infrastructure.py` + 22 existing suite tests passed) |
| Frontend Build | `npm run build` (`tsc --noEmit && vite build`) | Exited `0`; `2106 modules transformed`, built in `1.27s` |
| Live API Health & UI | `GET http://127.0.0.1:8000/health`, `GET http://127.0.0.1:5173/` | `200 ok / connected` and `200` (`1045` bytes) |
| Live Core Tools & MCP | `GET /api/v1/hr-agent/tools?core_only=true`, `/mcp/servers` | `200` returning all 10 explicit core tools; `200` on MCP endpoint |
| Live Sandbox Lifecycle | `POST/start/execute/DELETE /api/v1/hr-agent/runtimes` | `201 -> 200 (running) -> 200 (noop_ping, development_fallback, is_container_isolated=False) -> 200 (destroyed)` |
| Live Browser SSRF Block | `POST /api/v1/hr-agent/browser/inspect` (`127.0.0.1`) | Rejected HTTP `403`: `"Blocked private/loopback/metadata IP literal: '127.0.0.1'"` |
| Live Unified Workflow & Telemetry | `POST /api/v1/hr-agent/execute` -> `GET /api/v1/hr-agent/monitor` | `200 completed` (`jd-generator`); monitor recorded `execution_duration_ms=41`, `browser_activity="not_used"`, real `tool_calls`, and `token_usage` (`1317` total tokens) |
