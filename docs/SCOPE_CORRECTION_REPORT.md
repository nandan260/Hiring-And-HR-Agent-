# Scope Correction Phase Report — HireFlow AI — Hiring & HR AI Agent

## 1. Executive Summary

The Scope Correction Phase has transformed the **Hiring & HR AI Agent** repository (`c:\Users\nandan\Desktop\Hiring-And-HR Agent`) from the broader *Rent-an-Agent* marketplace concept into one cohesive, enterprise-grade, multi-tenant **Hiring & HR AI Agent** product branded **`HireFlow AI — Hiring & HR AI Agent`**.

All existing PostgreSQL 16 + `pgvector` schema, Alembic migrations, Row-Level Security (`FORCE ROW LEVEL SECURITY`) tenant isolation, JWT authentication, Fernet credential encryption, pgvector RAG chunking, HITL approval records, and 7 specialized LangGraph HR workflows were preserved intact and consolidated behind a unified `/api/v1/hr-agent/` backend layer and a 13-view React frontend workspace.

---

## 2. Phase 1 — Frontend Scope Correction & 13 Navigation Views

### 2.1 Marketplace Removal & Rebranding
- Updated branding across [frontend/index.html](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/index.html), [frontend/package.json](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/package.json) (`hireflow-hr-ai-agent`), [DemoBanner.tsx](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/components/common/DemoBanner.tsx), [PublicNavbar.tsx](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/components/layout/PublicNavbar.tsx), [PublicFooter.tsx](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/components/layout/PublicFooter.tsx), [LandingPage.tsx](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/pages/public/LandingPage.tsx), [SignInPage.tsx](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/pages/public/SignInPage.tsx), and [DashboardLayout.tsx](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/components/layout/DashboardLayout.tsx) to **HireFlow AI — Hiring & HR AI Agent**.
- Removed marketplace storefront UI, non-HR categories (Finance, Healthcare, Legal, Education, Customer Support, Operations), agent pricing cards, rental checkout buttons, and client-side mock runtime logic:
  - Deleted `frontend/src/components/marketplace/`
  - Deleted `MarketplacePage.tsx`, `CategoriesPage.tsx`, `AgentDetailsPage.tsx`, `MyRentalsPage.tsx`, `BillingPage.tsx`, `UsagePage.tsx`, `TokenConsumptionPage.tsx`, `AgentWorkspacePage.tsx`, and `demoRuntimeEngine.ts`.
- Verified via recursive scan across `frontend/` (`.ts`, `.tsx`, `.html`) that zero user-facing `"Rent-an-Agent"`, `"marketplace"`, `"Rent Now"`, or non-HR category storefront strings remain.

### 2.2 All 13 Authenticated Navigation Views Implemented
Configured in [App.tsx](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/App.tsx) and [DashboardLayout.tsx](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/components/layout/DashboardLayout.tsx), sharing [ExecutionResultPanel.tsx](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/components/common/ExecutionResultPanel.tsx) and [HireFlowApiClient](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/services/apiClient.ts) backed by real FastAPI endpoints:

| # | Sidebar Label | Route | Page Component |
|---|---|---|---|
| 1 | Dashboard | `/dashboard` | [OverviewPage.tsx](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/pages/dashboard/OverviewPage.tsx) |
| 2 | Recruitment | `/dashboard/recruitment` | [RecruitmentPage.tsx](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/pages/dashboard/RecruitmentPage.tsx) |
| 3 | Resume Screening | `/dashboard/screening` | [ResumeScreeningPage.tsx](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/pages/dashboard/ResumeScreeningPage.tsx) |
| 4 | Candidates | `/dashboard/candidates` | [CandidatesPage.tsx](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/pages/dashboard/CandidatesPage.tsx) |
| 5 | Job Description Generator | `/dashboard/jd-generator` | [JdGeneratorPage.tsx](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/pages/dashboard/JdGeneratorPage.tsx) |
| 6 | Interview Management | `/dashboard/interviews` | [InterviewsPage.tsx](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/pages/dashboard/InterviewsPage.tsx) |
| 7 | Employee Onboarding | `/dashboard/onboarding` | [OnboardingPage.tsx](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/pages/dashboard/OnboardingPage.tsx) |
| 8 | HR Assistant | `/dashboard/assistant` | [HrAssistantPage.tsx](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/pages/dashboard/HrAssistantPage.tsx) |
| 9 | HR Analytics | `/dashboard/analytics` | [HrAnalyticsPage.tsx](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/pages/dashboard/HrAnalyticsPage.tsx) |
| 10 | Agent Execution Monitor | `/dashboard/monitor` | [ExecutionHistoryPage.tsx](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/pages/dashboard/ExecutionHistoryPage.tsx) |
| 11 | Knowledge Base | `/dashboard/knowledge-base` | [KnowledgeBasePage.tsx](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/pages/dashboard/KnowledgeBasePage.tsx) |
| 12 | Tools and Integrations | `/dashboard/integrations` | [ToolsIntegrationsPage.tsx](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/pages/dashboard/ToolsIntegrationsPage.tsx) |
| 13 | Settings | `/dashboard/settings` | [SettingsPage.tsx](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/pages/dashboard/SettingsPage.tsx) |

Legacy paths (including old marketplace paths) redirect cleanly to `/` via catch-all route in [App.tsx](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/frontend/src/App.tsx).

---

## 3. Phase 2 — Backend Unified HR Agent & Internal Workflow Routing

### 3.1 Consolidated `/api/v1/hr-agent/*` Router
Added [hr_agent.py](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/backend/app/api/v1/hr_agent.py) (mounted in [router.py](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/backend/app/api/router.py)) and [hr_workspace.py](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/backend/app/services/hr_workspace.py):
- `GET /api/v1/hr-agent/workspace` — automatically provisions missing tenant HR workflow bindings (`ensure_tenant_hr_workflows`, keeping `/auth/register` untouched so existing rental lifecycle contracts remain intact) and returns role permissions, monthly token quota (`get_monthly_token_usage`), and tenant metrics.
- `POST /api/v1/hr-agent/execute` — unified single-agent execution endpoint that classifies and routes user prompts internally across all 7 HR workflows (`resolve_workflow_slug`), executes LangGraph (`agent_registry.execute`), and returns HTTP `403` / `429` for role or quota blocks.
- `GET /api/v1/hr-agent/conversations`, `POST /api/v1/hr-agent/conversations`, `GET /api/v1/hr-agent/conversations/{id}/messages`, `POST /api/v1/hr-agent/conversations/{id}/messages` — multi-turn conversational HR threads supporting seamless workflow switching and context continuity (`workflow_slug` persisted in message metadata).
- `GET/POST/DELETE /api/v1/hr-agent/knowledge` & `GET /api/v1/hr-agent/knowledge/{doc_id}/download` — unified tenant document upload (PDF/DOCX/TXT/MD/CSV/PNG/JPG via async `save_tenant_upload`), pgvector chunk indexing, role-access checks, and file downloads.
- `GET /api/v1/hr-agent/integrations`, `PATCH /api/v1/hr-agent/integrations/{permission_id}`, `POST /api/v1/hr-agent/integrations/{permission_id}/credentials` — tool permission toggles and Fernet-encrypted API key storage (`vault://<tenant_id>/<tool_slug>/...` masked refs).
- `PATCH /api/v1/hr-agent/settings` — tenant-wide workspace configuration updates (`blind_screening_mode`, `strict_pii_masking`, `require_hitl_approval`, `model_routing_tier`, `monthly_token_quota`, `custom_persona_prompt`).
- `GET /api/v1/hr-agent/executions` & `GET /api/v1/hr-agent/usage` — execution traces and per-workflow token consumption summaries.

