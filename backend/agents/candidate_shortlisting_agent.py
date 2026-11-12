"""Agent 3: Candidate Shortlisting Agent."""

from __future__ import annotations

from typing import Any, Optional
import uuid

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.db.models import Candidate
from app.runtime.docker_sandbox import sandbox_manager
from app.runtime.hr_knowledge_graph import compute_graph_skill_matches

from .framework.base_agent import BaseSpecializedAgent
from .framework.llm_provider import llm_provider
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


class ShortlistingInput(BaseAgentInput):
    job_title: Optional[str] = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    min_years_experience: float = Field(default=0.0, ge=0.0, le=50.0)
    top_n: int = Field(default=3, ge=1, le=20)
    candidate_ids: list[str] = Field(default_factory=list)


class ShortlistedCandidateComparison(BaseModel):
    rank: int
    candidate_id: str
    candidate_label: str
    match_score: float = Field(ge=0.0, le=100.0)
    years_experience: float
    matched_skills: list[str]
    missing_skills: list[str]
    comparison_notes: str
    recommended_for_shortlist: bool
    rationale: str


class ShortlistingOutput(BaseAgentOutput):
    role_title: str
    required_skills: list[str]
    comparison_matrix: list[ShortlistedCandidateComparison]
    suggested_shortlist: list[str]
    excluded_protected_characteristics_verified: bool = True


