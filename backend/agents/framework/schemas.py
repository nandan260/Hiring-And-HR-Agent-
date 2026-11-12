from typing import Any, Literal, Optional, Type
from pydantic import BaseModel, Field


class DomainDefinition(BaseModel):
    domain_name: str
    allowed_topics: list[str]
    rejected_categories: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of out-of-domain category label -> suggested marketplace category",
    )
    in_domain_keywords: list[str]
    min_keyword_hits: int = 1
    suggested_marketplace_category: str = "Hiring and HR"


class ToolPermissionConfig(BaseModel):
    default_allowed_tools: list[str]
    hitl_required_tools: list[str] = Field(default_factory=list)
    read_only_tools: list[str] = Field(default_factory=list)


class KnowledgeBaseConfig(BaseModel):
    enabled: bool = True
    top_k: int = 5
    min_similarity: float = 0.05
    require_citations: bool = False
    allowed_source_types: list[str] = Field(
        default_factory=lambda: ["handbook", "rubric", "jd_template", "resume", "kyc_doc", "policy"]
    )


class ModelConfig(BaseModel):
    provider: str = "auto"  # auto | gemini | openai | anthropic | deterministic
    model_tier: Literal["tier_0_rule", "tier_1_slm", "tier_2_flash", "tier_3_frontier"] = "tier_1_slm"
    model_name: str = "configurable-default"
    temperature: float = 0.1
    max_tokens: int = 1200
    enable_prompt_cache: bool = True


class GuardrailConfig(BaseModel):
    block_prompt_injection: bool = True
    block_protected_characteristics: bool = True
    prohibit_auto_reject: bool = True
    require_citation_grounding: bool = False
    require_hitl_actions: list[str] = Field(default_factory=list)
    pii_redaction_mode: Literal["none", "standard", "strict_blind"] = "standard"


class MemoryConfig(BaseModel):
    short_term_window_messages: int = 10
    summary_max_tokens: int = 400
    persist_to_db: bool = True


class ExecutionLimits(BaseModel):
    max_steps: int = 12
    max_tool_calls: int = 8
    max_input_tokens: int = 8000
    max_output_tokens: int = 1600
    timeout_seconds: int = 30


class AgentDefinition(BaseModel):
    """Declarative specification required for every independently configurable HR agent."""

    model_config = {"arbitrary_types_allowed": True}

    agent_id: str
    agent_name: str
    agent_version: str = "1.0.0"
    system_prompt_file: str
    domain: DomainDefinition
    input_schema: Type[BaseModel]
    output_schema: Type[BaseModel]
    allowed_tools: list[str]
    tool_permissions: ToolPermissionConfig
    knowledge_base: KnowledgeBaseConfig
    model_cfg: ModelConfig
    guardrails: GuardrailConfig
    memory: MemoryConfig
    execution_limits: ExecutionLimits


class BaseAgentInput(BaseModel):
    """Base input contract shared across specialized HR agents."""

    prompt: str = Field(min_length=1, max_length=12000)
    attachments: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseAgentOutput(BaseModel):
    """Base output contract extended by each specialized agent's structured Pydantic schema."""

    agent_id: str
    agent_version: str
    summary: str
    explanation: str
    citations: list[str] = Field(default_factory=list)
    requires_human_approval: bool = False
    hitl_requests: list[dict[str, Any]] = Field(default_factory=list)
    charts: list[dict[str, Any]] = Field(default_factory=list)
    structured_payload: dict[str, Any] = Field(default_factory=dict)
