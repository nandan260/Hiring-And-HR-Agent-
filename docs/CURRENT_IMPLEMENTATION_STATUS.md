# HireFlow AI — Hiring & HR AI Agent: Current Implementation Status & Audit Report

**Audit Date:** 2026-11-11  
**Repository:** `Hiring-And-HR-Agent-` (`c:\Users\nandan\Desktop\Hiring-And-HR Agent`)  
**Target Product Direction:** Unified single-domain **Hiring & HR AI Agent** (**HireFlow AI**) with internal HR workflows, multi-tenant business isolation, and strict out-of-domain rejection — replacing the multi-category *Rent-an-Agent* marketplace UX while preserving working backend, auth, DB, and LangGraph foundations.

> **Status Legend Used Throughout This Report**
> - **COMPLETED AND TESTED** — Implemented end-to-end and verified with automated tests or runtime checks in this repository.
> - **IMPLEMENTED BUT NOT TESTED** — Implemented in code, but not exercised by automated tests or live browser/external-provider integration runs.
> - **PARTIALLY IMPLEMENTED** — Structural scaffolding, mock adapters, or partial logic exist, but key production mechanics are missing or stubbed.
> - **NOT IMPLEMENTED** — Designed/documented only (or UI/metadata label only) with no executable runtime implementation.

---

## 1. Existing Project Structure

```text
Hiring-And-HR Agent/
├── docker-compose.yml                  # PostgreSQL 16 + backend service definition (no backend/Dockerfile present)
├── docs/
│   ├── AGENT_ARCHITECTURE.md           # Original 7-agent marketplace & LangGraph spec
│   ├── DATABASE_DESIGN.md              # Multi-tenant PostgreSQL + pgvector + RLS schema design
│   ├── IMPLEMENTATION_ROADMAP.md       # Phased MVP -> Production roadmap
│   ├── SECURITY_AND_GUARDRAILS.md      # Threat model, injection, DLP, HITL, SSRF design
│   ├── SYSTEM_DESIGN.md                # End-to-end Rent-an-Agent marketplace architecture
│   ├── TOKEN_OPTIMIZATION.md           # Tiered routing, semantic cache, compression architecture
│   └── CURRENT_IMPLEMENTATION_STATUS.md# This audit report
├── backend/
│   ├── .env.example                    # Env template (LLM keys, JWT, DATABASE_URL, CORS)
│   ├── alembic.ini                     # Alembic migration config
│   ├── alembic/versions/
│   │   ├── 20261111_0001_initial_multi_tenant_schema.py
│   │   └── 20261111_0002_pgvector_and_hr_agent_tables.py
│   ├── requirements.txt                # FastAPI, SQLAlchemy, Alembic, LangGraph, pgvector, pypdf, sqlglot, LLM SDKs
│   ├── app/
│   │   ├── main.py                     # FastAPI entry, CORS, /health, catalog/tenant auto-seed lifespan
│   │   ├── config.py                   # Pydantic Settings + dev Fernet key management
│   │   ├── api/router.py               # /api/v1 router aggregator
│   │   ├── api/v1/
│   │   │   ├── auth.py                 # Register, login, logout (JTI revocation), /me
│   │   │   ├── organizations.py        # Org details, member invite, role updates
│   │   │   ├── marketplace.py          # Marketplace categories (7), plans (3), tools (27), agent catalog
│   │   │   ├── rentals.py              # Rental lifecycle, config updates, tool permissions/secrets, KB upload/download
│   │   │   ├── conversations.py        # Threads & live LangGraph message execution
│   │   │   ├── analytics.py            # Usage summary, token ledger, billing records, execution & audit logs
│   │   │   └── agents.py               # /agents/specs, /rentals/{id}/execute, HITL queue/resolve, candidates, interviews, onboarding
│   │   ├── core/
│   │   │   ├── dependencies.py         # JWT auth principal, get_tenant_db (SET LOCAL RLS), require_roles
│   │   │   ├── security.py             # Argon2id password hashing, JWT encode/decode, Fernet encryption/masking
│   │   │   └── storage.py              # Safe tenant upload path enforcement, extension/MIME/%PDF magic checks, SHA-256
│   │   ├── db/
│   │   │   ├── base.py                 # SQLAlchemy DeclarativeBase + TenantScopedMixin
│   │   │   ├── models.py               # 19 ORM models across auth, catalog, rentals, HR entities, telemetry
│   │   │   ├── session.py              # Engine/session + pgserver embedded fallback + apply_tenant_rls()
│   │   │   └── seed.py                 # Idempotent plans, 27 tools, 7 HR agents, Acme Cloud & NovaBio demo tenants
│   │   ├── schemas/                    # Pydantic request/response DTOs (auth, conversation, marketplace, organization, rental, telemetry)
│   │   └── services/
│   │       ├── audit.py                # AuditLog helper
│   │       └── domain_guard.py         # Unused legacy pre-filter superseded by agents/framework/classifier.py
│   ├── agents/
│   │   ├── registry.py                 # HRAgentRegistry singleton wrapping 7 agent instances + AgentToolBox
│   │   ├── recruitment_agent.py        # Agent 1: Resume screening & blind matching
│   │   ├── jd_generator_agent.py       # Agent 2: Structured JD authoring & inclusive linter
│   │   ├── candidate_shortlisting_agent.py # Agent 3: Fair merit comparison & shortlisting
│   │   ├── interview_scheduling_agent.py   # Agent 4: Slot solver, invites, InterviewRecord persistence
│   │   ├── employee_onboarding_agent.py    # Agent 5: KYC doc verification, checklists, IT/team HITL gates
│   │   ├── employee_support_agent.py       # Agent 6: Handbook RAG + role-filtered citations + escalation
│   │   ├── hr_analytics_agent.py           # Agent 7: sqlglot validator + tenant KPIs + chart JSON
│   │   ├── prompts/*.md                    # 7 dedicated markdown system prompt files
│   │   └── framework/
│   │       ├── base_agent.py           # BaseSpecializedAgent class + prompt loading + memory window + output guardrails
│   │       ├── classifier.py           # Prompt injection, protected-attribute fairness & out-of-domain classifier
│   │       ├── llm_provider.py         # Gemini/OpenAI/Anthropic SDK adapter + deterministic fallback
│   │       ├── rag.py                  # 384-d BLAKE2b embeddings, PDF/DOCX extraction, chunking, pgvector search
│   │       ├── schemas.py              # Pydantic config & I/O base schemas
│   │       ├── state.py                # LangGraph AgentExecutionState TypedDict
│   │       ├── tools.py                # Permission-checked AgentToolBox
│   │       └── workflow.py             # 13-node compiled LangGraph StateGraph
│   └── tests/                          # 13 pytest files (15 test cases total)
└── frontend/
    ├── index.html                      # Currently titled "Rent-an-Agent — Enterprise AI Agent Marketplace (Hiring & HR)"
    ├── package.json                    # React 19, Vite 8, Tailwind v4, React Router v7, lucide-react
    └── src/
        ├── App.tsx                     # Public marketplace + /signin + /dashboard routes
        ├── context/AppContext.tsx      # Auth/session state, live FastAPI client bridge + localStorage demo fallback
        ├── data/catalogData.ts         # Local fallback catalog (all 7 marketplace categories, 7 HR templates, demo tenants)
        ├── services/
        │   ├── apiClient.ts            # Typed REST client covering /auth, /marketplace, /rentals, /conversations, /hitl, /usage
        │   └── demoRuntimeEngine.ts    # Client-side fallback execution simulator when FastAPI backend is offline
        ├── types/agent.ts              # Frontend TypeScript interfaces
        ├── components/
        │   ├── common/                 # Badge, DemoBanner, Modal, StatCard
        │   ├── layout/                 # DashboardLayout, PublicNavbar, PublicFooter
        │   └── marketplace/            # AgentCard, CategoryCard, RentAgentModal
        └── pages/
            ├── public/                 # LandingPage, MarketplacePage, CategoriesPage, AgentDetailsPage, SignInPage
            └── dashboard/              # OverviewPage, MyRentalsPage, UsagePage, TokenConsumptionPage, BillingPage, ExecutionHistoryPage, SettingsPage, AgentWorkspacePage
```

