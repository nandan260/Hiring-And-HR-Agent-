# Rent-an-Agent (Hiring & HR Category) — Agent Architecture

> **Status:** Proposed Architecture (Design Phase — No Code Implemented Yet)

---

## 1. Anatomy of a Rented Agent Instance

In Rent-an-Agent, an **Agent Template** (`agent_templates`) is a marketplace blueprint (e.g., *Recruitment & Resume Screening Agent*), whereas a **Rented Agent Instance** (`agent_rentals`) is an isolated, tenant-bound runtime configuration provisioned when a business rents that agent.

Every rented agent instance strictly isolates and encapsulates **10 mandatory components**:

| # | Component | Per-Rental Isolation Implementation |
| :--- | :--- | :--- |
| **1** | **System Prompt** | Compiled dynamically via a 3-layer immutable prompt hierarchy: `[Base Role + Anti-Override Guardrails (Locked)]` + `[Tenant Persona & Rubric Overrides (Configurable)]` + `[Dynamic Task Context]`. Stored versioned per `rental_id`. |
| **2** | **Execution Environment** | Dedicated execution working directory (`/{tenant_id}/{rental_id}/{run_id}/`) and ephemeral sandbox container/microVM allocation with explicit CPU/RAM/disk/PID quotas and zero shared `/tmp` across tenants. |
| **3** | **Allowed Tools** | Explicit capability allowlist stored on `agent_rentals.allowed_tools`. Tools not in the allowlist are omitted from the LLM function schema entirely (reducing both attack surface and token overhead). |
| **4** | **Browser Session** | Fresh ephemeral Playwright `BrowserContext` instantiated per run (zero shared cookies, `localStorage`, IndexedDB, or cache) inside a hardened non-root browser container with per-rental allowed domain lists. |
| **5** | **Memory & Knowledge Base** | • **Short-term / Workflow Memory:** LangGraph `thread_id` bound to `(tenant_id, rental_id)` in `agent_sessions` (RLS-enforced).<br>• **Long-term / Knowledge Base:** Vector namespace `tenant_{tenant_id}_rental_{rental_id}` in `pgvector` / Qdrant containing only documents uploaded or linked to this rental. |
| **6** | **Domain Classifier** | Per-agent boundary specification (`allowed_intents`, `out_of_scope_examples`, `rejection_template`) evaluated by the 3-Tier Domain Classifier *before* LangGraph runs. |
| **7** | **Guardrails** | Per-rental guardrail profile: input injection filter sensitivity, PII redaction policy (e.g., blind-hiring mode masks candidate names/emails), output schema enforcement, HITL trigger thresholds, and `max_steps` recursion limit. |
| **8** | **Execution Logs** | Append-only per-rental records in `agent_execution_runs`, `tool_execution_logs`, and `audit_logs`, plus OpenTelemetry `gen_ai.*` trace spans filtered strictly by `(tenant_id, rental_id)`. |
| **9** | **Token Usage Tracking** | Granular metering per `run_id` and `rental_id` in `token_usage_ledger`: classifier tokens, cache-hit/miss input tokens, output tokens, guardrail tokens, and USD cost against monthly rental quota. |
| **10** | **Configurable MCP Integrations** | Per-rental bindings (`rental_mcp_bindings`) selecting which external MCP servers (ATS, Calendar, HRMS, Slack) are enabled, with encrypted tenant credentials resolved server-side by the MCP Bridge Proxy. |

---

## 2. Intent Classification & Agent Routing Architecture

### 2.1 Why Needed, Alternatives & Limitations
* **Why Needed:** Businesses expect specialized agents to perform their designated HR task reliably while rejecting prompt drift, off-topic chatter (medical advice, stock trading, coding homework), and cross-agent privilege abuse (e.g., asking the JD Generator to run payroll analytics). Moreover, rejecting irrelevant inputs *before* loading LangGraph state and MCP schemas saves 90%+ of wasted tokens.
* **Alternatives Evaluated:**
  1. *System-Prompt-Only Refusal ("You are an HR agent, decline anything else"):* Weakest defense—easily bypassed by jailbreaks ("Ignore previous instructions...") and wastes thousands of tokens on system prompt + tool schemas just to produce a refusal.
  2. *Keyword / Regex Allowlists:* Zero latency and zero token cost, but high false-negative/false-positive rates on natural HR phrasing (e.g., "Compare Python vs Java candidates" mentions "Python", which looks like a coding query to naive regex).
  3. *Frontier LLM Router:* High accuracy, but adds 500–1,500ms latency and high cost on every turn.
