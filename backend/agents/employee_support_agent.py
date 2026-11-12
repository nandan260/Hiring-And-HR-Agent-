"""Agent 6: Employee Support & HR Policy Agent (Tenant-Isolated pgvector RAG with Mandatory Citations)."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from .framework.base_agent import BaseSpecializedAgent
from .framework.llm_provider import llm_provider
from .framework.rag import semantic_search_knowledge
from .framework.schemas import (
    BaseAgentInput,
    BaseAgentOutput,
    DomainDefinition,
    ExecutionLimits,
    GuardrailConfig,
    KnowledgeBaseConfig,
    MemoryConfig,
    ModelConfig,
    ToolPermissionConfig,
)
from .framework.state import AgentExecutionState
from .framework.tools import AgentToolBox, ToolContext


class EmployeeSupportInput(BaseAgentInput):
    policy_category: Optional[str] = Field(default=None, description="leave | attendance | payroll | benefits | general")
    open_escalation_ticket: bool = False


class PolicyChunkCitation(BaseModel):
    document_id: str
    document_title: str
    section_title: str
    similarity: float
    excerpt: str


class EmployeeSupportOutput(BaseAgentOutput):
    answer: str
    policy_category: str
    grounded_in_tenant_docs: bool
    retrieved_chunks: list[PolicyChunkCitation]


def _classify_policy_category(prompt: str, override: Optional[str]) -> str:
    if override:
        return override
    low = (prompt or "").lower()
    if any(w in low for w in ["leave", "pto", "parental", "maternity", "paternity", "sick", "vacation", "holiday"]):
        return "leave"
    if any(w in low for w in ["attendance", "hybrid", "remote", "working hours", "wfh"]):
        return "attendance"
    if any(w in low for w in ["payroll", "salary", "payday", "reimbursement", "stipend", "expense"]):
        return "payroll"
    if any(w in low for w in ["benefit", "insurance", "medical", "dental", "vision", "401k", "retirement"]):
        return "benefits"
    return "general"


class EmployeeSupportAgent(BaseSpecializedAgent):
    """Answers HR policy, leave, attendance, payroll, and benefits queries using tenant pgvector RAG."""

    agent_id = "hr-policy-support"
    agent_name = "Employee Support & HR Policy Agent"
    agent_version = "1.2.0"
    system_prompt_file = "employee_support_agent.md"
    domain = DomainDefinition(
        domain_name="Employee Support & HR Policies",
        allowed_topics=[
            "leave and PTO policy questions",
            "attendance and hybrid work guidelines",
            "payroll schedule and expense reimbursements",
            "employee benefits and retirement plans",
            "tenant HR handbook retrieval with citations",
        ],
        rejected_categories={
            "Medical Diagnosis & Clinical Advice": "Healthcare",
            "Financial Trading & Cryptocurrency": "Business and Finance",
            "Legal Litigation & Contract Redlining": "Legal and Compliance",
        },
        in_domain_keywords=[
            "leave",
            "pto",
            "parental",
            "maternity",
            "paternity",
            "sick",
            "holiday",
            "attendance",
            "hybrid",
            "remote",
            "payroll",
            "payday",
            "salary",
            "reimbursement",
            "stipend",
            "benefits",
            "insurance",
            "medical",
            "dental",
            "401k",
            "policy",
            "handbook",
            "policy",
            "employee",
            "hr",
            "compensation",
            "bonus",
        ],
        min_keyword_hits=1,
        suggested_marketplace_category="Hiring and HR",
    )
    input_schema = EmployeeSupportInput
    output_schema = EmployeeSupportOutput
    allowed_tools = [
        "tenant_policy_rag_search",
        "jira_create_hr_escalation",
    ]
    tool_permissions = ToolPermissionConfig(
        default_allowed_tools=allowed_tools,
        hitl_required_tools=["jira_create_hr_escalation"],
        read_only_tools=["tenant_policy_rag_search"],
    )
    knowledge_base = KnowledgeBaseConfig(
        enabled=True,
        top_k=4,
        min_similarity=0.14,
        require_citations=True,
        allowed_source_types=["handbook", "policy", "jd_template"],
    )
    model_cfg = ModelConfig(provider="auto", model_tier="tier_1_slm", temperature=0.05, max_tokens=1200)
    guardrails = GuardrailConfig(
        block_prompt_injection=True,
        block_protected_characteristics=True,
        require_citation_grounding=True,
    )
    memory = MemoryConfig(short_term_window_messages=10, summary_max_tokens=300, persist_to_db=True)
    execution_limits = ExecutionLimits(max_steps=10, max_tool_calls=4, max_input_tokens=6000, max_output_tokens=1400)

    def register_tools(self, toolbox: AgentToolBox) -> None:
        toolbox.register("tenant_policy_rag_search", self._tool_tenant_policy_rag_search)
        toolbox.register("jira_create_hr_escalation", self._tool_jira_create_hr_escalation)

    def _tool_tenant_policy_rag_search(self, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query", ""))
        hits = semantic_search_knowledge(
            ctx.db,
            tenant_id=ctx.tenant_id,
            rental_id=ctx.rental_id,
            actor_role=ctx.actor_role,
            query=query,
            top_k=self.knowledge_base.top_k,
            min_similarity=self.knowledge_base.min_similarity,
            source_types=["handbook", "policy", "jd_template"],
        )
        # If rental-specific search returned nothing, allow tenant-wide handbook docs (still strict tenant_id + min_role_access)
        if not hits and ctx.rental_id is not None:
            hits = semantic_search_knowledge(
                ctx.db,
                tenant_id=ctx.tenant_id,
                rental_id=None,
                actor_role=ctx.actor_role,
                query=query,
                top_k=self.knowledge_base.top_k,
                min_similarity=self.knowledge_base.min_similarity,
                source_types=["handbook", "policy"],
            )
        return {"hits": hits, "actor_role": ctx.actor_role}

    def _tool_jira_create_hr_escalation(self, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        return {"escalation_staged": True, "topic": args.get("topic", "HR Policy Exception")}

    def select_tools(
        self,
        parsed_input: EmployeeSupportInput,
        state: AgentExecutionState,
        ctx: ToolContext,
    ) -> list[dict[str, Any]]:
        planned = [{"tool": "tenant_policy_rag_search", "args": {"query": parsed_input.prompt}}]
        if parsed_input.open_escalation_ticket:
            planned.append({"tool": "jira_create_hr_escalation", "args": {"topic": parsed_input.prompt[:160]}})
        return planned

    def synthesize_output(
        self,
        parsed_input: EmployeeSupportInput,
        tool_results: list[dict[str, Any]],
        memory_ctx: dict[str, Any],
        state: AgentExecutionState,
        ctx: ToolContext,
    ) -> tuple[EmployeeSupportOutput, dict[str, Any]]:
        category = _classify_policy_category(parsed_input.prompt, parsed_input.policy_category)
        hits: list[dict[str, Any]] = []
        for res in tool_results:
            if res.get("status") == "completed" and res["tool"] == "tenant_policy_rag_search":
                hits = list(res["output"].get("hits", []))

        # Keep high-confidence hits grounded to actual policy tokens when similarity comes purely from noise
        query_words = {
            w for w in parsed_input.prompt.lower().replace("?", "").split() if len(w) >= 3
        }
        relevant_hits = [
            h for h in hits
            if h["similarity"] >= 0.16 or any(w in f"{h['section_title']} {h['excerpt']}".lower() for w in query_words)
        ]

        citations = [
            f"[{h['document_title']} - {h['section_title']}] (similarity {h['similarity']:.2f})"
            for h in relevant_hits[:3]
        ]

        if not relevant_hits:
            no_doc_msg = (
                "No matching policy document was found in your company's indexed HR Knowledge Base "
                f"(or your current role `{ctx.actor_role}` lacks access to restricted policies). "
                "Please upload the relevant policy handbook or escalate this question to your HR team."
            )
            hitl_reqs = [
                {
                    "action_type": "hr_policy_escalation",
                    "title": "Escalate Unanswered HR Policy Question to Human HR Desk",
                    "summary": parsed_input.prompt[:200],
                    "payload": {"query": parsed_input.prompt, "policy_category": category},
                }
            ]
            output = EmployeeSupportOutput(
                agent_id=self.agent_id,
                agent_version=self.agent_version,
                summary=no_doc_msg,
                explanation="Strict RAG grounding guardrail prevented answering without verified tenant policy chunks.",
                citations=[],
                requires_human_approval=True,
                hitl_requests=hitl_reqs,
                structured_payload={"grounded_in_tenant_docs": False, "policy_category": category},
                answer=no_doc_msg,
                policy_category=category,
                grounded_in_tenant_docs=False,
                retrieved_chunks=[],
            )
            return output, {
                "provider_used": "deterministic",
                "model_used": "rag-grounding-refusal",
                "input_tokens": max(30, len(parsed_input.prompt) // 4),
                "cached_tokens": 0,
                "output_tokens": 45,
                "estimated_cost_usd": 0.0,
            }

        def _fallback_json(_context: dict[str, Any] | None = None) -> dict[str, Any]:
            top_sections = []
            for h in relevant_hits[:2]:
                top_sections.append(f"**{h['section_title']}** ({h['document_title']}): {h['excerpt']}")
            answer_text = "\n\n".join(top_sections)
            return {
                "answer": answer_text,
                "summary": answer_text,
                "explanation": f"Grounded directly in {len(relevant_hits)} tenant-isolated pgvector document chunk(s).",
            }

        llm_res = llm_provider.generate_structured(
            system_prompt=self.load_system_prompt(state.get("custom_persona_prompt", "")),
            user_prompt=parsed_input.prompt,
            context_data={"policy_category": category, "retrieved_chunks": relevant_hits[:3]},
            fallback_fn=_fallback_json,
            provider_override=state.get("model_provider_override"),
            temperature=self.model_cfg.temperature,
            max_tokens=self.model_cfg.max_tokens,
        )
        fb = _fallback_json()
        parsed = llm_res.parsed_json or fb

        retrieved_models = [
            PolicyChunkCitation(
                document_id=h["document_id"],
                document_title=h["document_title"],
                section_title=h["section_title"],
                similarity=h["similarity"],
                excerpt=h["excerpt"],
            )
            for h in relevant_hits[:3]
        ]

        output = EmployeeSupportOutput(
            agent_id=self.agent_id,
            agent_version=self.agent_version,
            summary=str(parsed.get("summary") or fb["summary"]),
            explanation=str(parsed.get("explanation") or fb["explanation"]),
            citations=citations,
            requires_human_approval=parsed_input.open_escalation_ticket,
            hitl_requests=(
                [
                    {
                        "action_type": "hr_policy_escalation",
                        "title": "Submit HR Policy Escalation Ticket",
                        "summary": parsed_input.prompt[:200],
                        "payload": {"query": parsed_input.prompt, "policy_category": category},
                    }
                ]
                if parsed_input.open_escalation_ticket
                else []
            ),
            structured_payload={
                "grounded_in_tenant_docs": True,
                "policy_category": category,
                "citation_count": len(citations),
            },
            answer=str(parsed.get("answer") or fb["answer"]),
            policy_category=category,
            grounded_in_tenant_docs=True,
            retrieved_chunks=retrieved_models,
        )
        metrics = {
            "provider_used": llm_res.provider_used,
            "model_used": llm_res.model_used,
            "input_tokens": llm_res.input_tokens,
            "cached_tokens": llm_res.cached_tokens,
            "output_tokens": llm_res.output_tokens,
            "estimated_cost_usd": llm_res.estimated_cost_usd,
        }
        return output, metrics