---

## 2. Existing Frontend Pages

| Route | Component | Implementation Status | Notes & Scope Alignment |
|---|---|---|---|
| `/` | `LandingPage.tsx` | `IMPLEMENTED BUT NOT TESTED` | Presents Rent-an-Agent multi-category marketplace, 7 industry verticals, search bar, and pricing cards. Needs rebranding to single **HireFlow AI — Hiring & HR AI Agent** product landing page (or direct HR workflow showcase). |
| `/marketplace` | `MarketplacePage.tsx` | `IMPLEMENTED BUT NOT TESTED` | Multi-category marketplace catalog with Finance/Healthcare/Legal "Coming Soon" pills and "Rent Agent" modal. **Out of target scope — remove from UI.** |
| `/categories` | `CategoriesPage.tsx` | `IMPLEMENTED BUT NOT TESTED` | Displays all 7 Rent-an-Agent marketplace categories. **Out of target scope — remove from UI.** |
| `/marketplace/agents/:slug` | `AgentDetailsPage.tsx` | `IMPLEMENTED BUT NOT TESTED` | Per-agent marketplace listing, pricing box, "Rent Now" trigger. **Out of target scope — remove or convert marketplace framing.** |
| `/signin` | `SignInPage.tsx` | `IMPLEMENTED BUT NOT TESTED` | Supports live JWT login, new business tenant registration, and seeded demo logins (`Acme Cloud`, `NovaBio`), plus offline fallback. Preserve (update subtle marketplace text). |
| `/dashboard` | `OverviewPage.tsx` | `IMPLEMENTED BUT NOT TESTED` | Displays tenant KPIs, pending HITL approval inbox, active agent workspaces, `+ Rent HR Agent` button. Preserve and realign CTA to HR workflows. |
| `/dashboard/rentals` | `MyRentalsPage.tsx` | `IMPLEMENTED BUT NOT TESTED` | Lists rented HR agents with Pause/Activate & marketplace links. Needs removal/replacement in favor of unified HR workflow navigation. |
| `/dashboard/marketplace*` | Embedded `MarketplacePage` / `AgentDetailsPage` | `IMPLEMENTED BUT NOT TESTED` | Embedded marketplace inside dashboard sidebar. **Out of target scope — remove.** |
| `/dashboard/usage` | `UsagePage.tsx` | `IMPLEMENTED BUT NOT TESTED` | Execution metrics & rejection stats; useful telemetry backing Monitoring / Analytics. |
| `/dashboard/tokens` | `TokenConsumptionPage.tsx` | `IMPLEMENTED BUT NOT TESTED` | Displays token consumption, tier distribution bars, cache savings. Needs honest labeling where cache numbers are heuristic estimates. |
| `/dashboard/billing` | `BillingPage.tsx` | `IMPLEMENTED BUT NOT TESTED` | Demo rental billing ledger. Evaluate whether to keep inside Settings or remove if marketplace rental UX is retired. |
| `/dashboard/history` | `ExecutionHistoryPage.tsx` | `IMPLEMENTED BUT NOT TESTED` | Filterable LangGraph trace inspector, classifier results, HITL queue. Maps directly to target **Agent Execution Monitor**. |
| `/dashboard/workspace/:rentalId` | `AgentWorkspacePage.tsx` | `IMPLEMENTED BUT NOT TESTED` | Rich multi-tab workspace (Chat + file attachment, Traces, Tokens, Config, KB upload/RBAC, Integrations/MCP toggles + HITL approval buttons, Analytics charts). Strong asset to preserve and map onto **HR Assistant** + **Knowledge Base** + **Tools & Integrations**. |
| `/dashboard/settings` | `SettingsPage.tsx` | `IMPLEMENTED BUT NOT TESTED` | Backend API toggle/URL, member invitations/role management, immutable audit log viewer. Maps cleanly to target **Settings**. |
| *(Missing Target Pages)* | Standalone **Recruitment**, **Resume Screening**, **Candidates**, **Job Description Generator**, **Interview Management**, **Employee Onboarding**, **HR Assistant**, **HR Analytics**, **Knowledge Base**, **Tools & Integrations** routes | `NOT IMPLEMENTED` | Currently all 7 workflows are accessed indirectly inside `/dashboard/workspace/:rentalId` chats rather than dedicated 13-item sidebar views consuming `/candidates`, `/interviews`, `/onboarding`, KB, and tool integration APIs. |

---

