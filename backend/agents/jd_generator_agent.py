"""Agent 2: Job Description Generator Agent."""

from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import Field

from app.runtime.playwright_browser import BrowserSecurityError, browser_manager

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

BIASED_PHRASE_REPLACEMENTS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"\brockstar\b", re.IGNORECASE), "high-impact engineer", "Replaced 'rockstar' with 'high-impact engineer'"),
    (re.compile(r"\bninja\b", re.IGNORECASE), "specialist", "Replaced 'ninja' with 'specialist'"),
    (re.compile(r"\bguru\b", re.IGNORECASE), "subject-matter expert", "Replaced 'guru' with 'subject-matter expert'"),
    (re.compile(r"\byoung\s+and\s+energetic\b", re.IGNORECASE), "motivated and collaborative", "Removed age-coded phrase 'young and energetic'"),
    (re.compile(r"\bdigital\s+native\b", re.IGNORECASE), "proficient with modern digital tools", "Replaced age-coded phrase 'digital native'"),
    (re.compile(r"\bmanpower\b", re.IGNORECASE), "workforce capacity", "Replaced gendered term 'manpower'"),
    (re.compile(r"\bguys\b", re.IGNORECASE), "team members", "Replaced gendered term 'guys'"),
    (re.compile(r"\bhe/she\b", re.IGNORECASE), "they", "Replaced binary pronoun 'he/she' with 'they'"),
]

COMMON_JD_SKILLS = [
    "Python",
    "FastAPI",
    "PostgreSQL",
    "pgvector",
    "LangGraph",
    "Docker",
    "Kubernetes",
    "React",
    "TypeScript",
    "AWS",
    "Redis",
    "Kafka",
    "SQL",
    "Terraform",
    "CI/CD",
    "REST APIs",
    "Distributed Systems",
    "Row-Level Security",
]


class JDGeneratorInput(BaseAgentInput):
    job_title: Optional[str] = None
    department: str = Field(default="Engineering")
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    experience_level: Optional[str] = None
    work_mode: str = Field(default="Hybrid")
    location: str = Field(default="Remote / Hybrid")


class JDGeneratorOutput(BaseAgentOutput):
    job_title: str
    suggested_experience_level: str
    experience_range_years: str
    role_overview: str
    responsibilities: list[str]
    must_have_qualifications: list[str]
    nice_to_have_qualifications: list[str]
    inclusive_language_findings: list[str]
    inclusive_language_score: int = Field(ge=0, le=100)
    formatted_job_description_markdown: str


def _infer_title_and_level(parsed_input: JDGeneratorInput) -> tuple[str, str, str]:
    prompt = parsed_input.prompt
    title = parsed_input.job_title
    if not title:
        m = re.search(
            r"(?:for\s+(?:a|an)?|job description\s+(?:for)?|role\s*:)\s*([A-Z][A-Za-z0-9/\s&-]{3,50}?)(?:\s+(?:with|requiring|in|who|,|\.|$))",
            prompt,
        )
        title = m.group(1).strip() if m else "Senior Software Engineer"

    level_text = f"{parsed_input.experience_level or ''} {title} {prompt}".lower()
    if any(w in level_text for w in ["staff", "principal", "architect"]):
        return title, "Staff / Principal (L5+)", "6+ years"
    if any(w in level_text for w in ["lead", "head", "director", "manager"]):
        return title, "Lead / Management", "5-8 years"
    if "senior" in level_text or "l4" in level_text:
        return title, "Senior (L4)", "4-6 years"
    if any(w in level_text for w in ["junior", "entry", "associate", "intern", "l3"]):
        return title, "Junior / Entry (L3)", "0-2 years"
    return title, "Mid-Level / Senior", "3-5 years"


def _infer_skills(parsed_input: JDGeneratorInput) -> tuple[list[str], list[str]]:
    lower_prompt = parsed_input.prompt.lower()
    detected = [sk for sk in COMMON_JD_SKILLS if sk.lower() in lower_prompt]
    req = list(parsed_input.required_skills) or detected[:5] or ["Python", "PostgreSQL", "API Design"]
    pref = list(parsed_input.preferred_skills) or [sk for sk in detected if sk not in req][:3] or ["Docker", "CI/CD"]
    return req, pref


