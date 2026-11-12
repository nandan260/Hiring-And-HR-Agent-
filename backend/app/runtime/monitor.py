from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AgentSandboxRuntime, ExecutionLog, McpExecutionLog, McpServerRecord, TokenUsage
from app.runtime.redaction import redact_secrets_in_text, sanitize_structured_payload


class ExecutionMonitorTracker:
    """Thread-safe tracker for currently running workflows + DB telemetry aggregator."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active: dict[str, dict[str, Any]] = {}

    def start_run(
        self,
        *,
        tenant_id: uuid.UUID,
        workflow: str,
        prompt_preview: str,
        actor_user_id: uuid.UUID | None,
    ) -> str:
        run_id = uuid.uuid4().hex[:16]
        with self._lock:
            self._active[run_id] = {
                "run_id": run_id,
                "tenant_id": str(tenant_id),
                "current_task": redact_secrets_in_text(prompt_preview, max_len=240),
                "current_workflow": workflow,
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "tool_calls": [],
                "browser_activity": {"status": "not_used"},
                "sandbox_status": {"status": "initializing"},
                "actor_user_id": str(actor_user_id) if actor_user_id else None,
            }
        return run_id

    def update_run(self, run_id: str | None, **updates: Any) -> None:
        if not run_id:
            return
        with self._lock:
            item = self._active.get(run_id)
            if item is not None:
                item.update(sanitize_structured_payload(updates))

    def finish_run(self, run_id: str | None) -> None:
        if not run_id:
            return
        with self._lock:
            self._active.pop(run_id, None)

    def get_active_runs(self, tenant_id: uuid.UUID) -> list[dict[str, Any]]:
        tid = str(tenant_id)
        with self._lock:
            return [dict(v) for v in self._active.values() if v.get("tenant_id") == tid]

    def build_monitor_snapshot(self, db: Session, tenant_id: uuid.UUID, *, limit: int = 25) -> dict[str, Any]:
        active_runs = self.get_active_runs(tenant_id)
        recent_logs = db.scalars(
            select(ExecutionLog)
            .where(ExecutionLog.tenant_id == tenant_id)
            .order_by(ExecutionLog.created_at.desc())
            .limit(limit)
        ).all()

        runtimes = db.scalars(
            select(AgentSandboxRuntime)
            .where(AgentSandboxRuntime.tenant_id == tenant_id, AgentSandboxRuntime.status != "destroyed")
            .order_by(AgentSandboxRuntime.created_at.desc())
        ).all()

        token_totals = db.execute(
            select(
                func.coalesce(func.sum(TokenUsage.input_tokens), 0),
                func.coalesce(func.sum(TokenUsage.output_tokens), 0),
                func.coalesce(func.sum(TokenUsage.estimated_cost_usd), 0),
            ).where(TokenUsage.tenant_id == tenant_id)
        ).one()

        mcp_servers_count = db.scalar(
            select(func.count(McpServerRecord.id)).where(McpServerRecord.tenant_id == tenant_id)
        ) or 0
        mcp_connected_count = db.scalar(
            select(func.count(McpServerRecord.id)).where(
                McpServerRecord.tenant_id == tenant_id,
                McpServerRecord.is_approved.is_(True),
                McpServerRecord.connection_status == "connected",
            )
        ) or 0
        recent_mcp_logs = db.scalars(
            select(McpExecutionLog)
            .where(McpExecutionLog.tenant_id == tenant_id)
            .order_by(McpExecutionLog.created_at.desc())
            .limit(10)
        ).all()

        executions: list[dict[str, Any]] = []
        for log in recent_logs:
            telemetry = dict(log.runtime_telemetry_json or {})
            browser_info = dict(log.browser_activity_json or {"status": "not_used"})
            if browser_info.get("status") == "idle":
                browser_info["status"] = "not_used"
            executions.append(
                {
                    "id": str(log.id),
                    "current_task": log.prompt_preview,
                    "current_workflow": str(browser_info.get("agent_slug") or log.classifier_result),
                    "classifier_result": log.classifier_result,
                    "status": log.status,
                    "execution_duration_ms": log.latency_ms,
                    "model_tier_used": log.model_tier_used,
                    "tool_calls": telemetry.get("tool_calls", []),
                    "browser_activity": browser_info,
                    "sandbox_status": telemetry.get(
                        "sandbox",
                        {
                            "status": "not_used",
                            "backend_mode": "none",
                            "is_container_isolated": False,
                        },
                    ),
                    "token_usage": telemetry.get(
                        "token_usage",
                        {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0.0},
                    ),
                    "steps": log.steps_json,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
            )

        current_task = (
            active_runs[0]["current_task"]
            if active_runs
            else (executions[0]["current_task"] if executions else None)
        )
        current_workflow = (
            active_runs[0]["current_workflow"]
            if active_runs
            else (executions[0]["current_workflow"] if executions else None)
        )

        return {
            "active_runs": active_runs,
            "current_task": current_task,
            "current_workflow": current_workflow,
            "executions": executions,
            "sandbox_runtimes": [
                {
                    "id": str(r.id),
                    "agent_runtime_id": r.agent_runtime_id,
                    "status": r.status,
                    "backend_mode": r.backend_mode,
                    "is_container_isolated": r.is_container_isolated,
                    "network_mode": r.network_mode,
                    "cpu_limit": r.cpu_limit,
                    "memory_limit_mb": r.memory_limit_mb,
                    "timeout_seconds": r.timeout_seconds,
                    "last_health": r.last_health_json,
                    "recent_logs": (r.execution_logs_json or [])[-10:],
                }
                for r in runtimes
            ],
            "token_summary": {
                "input_tokens": int(token_totals[0] or 0),
                "output_tokens": int(token_totals[1] or 0),
                "total_tokens": int(token_totals[0] or 0) + int(token_totals[1] or 0),
                "estimated_cost_usd": float(token_totals[2] or 0),
            },
            "mcp_summary": {
                "total_servers": int(mcp_servers_count),
                "connected_approved_servers": int(mcp_connected_count),
                "recent_calls": [
                    {
                        "id": str(m.id),
                        "server_id": str(m.server_id),
                        "tool_name": m.tool_name,
                        "status": m.status,
                        "duration_ms": m.duration_ms,
                        "error_message": m.error_message,
                        "created_at": m.created_at.isoformat() if m.created_at else None,
                    }
                    for m in recent_mcp_logs
                ],
            },
        }


monitor_tracker = ExecutionMonitorTracker()