## 3. Existing Backend Architecture

- **Framework & Control Plane (`COMPLETED AND TESTED`)**: FastAPI (`backend/app/main.py`) with lifespan engine boot (`get_engine()`), auto-seeding option (`AUTO_SEED_CATALOG`), CORS middleware, and `/health` PostgreSQL connectivity endpoint.
- **API Router (`backend/app/api/router.py`)**: Mounts 7 `/api/v1` router modules:
  1. `auth.py`: `/auth/register`, `/auth/login`, `/auth/logout` (JTI DB revocation), `/auth/me` — **`COMPLETED AND TESTED`**.
  2. `organizations.py`: `/organizations/current`, `/organizations/members` (list/invite/role update) — **`COMPLETED AND TESTED`**.
  3. `marketplace.py`: `/marketplace/categories`, `/marketplace/plans`, `/marketplace/tools`, `/marketplace/agents`, `/marketplace/agents/{slug}` — **`COMPLETED AND TESTED`** *(Note: still serves marketplace abstractions & 6 "Coming Soon" categories for API compatibility).*
  4. `rentals.py`: `/rentals` CRUD, lifecycle (`activate`/`pause`/`resume`/`cancel`), `/configuration`, `/tools/{tool_id}` toggles & `/credentials` encrypted binding, `/knowledge` upload/download/delete with auto `pgvector` indexing — **`COMPLETED AND TESTED`**.
  5. `conversations.py`: Thread CRUD + `POST /conversations/{id}/messages` invoking `agent_registry.execute(...)` with conversation history — **`COMPLETED AND TESTED`**.
  6. `analytics.py`: `/usage/summary`, `/usage/tokens`, `/billing/records`, `/execution-logs`, `/audit-logs` — **`COMPLETED AND TESTED`**.
  7. `agents.py`: `GET /agents/specs`, `POST /rentals/{rental_id}/execute`, `GET /hitl/approvals`, `POST /hitl/approvals/{approval_id}/resolve` (with domain side effects on `InterviewRecord` and `OnboardingWorkflow`), `GET /candidates`, `GET /interviews`, `GET /onboarding` — **`COMPLETED AND TESTED`** (`GET /agents/specs`, `/execute`, `/hitl/*`, `/candidates`, `/interviews`, `/onboarding` exercised in `test_end_to_end_agents_api.py` and agent tests).
- **Multi-Tenant RLS Session Engine (`COMPLETED AND TESTED`)**: `get_tenant_db()` in `dependencies.py` calls `apply_tenant_rls(db, principal.tenant_id)`, running `SET LOCAL ROLE rent_agent_app` and `set_config('app.current_tenant', :tid, true)`. Never trusts frontend tenant headers or body IDs.
- **Unified Single-Agent Entry Endpoint (`NOT IMPLEMENTED`)**: There is no unified `/api/v1/hr-agent/execute` or single orchestrator endpoint that automatically dispatches among the 7 internal HR sub-workflows without specifying a pre-rented `rental_id` / `agent_slug`.

---

## 4. Existing Database Schema

Managed via Alembic (`alembic upgrade head`, two revisions: `0001_initial_multi_tenant_schema` and `0002_pgvector_and_hr_agent_tables`) running on PostgreSQL 16 + `pgvector 0.6.2`:

- **Platform / Identity Tables (no RLS `tenant_id`, or dual-lookup)**:
  - `users`, `organizations`, `revoked_tokens`, `agent_catalog`, `agent_versions`, `subscription_plans`, `tool_registry` — **`COMPLETED AND TESTED`**.
- **Tenant-Scoped Tables Protected by `ENABLE` + `FORCE ROW LEVEL SECURITY` (`tenant_isolation_*` policies)**:
  - `organization_members`, `agent_rentals`, `agent_configurations`, `agent_conversations`, `messages`, `tool_permissions`, `knowledge_documents`, `execution_logs`, `token_usage`, `billing_records`, `audit_logs` (Migration `0001`) — **`COMPLETED AND TESTED`**.
  - `knowledge_chunks` (`Vector(384)` + HNSW cosine index), `candidates` (`Vector(384)` + HNSW cosine index), `hitl_approvals`, `interviews`, `onboarding_workflows` (Migration `0002`) — **`COMPLETED AND TESTED`**.
- **Missing Domain Tables Relative to Target Sidebar Scope**:
  - Dedicated `job_openings` / `job_requisitions` table (JDs currently return ephemeral JSON without persisted requisition management endpoints) — **`NOT IMPLEMENTED`**.
  - Persistent `semantic_cache` or Redis backing store — **`NOT IMPLEMENTED`**.

---

## 5. Existing HR Workflows

