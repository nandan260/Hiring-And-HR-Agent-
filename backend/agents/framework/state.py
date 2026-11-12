from typing import Any, Optional, TypedDict


class TraceStep(TypedDict):
    step: str
    status: str
    duration_ms: int
    detail: str


class AgentExecutionState(TypedDict, total=False):
    # Identity & multi-tenant security context
    request_id: str
    user_input: str
    structured_input: dict[str, Any]
    attachments: list[str]
    actor_user_id: Optional[str]
    actor_role: str
    principal_verified: bool
    tenant_id: str
    tenant_slug: str
    rental_id: Optional[str]
    rental_status: str
    rental_allowed_tools: Optional[list[str]]
    custom_persona_prompt: str
    blind_screening_mode: bool
    strict_pii_masking: bool
    require_hitl_approval: bool
    model_provider_override: Optional[str]
    model_tier_override: Optional[str]

    # Target agent / internal HR workflow identity
    requested_agent_id: str
    routed_agent_id: Optional[str]
    routing_reason: Optional[str]
    selected_agent_id: str
    selected_agent_version: str
    system_prompt_loaded: str
    conversation_history: list[dict[str, str]]
    conversation_summary: str

    # Classification & validation gates
    intent_label: str
    intent_analysis: dict[str, Any]
    clarification_questions: list[str]
    classifier_result: str  # in_domain | rejected_out_of_domain | blocked_injection | blocked_permission | blocked_quota | invalid_input | needs_clarification
    domain_allowed: bool
    rejection_reason: str
    suggested_category: Optional[str]
    permissions_ok: bool
    quota_ok: bool
    quota_limit: Optional[int]
    quota_used: Optional[int]
    input_valid: bool

    # Execution & tools
    planned_tools: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    agent_raw_output: dict[str, Any]
    validated_output: dict[str, Any]
    final_response_text: str
    citations: list[str]
    charts: list[dict[str, Any]]
    hitl_requests: list[dict[str, Any]]

    # Guardrails & telemetry
    enable_optimization: bool
    workflow_started_at_monotonic: float
    guardrail_passed: bool
    guardrail_notes: list[str]
    guardrail_flags: list[str]
    execution_status: str  # completed | rejected | blocked | paused_hitl | failed | needs_clarification
    trace_steps: list[TraceStep]
    baseline_input_tokens: int
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    optimization_methods_used: list[str]
    optimization_telemetry: dict[str, Any]
    model_used: str
    llm_provider_used: str
    latency_ms: int
    execution_log_id: Optional[str]
    error_message: Optional[str]
