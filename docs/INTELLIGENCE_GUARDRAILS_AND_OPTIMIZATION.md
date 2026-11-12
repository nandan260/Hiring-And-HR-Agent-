# HireFlow AI — Intent Classification, Domain Enforcement, Guardrails & Token Optimization Report

**Date:** 2026-11-11  
**Scope:** Intelligent classification, domain boundary enforcement, multi-layer safety & document security guardrails, honest token optimization & baseline comparison, Obsidian Markdown interoperability, and PostgreSQL-native HR knowledge/skill graph.

---

## 1. Executive Summary

This phase hardened the single unified **HireFlow AI — Hiring & HR AI Agent** (`backend/` and `frontend/`) without altering the underlying LangGraph state architecture (`run_agent_workflow`), breaking tenant `FORCE RLS` isolation, or fabricating simulated token savings:

1. **Hybrid Intent Classifier (`backend/agents/framework/classifier.py`)**: Deterministic fast-path classification first (`classifier_method: "deterministic"`), identifying `intent_label`, `user_intent`, `requested_task`, `hr_workflow`, `required_tools`, `risk_level`, `required_permissions`, `needs_clarification`, and `clarification_questions`. Optional LLM-assisted fallback (`_llm_classify_ambiguous_intent`) engages only when deterministic matching is ambiguous and a live provider key is configured.
2. **Domain Boundary Classifier**: Enforces strictly Hiring & HR specialization with explicit `HR_CONTEXT_EXEMPT_RX` exemptions for legitimate HR benefit/equity terms (e.g., *employee stock options*, *medical leave*, *medical reimbursement*) while blocking medical diagnosis, stock/crypto trading advice, unrelated legal litigation, and general personal requests with **zero tool calls**.
3. **End-to-End Guardrails & Runtime Defenses**:
   - Prompt injection & system-prompt leak detection (direct patterns + base64 segment decoding).
   - Input safety caps (empty input, NUL control bytes, >10 non-printable control chars, `max_input_tokens=8000`, and consecutive repetition bombs `>=120` repeated tokens) + PostgreSQL NUL-byte sanitization (`redact_secrets_in_text`).
   - HR Fairness & Anti-Auto-Reject enforcement (`check_hr_safety_input`).
   - Outbound & response secret/system-marker/PII scrubbing (`sanitize_outbound_llm_context`, `scrub_output_for_secrets_and_pii`).
   - Malicious file upload blocking & inline untrusted CV/document neutralization (`inspect_document_bytes`, `neutralize_untrusted_document_text`).
   - Sliding-window per-tenant/per-user rate limiting (`SlidingWindowRateLimiter`, HTTP `429` + `Retry-After`) and execution/recursion caps.
4. **Honest Token Optimization & A/B Telemetry (`backend/agents/framework/optimizer.py`)**:
   - Replaced synthetic cache estimates with measured `baseline_input_tokens`, actual `input_tokens`, `cached_tokens`, `output_tokens`, `duration_ms`, and `optimization_methods_json` stored via **Alembic migration `20261111_0004`**.
   - Exposed `POST /api/v1/hr-agent/optimization/compare` for real unoptimized vs. optimized execution comparison.
5. **Pragmatic Knowledge Architecture (`rag.py` & `hr_knowledge_graph.py`)**:
   - **Obsidian Markdown Interoperability**: YAML frontmatter tags/`#tags` and `[[wikilinks]]` parsed on ingestion and exported via `GET /api/v1/hr-agent/knowledge/{doc_id}/markdown`, with 1-hop wikilink context expansion during RAG.
   - **PostgreSQL-Native HR Knowledge & Skill Graph**: Implemented `build_tenant_hr_graph` and `compute_graph_skill_matches` inside the tenant RLS transaction scope (`GET /api/v1/hr-agent/knowledge-graph`), gaining explainable skill clusters (`FastAPI <-> Python`) without introducing an external graph database outside RLS.

---

## 2. Intent & Domain Classification Architecture

### 2.1 Hybrid Classifier (`backend/agents/framework/classifier.py`)