| HR Workflow | Backend Module | Classification | Actual Runtime Capabilities & Honest Limitations |
|---|---|---|---|
| **Recruitment & Resume Screening** | `backend/agents/recruitment_agent.py` | **`COMPLETED AND TESTED`** *(core flow)* / **`PARTIALLY IMPLEMENTED`** *(OCR/portfolio)* | Parses uploaded PDF/DOCX/txt docs via `pypdf`/XML, extracts skills/experience, persists `Candidate` + `Vector(384)` embedding, applies blind PII masking & rubric scoring with quotes, flags human review. Limitation: `sandbox_ocr_extract` runs in-process (no Docker OCR for scanned images/PNGs); `playwright_verify_portfolio` only checks URL prefixes against `github.com`/`gitlab.com`. |
| **Candidate Matching** | `recruitment_agent.py`, `candidate_shortlisting_agent.py` | **`COMPLETED AND TESTED`** | Semantic vector cosine matching + skill overlap rubric scoring against tenant candidate DB pool. |
| **Job Description Generation** | `backend/agents/jd_generator_agent.py` | **`COMPLETED AND TESTED`** *(drafting)* / **`NOT IMPLEMENTED`** *(persistence/ATS push)* | Generates structured `JDGeneratorOutput` (title, level, responsibilities, qualifications, EEO statement), searches leveling KB via `pgvector`, runs deterministic `inclusive_language_linter`, creates HITL request. `playwright_careers_style_check` and `ats_create_draft_req` are stubs; generated JDs are not saved into a dedicated `job_openings` table. |
| **Candidate Shortlisting** | `backend/agents/candidate_shortlisting_agent.py` | **`COMPLETED AND TESTED`** | Queries tenant candidate pool, computes deterministic weighted skill+experience scores without protected characteristics, outputs comparison matrix & HITL shortlist sign-off request. `slack_notify_hiring_manager` is staged/simulated. |
| **Interview Scheduling** | `backend/agents/interview_scheduling_agent.py` | **`COMPLETED AND TESTED`** *(DB + mock calendar)* / **`NOT IMPLEMENTED`** *(live GCal/Playwright)* | Checks existing tenant `InterviewRecord` rows for conflicts, solves timezone slots, persists `InterviewRecord`, and transitions status to `scheduled` upon HITL approval. Uses `mock_google_calendar_adapter`; `playwright_legacy_portal` returns `portal_checked: False`. |
| **Employee Onboarding** | `backend/agents/employee_onboarding_agent.py` | **`COMPLETED AND TESTED`** *(stateful HITL workflow)* / **`NOT IMPLEMENTED`** *(live SCIM/Jira/HRMS)* | Tracks 4 required KYC docs, verifies uploaded docs via `KnowledgeDocument`, creates/updates `OnboardingWorkflow`, builds checklist & training tracks, and gates IT provisioning & team allocation behind 2 HITL approvals (updating progress to 100% when approved). `scim_provision_account`, `jira_create_hardware_ticket`, and `hrms_assign_buddy` are simulated status builders. |
| **Employee Support / HR Policy** | `backend/agents/employee_support_agent.py` | **`COMPLETED AND TESTED`** | Hybrid cosine+lexical search over tenant `pgvector` `knowledge_chunks` enforcing `min_role_access`, refuses ungrounded answers by escalating via HITL, attaches citations. |
| **HR Analytics** | `backend/agents/hr_analytics_agent.py` | **`COMPLETED AND TESTED`** *(KPIs & AST validator)* / **`PARTIALLY IMPLEMENTED`** *(chart rendering/SQL execution)* | Validates optional custom SQL via `sqlglot` AST (`SELECT`-only over 5 whitelisted tables), aggregates live KPIs across `Candidate`, `InterviewRecord`, `OnboardingWorkflow`, `ExecutionLog`, and `TokenUsage`, returns Recharts-ready JSON specs. Limitations: `custom_sql_query` is validated only, not dynamically executed; `sandbox_python_chart` builds JSON specs in-process (no Matplotlib/Plotly container); k-anonymity cohort >= 5 suppression is mentioned in metadata/seed descriptions rather than enforced across arbitrary cohorts. |

---

## 6. Existing AI Agent Implementation

- **Architecture Pattern**: `backend/agents/registry.py` instantiates **7 separate `BaseSpecializedAgent` classes** bound to `HRAgentRegistry`, all executed through one shared 13-node compiled LangGraph `StateGraph` (`COMPILED_HR_WORKFLOW` in `backend/agents/framework/workflow.py`):
  `authenticate -> validate_tenant -> classify_intent -> classify_domain -> check_permissions -> validate_input -> select_agent -> execute_agent -> execute_tools -> validate_output -> check_guardrails -> build_response -> log_execution`.
- **Per-Agent Declarations**: Each of the 7 agents defines `agent_id`, `agent_version`, markdown prompt in `backend/agents/prompts/*.md`, `DomainDefinition`, typed Pydantic `input_schema` & `output_schema`, `allowed_tools`, `ToolPermissionConfig`, `KnowledgeBaseConfig`, `ModelConfig`, `GuardrailConfig`, `MemoryConfig`, and `ExecutionLimits`.
- **Gap vs Corrected Single-Agent Scope**:
  - Today, the user must pick 1 of 7 separate rented agents (`recruitment-screening`, `jd-generator`, etc.).
  - Worse, `classify_domain_boundary()` (`backend/agents/framework/classifier.py:177-189`) actively **rejects** valid cross-HR queries sent to the wrong specialist (e.g., asking the Recruitment agent about PTO) and tells the user to switch agents in the marketplace.
  - Under the corrected single-agent scope (`HireFlow AI`), an internal HR **workflow router** must route any in-domain Hiring & HR query seamlessly to the appropriate internal workflow(s) while keeping strict backend rejection for non-HR queries.
- **LLM Integration**:
  - `ConfigurableLLMProvider` (`backend/agents/framework/llm_provider.py`): Deterministic structured synthesis is **`COMPLETED AND TESTED`**. Live Google Gemini (`google-genai`), OpenAI (`openai`), and Anthropic (`anthropic`) API calls are **`IMPLEMENTED BUT NOT TESTED`** (no API keys configured in local environment; live JSON responses and exceptions gracefully fall back to deterministic synthesis).

---

## 7. Working Features (Verified)

All items below are directly verified via `.\.venv\Scripts\pytest.exe -v` (**15 passed in 15.01s**), `npm run build` (**1.31s, 0 TS/Vite errors**), and live HTTP checks against `uvicorn` (`:8000`) + Vite (`:5173`):
1. Multi-tenant PostgreSQL 16 + `pgvector` schema & Alembic migrations (`0001`, `0002`) with `FORCE ROW LEVEL SECURITY` verified across tenants.
2. JWT authentication, Argon2id password hashing, database-backed JTI logout revocation, and organization member RBAC (`platform_admin`, `business_owner`, `business_admin`, `business_employee`).
3. Fernet encryption at rest + masked display for tool credentials (`tool_permissions.encrypted_secret`).
4. Tenant-isolated file upload validation (extension allowlist, MIME check, `%PDF` magic-byte check, 10 MB cap, filename sanitization, path traversal guard, SHA-256) + auto chunking & indexing into `pgvector`.
5. Shared 13-node LangGraph workflow with `ExecutionLog`, `TokenUsage`, `AuditLog`, and `HitlApproval` persistence.
6. All 7 HR specialized agent pipelines (deterministic synthesis, structured Pydantic I/O validation, pgvector RAG with role filtering, HITL resolution updating DB interview/onboarding states, `sqlglot` AST check).
7. Frontend TypeScript + Tailwind v4 SPA connecting live to FastAPI (`Overview`, `ExecutionHistory`, `AgentWorkspace` with HITL controls & analytics chart rendering, `Settings`) with automatic offline Demo Mode fallback.

---

## 8. Partially Implemented Features