* **Limitations of Chosen Hybrid Approach:** Embedding models can misclassify ambiguous adversarial phrasing ("Write Python code to screen resumes" vs "Write Python code for my Bitcoin bot"), and SLM classifiers require maintained domain boundary examples per agent. Combining deterministic pre-checks, embedding boundaries, and an SLM fallback minimizes both false rejections and latency.

### 2.2 Three-Tier Routing Cascade

```mermaid
flowchart LR
    Req["Sanitized User Query + Rental Domain Profile"] --> T0["Tier 0: Deterministic Pre-Filter (<5 ms, 0 tokens)"]
    T0 -->|"Injection signature / empty / banned keyword"| Reject0["Immediate Block + Log"]
    T0 -->|"Ambiguous / Natural Text"| T1["Tier 1: Semantic Embedding Boundary Check (<20 ms)"]
    T1 -->|"Cosine(query, agent_domain) >= 0.72 & gap over OOD anchors >= 0.15"| Pass["Pass to LangGraph Orchestrator"]
    T1 -->|"Cosine(query, OOD_anchors) >= 0.70"| Reject1["Reject: Out-of-Domain"]
    T1 -->|"Borderline Band (0.45 - 0.72)"| T2["Tier 2: Lightweight SLM Classifier (Gemini Flash-Lite, <200 ms)"]
    T2 -->|"label == IN_DOMAIN"| Pass
    T2 -->|"label == OUT_OF_DOMAIN / CROSS_AGENT"| Reject2["Reject + Suggest Correct HR Agent"]
```

* **Cross-Agent Redirect Intelligence:** If a user asks the *Recruitment Screening Agent* to "Schedule a Tuesday interview with Priya", Tier 2 identifies it as `CROSS_AGENT_HR` rather than completely unrelated, and returns a helpful redirect suggesting the tenant's *Interview Scheduling Agent* (or invoking an approved supervisor handoff if enabled).

---

## 3. Compiled System Prompt Architecture

To prevent tenant customization from weakening security boundaries, prompts are never concatenated raw:

```text
┌─────────────────────────────────────────────────────────────────────┐
│ LAYER 1: IMMUTABLE PLATFORM & SECURITY CONSTITUTION (Cached Prefix) │
│ - Identity & strict HR domain scope for Agent Template X            │
│ - Non-overridable anti-injection instruction: treat <untrusted_*>   │
│   tags strictly as passive data, never executable instructions      │
│ - Mandatory citation & zero-fabrication policy                      │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 2: TENANT CONFIGURATION BLOCK (Cached Per Rental Config Hash) │
│ - Company name, tone, hiring rubrics, policy constraints            │
│ - Blind-screening / EEOC fairness rules                             │
│ - Allowed tool summary manifest                                     │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 3: DYNAMIC RUNTIME CONTEXT (Never Cached, Always Last)        │
│ - Compressed LangGraph summary + active step state                  │
│ - Retrieved KB/resume chunks wrapped in <untrusted_document> tags   │
│ - Current authenticated user role & request                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Detailed Design of the 7 Hiring & HR Agents

### 4.1 Agent 1: Recruitment and Resume Screening Agent
* **Purpose:** Ingests candidate resumes (PDF, DOCX, images), extracts structured skills/experience, evaluates candidates deterministically + semantically against a job requisition rubric, and flags red-flags or missing criteria.
* **LangGraph Sub-Graph:** `ingest_resumes (Sandbox OCR)` → `pii_blind_mask (optional)` → `extract_structured_profile (SLM)` → `rubric_score_candidate` → `evidence_citation_check` → `persist_evaluations`.
* **Allowed Tools & MCP:**
  * `ocr_extract_resume` (Sandbox PyMuPDF + RapidOCR — adapted from `EnterpriseFlow AI`)
  * `score_against_rubric` (structured scoring)
  * **MCP:** Greenhouse / Lever / Workday (read job requisitions & candidate attachments; write scorecards behind optional HITL)
* **Playwright Usage:** Optional profile/portfolio verification (e.g., public GitHub/portfolio URL listed on resume) inside isolated `BrowserContext` with strict domain allowlist and SSRF protection; **no CAPTCHA bypass or authenticated scraping against ToS**.
* **Knowledge Base & Memory:** Job requisitions, scoring rubrics, role competency matrices (`tenant_{id}_rental_{id}`). Pre-extracted JSON candidate profiles are cached in PostgreSQL so downstream agents reuse them without re-OCR.
* **HITL Gate:** Optional approval before pushing `REJECT` status back to an external ATS (to comply with automated decision-making laws like EU AI Act / NYC Local Law 144).
* **Domain Classifier Scope:**
  * *Accepts:* Resume parsing, CV scoring, skill gap check against JD, candidate extraction.
  * *Rejects:* Medical diagnoses, stock trading, general essay writing, salary payroll processing.
* **Model Tier:** SLM (`flash-lite`) for structured CV JSON extraction; Mid-tier (`flash`) for nuanced rubric reasoning.
* **MVP vs. Production:**
  * *MVP:* Local PyMuPDF/RapidOCR + mock ATS MCP + structured DB persistence + blind-hiring toggle.
  * *Prod:* Live Greenhouse/Lever MCP via OAuth Bridge + async batch queue (Celery/Temporal) for 1,000+ resumes + bias audit export.

---

### 4.2 Agent 2: Job Description (JD) Generator Agent
* **Purpose:** Generates role-specific, inclusive, legally compliant, and SEO-optimized job descriptions grounded in the tenant's internal leveling guides, compensation bands, and brand voice.
* **LangGraph Sub-Graph:** `collect_role_brief` → `retrieve_tenant_leveling_&_templates` → `draft_jd` → `inclusive_language_&_bias_lint` → `compliance_salary_band_check` → `refine_or_export`.
* **Allowed Tools & MCP:**
  * `kb_search_leveling_guide` (tenant KB)
  * `inclusive_language_linter` (deterministic + SLM check for gendered/exclusionary phrasing like "rockstar/ninja", age-biased requirements)
  * **MCP:** Notion / Confluence (read team templates), LinkedIn / ATS Draft API (export draft JD).
* **Playwright Usage:** Optional read-only inspection of tenant's existing public careers page to match formatting/tone (`BrowserContext`, domain-allowlisted).
* **Knowledge Base & Memory:** Company mission/benefits boilerplates, engineering/sales leveling ladders, approved compensation bands, past high-performing JDs.
* **HITL Gate:** Required before publishing a JD directly to a live external ATS/careers portal (`Publish JD Approval`).
* **Domain Classifier Scope:**
  * *Accepts:* Writing/editing/localizing JDs, checking JD bias, aligning role seniority/requirements.
  * *Rejects:* Marketing ad copy for products, legal contract drafting, personal cover letters, non-HR writing.
* **Model Tier:** Mid-tier (`flash`) for drafting; deterministic rules + SLM (`flash-lite`) for inclusive-language linting.
* **MVP vs. Production:** *MVP:* Markdown/DOCX export + tenant KB tone grounding + built-in bias linter. *Prod:* Direct ATS publishing MCP + A/B job board readability analytics.

---

### 4.3 Agent 3: Candidate Shortlisting Agent
* **Purpose:** Compares screened candidates across a requisition pool, constructs an evidence-backed comparison matrix, applies tenant-configured diversity/fairness guardrails, and recommends a top-N shortlist.
* **LangGraph Sub-Graph:** `load_screened_profiles` → `check_minimum_knockout_criteria (Deterministic)` → `comparative_ranking_node` → `citation_grounding_verifier` → `hitl_shortlist_approval_gate` → `notify_hiring_manager`.
* **Allowed Tools & MCP:**
  * `query_screened_candidates` (SQL over `screening_evaluations` strictly scoped by `tenant_id` & `requisition_id`)
  * `compute_weighted_rank` (deterministic Python scorer in sandbox)
  * **MCP:** ATS (move candidate stage), Slack / Email (notify hiring manager *only after HITL approval*).
* **Playwright Usage:** None required (operates over structured profiles and ATS data to avoid unnecessary scraping cost/risk).
* **Knowledge Base & Memory:** Hiring manager preferences, knockout rules (e.g., work authorization, required certifications), comparative evaluation history.
* **HITL Gate:** **Mandatory HITL pause** before advancing or rejecting candidates in ATS or sending notifications (`Shortlist Sign-Off`).
* **Domain Classifier Scope:**
  * *Accepts:* Ranking applicants for a role, comparing top candidates, explaining why Candidate A outranked Candidate B using resume evidence.
  * *Rejects:* Ranking stocks, comparing SaaS vendors, evaluating current employees for termination (outside hiring scope).
* **Model Tier:** Deterministic math for weighted scores; Mid-tier/Frontier (`flash` / `pro` escalation only on close ties) for comparative narrative justification.
* **MVP vs. Production:** *MVP:* Deterministic weighted matrix + LLM justification with mandatory resume quote citations + HITL inbox approval. *Prod:* Automated NYC-144 / EEOC disparate impact ratio telemetry across cohorts.

---

### 4.4 Agent 4: Interview Scheduling Agent
* **Purpose:** Coordinates interview panels, checks multi-interviewer calendar availability across timezones, handles candidate rescheduling requests, generates interview scorecards/prep briefs, and dispatches calendar invites.
* **LangGraph Sub-Graph:** `parse_scheduling_request` → `fetch_interviewer_availability (MCP)` → `load_balance_&_slot_match (Deterministic)` → `hitl_confirm_external_invite` → `book_calendar_&_ats_stage`.
* **Allowed Tools & MCP:**
  * `timezone_slot_solver` (deterministic constraint solver — 0 LLM tokens for time math!)
  * **MCP:** Google Calendar / Microsoft Outlook (free/busy lookup, event creation), Zoom / Google Meet (link creation), Email / Slack.
* **Playwright Usage:** Fallback adapter *only* when a tenant uses a legacy ATS/scheduling portal without API/MCP access, operating inside an isolated `BrowserContext` using tenant-configured portal credentials injected outside LLM reach.
* **Knowledge Base & Memory:** Interview panel rosters, interviewer training/calibration eligibility, interview stage durations, timezone rules, email templates.
* **HITL Gate:** Configurable HITL pause before sending external calendar invites to candidates or modifying executive calendars.
* **Domain Classifier Scope:**
  * *Accepts:* Finding interview slots, rescheduling panels, assigning calibrated interviewers, generating prep briefs.
  * *Rejects:* Booking personal vacations, flight/hotel travel booking, general calendar management unrelated to hiring.
* **Model Tier:** SLM (`flash-lite`) for intent/slot extraction from natural language; deterministic Python solver for actual time-slot intersections.
* **MVP vs. Production:** *MVP:* Mock Calendar + Google Calendar API adapter + deterministic timezone solver + HITL confirmation card. *Prod:* Full multi-panel load balancing, Slack interviewer ping workflows, automated reminder & reschedule loop.

---

### 4.5 Agent 5: Employee Onboarding Agent *(Evolved from EnterpriseFlow AI)*
* **Purpose:** Automates post-offer employee onboarding end-to-end: KYC/education document verification, IT account & hardware provisioning, team/buddy/desk allocation, role-based LMS training assignment, and continuous progress monitoring.
* **LangGraph Sub-Graph (Upgraded from `EnterpriseFlow AI`):**
  ```mermaid
  flowchart LR
      Start([New Hire Enrolled]) --> Doc["1. Document Verification\n(Sandbox OCR + Dual Fallback)"]
      Doc --> DocGate{"Compliance\nIssues?"}
      DocGate -->|Flagged| HITL_HR["HITL: HR Doc Review"]
      DocGate -->|Passed| IT["2. IT Provisioning\n(Email, Laptop, Licenses)"]
      HITL_HR -->|Approved| IT
      IT --> HITL_IT["HITL: IT Admin Sign-Off"]
      HITL_IT -->|Resumed via Checkpointer| Team["3. Team Allocation\n(Manager, Buddy, Desk, Slack)"]
      Team --> HITL_Mgr["HITL: Manager Confirmation"]
      HITL_Mgr -->|Resumed via Checkpointer| Train["4. Training & LMS\n(Role Courses & Day-1 Checklist)"]
      Train --> Monitor["5. Monitoring & Telemetry\n(Progress & Audit Report)"]
  ```
* **Key Architectural Upgrades over Reference Project:**
  1. **True Persistence:** Replaces `EnterpriseFlow AI`'s manual DB re-query + fresh graph invoke with `AsyncPostgresSaver` checkpoints protected by RLS `agent_sessions`.
  2. **Multi-Tenancy:** Every `Employee`, `DocumentRecord`, `ITAssetRecord`, `ApprovalRequest`, and upload path is strictly scoped to `(tenant_id, rental_id)`.
  3. **Configurable MCPs:** Replaces hardcoded `mock_external_apis.py` with pluggable MCP bindings (Okta/Azure AD SCIM, Jira/ServiceNow, Slack, BambooHR) while keeping mock adapters for zero-config MVP demos.
  4. **Anti-Injection OCR:** Extracted Aadhaar/degree/offer PDF text is wrapped in `<untrusted_document>` delimiters before Gemini verification.
* **Allowed Tools & MCP:** `sandbox_ocr_verify`, `provision_it_bundle`, `assign_team_buddy`, `assign_lms_curriculum`; MCPs: Okta, Jira/ServiceNow, Slack, Google Workspace.
* **Domain Classifier Scope:** *Accepts:* Onboarding new hires, KYC doc verification, IT/team/training setup, checking onboarding status. *Rejects:* Recruiting external candidates, answering general medical questions, running company finance audits.

---

### 4.6 Agent 6: Employee Support and HR Policy Agent
* **Purpose:** Acts as an always-on internal HR Helpdesk answering employee queries (PTO/leave balance rules, expense reimbursement, parental leave, WFH policy, benefits) strictly grounded in the tenant's uploaded HR handbooks, with seamless escalation to human HR tickets.
* **LangGraph Sub-Graph:** `semantic_cache_lookup` → `hybrid_rag_retrieve (tenant_namespace)` → `grounding_sufficiency_check` → `answer_with_citations` OR `escalate_hr_ticket (HITL/MCP)`.
* **Allowed Tools & MCP:**
  * `tenant_policy_rag_search` (BM25 + vector search + rerank scoped strictly to `tenant_id` & `rental_id`)
  * `create_hr_support_ticket` (creates ticket in DB / Zendesk / Jira Service Management MCP)
  * **MCP:** Slack (bot channel), Confluence/Notion/Google Drive (sync policy docs), Zendesk/Jira.
* **Playwright Usage:** None (relies on synced KB documents to prevent stale or untrusted web lookups).
* **Knowledge Base & Memory:** Tenant Employee Handbooks, Benefits Guides, Country-Specific Labor Addenda, IT/Expense policies.
* **HITL Gate:** Required before submitting sensitive escalation tickets (e.g., harassment report, formal grievance, salary dispute) or modifying any HRMS employee record.
* **Domain Classifier Scope:**
  * *Accepts:* Leave policy, benefits, travel reimbursement, onboarding policy FAQs, creating HR helpdesk tickets.
  * *Rejects:* Legal/tax filing advice outside company policy, medical diagnosis ("should I take antibiotics?"), coding help, external competitor analysis.
* **Model Tier:** Semantic cache hit (0 LLM tokens!) → SLM (`flash-lite`) for factual policy lookup → Mid-tier (`flash`) for multi-policy synthesis.
* **MVP vs. Production:** *MVP:* PDF/Markdown handbook ingestion + `pgvector` hybrid retrieval + mandatory `[Doc Title, Section]` citations + mock ticket escalation. *Prod:* Scheduled Google Drive/Confluence MCP auto-sync + Slack bot + RBAC-filtered policy docs (e.g., executive comp handbook hidden from general employees).

---

### 4.7 Agent 7: HR Analytics Agent
* **Purpose:** Enables HR leaders to ask natural-language analytical questions over their tenant's hiring and workforce data (e.g., *"What is our engineering time-to-hire trend over Q1–Q3?"*, *"Which sourcing channel yields the highest shortlist conversion?"*), generating validated SQL queries, sandboxed Python charts/forecasts, and executive summaries.
* **LangGraph Sub-Graph:** `check_analytics_rbac` → `schema_link_tenant_views` → `generate_readonly_sql` → `sql_ast_validator (SELECT only on allowed views)` → `execute_sql_rls` → `python_sandbox_analysis_&_chart` → `k_anonymity_&_pii_check` → `respond`.
* **Allowed Tools & MCP:**
  * `query_hr_metrics_sql` (runs strictly against read-only PostgreSQL views under RLS `SET LOCAL app.current_tenant`)
  * `sandbox_python_analytics` (executes `pandas`/`matplotlib` inside network-isolated Docker/gVisor container to compute stats and return PNG/JSON chart artifacts)
  * **MCP:** Read-only HRIS/ATS warehouse views (optional external Snowflake/BigQuery read-only scoped role in production).
* **Playwright Usage:** None.
* **Knowledge Base & Memory:** Tenant metric definitions (how this company defines "Time to Fill" or "Voluntary Attrition"), database view catalog, previous chart definitions.
* **HITL Gate:** None for read-only aggregated analytics; **Hard Block** on any SQL `INSERT/UPDATE/DELETE/DDL` or attempts to inspect raw tables outside whitelisted analytics views.
* **Guardrail Specifics (Privacy Protection):** Enforces **minimum cohort threshold ($k \ge 5$)** for sensitive breakdowns (e.g., attrition or compensation by demographic/department) so small-group queries cannot de-anonymize an individual employee's salary or review score.
* **Domain Classifier Scope:**
  * *Accepts:* Hiring funnel metrics, attrition rates, headcount trends, interview-to-offer ratios, onboarding completion SLAs.
  * *Rejects:* Stock market technical analysis, sales revenue forecasting, engineering system logs, non-HR database queries.
* **Model Tier:** Mid-tier/Frontier (`flash` / `pro`) for accurate SQL + Python code generation; deterministic SQL AST parser (`sqlglot`) for read-only safety validation.
* **MVP vs. Production:** *MVP:* `sqlglot` AST validator + RLS read-only PostgreSQL views + local Docker Python chart runner. *Prod:* Dedicated PostgreSQL read-replica + Firecracker/gVisor Python sandbox + scheduled executive PDF digests.

---

## 5. Inter-Agent Handoff & End-to-End Hiring Workflow Composition

Tenants who rent multiple HR agents can chain them into an automated hiring-to-onboarding pipeline while preserving **strict permission boundaries**—each agent retains its own isolated tools, prompt, and token ledger, communicating only via typed handoff contracts stored in PostgreSQL:

```mermaid
flowchart LR
    A2["2. JD Generator Agent"] -->|"Approved JD + Rubric ID"| A1["1. Resume Screening Agent"]
    A1 -->|"Screened Candidate JSON Profiles"| A3["3. Candidate Shortlisting Agent"]
    A3 -->|"HITL Approved Shortlist"| A4["4. Interview Scheduling Agent"]
    A4 -->|"Offer Accepted Event"| A5["5. Employee Onboarding Agent"]
    A5 -->|"Day 1 Active Employee"| A6["6. Employee Support & HR Policy Agent"]
    A1 & A3 & A4 & A5 -->|"Aggregated Funnel & SLA Events"| A7["7. HR Analytics Agent"]
```

* **Zero Implicit Privilege Escalation:** When *Agent 3 (Shortlisting)* hands off an approved candidate to *Agent 4 (Scheduling)*, Agent 3 cannot call Google Calendar directly; it emits a validated `HandoffPayload` event, which triggers Agent 4 under Agent 4's own `rental_id`, permissions, and token budget.
