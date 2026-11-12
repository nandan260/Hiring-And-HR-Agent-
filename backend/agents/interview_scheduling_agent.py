"""Agent 4: Interview Scheduling Agent (mock calendar + DB interview tracker + HITL invite gate)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any, Literal, Optional
import uuid

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.db.models import AgentRental, InterviewRecord
from app.runtime.playwright_browser import BrowserSecurityError, browser_manager

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


class InterviewSchedulingInput(BaseAgentInput):
    candidate_name: Optional[str] = None
    candidate_id: Optional[str] = None
    role_title: str = Field(default="Senior Backend Engineer")
    interview_stage: str = Field(default="technical_round")
    interviewer_emails: list[str] = Field(
        default_factory=lambda: ["ananya@acmecloud.io", "vikram@acmecloud.io"]
    )
    duration_minutes: int = Field(default=45, ge=15, le=180)
    timezone: str = Field(default="UTC")
    preferred_days_ahead: int = Field(default=2, ge=1, le=21)
    custom_availability: list[str] = Field(default_factory=list)
    action: Literal["suggest_and_schedule", "check_status", "reschedule"] = Field(
        default="suggest_and_schedule"
    )
    interview_id: Optional[str] = None


class SuggestedSlot(BaseModel):
    slot_start_iso: str
    slot_end_iso: str
    timezone: str
    available_interviewers: list[str]
    conflict_free: bool = True


class InterviewRecordSummary(BaseModel):
    interview_id: str
    candidate_name: str
    role_title: str
    interview_stage: str
    scheduled_start_iso: str
    duration_minutes: int
    status: str
    meeting_link: str


class InterviewSchedulingOutput(BaseAgentOutput):
    suggested_slots: list[SuggestedSlot]
    scheduled_interview: Optional[InterviewRecordSummary] = None
    tracked_interviews: list[InterviewRecordSummary] = Field(default_factory=list)
    invitation_draft: str = ""
    calendar_provider_mode: str = "mock_google_calendar_adapter"


def _infer_candidate_from_prompt(prompt: str) -> str:
    m = re.search(r"(?:for|with)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})", prompt or "")
    return m.group(1).strip() if m else "Aarav Mehta"


class InterviewSchedulingAgent(BaseSpecializedAgent):
    """Collects mock interviewer availability, solves conflict-free slots, drafts invitations, and tracks interviews."""

    agent_id = "interview-scheduling"
    agent_name = "Interview Scheduling Agent"
    agent_version = "1.1.0"
    system_prompt_file = "interview_scheduling_agent.md"
    domain = DomainDefinition(
        domain_name="Interview Scheduling & Coordination",
        allowed_topics=[
            "interviewer availability collection",
            "conflict-free interview slot suggestions",
            "interview invitation drafting",
            "interview tracking & rescheduling",
        ],
        rejected_categories={
            "Medical Diagnosis & Clinical Advice": "Healthcare",
            "Financial Trading & Cryptocurrency": "Business and Finance",
            "Legal Litigation & Contract Redlining": "Legal and Compliance",
        },
        in_domain_keywords=[
            "interview",
            "interviews",
            "schedule",
            "scheduling",
            "reschedule",
            "slot",
            "slots",
            "availability",
            "calendar",
            "interviewer",
            "invite",
            "invitation",
            "panel",
            "meeting",
            "round",
            "status",
        ],
        min_keyword_hits=1,
        suggested_marketplace_category="Hiring and HR",
    )
    input_schema = InterviewSchedulingInput
    output_schema = InterviewSchedulingOutput
    allowed_tools = [
        "gcal_free_busy",
        "timezone_slot_solver",
        "playwright_legacy_portal",
        "gcal_create_interview_event",
    ]
    tool_permissions = ToolPermissionConfig(
        default_allowed_tools=allowed_tools,
        hitl_required_tools=["gcal_create_interview_event"],
        read_only_tools=["gcal_free_busy", "timezone_slot_solver", "playwright_legacy_portal"],
    )
    knowledge_base = KnowledgeBaseConfig(enabled=False)
    model_cfg = ModelConfig(provider="auto", model_tier="tier_1_slm", temperature=0.1, max_tokens=1200)
    guardrails = GuardrailConfig(
        block_prompt_injection=True,
        block_protected_characteristics=True,
        require_hitl_actions=["send_interview_invites"],
    )
    memory = MemoryConfig(short_term_window_messages=8, summary_max_tokens=300, persist_to_db=True)
    execution_limits = ExecutionLimits(max_steps=10, max_tool_calls=5, max_input_tokens=6000, max_output_tokens=1500)

    def register_tools(self, toolbox: AgentToolBox) -> None:
        toolbox.register("gcal_free_busy", self._tool_gcal_free_busy)
        toolbox.register("timezone_slot_solver", self._tool_timezone_slot_solver)
        toolbox.register("playwright_legacy_portal", self._tool_playwright_legacy_portal)
        toolbox.register("gcal_create_interview_event", self._tool_gcal_create_interview_event)

    def _tool_gcal_free_busy(self, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        interviewers = list(args.get("interviewer_emails") or ["ananya@acmecloud.io"])
        days_ahead = int(args.get("preferred_days_ahead") or 2)
        base_day = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).replace(
            hour=10, minute=0, second=0, microsecond=0
        )

        # Fetch existing tenant interviews to avoid double booking
        existing_rows = ctx.db.execute(
            select(InterviewRecord)
            .where(InterviewRecord.tenant_id == ctx.tenant_id, InterviewRecord.status != "cancelled")
            .order_by(InterviewRecord.scheduled_start.asc())
        ).scalars().all()
        busy_starts = {
            row.scheduled_start.astimezone(timezone.utc).replace(second=0, microsecond=0).isoformat()
            for row in existing_rows
        }

        candidate_windows = [
            base_day + timedelta(hours=offset) for offset in (0, 2, 4, 24, 26)
        ]
        if args.get("custom_availability"):
            parsed_custom: list[datetime] = []
            for iso_str in args["custom_availability"]:
                try:
                    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    parsed_custom.append(dt.astimezone(timezone.utc))
                except ValueError:
                    continue
            if parsed_custom:
                candidate_windows = parsed_custom + candidate_windows

        free_windows = [
            dt for dt in candidate_windows if dt.replace(second=0, microsecond=0).isoformat() not in busy_starts
        ]
        tracked = [
            {
                "interview_id": str(row.id),
                "candidate_name": row.candidate_name,
                "role_title": row.role_title,
                "interview_stage": row.interview_stage,
                "scheduled_start_iso": row.scheduled_start.astimezone(timezone.utc).isoformat(),
                "duration_minutes": row.duration_minutes,
                "status": row.status,
                "meeting_link": row.meeting_link,
            }
            for row in existing_rows
        ]
        return {
            "provider": "mock_google_calendar_adapter",
            "interviewers": interviewers,
            "free_start_isos": [dt.isoformat() for dt in free_windows[:5]],
            "tracked_interviews": tracked,
        }

    def _tool_timezone_slot_solver(self, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        fb = self._tool_gcal_free_busy(ctx, args)
        duration = int(args.get("duration_minutes") or 45)
        tz_name = str(args.get("timezone") or "UTC")
        interviewers = fb["interviewers"]
        slots: list[dict[str, Any]] = []

        for iso_str in fb["free_start_isos"][:3]:
            start_dt = datetime.fromisoformat(iso_str)
            end_dt = start_dt + timedelta(minutes=duration)
            slots.append(
                {
                    "slot_start_iso": start_dt.isoformat(),
                    "slot_end_iso": end_dt.isoformat(),
                    "timezone": tz_name,
                    "available_interviewers": interviewers,
                    "conflict_free": True,
                }
            )
        return {"suggested_slots": slots, "tracked_interviews": fb["tracked_interviews"]}

    def _tool_playwright_legacy_portal(self, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        portal_url = str(args.get("portal_url") or "").strip()
        if not portal_url:
            return {
                "portal_checked": False,
                "status": "not_used",
                "note": "No approved portal URL supplied; internal DB calendar solver used.",
            }
        try:
            page = browser_manager.navigate_and_extract(
                tenant_id=ctx.tenant_id,
                url=portal_url,
                capture_screenshot=True,
            )
            return {"portal_checked": True, "status": "completed", "visited_pages": [page]}
        except BrowserSecurityError as exc:
            return {"portal_checked": False, "status": "blocked", "error": str(exc)}

    def _tool_gcal_create_interview_event(self, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        solved = self._tool_timezone_slot_solver(ctx, args)
        action = args.get("action", "suggest_and_schedule")
        tracked = solved["tracked_interviews"]
        if action == "check_status":
            return {
                "suggested_slots": solved["suggested_slots"],
                "scheduled_interview": None,
                "tracked_interviews": tracked,
                "invitation_draft": "",
            }

        slots = solved["suggested_slots"]
        chosen_iso = slots[0]["slot_start_iso"] if slots else datetime.now(timezone.utc).isoformat()
        chosen_dt = datetime.fromisoformat(chosen_iso)
        cand_name = str(args.get("candidate_name") or "Aarav Mehta")
        role_title = str(args.get("role_title") or "Senior Backend Engineer")
        stage = str(args.get("interview_stage") or "technical_round")
        duration = int(args.get("duration_minutes") or 45)
        interviewers = list(args.get("interviewer_emails") or ["ananya@acmecloud.io"])
        tz_name = str(args.get("timezone") or "UTC")

        invite_draft = (
            f"Subject: Interview Invitation - {role_title} ({stage.replace('_', ' ').title()})\n"
            f"Candidate: {cand_name}\n"
            f"Panel: {', '.join(interviewers)}\n"
            f"Date & Time: {chosen_dt.strftime('%Y-%m-%d %H:%M %Z')} ({duration} mins)\n"
            f"Location: Google Meet (mock link generated upon HR confirmation)"
        )

        # Resolve valid rental_id for persistence (even during direct unit runs)
        rental_id = ctx.rental_id
        if rental_id is None:
            fallback_rental = ctx.db.execute(
                select(AgentRental).where(AgentRental.tenant_id == ctx.tenant_id).limit(1)
            ).scalar_one_or_none()
            rental_id = fallback_rental.id if fallback_rental else None

        scheduled_summary = None
        if rental_id is not None:
            if action == "reschedule" and args.get("interview_id"):
                try:
                    existing = ctx.db.execute(
                        select(InterviewRecord).where(
                            InterviewRecord.id == uuid.UUID(str(args["interview_id"])),
                            InterviewRecord.tenant_id == ctx.tenant_id,
                        )
                    ).scalar_one_or_none()
                except ValueError:
                    existing = None
                if existing is not None:
                    existing.scheduled_start = chosen_dt
                    existing.duration_minutes = duration
                    existing.status = "invite_pending_approval"
                    existing.invitation_draft = invite_draft
                    ctx.db.flush()
                    record = existing
                else:
                    record = None
            else:
                record = None

            if record is None:
                cand_uuid = None
                if args.get("candidate_id"):
                    try:
                        cand_uuid = uuid.UUID(str(args["candidate_id"]))
                    except ValueError:
                        cand_uuid = None
                record = InterviewRecord(
                    tenant_id=ctx.tenant_id,
                    rental_id=rental_id,
                    candidate_id=cand_uuid,
                    candidate_name=cand_name,
                    role_title=role_title,
                    interview_stage=stage,
                    interviewer_emails=interviewers,
                    scheduled_start=chosen_dt,
                    duration_minutes=duration,
                    timezone=tz_name,
                    meeting_link=f"https://meet.rentanagent.demo/{uuid.uuid4().hex[:10]}",
                    status="invite_pending_approval",
                    invitation_draft=invite_draft,
                )
                ctx.db.add(record)
                ctx.db.flush()

            scheduled_summary = {
                "interview_id": str(record.id),
                "candidate_name": record.candidate_name,
                "role_title": record.role_title,
                "interview_stage": record.interview_stage,
                "scheduled_start_iso": record.scheduled_start.astimezone(timezone.utc).isoformat(),
                "duration_minutes": record.duration_minutes,
                "status": record.status,
                "meeting_link": record.meeting_link,
            }
            tracked = [t for t in tracked if t["interview_id"] != scheduled_summary["interview_id"]] + [scheduled_summary]

        return {
            "suggested_slots": slots,
            "scheduled_interview": scheduled_summary,
            "tracked_interviews": tracked,
            "invitation_draft": invite_draft,
        }

    def select_tools(
        self,
        parsed_input: InterviewSchedulingInput,
        state: AgentExecutionState,
        ctx: ToolContext,
    ) -> list[dict[str, Any]]:
        cand_name = parsed_input.candidate_name or _infer_candidate_from_prompt(parsed_input.prompt)
        common_args = {
            "candidate_name": cand_name,
            "candidate_id": parsed_input.candidate_id,
            "role_title": parsed_input.role_title,
            "interview_stage": parsed_input.interview_stage,
            "interviewer_emails": parsed_input.interviewer_emails,
            "duration_minutes": parsed_input.duration_minutes,
            "timezone": parsed_input.timezone,
            "preferred_days_ahead": parsed_input.preferred_days_ahead,
            "custom_availability": parsed_input.custom_availability,
            "action": parsed_input.action,
            "interview_id": parsed_input.interview_id,
        }
        planned = [
            {"tool": "gcal_free_busy", "args": common_args},
            {"tool": "timezone_slot_solver", "args": common_args},
        ]
        if parsed_input.action != "check_status":
            planned.append({"tool": "gcal_create_interview_event", "args": common_args})
        return planned

    def synthesize_output(
        self,
        parsed_input: InterviewSchedulingInput,
        tool_results: list[dict[str, Any]],
        memory_ctx: dict[str, Any],
        state: AgentExecutionState,
        ctx: ToolContext,
    ) -> tuple[InterviewSchedulingOutput, dict[str, Any]]:
        slots: list[dict[str, Any]] = []
        scheduled: Optional[dict[str, Any]] = None
        tracked: list[dict[str, Any]] = []
        invite_draft = ""

        for res in tool_results:
            if res.get("status") != "completed":
                continue
            out = res.get("output", {})
            if res["tool"] == "timezone_slot_solver":
                slots = list(out.get("suggested_slots", []))
                tracked = list(out.get("tracked_interviews", []))
            elif res["tool"] == "gcal_create_interview_event":
                slots = list(out.get("suggested_slots", slots))
                scheduled = out.get("scheduled_interview")
                tracked = list(out.get("tracked_interviews", tracked))
                invite_draft = str(out.get("invitation_draft", ""))

        def _fallback_json(_context: dict[str, Any] | None = None) -> dict[str, Any]:
            if parsed_input.action == "check_status":
                return {
                    "summary": f"Tracking {len(tracked)} interview(s) via mock Google Calendar integration.",
                    "explanation": "Checked tenant interview database and free/busy windows with zero conflicts.",
                }
            cand = (scheduled or {}).get("candidate_name") or parsed_input.candidate_name or "candidate"
            slot_txt = slots[0]["slot_start_iso"] if slots else "TBD"
            return {
                "summary": (
                    f"Proposed {len(slots)} conflict-free interview slot(s) for **{cand}** ({parsed_input.role_title}) "
                    f"and staged calendar invitation at `{slot_txt}` awaiting HR approval."
                ),
                "explanation": (
                    "Collected mock calendar free/busy availability across the interview panel, checked existing "
                    "tenant interviews to avoid double-booking, drafted the invite, and gated outbound dispatch behind HITL."
                ),
            }

        llm_res = llm_provider.generate_structured(
            system_prompt=self.load_system_prompt(state.get("custom_persona_prompt", "")),
            user_prompt=parsed_input.prompt,
            context_data={"suggested_slots": slots, "scheduled_interview": scheduled, "tracked_count": len(tracked)},
            fallback_fn=_fallback_json,
            provider_override=state.get("model_provider_override"),
            temperature=self.model_cfg.temperature,
            max_tokens=self.model_cfg.max_tokens,
        )
        fb = _fallback_json()
        parsed = llm_res.parsed_json or fb

        hitl_requests = []
        if scheduled and parsed_input.action != "check_status":
            hitl_requests.append(
                {
                    "action_type": "send_interview_invites",
                    "title": f"Send Calendar Invite to {scheduled['candidate_name']} ({scheduled['role_title']})",
                    "summary": f"Confirm dispatching mock calendar invite for {scheduled['scheduled_start_iso']}",
                    "payload": {
                        "interview_id": scheduled["interview_id"],
                        "candidate_name": scheduled["candidate_name"],
                        "scheduled_start_iso": scheduled["scheduled_start_iso"],
                    },
                }
            )

        output = InterviewSchedulingOutput(
            agent_id=self.agent_id,
            agent_version=self.agent_version,
            summary=str(parsed.get("summary") or fb["summary"]),
            explanation=str(parsed.get("explanation") or fb["explanation"]),
            citations=["Mock Google Calendar Free/Busy Adapter", "Tenant Interview Schedule Ledger"],
            requires_human_approval=bool(hitl_requests),
            hitl_requests=hitl_requests,
            structured_payload={
                "suggested_slots": slots,
                "scheduled_interview": scheduled,
                "tracked_count": len(tracked),
            },
            suggested_slots=[SuggestedSlot.model_validate(s) for s in slots],
            scheduled_interview=InterviewRecordSummary.model_validate(scheduled) if scheduled else None,
            tracked_interviews=[InterviewRecordSummary.model_validate(t) for t in tracked],
            invitation_draft=invite_draft,
            calendar_provider_mode="mock_google_calendar_adapter",
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