1. **Unified Hiring & HR Agent Experience**: Core 7 workflows exist, but are exposed as 7 separate marketplace rentals with cross-HR rejection instead of one unified assistant with internal workflow routing.
2. **Intent & Domain Classifier**: Prompt injection, bias patterns, and out-of-domain signatures work deterministically via regex + keyword counts (`classifier.py`), but there is no Tier-1 semantic embedding boundary or Tier-2 fast-SLM adjudicator, and rejection copy references "Marketplace Category".
3. **LLM Model Routing & Cost Controls**: `model_routing_tier` and `ModelConfig.model_tier` exist as metadata/config, and `LLM_FAST_MODEL` exists in `config.py`, but `llm_provider.py` does not dynamically route Tier 0 -> Tier 1 -> Tier 2 -> Tier 3 based on confidence or task complexity.
4. **Conversation Memory & Summarization**: Last `N` messages (`short_term_window_messages`) are loaded and older messages are concatenated via substring truncation (`[:120]`) into `summary_memory`; there is no LLM semantic summarization or cross-thread long-term company HR memory store.
5. **HR Analytics**: Live KPIs + chart payloads + SQL AST validator work, but arbitrary validated SQL is not executed against PostgreSQL views, charts are JSON specs rather than sandboxed rendered plots, and automated k-anonymity cohort >= 5 suppression is not implemented on dynamic breakdowns.
6. **Workspace Navigation Structure**: Dashboard has 8 rental/marketplace/telemetry pages; the 13 domain-centric HR navigation views requested in Section 3 only exist in fragmented form inside `AgentWorkspacePage.tsx` or backend list APIs.
7. **Tool / Connector Governance**: Permission toggles and encrypted credential storage are fully implemented; actual external execution connectors (Greenhouse, Lever, Google Calendar, Okta SCIM, Jira, Slack, BambooHR) are mock/staged adapters.

---

## 9. Missing Features

1. **Dockerized / Containerized Sandbox Execution** (`docker_runner.py`, worker image, `backend/Dockerfile`).
2. **Real Playwright Browser Automation Engine** (ephemeral `BrowserContext`, Accessibility Tree distillation, SSRF DNS/IP/redirect blocking).
3. **Real MCP Protocol Client / Server Transports** (`mcp` Python SDK, stdio/SSE/Streamable-HTTP bridges).
4. **Unified Internal HR Workflow Router Node** allowing one single HR Agent endpoint & chat interface to route seamlessly between Recruitment, JD, Shortlisting, Scheduling, Onboarding, Policy Support, and Analytics.
5. **Dedicated Frontend Pages for the 13 HR Navigation Items** (e.g., Candidates pipeline view, Job Descriptions view & DB persistence, Interview calendar tracker UI, Onboarding tracker UI, unified HR Assistant, dedicated Knowledge Base & Tools/Integrations hubs).
6. **Semantic Response Cache (Redis)** and exact token counting (`tiktoken`).
7. **Advanced PDF / Document Injection Defenses** (e.g., PyMuPDF font-size / white-text / hidden-layer inspection, OCR image rasterization inside sandbox).
8. **Production Controls**: Rate limiting, refresh-token rotation, automated frontend tests (Vitest / Playwright E2E), live external API integration tests.

---

## 10. Duplicate or Unnecessary Modules

| File / Symbol | Finding | Recommendation |
|---|---|---|
| [`backend/app/services/domain_guard.py`](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/backend/app/services/domain_guard.py) (`evaluate_domain_and_injection`) | Unused leftover from Phase 1; completely superseded by `backend/agents/framework/classifier.py` (`classify_user_intent`, `classify_domain_boundary`). Zero active callers in the repo. | Remove cleanly after confirming no external scripts import it. |
| [`frontend/src/data/catalogData.ts`](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/data/catalogData.ts) (`AGENT_CATEGORIES`, non-HR demo items) | Contains 6 non-HR coming-soon verticals (`Business and Finance`, `Healthcare`, `Customer Support and Sales`, `Legal and Compliance`, `Education`, `Operations and Internal Work`) and marketplace pricing narratives. | Strip multi-category marketplace constants; retain only HR workflow metadata aligned with HireFlow AI. |
| Marketplace Routes/Components (see Section 11) | Unnecessary marketplace storefront layer conflicts with single Hiring & HR product scope. | Remove from user-facing navigation and routes while keeping backend DB tables untouched unless needed. |

---

## 11. Marketplace-Related Components to Remove from the UI

Per the corrected **Hiring & HR AI Agent (`HireFlow AI`)** product scope, remove or replace these marketplace-focused UI files, routes, and copy:

1. **Public Marketplace Pages to Remove from Routes & App**:
   - `frontend/src/pages/public/MarketplacePage.tsx` (`/marketplace`, `/dashboard/marketplace`)
   - `frontend/src/pages/public/CategoriesPage.tsx` (`/categories`)
   - `frontend/src/pages/public/AgentDetailsPage.tsx` (`/marketplace/agents/:slug`, `/dashboard/marketplace/agents/:slug`)
2. **Marketplace UI Components to Remove**:
   - `frontend/src/components/marketplace/CategoryCard.tsx`
   - `frontend/src/components/marketplace/AgentCard.tsx`
   - `frontend/src/components/marketplace/RentAgentModal.tsx`
3. **Navigation, Layout & Branding Cleanup**:
   - `frontend/index.html`: Change `<title>` from *Rent-an-Agent — Enterprise AI Agent Marketplace* to **HireFlow AI — Hiring & HR AI Agent**.
   - `frontend/src/components/layout/PublicNavbar.tsx`: Remove *Marketplace*, *Categories*, *Pricing* links and *Rent-an-Agent* branding; use **HireFlow AI**.
   - `frontend/src/components/layout/PublicFooter.tsx`: Remove marketplace/categories links and update branding to **HireFlow AI**.
   - `frontend/src/pages/public/LandingPage.tsx`: Remove search marketplace bar, 7-category grid, "Rent Specialized AI Agents" hero copy, pricing tiers, and `RentAgentModal`; reframe around **HireFlow AI — Unified Hiring & HR AI Agent**.
   - `frontend/src/components/layout/DashboardLayout.tsx`: Replace `Rent-an-Agent` sidebar branding, `Agent Marketplace`, `My Rented Agents`, `Billing`, and `+ Rent` shortcuts with **HireFlow AI** and the 13 Hiring & HR navigation items.
   - `frontend/src/pages/dashboard/OverviewPage.tsx`, `MyRentalsPage.tsx`, `BillingPage.tsx`: Remove `+ Rent HR Agent` CTAs and multi-agent rental marketplace copy (archive/replace `MyRentalsPage` & `BillingPage` routes unless an Admin workspace plan view is retained under Settings).
   - `frontend/src/pages/dashboard/AgentWorkspacePage.tsx`: Change `Suggested Marketplace Category:` rejection notice (`line 368`) to clean HR domain boundary messaging.
   - **Backend User-Facing Response Copy Cleanup (non-structural)**:
     - `backend/agents/framework/workflow.py` (`line 502`: `"Suggested Marketplace Category:"`), `backend/agents/framework/classifier.py` (`lines 185, 198`: `"switch to that specialized HR agent in your marketplace"`), and `backend/app/api/v1/marketplace.py` (`MARKETPLACE_CATEGORIES` non-HR items) — update messaging so API replies never direct users to a marketplace.