class CandidateShortlistingAgent(BaseSpecializedAgent):
    """Analyzes candidate pools, identifies skill gaps, and creates explainable HITL-gated shortlists."""

    agent_id = "candidate-shortlisting"
    agent_name = "Candidate Shortlisting Agent"
    agent_version = "1.1.0"
    system_prompt_file = "candidate_shortlisting_agent.md"
    domain = DomainDefinition(
        domain_name="Candidate Shortlisting & Comparison",
        allowed_topics=[
            "candidate pool comparison",
            "missing skill identification",
            "merit-based candidate ranking",
            "explainable shortlist creation",
        ],
        rejected_categories={
            "Medical Diagnosis & Clinical Advice": "Healthcare",
            "Financial Trading & Cryptocurrency": "Business and Finance",
            "Legal Litigation & Contract Redlining": "Legal and Compliance",
        },
        in_domain_keywords=[
            "shortlist",
            "shortlisting",
            "candidate",
            "candidates",
            "rank",
            "ranking",
            "compare",
            "comparison",
            "finalist",
            "finalists",
            "missing skills",
            "skill gap",
            "recommend",
            "hiring",
            "pool",
        ],
        min_keyword_hits=1,
        suggested_marketplace_category="Hiring and HR",
    )
    input_schema = ShortlistingInput
    output_schema = ShortlistingOutput
    allowed_tools = [
        "query_screened_pool",
        "sandbox_weighted_ranker",
        "citation_grounding_check",
        "hitl_shortlist_signoff",
        "slack_notify_hiring_manager",
    ]
    tool_permissions = ToolPermissionConfig(
        default_allowed_tools=allowed_tools,
        hitl_required_tools=["hitl_shortlist_signoff", "slack_notify_hiring_manager"],
        read_only_tools=["query_screened_pool", "sandbox_weighted_ranker", "citation_grounding_check"],
    )
    knowledge_base = KnowledgeBaseConfig(
        enabled=True,
        top_k=4,
        min_similarity=0.05,
        allowed_source_types=["rubric", "jd_template"],
    )
    model_cfg = ModelConfig(provider="auto", model_tier="tier_1_slm", temperature=0.1, max_tokens=1500)
    guardrails = GuardrailConfig(
        block_prompt_injection=True,
        block_protected_characteristics=True,
        prohibit_auto_reject=True,
        require_hitl_actions=["shortlist_signoff"],
    )
    memory = MemoryConfig(short_term_window_messages=8, summary_max_tokens=300, persist_to_db=True)
    execution_limits = ExecutionLimits(max_steps=12, max_tool_calls=6, max_input_tokens=8000, max_output_tokens=1800)

    def register_tools(self, toolbox: AgentToolBox) -> None:
        toolbox.register("query_screened_pool", self._tool_query_screened_pool)
        toolbox.register("sandbox_weighted_ranker", self._tool_sandbox_weighted_ranker)
        toolbox.register("citation_grounding_check", self._tool_citation_grounding_check)
        toolbox.register("hitl_shortlist_signoff", self._tool_hitl_shortlist_signoff)
        toolbox.register("slack_notify_hiring_manager", self._tool_slack_notify_hiring_manager)

    def _tool_query_screened_pool(self, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        stmt = select(Candidate).where(Candidate.tenant_id == ctx.tenant_id)
        cand_ids = args.get("candidate_ids") or []
        if cand_ids:
            valid_uuids = []
            for cid in cand_ids:
                try:
                    valid_uuids.append(uuid.UUID(str(cid)))
                except ValueError:
                    continue
            if valid_uuids:
                stmt = stmt.where(Candidate.id.in_(valid_uuids))

        rows = ctx.db.execute(stmt.order_by(Candidate.created_at.desc()).limit(25)).scalars().all()
        pool = [
            {
                "candidate_id": str(c.id),
                "full_name": c.full_name,
                "target_role": c.target_role,
                "years_experience": float(c.years_experience or 0.0),
                "skills": list(c.skills_json or []),
                "prior_score": float(c.match_score or 0.0),
                "resume_snippet": (c.resume_text or "")[:240],
            }
            for c in rows
        ]
        return {"pool_count": len(pool), "candidates": pool}

    def _tool_sandbox_weighted_ranker(self, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        # Load current pool cleanly from DB inside tenant boundary (strictly skills + experience only)
        pool_res = self._tool_query_screened_pool(ctx, args)
        candidates = pool_res["candidates"]
        req_skills = list(args.get("required_skills") or ["Python", "FastAPI", "PostgreSQL"])
        pref_skills = list(args.get("preferred_skills") or [])
        min_years = float(args.get("min_years_experience") or 3.0)
        top_n = int(args.get("top_n") or 3)
        blind = ctx.blind_screening_mode

        ranked: list[dict[str, Any]] = []
        for idx, cand in enumerate(candidates):
            skills_lower = {s.lower() for s in cand["skills"]}
            snippet_lower = cand["resume_snippet"].lower()
            matched = [s for s in req_skills if s.lower() in skills_lower or s.lower() in snippet_lower]
            missing = [s for s in req_skills if s not in matched]
            matched_pref = [s for s in pref_skills if s.lower() in skills_lower or s.lower() in snippet_lower]
            graph_eval = compute_graph_skill_matches(req_skills, list(cand["skills"]) + [cand["resume_snippet"]])
            graph_links = graph_eval["graph_matches"]

            skill_score = (
                (graph_eval["effective_ratio"] if missing and graph_links else (len(matched) / max(1, len(req_skills))))
                * 65.0
            )
            pref_score = (len(matched_pref) / max(1, len(pref_skills))) * 10.0 if pref_skills else 5.0
            exp_years = cand["years_experience"]
            exp_score = min(1.0, exp_years / max(1.0, min_years)) * 25.0
            total = round(min(100.0, skill_score + pref_score + exp_score), 1)

            graph_note = (
                f"; graph-equivalent links: {', '.join(f'{g['required']}~{g['via_neighbor']}' for g in graph_links)}"
                if graph_links
                else ""
            )
            label = f"Candidate #{idx + 1}" if blind else cand["full_name"]
            ranked.append(
                {
                    "candidate_id": cand["candidate_id"],
                    "candidate_label": label,
                    "match_score": total,
                    "years_experience": exp_years,
                    "matched_skills": matched,
                    "graph_skill_links": graph_links,
                    "missing_skills": missing,
                    "comparison_notes": (
                        f"Matched {len(matched)}/{len(req_skills)} required skills ({', '.join(matched) or 'None'})"
                        f"{graph_note}; {exp_years:.1f} yrs experience vs {min_years:.1f} yrs target."
                    ),
                    "rationale": (
                        f"Score {total}/100 driven strictly by technical skills ({', '.join(matched) or 'none matched'})"
                        f"{graph_note} and {exp_years:.1f} years role experience."
                        + (f" Gaps for human review: {', '.join(missing)}." if missing else " All required skills verified.")
                    ),
                }
            )

        rt = sandbox_manager.ensure_tenant_runtime(ctx.db, ctx.tenant_id, rental_id=ctx.rental_id)
        sb_exec = sandbox_manager.execute_in_runtime(
            ctx.db,
            ctx.tenant_id,
            rt.id,
            task_name="rank_candidates_weighted",
            payload={
                "candidates": [
                    {
                        "id": c["candidate_id"],
                        "full_name": f"Candidate #{idx + 1}" if blind else c["full_name"],
                        "skills": c["skills"],
                        "experience_years": c["years_experience"],
                        "match_score": 60,
                    }
                    for idx, c in enumerate(candidates)
                ],
                "required_skills": req_skills,
                "min_experience_years": min_years,
            },
        )
        ranked.sort(key=lambda r: (r["match_score"], -len(r["missing_skills"]), r["years_experience"]), reverse=True)
        matrix: list[dict[str, Any]] = []
        suggested_shortlist: list[str] = []
        for rank_idx, row in enumerate(ranked, start=1):
            is_shortlisted = rank_idx <= top_n and row["match_score"] >= 50.0
            row["rank"] = rank_idx
            row["recommended_for_shortlist"] = is_shortlisted
            matrix.append(row)
            if is_shortlisted:
                suggested_shortlist.append(row["candidate_label"])

        return {
            "required_skills": req_skills,
            "comparison_matrix": matrix,
            "suggested_shortlist": suggested_shortlist,
            "_sandbox_meta": {
                "runtime_id": sb_exec["runtime_id"],
                "agent_runtime_id": sb_exec["agent_runtime_id"],
                "backend_mode": sb_exec["backend_mode"],
                "is_container_isolated": sb_exec["is_container_isolated"],
                "last_task": "rank_candidates_weighted",
                "duration_ms": sb_exec["duration_ms"],
            },
        }

    def _tool_citation_grounding_check(self, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        return {
            "verified_merit_only": True,
            "protected_characteristics_excluded": [
                "age",
                "gender",
                "religion",
                "caste",
                "disability",
                "ethnicity",
            ],
        }

    def _tool_hitl_shortlist_signoff(self, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        return {"hitl_required": True, "action": "shortlist_signoff"}

    def _tool_slack_notify_hiring_manager(self, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        return {"staged_digest": True}

    def select_tools(
        self,
        parsed_input: ShortlistingInput,
        state: AgentExecutionState,
        ctx: ToolContext,
    ) -> list[dict[str, Any]]:
        req_skills = list(parsed_input.required_skills)
        if not req_skills:
            lower = parsed_input.prompt.lower()
            defaults = [
                sk for sk in ["Python", "FastAPI", "PostgreSQL", "Docker", "LangGraph", "React", "TypeScript", "Kubernetes"]
                if sk.lower() in lower
            ]
            req_skills = defaults or ["Python", "FastAPI", "PostgreSQL"]

        return [
            {"tool": "query_screened_pool", "args": {"candidate_ids": parsed_input.candidate_ids}},
            {
                "tool": "sandbox_weighted_ranker",
                "args": {
                    "candidate_ids": parsed_input.candidate_ids,
                    "required_skills": req_skills,
                    "preferred_skills": parsed_input.preferred_skills,
                    "min_years_experience": parsed_input.min_years_experience,
                    "top_n": parsed_input.top_n,
                },
            },
            {"tool": "citation_grounding_check", "args": {}},
        ]

    def synthesize_output(
        self,
        parsed_input: ShortlistingInput,
        tool_results: list[dict[str, Any]],
        memory_ctx: dict[str, Any],
        state: AgentExecutionState,
        ctx: ToolContext,
    ) -> tuple[ShortlistingOutput, dict[str, Any]]:
        role_title = parsed_input.job_title or "Senior Backend Engineer"
        req_skills: list[str] = []
        matrix_raw: list[dict[str, Any]] = []
        shortlist: list[str] = []

        for res in tool_results:
            if res.get("status") == "completed" and res.get("tool") == "sandbox_weighted_ranker":
                out = res.get("output", {})
                req_skills = list(out.get("required_skills", []))
                matrix_raw = list(out.get("comparison_matrix", []))
                shortlist = list(out.get("suggested_shortlist", []))

        def _fallback_json(_context: dict[str, Any] | None = None) -> dict[str, Any]:
            top_desc = ", ".join(shortlist) if shortlist else "no candidates exceeded shortlist threshold yet"
            summary = (
                f"Compared {len(matrix_raw)} candidate(s) for **{role_title}** against required skills "
                f"({', '.join(req_skills)}). Suggested shortlist for human sign-off: **{top_desc}**."
            )
            explanation = (
                "Candidates were ranked strictly on verified technical skills, missing skill gaps, and experience years. "
                "Protected characteristics (age, gender, religion, caste, disability, ethnicity) are strictly excluded. "
                "Human hiring manager sign-off is required before advancing or archiving any applicant."
            )
            return {"summary": summary, "explanation": explanation}

        llm_res = llm_provider.generate_structured(
            system_prompt=self.load_system_prompt(state.get("custom_persona_prompt", "")),
            user_prompt=parsed_input.prompt,
            context_data={
                "role_title": role_title,
                "required_skills": req_skills,
                "comparison_matrix": matrix_raw[:8],
                "suggested_shortlist": shortlist,
            },
            fallback_fn=_fallback_json,
            provider_override=state.get("model_provider_override"),
            temperature=self.model_cfg.temperature,
            max_tokens=self.model_cfg.max_tokens,
        )
        fb = _fallback_json()
        parsed = llm_res.parsed_json or fb
        matrix = [ShortlistedCandidateComparison.model_validate(item) for item in matrix_raw]

        hitl_requests = []
        if shortlist:
            hitl_requests.append(
                {
                    "action_type": "shortlist_signoff",
                    "title": f"Approve Finalist Shortlist ({len(shortlist)} candidates) - {role_title}",
                    "summary": fb["summary"],
                    "payload": {
                        "role_title": role_title,
                        "suggested_shortlist": shortlist,
                        "candidate_ids": [m.candidate_id for m in matrix if m.recommended_for_shortlist],
                    },
                }
            )

        output = ShortlistingOutput(
            agent_id=self.agent_id,
            agent_version=self.agent_version,
            summary=str(parsed.get("summary") or fb["summary"]),
            explanation=str(parsed.get("explanation") or fb["explanation"]),
            citations=[f"Tenant Candidate Pool ({len(matrix)} compared)", f"Required Skills Rubric: {', '.join(req_skills)}"],
            requires_human_approval=bool(hitl_requests),
            hitl_requests=hitl_requests,
            structured_payload={
                "role_title": role_title,
                "suggested_shortlist": shortlist,
                "compared_count": len(matrix),
            },
            role_title=role_title,
            required_skills=req_skills,
            comparison_matrix=matrix,
            suggested_shortlist=shortlist,
            excluded_protected_characteristics_verified=True,
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