- **Core Structures**:
  - `IntentClassification` dataclass (`to_dict()`) capturing: `intent_label`, `user_intent`, `requested_task`, `hr_workflow`, `required_tools`, `risk_level`, `required_permissions`, `needs_clarification`, `clarification_questions`, `classifier_method`, `is_injection`, `is_bias_attempt`, `is_out_of_domain`.
  - `WORKFLOW_TOOL_PERMISSIONS` mapping each of the 7 HR workflows (`recruitment`, `jd-generator`, `candidate-shortlisting`, `interview-scheduling`, `employee-onboarding`, `hr-policy-support`, `hr-analytics`) to authorized tool sets, risk level, and required RBAC roles.
- **Functions**:
  - `classify_intent_detailed(...)`: Runs injection scan -> HR safety scan -> domain boundary check -> deterministic intent/workflow scoring -> ambiguity clarification check -> optional `_llm_classify_ambiguous_intent` fallback when needed.
  - `classify_user_intent(...)` & `classify_domain_boundary(...)`: Preserved compatible entrypoints for `workflow.py` and external callers.
- **API Inspection Endpoint**: `POST /api/v1/hr-agent/classify` returns full `intent_analysis`, `domain_allowed`, `classifier_result`, `reason`, `routed_workflow`, and `routed_workflow_name` without mutating workspace state.

### 2.2 Domain Enforcement & HR Compensation Exemptions

- **Allowed Workflows**: Recruitment & resume screening, job description generation, candidate shortlisting/matching, interview scheduling, employee onboarding, HR policy Q&A, and HR analytics.
- **Out-of-Domain Rejection**: Rejects medical diagnosis/prescriptions, stock/crypto portfolio trading, unrelated legal representation/lawsuits, and non-HR personal tasks with `execution_status="rejected"`, `classifier_result="rejected_out_of_domain"`, and `tool_calls=[]`.
- **False-Positive Protection (`HR_CONTEXT_EXEMPT_RX`)**: Legitimate HR compensation, equity (`employee stock option`), and benefits (`medical leave`, `medical reimbursement`, `health insurance`) prompts bypass non-HR trading/medical rejection cleanly and route to `hr-policy-support` (verified live HTTP `200`).

---

## 3. Security Guardrails & Abuse Prevention

| Layer | Module | Enforcement & Behavior |
|---|---|---|
| **Prompt Injection & Leak Defense** | `guardrails.py` (`scan_prompt_injection`), `redaction.py` | Scans direct override/role-tag/SQL/RLS exfil patterns, system-prompt extraction attempts, and decoded base64 segments (`_decode_suspicious_base64_segments`). |
| **Input Validation & Repetition Bombs** | `guardrails.py` (`validate_input_safety`), `redaction.py` (`redact_secrets_in_text`) | Blocks empty prompts (`invalid_empty_input`), `\x00` NUL bytes (`invalid_control_chars`), >10 control chars, `>8000` estimated input tokens (`excessive_input_tokens`), and `>=120` repeated consecutive tokens (`repetition_bomb_blocked`). Sanitizes `\x00` -> `[NUL]` before PostgreSQL log insertion. |
| **HR Fairness & Anti-Auto-Reject** | `guardrails.py` (`check_hr_safety_input`), `PROTECTED_BIAS_PATTERNS`, `AUTO_REJECT_INPUT_PATTERNS` | Blocks age/gender/religion/caste/race/disability candidate filtering (`blocked_policy_fairness`, status `"rejected"`) and autonomous rejection bypassing human approval (`blocked_auto_reject`, status `"blocked"`). |
| **Secret & PII Scrubbing** | `guardrails.py` (`sanitize_outbound_llm_context`, `scrub_output_for_secrets_and_pii`) | Strips secrets/system markers outbound and masks PII in blind screening mode, strict PII mode, or `business_employee` role. |
| **Document Upload Security** | `app/runtime/document_security.py` (`inspect_document_bytes`), `core/storage.py`, `api/v1/hr_agent.py`, `api/v1/rentals.py` | Blocks disguised binaries (`MZ`, `\x7fELF`, Mach-O, Java class, `#!`), PDF active threats (`/JavaScript`, `/JS`, `/Launch`, `/OpenAction`, `/RichMedia`, `/EmbeddedFile`), DOCX zip-slip / zip-bombs (`>25 MB`) / VBA macros (`vbaProject.bin`) / XXE (`<!ENTITY`, `<!DOCTYPE`), and HTML/JS smuggling (`<script>`, `<iframe>`, `javascript:`, inline handlers, `<?php`). |
| **Untrusted CV/Doc Neutralization** | `document_security.py` (`neutralize_untrusted_document_text`), `recruitment_agent.py` | Strips embedded `<script>` blocks and indirect candidate-ranking override directives (`[FILTERED_UNTRUSTED_DIRECTIVE]`) prior to scoring. |
| **RBAC & Tool Authorization** | `app/runtime/tool_registry.py`, `workflow.py` (`node_execute_tools`) | Enforces role permissions per workflow and per tool (returns `403` when `business_employee` invokes restricted workflows like `candidate-shortlisting` or admin/HITL tools like `email_draft_generator`, `onboarding_checklist_manager`, `browser_search`). |
| **Rate Limiting & Step Caps** | `app/core/rate_limiter.py` (`SlidingWindowRateLimiter`), `app/config.py`, `workflow.py` | Enforces 60-second sliding-window request (`120/min`) and token (`120000/min`) limits (`429` + `Retry-After`) plus `MAX_WORKFLOW_STEPS_HARD_CAP=20` and LangGraph `recursion_limit`. |