class JobDescriptionGeneratorAgent(BaseSpecializedAgent):
    """Generates structured, leveled, and inclusive job descriptions."""

    agent_id = "jd-generator"
    agent_name = "Job Description Generator Agent"
    agent_version = "1.1.0"
    system_prompt_file = "jd_generator_agent.md"
    domain = DomainDefinition(
        domain_name="Job Description Generation",
        allowed_topics=[
            "job description drafting",
            "role responsibilities definition",
            "must-have and nice-to-have qualifications",
            "experience leveling alignment",
            "inclusive language review",
        ],
        rejected_categories={
            "Medical Diagnosis & Clinical Advice": "Healthcare",
            "Financial Trading & Cryptocurrency": "Business and Finance",
            "Legal Litigation & Contract Redlining": "Legal and Compliance",
        },
        in_domain_keywords=[
            "job description",
            "jd",
            "responsibilities",
            "qualifications",
            "hiring",
            "role",
            "position",
            "requirements",
            "skills",
            "experience level",
            "career",
            "requisition",
            "engineer",
            "manager",
            "designer",
            "analyst",
        ],
        min_keyword_hits=1,
        suggested_marketplace_category="Hiring and HR",
    )
    input_schema = JDGeneratorInput
    output_schema = JDGeneratorOutput
    allowed_tools = [
        "kb_search_leveling_guide",
        "inclusive_language_linter",
        "playwright_careers_style_check",
        "ats_create_draft_req",
    ]
    tool_permissions = ToolPermissionConfig(
        default_allowed_tools=allowed_tools,
        hitl_required_tools=["ats_create_draft_req"],
        read_only_tools=["kb_search_leveling_guide", "inclusive_language_linter", "playwright_careers_style_check"],
    )
    knowledge_base = KnowledgeBaseConfig(
        enabled=True,
        top_k=4,
        min_similarity=0.05,
        require_citations=False,
        allowed_source_types=["jd_template", "handbook", "policy"],
    )
    model_cfg = ModelConfig(provider="auto", model_tier="tier_1_slm", temperature=0.2, max_tokens=1500)
    guardrails = GuardrailConfig(block_prompt_injection=True, block_protected_characteristics=True)
    memory = MemoryConfig(short_term_window_messages=8, summary_max_tokens=300, persist_to_db=True)
    execution_limits = ExecutionLimits(max_steps=10, max_tool_calls=5, max_input_tokens=6000, max_output_tokens=1800)

    def register_tools(self, toolbox: AgentToolBox) -> None:
        toolbox.register("kb_search_leveling_guide", self._tool_kb_search_leveling_guide)
        toolbox.register("inclusive_language_linter", self._tool_inclusive_language_linter)
        toolbox.register("playwright_careers_style_check", self._tool_playwright_careers_style_check)
        toolbox.register("ats_create_draft_req", self._tool_ats_create_draft_req)

    def _tool_kb_search_leveling_guide(self, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        hits = semantic_search_knowledge(
            ctx.db,
            tenant_id=ctx.tenant_id,
            rental_id=None,
            actor_role=ctx.actor_role,
            query=args.get("query", "leveling compensation guide"),
            top_k=3,
            source_types=["jd_template", "handbook", "policy"],
        )
        return {"leveling_hits": hits}

    def _tool_inclusive_language_linter(self, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        text = str(args.get("text", ""))
        findings: list[str] = []
        sanitized = text
        for rx, repl, note in BIASED_PHRASE_REPLACEMENTS:
            if rx.search(sanitized):
                findings.append(note)
                sanitized = rx.sub(repl, sanitized)
        score = max(60, 100 - (len(findings) * 10))
        return {
            "sanitized_text": sanitized,
            "findings": findings,
            "inclusive_score": score,
        }

    def _tool_playwright_careers_style_check(self, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        target_url = str(args.get("careers_url") or "").strip()
        if not target_url:
            return {
                "style_checked": False,
                "status": "not_used",
                "structure": ["Overview", "Responsibilities", "Qualifications", "EEO Statement"],
                "note": "No careers URL supplied; using structured HR template rules",
            }
        try:
            page = browser_manager.navigate_and_extract(
                tenant_id=ctx.tenant_id,
                url=target_url,
                capture_screenshot=True,
            )
            return {
                "style_checked": True,
                "status": "completed",
                "visited_pages": [page],
                "structure": ["Overview", "Responsibilities", "Qualifications", "EEO Statement"],
            }
        except BrowserSecurityError as exc:
            return {"style_checked": False, "status": "blocked", "error": str(exc)}

    def _tool_ats_create_draft_req(self, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        return {"staged_draft": True}

    def select_tools(
        self,
        parsed_input: JDGeneratorInput,
        state: AgentExecutionState,
        ctx: ToolContext,
    ) -> list[dict[str, Any]]:
        title, level, _ = _infer_title_and_level(parsed_input)
        return [
            {
                "tool": "kb_search_leveling_guide",
                "args": {"query": f"{title} {level} leveling compensation band"},
            },
            {
                "tool": "inclusive_language_linter",
                "args": {"text": f"{parsed_input.prompt} {title}"},
            },
        ]

    def synthesize_output(
        self,
        parsed_input: JDGeneratorInput,
        tool_results: list[dict[str, Any]],
        memory_ctx: dict[str, Any],
        state: AgentExecutionState,
        ctx: ToolContext,
    ) -> tuple[JDGeneratorOutput, dict[str, Any]]:
        title, level, exp_years = _infer_title_and_level(parsed_input)
        req_skills, pref_skills = _infer_skills(parsed_input)

        kb_citations: list[str] = []
        kb_band_note = ""
        linter_findings: list[str] = []
        linter_score = 100

        for res in tool_results:
            if res.get("status") != "completed":
                continue
            out = res.get("output", {})
            if res["tool"] == "kb_search_leveling_guide":
                hits = out.get("leveling_hits", [])
                kb_citations = [f"{h['document_title']} ({h['section_title']})" for h in hits]
                if hits:
                    kb_band_note = hits[0]["excerpt"][:180]
            elif res["tool"] == "inclusive_language_linter":
                linter_findings = list(out.get("findings", []))
                linter_score = int(out.get("inclusive_score", 100))

        def _fallback_json(_context: dict[str, Any] | None = None) -> dict[str, Any]:
            overview = (
                f"We are seeking a **{title}** ({level}) to join our {parsed_input.department} team "
                f"({parsed_input.work_mode} — {parsed_input.location}). You will architect scalable systems, "
                f"collaborate cross-functionally, and mentor peers while upholding strong engineering rigor."
            )
            responsibilities = [
                f"Design, implement, and maintain production services using {', '.join(req_skills[:3])}.",
                "Write clean, well-tested code with peer code reviews, observability, and documentation.",
                "Partner with product, security, and platform teams to deliver reliable multi-tenant features.",
                "Contribute to architectural design reviews, performance optimization, and incident postmortems.",
            ]
            must_haves = [
                f"{exp_years} of hands-on experience in a comparable {parsed_input.department} role.",
                *[f"Strong production proficiency with {skill}." for skill in req_skills],
                "Track record of shipping reliable software with automated testing and clear communication.",
            ]
            nice_to_haves = [
                *[f"Experience working with {skill} in cloud-native environments." for skill in pref_skills],
                "Familiarity with SOC2 security practices, CI/CD automation, and distributed tracing.",
            ]
            md_lines = [
                f"# {title} ({level})",
                f"**Department:** {parsed_input.department} | **Experience:** {exp_years} | **Work Mode:** {parsed_input.work_mode}",
                "",
                "## Role Overview",
                overview,
                "",
                "## Key Responsibilities",
                *[f"- {r}" for r in responsibilities],
                "",
                "## Required Qualifications (Must-Have)",
                *[f"- {m}" for m in must_haves],
                "",
                "## Preferred Qualifications (Nice-to-Have)",
                *[f"- {n}" for n in nice_to_haves],
                "",
                "## Equal Opportunity Statement",
                "We evaluate qualified applicants strictly on skills, experience, and merit without regard to protected characteristics.",
            ]
            return {
                "role_overview": overview,
                "responsibilities": responsibilities,
                "must_have_qualifications": must_haves,
                "nice_to_have_qualifications": nice_to_haves,
                "formatted_job_description_markdown": "\n".join(md_lines),
                "summary": f"Generated structured job description for **{title}** ({level}, {exp_years}).",
                "explanation": (
                    f"Aligned experience band ({exp_years}) and requirements to skills ({', '.join(req_skills)}), "
                    f"checked inclusive phrasing (score {linter_score}/100)"
                    + (f", and referenced tenant guide: {kb_band_note[:90]}..." if kb_band_note else ".")
                ),
            }

        llm_res = llm_provider.generate_structured(
            system_prompt=self.load_system_prompt(state.get("custom_persona_prompt", "")),
            user_prompt=parsed_input.prompt,
            context_data={
                "job_title": title,
                "level": level,
                "experience_range_years": exp_years,
                "required_skills": req_skills,
                "preferred_skills": pref_skills,
                "inclusive_language_findings": linter_findings,
                "kb_context": kb_band_note,
            },
            fallback_fn=_fallback_json,
            provider_override=state.get("model_provider_override"),
            temperature=self.model_cfg.temperature,
            max_tokens=self.model_cfg.max_tokens,
        )
        fb = _fallback_json()
        parsed = llm_res.parsed_json or fb

        output = JDGeneratorOutput(
            agent_id=self.agent_id,
            agent_version=self.agent_version,
            summary=str(parsed.get("summary") or fb["summary"]),
            explanation=str(parsed.get("explanation") or fb["explanation"]),
            citations=kb_citations or ["Inclusive Language Standard Rubric"],
            structured_payload={
                "job_title": title,
                "suggested_experience_level": level,
                "experience_range_years": exp_years,
                "inclusive_language_score": linter_score,
            },
            job_title=title,
            suggested_experience_level=level,
            experience_range_years=exp_years,
            role_overview=str(parsed.get("role_overview") or fb["role_overview"]),
            responsibilities=list(parsed.get("responsibilities") or fb["responsibilities"]),
            must_have_qualifications=list(parsed.get("must_have_qualifications") or fb["must_have_qualifications"]),
            nice_to_have_qualifications=list(parsed.get("nice_to_have_qualifications") or fb["nice_to_have_qualifications"]),
            inclusive_language_findings=linter_findings,
            inclusive_language_score=linter_score,
            formatted_job_description_markdown=str(
                parsed.get("formatted_job_description_markdown") or fb["formatted_job_description_markdown"]
            ),
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
