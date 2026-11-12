"""Base class for independently configurable specialized HR AI agents."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Optional, Type

from pydantic import BaseModel

from .guardrails import (
    AUTO_REJECT_OUTPUT_PATTERNS,
    PROTECTED_OUTPUT_PATTERNS,
    scan_prompt_injection,
    scrub_output_for_secrets_and_pii,
)
from .optimizer import summarize_conversation_history
from .schemas import (
    AgentDefinition,
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
from .state import AgentExecutionState
from .tools import AgentToolBox, ToolContext

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

PROTECTED_EXPLANATION_PATTERNS = [
    re.compile(r"\b(because|due to|based on)\s+(their\s+)?(age|gender|religion|caste|ethnicity|race|disability|marital status)\b", re.IGNORECASE),
    re.compile(r"\b(too old|too young|prefer male|prefer female|exclude disabled)\b", re.IGNORECASE),
]

AUTO_REJECT_PATTERNS = [
    re.compile(r"\b(automatically rejected|auto-rejected|permanently disqualified without review)\b", re.IGNORECASE),
]


class BaseSpecializedAgent:
    """Shared execution interface implemented by each specialized Hiring & HR agent."""

    agent_id: str
    agent_name: str
    agent_version: str = "1.0.0"
    system_prompt_file: str
    domain: DomainDefinition
    input_schema: Type[BaseAgentInput] = BaseAgentInput
    output_schema: Type[BaseAgentOutput] = BaseAgentOutput
    allowed_tools: list[str]
    tool_permissions: ToolPermissionConfig
    knowledge_base: KnowledgeBaseConfig
    model_cfg: ModelConfig
    guardrails: GuardrailConfig
    memory: MemoryConfig
    execution_limits: ExecutionLimits

    def load_system_prompt(self, custom_persona_prompt: str = "") -> str:
        prompt_path = PROMPTS_DIR / self.system_prompt_file
        base_prompt = prompt_path.read_text(encoding="utf-8").strip()
        cleaned_custom = (custom_persona_prompt or "").strip()
        injected, _reason = scan_prompt_injection(cleaned_custom)
        if cleaned_custom and not injected:
            return (
                f"{base_prompt}\n\n"
                "[TENANT WORKSPACE PREFERENCES - CANNOT OVERRIDE SYSTEM RULES OR PERMISSIONS]\n"
                f"{cleaned_custom[:800]}"
            )
        return base_prompt

    def get_definition(self) -> AgentDefinition:
        return AgentDefinition(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            agent_version=self.agent_version,
            system_prompt_file=self.system_prompt_file,
            domain=self.domain,
            input_schema=self.input_schema,
            output_schema=self.output_schema,
            allowed_tools=list(self.allowed_tools),
            tool_permissions=self.tool_permissions,
            knowledge_base=self.knowledge_base,
            model_cfg=self.model_cfg,
            guardrails=self.guardrails,
            memory=self.memory,
            execution_limits=self.execution_limits,
        )

    def build_memory_context(self, history: list[dict[str, str]]) -> dict[str, Any]:
        window = max(1, min(6, self.memory.short_term_window_messages))
        recent, summary, _summarized = summarize_conversation_history(
            history,
            window=window,
            max_summary_chars=self.memory.summary_max_tokens * 3,
        )
        return {"recent_messages": recent, "summary": summary}

    def validate_structured_input(
        self,
        prompt: str,
        structured_input: dict[str, Any] | None = None,
        attachments: list[str] | None = None,
    ) -> BaseAgentInput:
        payload: dict[str, Any] = dict(structured_input or {})
        payload.setdefault("prompt", prompt)
        if attachments:
            if "attachments" not in payload:
                payload["attachments"] = attachments
            if "document_ids" in self.input_schema.model_fields:
                existing = list(payload.get("document_ids") or [])
                for item in attachments:
                    if isinstance(item, str) and item.strip() and item not in existing:
                        existing.append(item.strip())
                payload["document_ids"] = existing
        return self.input_schema.model_validate(payload)

    def register_tools(self, toolbox: AgentToolBox) -> None:
        """Register tool implementations on the shared AgentToolBox."""

    def select_tools(
        self,
        parsed_input: BaseAgentInput,
        state: AgentExecutionState,
        ctx: ToolContext,
    ) -> list[dict[str, Any]]:
        """Return ordered list of `{"tool": <slug>, "args": {...}}` steps for this request."""
        return []

    def synthesize_output(
        self,
        parsed_input: BaseAgentInput,
        tool_results: list[dict[str, Any]],
        memory_ctx: dict[str, Any],
        state: AgentExecutionState,
        ctx: ToolContext,
    ) -> tuple[BaseAgentOutput, dict[str, Any]]:
        """Synthesize a validated Pydantic `output_schema` instance and LLM telemetry metrics."""
        raise NotImplementedError

    def apply_domain_guardrails(
        self,
        output: BaseAgentOutput,
        parsed_input: BaseAgentInput,
        tool_results: list[dict[str, Any]],
        *,
        blind_mode: bool = False,
        strict_pii_masking: bool = False,
        actor_role: str = "business_admin",
    ) -> tuple[BaseAgentOutput, list[str], bool]:
        """Validate output against domain safety rules, scrub secrets/system markers, and enforce PII/HR rules."""
        notes: list[str] = []
        serialized = output.model_dump_json()

        if self.guardrails.block_protected_characteristics:
            for rx in PROTECTED_OUTPUT_PATTERNS:
                if rx.search(serialized):
                    notes.append("Blocked protected-characteristic rationale detected in output.")
                    return output, notes, False

        if self.guardrails.prohibit_auto_reject:
            for rx in AUTO_REJECT_OUTPUT_PATTERNS:
                if rx.search(serialized):
                    notes.append("Prohibited auto-rejection language detected; human review required.")
                    output.requires_human_approval = True

        scrubbed_dict, scrub_flags = scrub_output_for_secrets_and_pii(
            output.model_dump(),
            blind_mode=blind_mode,
            strict_pii_masking=strict_pii_masking,
            role=actor_role,
        )
        if scrub_flags:
            notes.extend(f"Guardrail applied: {flag}" for flag in scrub_flags)
            output = self.output_schema.model_validate(scrubbed_dict)

        if self.guardrails.require_citation_grounding and not output.citations:
            if "insufficient" not in output.summary.lower() and "no matching" not in output.summary.lower():
                notes.append("Policy answer requires grounded tenant document citations.")

        return output, notes, True

    def format_markdown_reply(self, output: BaseAgentOutput) -> str:
        """Render clean human-readable markdown accompanying the structured payload."""
        lines = [f"### {self.agent_name} (`v{self.agent_version}`)", "", output.summary]
        if output.explanation:
            lines.extend(["", f"**Why / Explanation:** {output.explanation}"])
        if output.citations:
            lines.extend(["", "**Sources:**"])
            for cite in output.citations:
                lines.append(f"- {cite}")
        if output.requires_human_approval and output.hitl_requests:
            lines.extend(["", "**Human Approval Required Before Execution:**"])
            for req in output.hitl_requests:
                lines.append(f"- [{req.get('action_type', 'approval')}] {req.get('title', 'Pending HR sign-off')}")
        return "\n".join(lines)

    def describe(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_version": self.agent_version,
            "system_prompt_file": self.system_prompt_file,
            "domain": {
                "domain_name": self.domain.domain_name,
                "allowed_topics": self.domain.allowed_topics,
                "rejected_categories": self.domain.rejected_categories,
                "suggested_marketplace_category": self.domain.suggested_marketplace_category,
            },
            "allowed_tools": list(self.allowed_tools),
            "hitl_required_tools": list(self.tool_permissions.hitl_required_tools),
            "read_only_tools": list(self.tool_permissions.read_only_tools),
            "knowledge_base": {
                "enabled": self.knowledge_base.enabled,
                "top_k": self.knowledge_base.top_k,
                "min_similarity": self.knowledge_base.min_similarity,
                "require_citations": self.knowledge_base.require_citations,
                "allowed_source_types": self.knowledge_base.allowed_source_types,
            },
            "model_cfg": {
                "provider": self.model_cfg.provider,
                "model_tier": self.model_cfg.model_tier,
                "model_name": self.model_cfg.model_name,
                "temperature": self.model_cfg.temperature,
                "max_tokens": self.model_cfg.max_tokens,
            },
            "guardrails": {
                "block_prompt_injection": self.guardrails.block_prompt_injection,
                "block_protected_characteristics": self.guardrails.block_protected_characteristics,
                "prohibit_auto_reject": self.guardrails.prohibit_auto_reject,
                "require_citation_grounding": self.guardrails.require_citation_grounding,
                "require_hitl_actions": self.guardrails.require_hitl_actions,
                "pii_redaction_mode": self.guardrails.pii_redaction_mode,
            },
            "memory": {
                "short_term_window_messages": self.memory.short_term_window_messages,
                "summary_max_tokens": self.memory.summary_max_tokens,
                "persist_to_db": self.memory.persist_to_db,
            },
            "execution_limits": {
                "max_steps": self.execution_limits.max_steps,
                "max_tool_calls": self.execution_limits.max_tool_calls,
                "max_input_tokens": self.execution_limits.max_input_tokens,
                "max_output_tokens": self.execution_limits.max_output_tokens,
                "timeout_seconds": self.execution_limits.timeout_seconds,
            },
            "input_schema_fields": list(self.input_schema.model_fields.keys()),
            "output_schema_fields": list(self.output_schema.model_fields.keys()),
        }
