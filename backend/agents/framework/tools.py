from dataclasses import dataclass
import time
from typing import Any, Callable
import uuid

from sqlalchemy.orm import Session

from app.runtime.redaction import redact_secrets_in_text, sanitize_structured_payload
from app.runtime.tool_registry import ToolExecutionContext, hr_tool_registry


@dataclass
class ToolContext:
    db: Session
    tenant_id: uuid.UUID
    rental_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    actor_role: str
    blind_screening_mode: bool = False
    strict_pii_masking: bool = True


ToolHandler = Callable[[ToolContext, dict[str, Any]], dict[str, Any]]


class AgentToolBox:
    """Permission-checked registry mapping tool slugs to schema-enforced HR tools & workflow handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, slug: str, handler: ToolHandler) -> None:
        self._handlers[slug] = handler
        hr_tool_registry.register_legacy_handler(slug, handler)

    def has_tool(self, slug: str) -> bool:
        return slug in self._handlers or hr_tool_registry.has_tool(slug)

    def run_tool(
        self,
        *,
        slug: str,
        ctx: ToolContext,
        args: dict[str, Any],
        agent_allowed_tools: list[str],
        rental_allowed_tools: list[str] | None,
    ) -> dict[str, Any]:
        if slug not in agent_allowed_tools:
            return {"tool": slug, "status": "denied", "duration_ms": 0, "error": f"Tool '{slug}' is not in agent allowed_tools."}
        if rental_allowed_tools is not None and slug not in rental_allowed_tools:
            return {
                "tool": slug,
                "status": "denied",
                "duration_ms": 0,
                "error": f"Tool '{slug}' is disabled in tenant rental configuration.",
            }
        handler = self._handlers.get(slug)
        if handler is None and hr_tool_registry.has_tool(slug):
            exec_ctx = ToolExecutionContext(
                db=ctx.db,
                tenant_id=ctx.tenant_id,
                rental_id=ctx.rental_id,
                actor_user_id=ctx.actor_user_id,
                actor_role=ctx.actor_role,
                blind_screening_mode=ctx.blind_screening_mode,
                strict_pii_masking=ctx.strict_pii_masking,
            )
            res = hr_tool_registry.execute(
                slug,
                exec_ctx,
                args,
                agent_allowed_tools=agent_allowed_tools,
                rental_allowed_tools=rental_allowed_tools,
            )
            return {
                "tool": slug,
                "status": "completed" if res.get("status") == "ok" else res.get("status", "error"),
                "duration_ms": res.get("duration_ms", 0),
                "output": res.get("result"),
                "error": res.get("error"),
            }

        if handler is None:
            return {"tool": slug, "status": "error", "duration_ms": 0, "error": f"No registered handler for tool '{slug}'."}

        t0 = time.perf_counter()
        try:
            output = handler(ctx, args)
            duration_ms = round((time.perf_counter() - t0) * 1000)
            spec = hr_tool_registry.get_spec(slug)
            return {
                "tool": slug,
                "status": "completed",
                "duration_ms": duration_ms,
                "risk_level": spec.risk_level if spec else "low",
                "requires_hitl": spec.requires_hitl if spec else False,
                "output": sanitize_structured_payload(output, max_str_len=4000),
            }
        except Exception as exc:
            return {
                "tool": slug,
                "status": "error",
                "duration_ms": round((time.perf_counter() - t0) * 1000),
                "error": redact_secrets_in_text(str(exc), max_len=400),
            }