---

## 4. Token Optimization, Telemetry & Honest Measurement

### 4.1 Real Optimization Pipeline (`backend/agents/framework/optimizer.py`)

`prepare_optimized_llm_request` computes exact `baseline_input_tokens` before optimization, then applies:
- `compress_system_prompt` (`prompt_compression`): strips blank lines, markdown dividers, and redundant indentation.
- Prompt whitespace normalization (`whitespace_compaction`).
- `summarize_conversation_history` (`window=4`, `max_summary_chars=520`): preserves the latest 4 messages verbatim and compacts older turns cleanly.
- `filter_and_compress_context` (`vector_blob_pruning`, `semantic_chunk_filtering`, `history_window_trimming`, `context_truncation`): strips vector arrays/raw binary fields and caps chunk count/length (`max_chunks=4`, `max_chunk_chars=460`).
- `select_routed_model`: selects `tier_0_rule` (`deterministic-hr-synthesizer-v1`), `tier_1_fast` (`gemini-2.5-flash` / `gpt-4o-mini` / `claude-3-5-haiku-latest`), or `tier_2_reasoning` (`gemini-2.5-pro` / `gpt-4o` / `claude-3-7-sonnet-latest`).
- `TenantAwareResponseCache` (`tenant_response_cache`): LRU+TTL (180s, max 400 entries) keyed by `tenant_id|actor_role|workflow_slug|blind_mode|sha256(sys+usr+ctx)` for cacheable read workflows (`hr-policy-support`, `jd-generator`, `hr-analytics`), automatically invalidated via `invalidate_tenant(tenant_id)` on KB uploads/deletions, settings updates, and mutating workflow runs.

### 4.2 Database & Usage APIs

- **Alembic Migration**: `20261111_0004_optimization_and_guardrail_telemetry.py` adds `baseline_input_tokens`, `duration_ms`, `tool_calls_count`, `optimization_enabled`, and `optimization_methods_json` to `token_usage`.
- **`POST /api/v1/hr-agent/optimization/compare`**: Executes a side-by-side unoptimized (`enable_optimization=False`) vs. optimized (`enable_optimization=True`) comparison and returns measured `input_tokens_saved`, `total_tokens_saved`, `input_reduction_percent`, `cost_saved_usd`, and `latency_diff_ms` without fabricated ratios.
- **`GET /api/v1/hr-agent/usage`**: Returns `optimization_summary` aggregated strictly from stored `TokenUsage` rows (`total_runs_measured`, `total_baseline_input_tokens`, `total_actual_input_tokens`, `total_cached_tokens`, `total_measured_tokens_saved`, `measured_reduction_percent`, `methods_frequency`).

---

## 5. Honest Architectural Evaluation: Knowledge Graph & Obsidian Markdown

