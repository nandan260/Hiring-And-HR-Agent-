# Rent-an-Agent (Hiring & HR Category) — Token Optimization & Cost Engineering

> **Status:** Proposed Architecture (Design Phase — No Code Implemented Yet)

---

## 1. The Token Bloat Problem in Multi-Agent HR Systems

Without deliberate token engineering, a single HR workflow (e.g., screening 25 resumes, running a shortlist comparison, or executing a multi-turn onboarding graph) can easily consume **50,000–250,000+ tokens**:
1. **Repeated Static Prefixes:** Re-sending a 2,000-token system prompt + rubric + company handbook summary across 8 LangGraph steps multiplies input spend by 8×.
2. **MCP Tool Schema Bloat:** Injecting full JSON schemas for 30–50 ATS, Calendar, Slack, and HRMS tools can consume **8,000–15,000 tokens per turn** even when the agent only calls one tool.
3. **Raw Document & HTML Dumping:** Passing raw Playwright HTML (`80,000+` tokens of `<div class="...">` and inline CSS) or uncleaned 10-page PDF resume text (`12,000+` tokens) directly into prompts.
4. **Frontier Model Overkill:** Using an expensive frontier reasoning model for trivial tasks like intent classification, JSON reformatting, date parsing, or standard FAQ replies.
5. **Unbounded Graph History:** Appending full `messages` arrays (including massive tool outputs) into every subsequent LangGraph node state.

---

## 2. Ten Practical Strategies to Cut Token Consumption Without Quality Loss

### Strategy 1: Prefix-Ordered Prompt Caching (Provider KV Caching)
* **Why Needed:** Frontier and Flash LLM APIs recompute Transformer Key-Value (KV) attention tensors for identical prefixes unless explicitly structured for prompt caching.
* **How It Works:** Order every prompt deterministically so **100% static bytes come first** and dynamic content goes at the very end:
  1. `[0 .. N]`: Layer-1 Immutable Agent Constitution + Domain Schema + Compressed Tool Directory *(static across all tenants)*
  2. `[N .. M]`: Layer-2 Tenant Persona, Hiring Rubric, & Policy Anchor *(static per `rental_id` config hash)*
  3. `[M .. End]`: Layer-3 Dynamic Conversation Summary + Retrieved Chunks + Current Query *(never cached)*
* **Expected Impact:** **50%–90% reduction** in input token cost on cached prefix reads (typically 0.1× standard input pricing) and significantly faster Time-To-First-Token (TTFT).
* **Limitations:** Requires minimum cacheable prefix lengths (commonly 1,024+ tokens depending on provider) and breaks completely if timestamps, random IDs, or dynamic state are injected into the prefix.

### Strategy 2: Tenant-Scoped Semantic Caching
* **Why Needed:** In the **Employee Support & HR Policy Agent**, 30%–50% of employee questions are semantic paraphrases of the same policies (*"How many paternity leave days do we get?"* vs *"What is the paternal leave allowance?"*).
* **How It Works:** Embed the incoming query and search a **tenant-and-rental-partitioned** Redis vector cache (`tenant_id + rental_id + kb_version_hash`). If cosine similarity exceeds a high precision threshold (e.g., $\ge 0.94$), return the verified cached response + citations immediately with **0 LLM generation tokens**.
* **Expected Impact:** Eliminates **20%–45%** of LLM calls entirely on HR Policy & FAQ workloads.
* **Alternatives:** Exact-string hash cache (zero embedding cost, but misses paraphrases).
* **Limitations:**
  * *Staleness:* If an HR admin uploads a revised handbook, cached answers become wrong. **Mitigation:** Include `kb_version_hash` inside the cache key so uploading a new KB document invalidates stale entries instantly.
  * *Cross-Tenant Leak Risk:* Never share semantic cache entries across tenants (`tenant_id` is mandatory in the lookup filter).

### Strategy 3: Tiered LLM Model Routing & Cascading
* **Why Needed:** Paying frontier-model prices for regex-solvable KYC checks or simple classification wastes 70%–85% of budget.
* **How It Works:** Route every sub-task inside LangGraph to the cheapest tier that satisfies accuracy benchmarks:

| Tier | Execution Engine / Model Class | Target HR Sub-Tasks | Cost & Latency Profile |
| :--- | :--- | :--- | :--- |
| **Tier 0** | **Deterministic Python / Regex / PyMuPDF / OR-Tools** | Missing-doc checks, IFSC/Aadhaar regex validation (as proven in `EnterpriseFlow AI`), timezone slot intersection, weighted math scoring, `sqlglot` SQL checks, hidden PDF text detection. | **0 LLM tokens**, <10ms |
| **Tier 1** | **Lightweight SLM (`gemini-3.5-flash-lite` / local 3B-8B SLM)** | Gray-zone intent adjudication, resume structured JSON extraction, JD bias keyword validation, output JSON repair. | ~$0.07–$0.15 / 1M tokens, <300ms |
| **Tier 2** | **Balanced Mid-Tier (`gemini-3.5-flash` / `gemini-3.8-flash`)** | Rubric candidate evaluation, JD drafting, HR policy RAG synthesis, onboarding orchestration. | Balanced quality/cost |
| **Tier 3** | **Frontier Reasoning Model (Escalation Only)** | Close-tie shortlist arbitration, complex multi-join HR Analytics SQL + Python cohort debugging, escalated low-confidence edge cases. | Escalated on `< 10%` of requests |

* **Expected Impact:** **60%–85% spend reduction** while preserving frontier-level reasoning where it actually moves quality needles.
* **Limitations:** Cascading introduces extra latency if Tier 1 fails and falls back to Tier 2/3; mitigated by routing explicitly by node type rather than speculative retry-cascading on every query.

### Strategy 4: Progressive MCP Tool Discovery & Schema Compression
* **Why Needed:** Passing full verbose OpenAPI/MCP JSON schemas for all connected integrations on every agent turn wastes thousands of input tokens.
* **How It Works:**
  1. **Rental Allowlist Filtering:** Never bind tools outside `agent_rentals.allowed_tools`.
  2. **2-Step Lazy Schema Loading:** By default, pass a compact 1-line tool index (`name: 8-word description`) costing ~25 tokens/tool. Only hydrate the full JSON parameter schema into context for the 1–2 tools the agent selects for execution.
  3. **Schema Minimization:** Strip redundant prose descriptions, unused optional flags, and deeply nested metadata examples from MCP schemas at registration time.
* **Expected Impact:** Reduces tool-definition token overhead by **50%–90%** per agentic turn.
* **Limitations:** Adds one lightweight selection step for rarely used tools; keep the top 2–3 core tools per agent pre-hydrated to avoid extra round trips on the common path.

### Strategy 5: Pre-LLM Document & Playwright DOM Distillation
* **Why Needed:** Raw PDF extractions contain repeated page headers, footers, ASCII borders, and whitespace; raw browser HTML contains megabytes of CSS/scripts.
* **How It Works:**
  * **PDF/Resume Distillation (Sandbox):** PyMuPDF extracts text + strips repeated page headers/footers, collapses whitespace, normalizes bullet lists, and segments sections (`Experience`, `Education`, `Skills`) before sending text to the LLM.
  * **Playwright Accessibility Tree (AXTree) Extraction:** When Playwright inspects a careers portal or candidate portfolio, extract the semantic **Accessibility Snapshot (`page.accessibility.snapshot()`)** or cleaned Reader-mode Markdown—never raw HTML `page.content()`.
* **Expected Impact:** Shrinks web page payloads from **50k–100k tokens (raw HTML)** down to **1k–2.5k tokens (AXTree/Markdown)** — a **95%+ reduction** with *higher* LLM accuracy (less noise!).
* **Limitations:** Highly visual/canvas-based pages may lack clean accessibility labels; fallback to targeted screenshot OCR/vision only when AXTree text density falls below threshold.