---

## 12. Sandbox Implementation Status

- **Classification:** **`COMPLETED AND TESTED`** *(Docker hardened CLI runner + honest `development_fallback` subprocess sandbox when Docker daemon is unavailable)*
- **Verified Evidence:**
  - `backend/Dockerfile` and `backend/Dockerfile.sandbox` define non-root `10001:10001` worker containers running `app/runtime/sandbox_worker.py`.
  - `backend/app/runtime/docker_sandbox.py` (`DockerSandboxManager` / `sandbox_manager`) provides per-tenant workspace isolation (`SANDBOX_ROOT/<tenant_id>/<runtime_id>`), lifecycle management (`create_runtime`, `start_runtime`, `stop_runtime`, `restart_runtime`, `destroy_runtime`, `get_runtime_status`), PostgreSQL persistence via `AgentSandboxRuntime`, secret-redacted execution logs (`app/runtime/redaction.py`), `psutil` resource sampling, timeout enforcement, and hardened Docker CLI flags (`--network=none`, `--read-only`, `--cap-drop=ALL`, `--security-opt=no-new-privileges:true`, `--user=10001:10001`, zero Docker socket mount).
  - When Docker CLI/daemon is unavailable on the host, the manager transparently runs an isolated child Python worker under `development_fallback` (`is_container_isolated=False`) rather than faking container isolation.
  - All sandbox tools (`sandbox_ocr_extract`, `sandbox_weighted_ranker`, `sandbox_kyc_ocr_verify`, `sandbox_python_chart`) and core runtime parsers delegate into `sandbox_manager.execute_task(...)` and are verified in `backend/tests/test_runtime_infrastructure.py`.

---

## 13. Browser Implementation Status

- **Classification:** **`COMPLETED AND TESTED`** *(Real headless Playwright engine + SSRF / DNS-rebinding / domain allowlist enforcement)*
- **Verified Evidence:**
  - `playwright` is installed (`playwright-1.65.0` in `backend/.venv`, listed in `backend/requirements.txt`).
  - `backend/app/runtime/playwright_browser.py` (`BrowserSessionManager` / `browser_manager` + `validate_browser_url`) isolates each call in a fresh per-tenant ephemeral `BrowserContext` (`accept_downloads=False`, zero cookie persistence), intercepts subresources/redirects via `context.route("**/*", ...)`, blocks `localhost`, private RFC1918 networks, `169.254.0.0/16` metadata IP, and `file://` schemes, enforces tenant/default domain allowlists, supports approval-gated form filling and PNG screenshot capture, and wraps extracted text in `<untrusted_webpage_content>`.
  - `playwright_verify_portfolio` (`recruitment_agent.py`), `playwright_careers_style_check` (`jd_generator_agent.py`), `playwright_legacy_portal` (`interview_scheduling_agent.py`), and core tool `browser_search` use `browser_manager`.
  - `workflow.py` records honest `browser_activity_json` (`"not_used"` when browser tools were not invoked, or real target URLs/actions/screenshots when invoked).

---

## 14. MCP Implementation Status

- **Classification:** **`COMPLETED AND TESTED`** *(Real `mcp` 2.3.0 SDK client manager + Admin approval governance & audit logging)*
- **Verified Evidence:**
  - `mcp` (`mcp-2.3.0`) and `jsonschema` (`jsonschema-4.26.0`) are installed and declared in `backend/requirements.txt`.
  - `backend/app/runtime/mcp_client.py` (`McpClientManager` / `mcp_manager`) supports `stdio` (`stdio_client`) and `sse` (`sse_client`) transports via `mcp.ClientSession`, defaults new servers to untrusted (`is_approved=False`, `approval_status="pending_approval"`), rejects SSRF URLs and shell wrapper commands, validates tool arguments against discovered JSON schemas, enforces per-tool RBAC and `ToolPermission`, resolves Fernet-encrypted credentials (`encrypted_secret`) without secret leakage, and persists every call in `McpExecutionLog` and `AuditLog`.
  - Managed via `/api/v1/hr-agent/mcp/*` endpoints and surfaced in `ToolsIntegrationsPage.tsx`, alongside the 10-tool schema-documented `StructuredHRToolRegistry` (`backend/app/runtime/tool_registry.py`) and real-time `ExecutionMonitorTracker` (`backend/app/runtime/monitor.py`, `ExecutionHistoryPage.tsx`).

---

## 15. Classifier and Guardrail Status