- **Graphify / Neo4j Evaluation**: Deploying a separate graph engine alongside PostgreSQL `FORCE RLS` risks split-brain tenant authorization and sync drift. Instead, `backend/app/runtime/hr_knowledge_graph.py` constructs a lightweight **PostgreSQL-native HR Knowledge & Skill Graph** inside the active RLS transaction (`build_tenant_hr_graph`, `SKILL_EQUIVALENTS`, `expand_skill_equivalents`, `compute_graph_skill_matches`, `get_compact_graph_context`), powering transparent 1-hop skill equivalency in candidate shortlisting and an interactive graph view at `GET /api/v1/hr-agent/knowledge-graph`.
- **Obsidian Vault Evaluation**: Instead of storing files outside tenant-controlled PG + encrypted storage, `backend/agents/framework/rag.py` adopts **Obsidian Markdown conventions** (`parse_obsidian_markdown`, `export_document_as_obsidian_markdown`) — preserving YAML frontmatter tags/`#tags` and `[[wikilinks]]` inside `KnowledgeChunk.metadata_json` and providing downloadable `.md` export (`GET /api/v1/hr-agent/knowledge/{doc_id}/markdown`) plus 1-hop wikilink retrieval expansion.

---

## 6. Verification & Observed Results

1. **Full Backend Test Suite (`pytest -v`)**:
   - Command: `.\.venv\Scripts\python.exe -m pytest -v` (in `backend/`)
   - Result: **35 passed, 1 warning in 41.76s** (0 failures, 0 skipped) covering all 28 prior suites plus all 7 tests in `tests/test_intelligence_guardrails_optimization.py`.
2. **Frontend Type Check & Production Build**:
   - Command: `npm run build` (`tsc --noEmit && vite build` in `frontend/`)
   - Result: Exited `0`; built `dist/assets/index-CE3wxs16.css` (`46.35 kB`) and `dist/assets/index-CN3Ws_y1.js` (`455.51 kB`) in `988ms`.
3. **Database Migration & Live HTTP Stack (`127.0.0.1:8000` & `127.0.0.1:5173`)**:
   - Applied `alembic upgrade head` -> `20261111_0004 (head)` and seeded `{'plans': 3, 'tools': 37, 'agents': 7}`.
   - `GET /health` -> `200 OK` (`PostgreSQL 16.2`).
   - `POST /api/v1/auth/login` -> `200 OK`.
   - `POST /api/v1/hr-agent/classify` -> `200 OK` (`interview_scheduling`, deterministic classifier, `risk_level: "high"`).
   - `POST /api/v1/hr-agent/execute` (out-of-domain stock/crypto query) -> `execution_status: "rejected"`, `classifier_result: "rejected_out_of_domain"`, `tool_calls: []`.
   - `POST /api/v1/hr-agent/execute` (HR compensation exemption: *"employee stock option vesting and medical leave reimbursement"*) -> `execution_status: "completed"`, `routed_workflow: "hr-policy-support"`, `classifier_result: "in_domain"`.
   - `POST /api/v1/hr-agent/optimization/compare` -> measured `903` unoptimized vs `902` optimized input tokens (`0.11%` saved, `$0.0` deterministic offline tier).
   - `GET /api/v1/hr-agent/usage` -> `optimization_summary` with `total_runs_measured: 8`, `total_baseline_input_tokens: 6022`, `total_actual_input_tokens: 6021`, `total_cached_tokens: 3003`.
   - `GET /api/v1/hr-agent/knowledge-graph` -> `21 nodes`, `20 edges`.
   - `POST /api/v1/hr-agent/knowledge` with `/OpenAction /JavaScript (alert(1))` PDF -> HTTP `400` blocked.
   - `GET http://127.0.0.1:5173/` -> HTTP `200 OK` (`1047` bytes).

---

## 7. Honest Current Limitations

- **Single-Process Memory Store for Cache & Rate Limiter**: `SlidingWindowRateLimiter` and `TenantAwareResponseCache` reside in process memory; multi-worker production deployment requires moving their backing store to Redis.
- **Offline / Deterministic Mode**: When live LLM API keys are unset, execution routes to `deterministic-hr-synthesizer-v1` (`$0.00`), where token reduction on single-turn short prompts is small (e.g., `0.11%` measured) compared to multi-turn conversations, large KB chunk pruning, and cache hits on repeated queries.
- **Container Runtime on Host**: Docker Desktop daemon is absent on the current Windows development host, so `DockerSandboxManager` runs in labelled `development_fallback` (`is_container_isolated=False`).