### 3.2 Classifier, Internal Routing & Context Continuity
Updated [classifier.py](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/backend/agents/framework/classifier.py), [registry.py](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/backend/agents/registry.py), [state.py](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/backend/agents/framework/state.py), and [workflow.py](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/backend/agents/framework/workflow.py):
- `WORKFLOW_ROUTING_RULES` and `score_hr_workflows` score incoming HR requests across all 7 HR workflows (`recruitment-screening`, `jd-generator`, `candidate-shortlisting`, `interview-scheduling`, `employee-onboarding`, `hr-policy-support`, `hr-analytics`).
- `classify_domain_boundary` routes cross-HR requests internally (`allowed=True`, `suggested_agent_slug=<target_slug>`) rather than rejecting them as out-of-domain.
- `workflow.py` dynamically switches active agent spec, tools, and role checks mid-graph when `suggested_agent_slug != requested_agent_id`, while preserving `HitlApproval` creation (`status="pending"`), protected-attribute fairness blocks (`execution_status="rejected"`), and `agent.synthesize_output` / `agent.apply_domain_guardrails` contracts.
- Multi-turn follow-up queries lacking new workflow keywords preserve prior HR context via `FOLLOWUP_HR_CONTINUITY_PATTERN` and `_has_prior_hr_context`.
- Prompt injection attempts (`blocked_injection`), protected-characteristic bias attempts (`blocked_policy_fairness`), and non-HR topics (`Medical Diagnosis & Clinical Advice`, `Financial Trading & Cryptocurrency`, `Legal Litigation & Contract Redlining`, `Personal Travel, Shopping & Homework`, `General Non-HR Request`) are cleanly declined with `HireFlow AI` messaging and zero marketplace references (`"Suggested Marketplace Category:"` removed from `node_build_response`).
- Updated [config.py](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/backend/app/config.py) `APP_NAME = "HireFlow AI — Hiring & HR AI Agent"`.

---

## 4. Phase 3 — Security, RBAC & Concurrency-Safe Quota Governance

- **Role-Based Access Control (RBAC):** `WORKFLOW_ALLOWED_ROLES` in [workflow.py](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/backend/agents/framework/workflow.py) restricts `business_employee` users strictly to `"hr-policy-support"` self-service queries and blocks access (`blocked_permission` -> HTTP `403` in [hr_agent.py](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/backend/app/api/v1/hr_agent.py), [agents.py](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/backend/app/api/v1/agents.py), and [conversations.py](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/backend/app/api/v1/conversations.py)) to recruitment, resume screening, JD generation, shortlisting, interviews, onboarding, and analytics. `business_admin`, `business_owner`, and `platform_admin` retain full workflow and admin mutation permissions.
- **Concurrency-Safe Monthly Token Quota:** `_check_and_lock_monthly_quota` in [workflow.py](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/backend/agents/framework/workflow.py) acquires deterministic row-level PostgreSQL locks (`SELECT ... FROM agent_configurations WHERE tenant_id = ... ORDER BY id FOR UPDATE`) and checks current UTC month `TokenUsage` (`input_tokens + output_tokens`) against `monthly_token_quota` and `extra_settings["unified_quota_limit"]` prior to model synthesis, raising HTTP `429` (`blocked_quota`) when exceeded.
- **Dead Code Removal:** Deleted unused `backend/app/services/domain_guard.py` after verifying zero callers.
- **Test Alignment:** Updated [test_agent_2_jd_generator.py](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/backend/tests/test_agent_2_jd_generator.py) to assert that `business_employee` execution on `jd-generator` returns `blocked_permission` while still testing `semantic_search_knowledge` role-level document filtering directly.

---

## 5. Verification Results (Executed After Final Edits)

### 5.1 Frontend Production Build
Command: `Set-Location "c:\Users\nandan\Desktop\Hiring-And-HR Agent\frontend"; npm run build` (`tsc --noEmit && vite build`)
- **Result:** Exit code `0`, `✓ 2106 modules transformed`, `✓ built in 1.48s`, TypeScript clean (`SettingsPage.tsx` unused `UserRole` import removed).