| Control | Classification | Verified Implementation Details |
|---|---|---|
| Prompt injection regex scanner (`PROMPT_INJECTION_PATTERNS`) | **`COMPLETED AND TESTED`** | Blocks instruction override, prompt/secret exfiltration, and RLS/tenant bypass attempts before tool execution (`classifier.py:7-14, 92-93, 125-134`), verified in `test_framework_workflow.py`. |
| HR fairness & protected-characteristic blocker | **`COMPLETED AND TESTED`** | Blocks requests attempting to rank/filter/exclude candidates by age, gender, religion, caste, disability, ethnicity, race, etc., and validates outputs in `BaseSpecializedAgent.apply_domain_guardrails()` (`test_agent_3_shortlisting.py`). |
| Out-of-domain blocker (Medical, Finance/Trading, Legal, Personal tasks) | **`COMPLETED AND TESTED`** | Short-circuits Graph before `select_agent` / `execute_tools` (`classifier.py:28-61`), returning polite rejection (`test_framework_workflow.py`). |
| Human-in-the-Loop (HITL) persistence & gating | **`COMPLETED AND TESTED`** | Persists `HitlApproval` rows for scorecards, JD requisitions, shortlists, interview invites, IT provisioning, team allocation, and HR policy escalations; role-restricted resolution triggers DB side effects (`test_end_to_end_agents_api.py`). |
| Prohibit autonomous candidate auto-rejection guardrail | **`COMPLETED AND TESTED`** | Enforced in `base_agent.py:34-36, 150-154` and agent synthesis outputs (`human_review_required = True`). |
| Citation grounding check (`require_citation_grounding`) | **`COMPLETED AND TESTED`** | Enforced on `EmployeeSupportAgent`; ungrounded policy queries refuse to hallucinate and create HITL escalations (`test_agent_6_employee_support.py`). |
| Indirect PDF hidden-text / white-text injection scanner | **`NOT IMPLEMENTED`** | `pypdf` extracts visible text with regex sanitization only (`_sanitize_resume_text`); no font-size, color, or invisible layer inspection exists. |
| Embedding / SLM Tier-1 & Tier-2 domain classifiers | **`NOT IMPLEMENTED`** | `classifier.py` relies purely on regex signatures + literal substring keyword matching (`domain.in_domain_keywords`). Subtle out-of-domain queries without matching keywords rely on keyword miss (`hits < min_keyword_hits`). |
| Cross-HR routing inside single agent | **`PARTIALLY IMPLEMENTED` (misaligned)** | `CROSS_HR_AGENT_HINTS` currently **blocks** cross-HR questions rather than routing internally between Recruitment, Scheduling, Onboarding, Policy, and Analytics workflows. |

---

## 16. Token Optimization Status

| Optimization Technique | Classification | Verified Implementation Details |
|---|---|---|
| Token usage DB ledger (`TokenUsage` + `/usage/*` APIs) | **`COMPLETED AND TESTED`** | Records `input_tokens`, `cached_tokens`, `output_tokens`, `estimated_cost_usd`, and `model_id` per run in PostgreSQL (`test_framework_workflow.py`). |
| Zero-token early rejection (`classify_domain` pre-LLM short-circuit) | **`COMPLETED AND TESTED`** | Out-of-domain & injection queries terminate before `execute_tools` / `validate_output`, incurring 0 LLM tokens (`workflow.py:604-605`). |
| Input token limit enforcement (`max_input_tokens`) & context truncation | **`COMPLETED AND TESTED`** | `node_validate_input` blocks oversized inputs (`workflow.py:296-305`); `llm_provider.py:122` caps JSON context at `[:9000]` chars. |
| Conversation short-term windowing + naive summary | **`PARTIALLY IMPLEMENTED`** | `BaseSpecializedAgent.build_memory_context()` keeps last `N` messages and concatenates `[:120]` snippets of up to 6 older messages into `AgentConversation.summary_memory` — no LLM abstractive compression or exact token budget counting (`tiktoken`). |
| Prompt caching & cache accounting | **`PARTIALLY IMPLEMENTED`** | System prompts stay static at prefix position (`llm_provider.py:136, 158, 174`), which is compatible with provider prefix caching, **but** `cached_tokens` reported in telemetry (`llm_provider.py:64, 103`) is a **synthetic estimate** (`len(system_prompt)/4` or `approx_in * 0.55`) rather than actual provider cache-read counters or local cache hits. |
| Confidence-based Model Routing (`Tier 0 -> Tier 1 SLM -> Tier 2 Flash -> Tier 3 Frontier`) | **`NOT IMPLEMENTED`** | Only metadata fields exist (`model_routing_tier`, `ModelConfig.model_tier`, unused `Settings.LLM_FAST_MODEL`); `ConfigurableLLMProvider` invokes a single `LLM_DEFAULT_MODEL` or deterministic synthesizer. |
| Tenant-isolated Redis Semantic / Response Cache | **`NOT IMPLEMENTED`** | No Redis container, client library, or semantic cache lookup exists anywhere in backend runtime (`UsagePage` cache hit stat relies on synthetic demo runs). |

---

## 17. Security Gaps

1. **Over-permissive `business_employee` execution allow-list in LangGraph (`workflow.py:268-276`)**: `node_check_permissions` includes all 7 agent IDs (`hr-analytics`, `candidate-shortlisting`, `recruitment-screening`, `jd-generator`, etc.) inside the allow-list for `business_employee`, allowing non-admin employees to invoke recruiting/analytics workflows unless restricted at higher RBAC boundaries.
2. **Untrusted / Uncontainerized Execution of Uploaded Content & Tools**: Resumes, PDFs, DOCX, and analytics code execute directly in the main FastAPI process (`NOT IMPLEMENTED` Docker sandbox), increasing blast radius if a parser vulnerability (e.g., `pypdf` / `zipfile` / regex DoS) is triggered.
3. **Lack of Hidden-Text / Visual Prompt-Injection Scanning on PDFs**: While visible `ignore previous instructions` text is regex-sanitized, subtle prompt injections or zero-opacity PDF layers are not inspected.
4. **No HTTP Rate Limiting / Brute-Force Protection**: `/api/v1/auth/login`, `/auth/register`, and `/rentals/{id}/execute` have no per-IP or per-tenant rate limiter.
5. **Development Secret Defaults**: Neither `backend/.env` nor `frontend/.env` exists locally; `config.py` falls back to default dev `JWT_SECRET_KEY` and writes a local `.dev_fernet.key` unless `APP_ENV=production` is set.
6. **Direct Execution Paths & Non-Atomic File Scanning**: Uploaded files are verified for extension/MIME/`%PDF` header and tenant path confinement, but have no malware/antivirus scan (e.g., ClamAV).
7. **Token Quota Soft-Only on Backend**: `AgentConfiguration.monthly_token_quota` is persisted and displayed in the UI (`RentAgentModal` / `TokenConsumptionPage`), **but `workflow.py` does not enforce a hard block when `TokenUsage` exceeds `monthly_token_quota`** on backend `/execute` or `/messages` calls (quota blocking only exists inside frontend `demoRuntimeEngine.ts`).

---

## 18. Recommended Next Implementation Steps