### Strategy 6: Compact Structured Formats & Constrained Decoding
* **Why Needed:** Verbose JSON arrays of candidate attributes repeat field names (`"years_of_experience": 5`) dozens of times, and unconstrained prose responses waste expensive **output tokens** (often priced 3×–5× higher than input tokens).
* **How It Works:**
  * Enforce strict Pydantic `response_schema` / structured outputs with concise schema keys and `max_tokens` caps per node.
  * When passing 20 candidate profiles into the **Candidate Shortlisting Agent**, serialize them as a compact **Markdown / Pipe-delimited table** instead of repeated JSON objects (cuts structural punctuation/key tokens by ~35%–45%).
* **Limitations:** Overly cryptic 2-letter schema keys can slightly hurt smaller SLM reasoning; use clear concise keys (`exp_yrs`, `match_score`, `evidence`) and map back to descriptive API fields in Python.

### Strategy 7: LangGraph Sliding-Window & Rolling State Summarization
* **Why Needed:** Multi-turn HR interviews/onboarding chats accumulate huge `messages` lists including prior raw tool outputs.
* **How It Works:** Keep only the last $K=4$ conversational turns verbatim in the prompt, compress older turns into a rolling `state.conversation_summary` (~250 tokens updated asynchronously by Tier 1 SLM), and **never keep raw bulk tool payloads** (e.g., 50-row SQL outputs or full PDF text) in message history—store large payloads in DB/artifacts and retain only concise handle IDs + summary stats in `AgentState`.
* **Expected Impact:** Prevents quadratic token growth across multi-turn sessions (caps per-turn history at ~1,500 tokens vs 30,000+ tokens).

### Strategy 8: Hybrid Retrieval + Reranking with Strict Context Budgets
* **Why Needed:** Naive top-10 vector RAG drags in overlapping, marginally relevant handbook pages that confuse the LLM and inflate input tokens.
* **How It Works:** Retrieve top-20 candidates fast using BM25 + `pgvector` cosine hybrid search, run a fast local cross-encoder reranker (or lightweight metadata boost), and inject **only the top 3–5 non-overlapping chunks** capped at a strict **1,500-token context budget**.
* **Expected Impact:** Cuts RAG prompt tokens by **50%–70%** while **improving** answer faithfulness ("lost-in-the-middle" reduction).

### Strategy 9: Early-Exit Out-of-Domain Rejection & Pre-Flight Quotas
* **Why Needed:** Rejecting an off-topic query *inside* LangGraph after loading the agent system prompt, memory, and tool schemas still bills thousands of input tokens.
* **How It Works:** Run Stage 0 (regex) and Stage 1 (embedding boundary) *before* LangGraph initialization. Out-of-domain queries cost **0 generation tokens** (or ~120 SLM tokens in Stage 2 gray zones).
* **Expected Impact:** Near-zero cost on spam, jailbreak probes, and off-topic requests.

### Strategy 10: Cross-Agent Artifact Reuse (Parse Once, Evaluate Many)
* **Why Needed:** If a candidate applies and moves through Screening → Shortlisting → Interview Scheduling → Onboarding, re-running LLM extraction on their PDF resume or offer letter at each agent multiplies inference costs by 3×–4×.
* **How It Works:** The *Recruitment Screening Agent* extracts a canonical, versioned `CandidateProfile` JSON upon ingestion and persists it in PostgreSQL (`candidates.parsed_profile_json`). Subsequent agents read the structured DB record directly (0 OCR / 0 re-extraction tokens).

---

## 3. Worked Token Economics Comparison (Illustrative Estimate)

Consider screening **25 PDF resumes** (avg. 3 pages / 2,500 raw tokens each) and shortlisting the top 5 for a Senior Backend role:

| Stage | Naive Unoptimized Agent | Rent-an-Agent Optimized Pipeline | Savings Driver |
| :--- | :--- | :--- | :--- |
| **1. Resume Parsing (25 docs)** | 25 × (2,500 raw + 1,500 prompt) on Frontier LLM ≈ **100k in / 15k out** | Sandbox PyMuPDF distill + Tier 1 SLM (`flash-lite`) + cached prefix + reuse DB profile ≈ **35k in (cached) / 6k out** | Distillation + Tier 1 SLM + KV Prefix Cache |
| **2. Tool Schemas (5 turns)** | 35 full MCP schemas injected per turn ≈ **45k in** | Rental allowlist + compressed lazy schema index ≈ **4k in** | Progressive MCP Loading |
| **3. Shortlist Ranking (25 profiles)** | Full JSON resumes stuffed into Frontier context ≈ **65k in / 4k out** | Deterministic knockout filter eliminates 15; compact table of top 10 scored via Tier 2 (`flash`) ≈ **5k in / 1.5k out** | Deterministic pre-filter + Compact Table |
| **4. Out-of-Domain Noise (3 probes)** | Loaded full graph & rejected via Frontier ≈ **18k in / 0.5k out** | Rejected at Tier 0/1 semantic gate ≈ **0.2k SLM tokens** | Early-Exit Classifier |
| **Total Estimated Spend** | ~**228k input / 19.5k output** (all Frontier rates) | ~**44k input (mostly cached/SLM) / 7.5k output (Flash-Lite/Flash)** | **~80%+ token volume cut & ~90%+ USD cost cut** |

*(Note: Exact real-world savings depend on document length, cache hit rates, and chosen provider pricing; verified empirically during Phase 6 benchmarking.)*

---

## 4. Token Metering, Budgets & Quality Preservation

### 4.1 Real-Time Metering & Circuit Breakers
1. **Normalized Usage Capture:** Every LLM call through `llm_gateway` captures `input_tokens`, `cached_input_tokens`, `output_tokens`, `model_id`, and `latency_ms`, writing an entry to `token_usage_ledger` linked to `(tenant_id, rental_id, run_id, agent_step)`.
2. **Pre-Flight Budget Check & Reservation:** Before launching a LangGraph run, Redis checks `tenant_monthly_tokens_used < rental.monthly_token_cap`. During batch loops (e.g., screening 200 resumes), each loop iteration checks remaining budget and suspends gracefully if a tenant hits 100% quota rather than failing silently mid-batch.
3. **Hard Recursion & Step Limits:** Every LangGraph invocation passes `recursion_limit=15` and `max_run_tokens` so infinite loops are impossible.

### 4.2 Quality Preservation Verification (Zero-Regression Guard)
Optimizations must never silently degrade hiring quality or policy accuracy:
* **Golden HR Evaluation Dataset:** Maintain synthetic benchmark suites for each of the 7 agents (e.g., 50 labeled resumes with ground-truth rubric scores, 40 HR handbook Q&A pairs with expected citations, 25 SQL analytics prompts, 30 out-of-domain adversarial prompts).
* **A/B Quality Gate:** Any prompt compression, schema minimization, or Tier-1 routing downgrade must score within **$\le 2\%$ F1 / faithfulness variance** against the unoptimized baseline on the golden eval set before promotion.

---

## 5. MVP vs. Production Optimization Matrix

| Optimization Feature | MVP Scope | Production Infrastructure |
| :--- | :--- | :--- |
| **Prompt Caching** | Static-first prefix prompt ordering + Gemini context/implicit caching support. | Multi-provider KV cache alignment + automated prefix-hit ratio telemetry alerts. |
| **Semantic Cache** | Redis exact + vector embedding lookup (`tenant_id + rental_id + kb_hash`). | Clustered Redis Enterprise / Qdrant cache with adaptive per-agent similarity thresholds. |
| **Model Routing** | Static node-level tier assignment (Tier 0 rules → Tier 1 `flash-lite` → Tier 2 `flash`). | Dynamic confidence-based cascading + RouteLLM / self-hosted quantized SLM pool. |
| **MCP Tool Loading** | Per-rental allowlist filtering + compressed static tool descriptions. | Full 2-step dynamic meta-tool index for tenants connecting 20+ MCP servers. |
| **Quota & Billing** | PostgreSQL `token_usage_ledger` + Redis monthly counter + hard cap stop. | Real-time sliding-window rate limits + Stripe usage-based overage billing webhooks. |