### 5.2 Backend Automated Test Suite (`pytest`)
Added [test_unified_hr_agent_and_governance.py](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/backend/tests/test_unified_hr_agent_and_governance.py) (7 new integration and governance tests) and executed the entire test suite against embedded PostgreSQL 16 + `pgvector`:
- Command: `Set-Location "c:\Users\nandan\Desktop\Hiring-And-HR Agent\backend"; & ".\.venv\Scripts\pytest.exe" -v`
- **Result:** **`22 passed, 1 warning in 17.49s`** (exit code `0`, zero failures, zero skipped tests):
  - All 15 pre-existing tests across `test_agent_1_recruitment.py` .. `test_agent_7_analytics.py`, `test_auth_and_rbac.py`, `test_end_to_end_agents_api.py`, `test_framework_workflow.py`, `test_multi_tenancy_and_rls.py`, `test_rental_lifecycle.py`, and `test_security_and_files.py`.
  - All 7 new Phase 4 tests in [test_unified_hr_agent_and_governance.py](file:///c:/Users/nandan/Desktop/Hiring-And-HR%20Agent/backend/tests/test_unified_hr_agent_and_governance.py):
    1. Unified `/api/v1/hr-agent/execute` internal routing across all 7 HR workflows without `workflow_hint`.
    2. Direct cross-HR internal routing inside `classify_domain_boundary` and `/hr-agent/execute`.
    3. Multi-turn `/hr-agent/conversations/{id}/messages` cross-workflow switching & follow-up continuity.
    4. Non-HR out-of-domain rejections (medical, financial trading, legal litigation, recipes) with zero marketplace wording.
    5. RBAC enforcement (`business_employee` allowed on `hr-policy-support`, `403` on the 6 sensitive workflows plus settings/integrations; `business_admin` & `business_owner` full access).
    6. Sequential quota enforcement (`429` at cap, restored on increase) + 2-thread concurrent `/hr-agent/execute` verification confirming strict `[200, 429]` serialization via PostgreSQL `SELECT ... FOR UPDATE`.
    7. Unified Knowledge Base upload/list/download/delete, tool permission toggles, encrypted secret masking (`vault://...`, `bound_encrypted`), cross-tenant `404` isolation, and `/executions` + `/usage` telemetry.

### 5.3 Live Running Application Check (`http://127.0.0.1:8000` & `http://127.0.0.1:5173`)
Restarted the backend cleanly (`uvicorn app.main:app --host 127.0.0.1 --port 8000`) alongside the running Vite dev server (`http://127.0.0.1:5173`) and verified live HTTP calls:
- `GET http://127.0.0.1:8000/health` -> `status=ok`, `service=HireFlow AI — Hiring & HR AI Agent`, `db=connected`.
- `GET http://127.0.0.1:5173` -> HTTP `200`, HTML title includes `HireFlow AI`.
- `POST /api/v1/auth/login` (`ananya@acmecloud.io` & `maya@acmecloud.io`) + `GET /api/v1/hr-agent/workspace` -> 7 workflows provisioned cleanly.
- `POST /api/v1/hr-agent/execute` (JD request without `workflow_hint`) -> `routed_workflow=jd-generator`, `execution_status=completed`, `classifier_result=in_domain`.
- `POST /api/v1/hr-agent/execute` (medical query) -> `execution_status=rejected`, `classifier_result=rejected_out_of_domain`, `hasMarketplaceText=False`.
- Employee live checks (`maya@acmecloud.io`): policy query -> HTTP `200` (`hr-policy-support`); resume screening query -> HTTP `403`.

---

## 6. Intentionally Deferred / Preserved Boundaries

The following architectural enhancements remain outside the scope of this correction phase and were intentionally deferred:
1. Containerized Docker sandbox runtime for arbitrary code execution.
2. Live Playwright headless browser automation sessions.
3. Live external MCP transport connectors (Greenhouse/Lever ATS, Google/Microsoft Calendar, Slack, Workday/BambooHR SCIM remain simulated/HITL-gated with encrypted credential vault storage).
4. Redis semantic response caching.
5. Tier 0–3 live LLM confidence escalation routing (system executes configured LLM providers when keys exist or deterministic rubric/structured fallbacks cleanly).
6. PyMuPDF hidden-text / adversarial PDF sanitization beyond magic-byte, extension, size, and path-traversal validation.