Ordered safely to execute the **Scope Correction** first without breaking working tests or schema foundations:

1. **Step 1 — Backend Unified HR Orchestrator & Scope Alignment (Non-Destructive)**:
   - Refactor `backend/agents/framework/classifier.py` so `CROSS_HR_AGENT_HINTS` becomes an **internal HR workflow router** rather than rejecting cross-HR questions to a marketplace, while keeping hard rejections for non-HR domains (medical, finance/trading, legal litigation, general tasks) without referencing *"Suggested Marketplace Category"*.
   - Add a unified `/api/v1/hr-agent/execute` (and `/api/v1/hr-agent/conversations/...`) entrypoint orchestrated by one logical **HireFlow AI** HR Assistant that auto-routes requests across the 7 internal workflows while preserving existing `/rentals/*` APIs if needed for existing tests or deprecating gracefully.
   - Tighten RBAC in `workflow.py:node_check_permissions` (e.g., restrict `hr-analytics` and `candidate-shortlisting` or allow configurable role matrix) and enforce backend `monthly_token_quota` caps in `node_validate_tenant`.
   - Remove unused duplicate `backend/app/services/domain_guard.py`.

2. **Step 2 — Frontend Scope Correction & 13-Item HR Navigation**:
   - Remove/de-route all marketplace pages & components (`MarketplacePage`, `CategoriesPage`, `AgentDetailsPage`, `CategoryCard`, `AgentCard`, `RentAgentModal`) and strip the 6 non-HR categories from `catalogData.ts`.
   - Update branding across `index.html`, `PublicNavbar`, `PublicFooter`, `LandingPage`, `DashboardLayout`, and `OverviewPage` to **HireFlow AI — Hiring & HR AI Agent**.
   - Implement the exact 13 navigation routes inside `DashboardLayout.tsx` and `App.tsx`, connecting dedicated UI views to live backend APIs (`/candidates`, `/interviews`, `/onboarding`, `/execution-logs`, `/hitl/approvals`, KB documents, tool permissions):
     1. **Dashboard** (`/dashboard`)
     2. **Recruitment** (`/dashboard/recruitment` + `/candidates` / pipeline overview)
     3. **Resume Screening** (`/dashboard/screening`)
     4. **Candidates** (`/dashboard/candidates`)
     5. **Job Description Generator** (`/dashboard/jd-generator`)
     6. **Interview Management** (`/dashboard/interviews`)
     7. **Employee Onboarding** (`/dashboard/onboarding`)
     8. **HR Assistant** (`/dashboard/assistant`)
     9. **HR Analytics** (`/dashboard/analytics`)
     10. **Agent Execution Monitor** (`/dashboard/monitor`)
     11. **Knowledge Base** (`/dashboard/knowledge-base`)
     12. **Tools and Integrations** (`/dashboard/integrations`)
     13. **Settings** (`/dashboard/settings`)

3. **Step 3 — Runtime Isolation, Real Browser/MCP Bridges & Security Hardening (`COMPLETED` — Verified 2026-11-11)**:
   - Implemented `backend/Dockerfile`, `backend/Dockerfile.sandbox`, and `DockerSandboxManager` (`--network=none`, `--read-only`, `--cap-drop=ALL`, `--user=10001:10001`) with honest `development_fallback` when Docker daemon is unavailable (`docs/RUNTIME_INFRASTRUCTURE_REPORT.md`).
   - Replaced stubbed `playwright_*` handlers with SSRF-hardened ephemeral Playwright `BrowserContext` (`BrowserSessionManager`) and real telemetry in `ExecutionMonitorTracker`.
   - Wired real `mcp` 2.3.0 SDK client transport (`McpClientManager`), 10-tool `StructuredHRToolRegistry`, and Alembic Migration `0003`.

4. **Step 4 — Hybrid Classification, Domain Exemptions, Guardrails, Token Optimization & Knowledge Graph (`COMPLETED` — Verified 2026-11-11)**:
   - **Hybrid Intent & Domain Classifier (`backend/agents/framework/classifier.py`)**: Deterministic fast path + ambiguous-case LLM fallback (`_llm_classify_ambiguous_intent`), structured `IntentClassification` (`risk_level`, `required_tools`, `required_permissions`, `needs_clarification`), and `HR_CONTEXT_EXEMPT_RX` protecting legitimate HR benefits/equity prompts while rejecting out-of-domain queries with zero tool calls (`POST /api/v1/hr-agent/classify`).
   - **Defense-in-Depth Guardrails (`guardrails.py`, `redaction.py`, `document_security.py`, `rate_limiter.py`)**: Base64 + direct prompt injection scan, NUL/control/token-cap/repetition-bomb checks, PostgreSQL NUL sanitization, HR fairness & anti-auto-reject rules, disguised executable/PDF JS/DOCX macro & XXE/script-smuggling upload scanner, inline CV injection neutralization, sliding-window rate limiting (`429` + `Retry-After`), and per-workflow/per-tool RBAC checks (`403`).
   - **Honest Token Optimization & Knowledge Graph (`optimizer.py`, `rag.py`, `hr_knowledge_graph.py`, Alembic `20261111_0004`)**: Real baseline vs. optimized token tracking (`POST /api/v1/hr-agent/optimization/compare`, enriched `GET /api/v1/hr-agent/usage`), prompt/history/chunk compression, model tier routing, tenant-scoped TTL cache with automatic mutation invalidation, Obsidian Markdown export (`GET /api/v1/hr-agent/knowledge/{doc_id}/markdown`), PostgreSQL RLS-scoped skill/policy graph (`GET /api/v1/hr-agent/knowledge-graph`), and updated UI panels (`HrAnalyticsPage.tsx`, `KnowledgeBasePage.tsx`, `ExecutionResultPanel.tsx`). Full details in `docs/INTELLIGENCE_GUARDRAILS_AND_OPTIMIZATION.md`.
   - **Verification**: `pytest -v` **35 passed, 0 failed** (`tests/test_intelligence_guardrails_optimization.py` + all 28 prior tests); frontend `npm run build` exited `0`; live endpoints verified on `127.0.0.1:8000` & `127.0.0.1:5173`.
   - **Remaining Optional Future Work**: Redis backing for multi-worker cache/rate-limiter scaling, live Docker daemon provisioning on Windows host for container-isolated runtime mode, and automated Playwright browser E2E UI tests.
