"""Intent classification, internal HR workflow routing, and domain boundary guardrails."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Optional

from app.runtime.redaction import _PROMPT_INJECTION_PATTERNS

from .guardrails import (
    PROTECTED_BIAS_PATTERNS,
    check_hr_safety_input,
    scan_prompt_injection,
)
from .schemas import DomainDefinition, GuardrailConfig

PROMPT_INJECTION_PATTERNS = _PROMPT_INJECTION_PATTERNS
PROTECTED_CHARACTERISTIC_BIAS_PATTERNS = PROTECTED_BIAS_PATTERNS

# Legitimate HR terms that must NOT trigger financial trading / medical diagnosis out-of-domain filters.
HR_CONTEXT_EXEMPT_RX = re.compile(
    r"\b("
    r"employee\s+stock\s+option|esop|rsu|restricted\s+stock|equity\s+(?:grant|vesting|plan|compensation)|stock\s+vesting|"
    r"medical\s+leave|sick\s+leave|parental\s+leave|maternity\s+leave|paternity\s+leave|"
    r"health\s+insurance|medical\s+reimbursement|medical\s+benefits|wellness\s+stipend|"
    r"legal\s+name\s+change|employment\s+contract|work\s+authorization|visa\s+sponsorship|"
    r"offer\s+letter|nda\s+policy|background\s+check\s+policy"
    r")\b",
    re.IGNORECASE,
)

OUT_OF_DOMAIN_SIGNATURES: list[tuple[str, str, re.Pattern[str]]] = [
    (
        "Medical Diagnosis & Clinical Advice",
        "Healthcare",
        re.compile(
            r"\b(fever|antibiotic|diagnose|symptom|medication|dosage|prescription|cholesterol|blood test|headache|chest pain|rash|cough|sore throat)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Financial Trading & Cryptocurrency",
        "Business and Finance",
        re.compile(
            r"\b(stock|nvda|aapl|bitcoin|btc|eth|crypto|cryptocurrency|ethereum|call option|put option|forex|rsi|moving average|day trade|buy\s+shares)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Legal Litigation & Contract Redlining",
        "Legal and Compliance",
        re.compile(
            r"\b(lawsuit|patent infringement|sue\s+competitor|court filing|mergers and acquisitions|nda redline)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Personal Travel, Shopping & Homework",
        "Operations and Internal Work",
        re.compile(
            r"\b(scrape amazon|book flight|hotel reservation|vacation itinerary|solve calculus|homework essay|recipe for|minecraft)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "General Non-HR Request",
        "General Non-HR",
        re.compile(
            r"\b(capital of france|weather forecast|pizza recipe|bake a cake|tell me a joke|write a poem|quantum mechanics|photosynthesis|world cup finals|cricket score|movie review|snake game)\b",
            re.IGNORECASE,
        ),
    ),
]

HR_WORKFLOW_DISPLAY_NAMES: dict[str, str] = {
    "recruitment-screening": "Recruitment & Resume Screening",
    "jd-generator": "Job Description Generation",
    "candidate-shortlisting": "Candidate Shortlisting",
    "interview-scheduling": "Interview Scheduling",
    "employee-onboarding": "Employee Onboarding",
    "hr-policy-support": "Employee Policy Support",
    "hr-analytics": "HR Analytics",
}

# Weighted pattern rules for unified internal routing across the 7 HR workflows.
# Tuple format: (slug, workflow_name, list[(pattern, weight)])
WORKFLOW_ROUTING_RULES: list[tuple[str, str, list[tuple[re.Pattern[str], int]]]] = [
    (
        "jd-generator",
        "Job Description Generation",
        [
            (re.compile(r"\b(write|generate|draft|create|build)\b.{0,35}\b(job description|jd|job posting|role spec)\b", re.IGNORECASE), 5),
            (re.compile(r"\b(job description|job posting|inclusive language|role responsibilities|qualifications section)\b", re.IGNORECASE), 4),
            (re.compile(r"\bjd\b", re.IGNORECASE), 2),
        ],
    ),
    (
        "recruitment-screening",
        "Recruitment & Resume Screening",
        [
            (re.compile(r"\b(screen|screening|parse|evaluate|assess)\b.{0,35}\b(resume|resumes|cv|candidate|candidates|applicant|applicants)\b", re.IGNORECASE), 5),
            (re.compile(r"\b(resume|resumes|\bcv\b|screening rubric|applicant match|screen candidates?|candidate screening)\b", re.IGNORECASE), 3),
            (re.compile(r"\b(skills match|experience extraction|blind screening)\b", re.IGNORECASE), 2),
        ],
    ),
    (
        "candidate-shortlisting",
        "Candidate Shortlisting",
        [
            (re.compile(r"\b(shortlist|rank|compare)\b.{0,35}\b(candidate|candidates|finalist|finalists|cohort|applicants)\b", re.IGNORECASE), 5),
            (re.compile(r"\b(shortlisting|compare finalists|missing skills gap|top candidates|ranked cohort)\b", re.IGNORECASE), 4),
        ],
    ),
    (
        "interview-scheduling",
        "Interview Scheduling",
        [
            (re.compile(r"\b(schedule|book|reschedule|propose|arrange)\b.{0,35}\b(interview|panel|slot|round|slots)\b", re.IGNORECASE), 5),
            (re.compile(r"\b(interview slot|interview slots|interviewer availability|technical round|interview panel)\b", re.IGNORECASE), 4),
            (re.compile(r"\b(calendar|interviewer|reschedule|interview)\b", re.IGNORECASE), 2),
        ],
    ),
    (
        "employee-onboarding",
        "Employee Onboarding",
        [
            (re.compile(r"\b(onboard|onboarding|provision|verify kyc|new hire)\b", re.IGNORECASE), 4),
            (re.compile(r"\b(kyc|aadhaar|it provisioning|laptop|buddy|mentor|welcome kit|joining checklist|orientation)\b", re.IGNORECASE), 3),
        ],
    ),
    (
        "hr-policy-support",
        "Employee Policy Support",
        [
            (
                re.compile(
                    r"\b(leave policy|parental leave|maternity|paternity|pto|attendance policy|reimbursement|"
                    r"expense policy|remote work|wfh|home office|ergonomics?|stipend|allowance|handbook|"
                    r"employee benefits?|sick leave|holiday calendar|health insurance|probation|notice period)\b",
                    re.IGNORECASE,
                ),
                4,
            ),
            (
                re.compile(
                    r"\b(policy|compensation band|relocation bonus|retention bonus|benefits?|wellness|equipment|bereavement|vacation)\b",
                    re.IGNORECASE,
                ),
                2,
            ),
        ],
    ),
    (
        "hr-analytics",
        "HR Analytics",
        [
            (re.compile(r"\b(time-to-hire|time to hire|hiring pipeline|attrition|funnel chart|workforce report|hiring metrics|headcount|offer acceptance|department funnel)\b", re.IGNORECASE), 5),
            (re.compile(r"\b(analytics|kpi|pipeline summary|open roles report|sql metrics)\b", re.IGNORECASE), 3),
        ],
    ),
]

# Legacy hint list kept for backwards compatibility
CROSS_HR_AGENT_HINTS: list[tuple[str, str, re.Pattern[str]]] = [
    ("recruitment-screening", "Recruitment & Resume Screening", re.compile(r"\b(resume|resumes|cv|parse resume|screen candidates?|candidate screening)\b", re.IGNORECASE)),
    ("jd-generator", "Job Description Generation", re.compile(r"\b(write|generate|draft|create).{0,30}(job description|\bjd\b|job posting)\b", re.IGNORECASE)),
    ("candidate-shortlisting", "Candidate Shortlisting", re.compile(r"\b(shortlist|rank candidates|compare finalists|compare candidates)\b", re.IGNORECASE)),
    ("interview-scheduling", "Interview Scheduling", re.compile(r"\b(schedule|interview slot|calendar|reschedule|interview panel)\b", re.IGNORECASE)),
    ("employee-onboarding", "Employee Onboarding", re.compile(r"\b(onboard|onboarding|kyc|aadhaar|it provisioning|laptop|buddy|new hire)\b", re.IGNORECASE)),
    ("hr-policy-support", "Employee Policy Support", re.compile(r"\b(leave policy|pto|parental leave|attendance policy|reimbursement|benefits|handbook|sick leave)\b", re.IGNORECASE)),
    ("hr-analytics", "HR Analytics", re.compile(r"\b(time-to-hire|time to hire|hiring pipeline|attrition|funnel chart|workforce report|hiring metrics)\b", re.IGNORECASE)),
]

FOLLOWUP_HR_CONTINUITY_PATTERN = re.compile(
    r"\b(candidate|candidates|resume|role|position|job|interview|slot|panel|policy|leave|pto|"
    r"onboarding|kyc|provision|report|metric|analytics|shortlist|hire|hiring|team|salary|band|"
    r"offer|employee|applicant|missing skills|next steps?|follow[- ]up|elaborate|clarify|"
    r"details|compare|summarize|continue|they|them|their|those|that|this)\b",
    re.IGNORECASE,
)


def _has_prior_hr_context(conversation_history: Optional[list[dict[str, str]]]) -> bool:
    if not conversation_history:
        return False
    for msg in reversed(conversation_history):
        if msg.get("role") == "assistant":
            content = (msg.get("content") or "").strip()
            if content and not content.startswith("**Request Declined"):
                return True
    return False


def _infer_history_workflow_slug(conversation_history: Optional[list[dict[str, str]]]) -> Optional[str]:
    if not conversation_history:
        return None
    for msg in reversed(conversation_history):
        wf = msg.get("workflow_slug") or msg.get("agent_id")
        if wf and wf in HR_WORKFLOW_DISPLAY_NAMES:
            return wf
    combined = " ".join((m.get("content") or "")[:400] for m in conversation_history[-4:])
    return detect_hr_workflow_slug(combined)


def score_hr_workflows(prompt: str) -> dict[str, int]:
    """Return weighted keyword/intent scores for all 7 Hiring & HR workflows."""
    text = (prompt or "").strip()
    scores: dict[str, int] = {slug: 0 for slug, _, _ in WORKFLOW_ROUTING_RULES}
    if not text:
        return scores
    for slug, _name, rules in WORKFLOW_ROUTING_RULES:
        total = 0
        for rx, weight in rules:
            matches = rx.findall(text)
            if matches:
                total += weight * min(len(matches), 2)
        scores[slug] = total
    return scores


def detect_hr_workflow_slug(
    prompt: str,
    *,
    conversation_history: Optional[list[dict[str, str]]] = None,
    default_slug: Optional[str] = None,
    structured_input: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    """Detect the best matching HR workflow across all 7 specialized HR capabilities."""
    text = (prompt or "").strip()
    if structured_input:
        hint = (structured_input.get("workflow") or structured_input.get("workflow_hint") or "").strip().lower()
        if hint in HR_WORKFLOW_DISPLAY_NAMES:
            return hint

    # Never route blocked/out-of-domain prompts into HR workflows
    if any(rx.search(text) for rx in PROMPT_INJECTION_PATTERNS):
        return default_slug
    masked_ood = HR_CONTEXT_EXEMPT_RX.sub(" hr_policy_term ", text)
    if any(rx.search(masked_ood) for _, _, rx in OUT_OF_DOMAIN_SIGNATURES):
        return None

    scores = score_hr_workflows(text)
    best_slug = max(scores, key=lambda s: scores[s])
    if scores[best_slug] > 0:
        return best_slug

    if _has_prior_hr_context(conversation_history) and FOLLOWUP_HR_CONTINUITY_PATTERN.search(text):
        prior_slug = _infer_history_workflow_slug(conversation_history)
        return prior_slug or default_slug

    return default_slug


WORKFLOW_TOOL_PERMISSIONS: dict[str, tuple[list[str], list[str], str]] = {
    "recruitment-screening": (
        ["sandbox_ocr_extract", "pii_blind_masker", "rubric_scorer"],
        ["platform_admin", "business_owner", "business_admin"],
        "medium",
    ),
    "jd-generator": (
        ["jd_bias_linter", "jd_template_search"],
        ["platform_admin", "business_owner", "business_admin"],
        "low",
    ),
    "candidate-shortlisting": (
        ["query_screened_pool", "sandbox_weighted_ranker", "hitl_shortlist_signoff"],
        ["platform_admin", "business_owner", "business_admin"],
        "high",
    ),
    "interview-scheduling": (
        ["calendar_slot_finder", "calendar_book_event", "email_candidate_invite"],
        ["platform_admin", "business_owner", "business_admin"],
        "high",
    ),
    "employee-onboarding": (
        ["onboarding_checklist_builder", "kyc_document_verify", "it_provisioning_request"],
        ["platform_admin", "business_owner", "business_admin"],
        "high",
    ),
    "hr-policy-support": (
        ["rag_policy_search", "citation_formatter"],
        ["platform_admin", "business_owner", "business_admin", "business_employee"],
        "low",
    ),
    "hr-analytics": (
        ["sql_hr_analytics", "chart_data_formatter"],
        ["platform_admin", "business_owner", "business_admin"],
        "medium",
    ),
}

_INTENT_LABELS: dict[str, str] = {
    "recruitment-screening": "candidate_screening",
    "jd-generator": "jd_generation",
    "candidate-shortlisting": "candidate_shortlisting",
    "interview-scheduling": "interview_scheduling",
    "employee-onboarding": "onboarding_orchestration",
    "hr-policy-support": "policy_rag_support",
    "hr-analytics": "hr_analytics_report",
}

_CLARIFICATION_VAGUE_RX = re.compile(
    r"^\s*(?:help|hi|hello|hr|hire|recruit|screen|shortlist|schedule|onboard|policy|analytics|jd|"
    r"help\s+with\s+hr|need\s+hr\s+help|hire\s+someone|screen\s+candidates?)\s*[?.!]*\s*$",
    re.IGNORECASE,
)


@dataclass
class IntentClassification:
    intent_label: str
    is_injection: bool
    is_bias_attempt: bool
    user_intent: str = ""
    requested_task: str = ""
    hr_workflow: str = "hr-policy-support"
    required_tools: list[str] = field(default_factory=list)
    risk_level: str = "low"
    required_permissions: list[str] = field(default_factory=list)
    needs_clarification: bool = False
    clarification_questions: list[str] = field(default_factory=list)
    classifier_method: str = "deterministic"
    is_out_of_domain: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_label": self.intent_label,
            "user_intent": self.user_intent or self.intent_label,
            "requested_task": self.requested_task,
            "hr_workflow": self.hr_workflow,
            "required_tools": list(self.required_tools),
            "risk_level": self.risk_level,
            "required_permissions": list(self.required_permissions),
            "needs_clarification": self.needs_clarification,
            "clarification_questions": list(self.clarification_questions),
            "classifier_method": self.classifier_method,
            "is_injection": self.is_injection,
            "is_bias_attempt": self.is_bias_attempt,
            "is_out_of_domain": self.is_out_of_domain,
        }


@dataclass
class DomainClassification:
    allowed: bool
    classifier_result: str
    reason: str
    suggested_category: Optional[str] = None
    suggested_agent_slug: Optional[str] = None


def _llm_classify_ambiguous_intent(prompt: str, default_slug: str) -> Optional[dict[str, Any]]:
    """Invoke configured external LLM ONLY when deterministic confidence is ambiguous & live key exists."""
    try:
        from .llm_provider import llm_provider

        if llm_provider.resolve_provider() == "deterministic":
            return None

        res = llm_provider.generate_structured(
            system_prompt=(
                "Classify an incoming Hiring & HR request into JSON with keys: "
                "hr_workflow (one of recruitment-screening, jd-generator, candidate-shortlisting, "
                "interview-scheduling, employee-onboarding, hr-policy-support, hr-analytics, or out_of_domain), "
                "requested_task (short phrase), needs_clarification (bool), clarification_questions (list of max 2 strings)."
            ),
            user_prompt=prompt[:800],
            context_data={"default_workflow": default_slug},
            fallback_fn=lambda ctx: {},
            max_tokens=220,
        )
        if res.parsed_json and not res.provider_used.startswith("deterministic"):
            return res.parsed_json
    except Exception:
        return None
    return None


def classify_intent_detailed(
    prompt: str,
    agent_id: str,
    *,
    structured_input: Optional[dict[str, Any]] = None,
    conversation_history: Optional[list[dict[str, str]]] = None,
    allow_llm_fallback: bool = True,
) -> IntentClassification:
    """Hybrid deterministic-first + LLM-assisted intent, risk, tool, permission, and clarification classifier."""
    text = (prompt or "").strip()

    injected, _inj_reason = scan_prompt_injection(text)
    if injected:
        return IntentClassification(
            intent_label="prompt_injection",
            is_injection=True,
            is_bias_attempt=False,
            user_intent="prompt_injection",
            requested_task="Unauthorized instruction or prompt extraction",
            hr_workflow=agent_id,
            required_tools=[],
            risk_level="critical",
            required_permissions=[],
            classifier_method="deterministic",
        )

    safe_hr, flag_code, _msg = check_hr_safety_input(text, structured_input)
    if not safe_hr:
        return IntentClassification(
            intent_label=flag_code,
            is_injection=False,
            is_bias_attempt=(flag_code == "blocked_policy_fairness"),
            user_intent=flag_code,
            requested_task="Prohibited protected-attribute discrimination or autonomous rejection",
            hr_workflow=agent_id,
            required_tools=[],
            risk_level="critical",
            required_permissions=[],
            classifier_method="deterministic",
        )

    masked_ood = HR_CONTEXT_EXEMPT_RX.sub(" hr_policy_term ", text)
    for out_cat, _suggested, rx in OUT_OF_DOMAIN_SIGNATURES:
        if rx.search(masked_ood):
            return IntentClassification(
                intent_label="out_of_domain",
                is_injection=False,
                is_bias_attempt=False,
                user_intent="out_of_domain",
                requested_task=f"Out-of-scope topic ({out_cat})",
                hr_workflow=agent_id,
                required_tools=[],
                risk_level="low",
                required_permissions=[],
                classifier_method="deterministic",
                is_out_of_domain=True,
            )

    has_structured_payload = bool(
        structured_input
        and any(k not in ("prompt", "attachments", "metadata", "workflow", "workflow_hint") and v for k, v in structured_input.items())
    )
    scores = score_hr_workflows(text)
    sorted_scores = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_slug, top_score = sorted_scores[0] if sorted_scores else (agent_id, 0)
    second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0
    resolved_slug = top_slug if top_score > 0 else agent_id
    method = "deterministic"

    # Clarification check for severely underspecified standalone requests without prior context
    if (
        not has_structured_payload
        and not _has_prior_hr_context(conversation_history)
        and (_CLARIFICATION_VAGUE_RX.match(text) or (len(text.split()) <= 2 and top_score <= 2 and "?" not in text))
    ):
        tools, perms, risk = WORKFLOW_TOOL_PERMISSIONS.get(resolved_slug, ([], ["business_admin"], "low"))
        return IntentClassification(
            intent_label="clarification_needed",
            is_injection=False,
            is_bias_attempt=False,
            user_intent="clarification_needed",
            requested_task="Underspecified HR request needing target details",
            hr_workflow=resolved_slug,
            required_tools=tools,
            risk_level=risk,
            required_permissions=perms,
            needs_clarification=True,
            clarification_questions=[
                "Which Hiring & HR workflow do you want to run (Resume Screening, JD Generation, Candidate Shortlisting, Interview Scheduling, Onboarding, Policy Support, or HR Analytics)?",
                "Please share the key parameters such as target role/skills, candidate details, employee name, or policy question.",
            ],
            classifier_method="deterministic",
        )

    # Optional LLM fallback ONLY when ambiguous (low score or tie) & external provider active
    if allow_llm_fallback and not has_structured_payload and (top_score == 0 or abs(top_score - second_score) <= 1):
        llm_res = _llm_classify_ambiguous_intent(text, resolved_slug)
        if llm_res:
            method = "llm_assisted"
            llm_wf = str(llm_res.get("hr_workflow") or "").strip()
            if llm_wf == "out_of_domain":
                return IntentClassification(
                    intent_label="out_of_domain",
                    is_injection=False,
                    is_bias_attempt=False,
                    user_intent="out_of_domain",
                    requested_task=str(llm_res.get("requested_task") or "Non-HR request"),
                    hr_workflow=agent_id,
                    required_tools=[],
                    risk_level="low",
                    required_permissions=[],
                    classifier_method=method,
                    is_out_of_domain=True,
                )
            if llm_wf in HR_WORKFLOW_DISPLAY_NAMES:
                resolved_slug = llm_wf
            if bool(llm_res.get("needs_clarification")):
                tools, perms, risk = WORKFLOW_TOOL_PERMISSIONS.get(resolved_slug, ([], ["business_admin"], "low"))
                qs = [str(q) for q in (llm_res.get("clarification_questions") or [])[:2] if q]
                return IntentClassification(
                    intent_label="clarification_needed",
                    is_injection=False,
                    is_bias_attempt=False,
                    user_intent="clarification_needed",
                    requested_task=str(llm_res.get("requested_task") or "Clarification required"),
                    hr_workflow=resolved_slug,
                    required_tools=tools,
                    risk_level=risk,
                    required_permissions=perms,
                    needs_clarification=True,
                    clarification_questions=qs
                    or ["Please specify the target HR role, candidate, or policy topic so we can assist accurately."],
                    classifier_method=method,
                )

    tools, perms, risk = WORKFLOW_TOOL_PERMISSIONS.get(resolved_slug, ([], ["business_admin"], "low"))
    label = _INTENT_LABELS.get(resolved_slug, "hr_task")
    wf_title = HR_WORKFLOW_DISPLAY_NAMES.get(resolved_slug, resolved_slug)
    return IntentClassification(
        intent_label=label,
        is_injection=False,
        is_bias_attempt=False,
        user_intent=label,
        requested_task=f"{wf_title}: {text[:90]}" if text else wf_title,
        hr_workflow=resolved_slug,
        required_tools=tools,
        risk_level=risk,
        required_permissions=perms,
        needs_clarification=False,
        clarification_questions=[],
        classifier_method=method,
    )


def classify_user_intent(prompt: str, agent_id: str) -> IntentClassification:
    return classify_intent_detailed(prompt, agent_id, allow_llm_fallback=False)


def classify_domain_boundary(
    prompt: str,
    agent_id: str,
    domain: DomainDefinition,
    guardrails: GuardrailConfig,
    structured_input: Optional[dict] = None,
    conversation_history: Optional[list[dict[str, str]]] = None,
) -> DomainClassification:
    text = prompt.strip()
    lower = text.lower()

    # 1. Prompt injection & secret/system-prompt extraction blocking (incl. base64/SQL/role tags)
    if guardrails.block_prompt_injection:
        injected, inj_reason = scan_prompt_injection(text)
        if injected:
            return DomainClassification(
                allowed=False,
                classifier_result="blocked_injection",
                reason=(
                    f"Request blocked: {inj_reason} "
                    "System prompts, permissions, and tenant boundaries cannot be overridden."
                ),
                suggested_category=None,
            )

    # 2. HR safety checks: protected-attribute discrimination & unauthorized auto-rejection
    if guardrails.block_protected_characteristics or guardrails.prohibit_auto_reject:
        safe_hr, flag_code, hr_reason = check_hr_safety_input(text, structured_input)
        if not safe_hr:
            return DomainClassification(
                allowed=False,
                classifier_result=flag_code,
                reason=hr_reason,
                suggested_category="Hiring and HR (Fairness & Human Review)",
            )

    # 3. Non-HR out-of-domain check (after exempting legitimate HR benefits/equity terms)
    masked_ood = HR_CONTEXT_EXEMPT_RX.sub(" hr_policy_term ", text)
    for out_cat, suggested_cat, rx in OUT_OF_DOMAIN_SIGNATURES:
        if rx.search(masked_ood):
            return DomainClassification(
                allowed=False,
                classifier_result="rejected_out_of_domain",
                reason=(
                    f"Request declined: HireFlow AI specializes strictly in Hiring & HR operations and cannot process "
                    f"{out_cat} requests."
                ),
                suggested_category=domain.rejected_categories.get(out_cat, suggested_cat),
            )

    # 4. Structured API callers with validated agent-specific fields stay in their requested workflow
    has_structured_payload = bool(
        structured_input
        and any(k not in ("prompt", "attachments", "metadata", "workflow", "workflow_hint") and v for k, v in structured_input.items())
    )
    if has_structured_payload:
        return DomainClassification(
            allowed=True,
            classifier_result="in_domain",
            reason=f"Matched {domain.domain_name} structured schema.",
            suggested_agent_slug=agent_id,
        )

    # 5. Internal HR workflow scoring & cross-HR routing
    wf_scores = score_hr_workflows(text)
    best_slug = max(wf_scores, key=lambda s: wf_scores[s]) if wf_scores else agent_id
    best_score = wf_scores.get(best_slug, 0)
    current_score = wf_scores.get(agent_id, 0)
    hits = sum(1 for kw in domain.in_domain_keywords if kw.lower() in lower)

    # Route internally to another HR workflow when it clearly matches that HR capability stronger than current workflow
    if best_slug != agent_id and best_score >= 3 and (hits < domain.min_keyword_hits or best_score >= current_score + 2):
        target_name = HR_WORKFLOW_DISPLAY_NAMES.get(best_slug, best_slug)
        return DomainClassification(
            allowed=True,
            classifier_result="in_domain",
            reason=f"Internally routed HR request to the {target_name} workflow.",
            suggested_category="Hiring and HR",
            suggested_agent_slug=best_slug,
        )

    # 6. Current workflow domain keyword match
    if hits >= domain.min_keyword_hits or current_score > 0:
        return DomainClassification(
            allowed=True,
            classifier_result="in_domain",
            reason=f"Matched {domain.domain_name} workflow boundary.",
            suggested_agent_slug=agent_id,
        )

    # 7. Other Hiring & HR workflow match fallback -> internal routing instead of failure
    for target_slug, target_name, rx in CROSS_HR_AGENT_HINTS:
        if rx.search(text):
            return DomainClassification(
                allowed=True,
                classifier_result="in_domain",
                reason=f"Internally routed cross-HR request to the {target_name} workflow.",
                suggested_category="Hiring and HR",
                suggested_agent_slug=target_slug,
            )

    # 8. Multi-turn HR follow-up continuity across turns
    if _has_prior_hr_context(conversation_history) and FOLLOWUP_HR_CONTINUITY_PATTERN.search(text):
        prior_slug = _infer_history_workflow_slug(conversation_history) or agent_id
        target_name = HR_WORKFLOW_DISPLAY_NAMES.get(prior_slug, domain.domain_name)
        return DomainClassification(
            allowed=True,
            classifier_result="in_domain",
            reason=f"Preserved multi-turn HR follow-up context for {target_name}.",
            suggested_category="Hiring and HR",
            suggested_agent_slug=prior_slug,
        )

    return DomainClassification(
        allowed=False,
        classifier_result="rejected_out_of_domain",
        reason=(
            "This request falls outside HireFlow AI's Hiring & HR scope. Supported capabilities cover: "
            "Recruitment Screening, Job Descriptions, Candidate Shortlisting, Interview Scheduling, "
            "Employee Onboarding, HR Policy Support, and HR Analytics."
        ),
        suggested_category=domain.suggested_marketplace_category,
    )
