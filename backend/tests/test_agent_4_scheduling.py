"""Tests for Agent 4: Interview Scheduling Agent."""

from __future__ import annotations

from sqlalchemy import select

from agents.framework.tools import AgentToolBox
from agents.framework.workflow import run_agent_workflow
from agents.interview_scheduling_agent import InterviewSchedulingAgent
from app.db.models import HitlApproval, InterviewRecord, Organization, User
from app.db.session import get_session_factory


def test_interview_scheduling_slots_persistence_tracking_and_hitl(test_environment):
    SessionFactory = get_session_factory()
    agent = InterviewSchedulingAgent()
    toolbox = AgentToolBox()
    agent.register_tools(toolbox)

    with SessionFactory() as db:
        acme = db.execute(select(Organization).where(Organization.slug == "acme-cloud")).scalar_one()
        novabio = db.execute(select(Organization).where(Organization.slug == "novabio-healthtech")).scalar_one()
        ananya = db.execute(select(User).where(User.email == "ananya@acmecloud.io")).scalar_one()

        from app.db.models import AgentRental
        screener = db.execute(
            select(AgentRental).where(
                AgentRental.tenant_id == acme.id,
                AgentRental.display_name == "Acme Talent Screener",
            )
        ).scalar_one()

        # 1. Suggest slots, create InterviewRecord, draft invitation, and stage HITL approval
        res = run_agent_workflow(
            agent=agent,
            toolbox=toolbox,
            db=db,
            tenant_id=acme.id,
            actor_user_id=ananya.id,
            actor_role="business_owner",
            rental_id=screener.id,
            user_input="Schedule a 45-minute technical interview for Elena Rostova with the engineering panel.",
            structured_input={
                "candidate_name": "Elena Rostova",
                "role_title": "Senior Backend Engineer",
                "duration_minutes": 45,
                "interviewer_emails": ["ananya@acmecloud.io", "vikram@acmecloud.io"],
            },
            persist_telemetry=True,
        )
        db.commit()

        assert res["execution_status"] == "paused_hitl"
        out = res["validated_output"]
        assert out["calendar_provider_mode"] == "mock_google_calendar_adapter"
        assert len(out["suggested_slots"]) >= 2
        assert out["scheduled_interview"]["candidate_name"] == "Elena Rostova"
        assert out["scheduled_interview"]["status"] == "invite_pending_approval"
        assert "Elena Rostova" in out["invitation_draft"]
        assert len(out["hitl_requests"]) == 1
        assert out["hitl_requests"][0]["action_type"] == "send_interview_invites"

        # Persistent HITL approval + InterviewRecord saved under Acme only
        approvals = db.execute(
            select(HitlApproval).where(
                HitlApproval.tenant_id == acme.id,
                HitlApproval.action_type == "send_interview_invites",
            )
        ).scalars().all()
        assert len(approvals) >= 1

        nb_interviews = db.execute(select(InterviewRecord).where(InterviewRecord.tenant_id == novabio.id)).scalars().all()
        assert all(i.candidate_name != "Elena Rostova" for i in nb_interviews)

        # 2. Check interview tracking status
        res_track = run_agent_workflow(
            agent=agent,
            toolbox=toolbox,
            db=db,
            tenant_id=acme.id,
            actor_user_id=ananya.id,
            actor_role="business_owner",
            rental_id=screener.id,
            user_input="Check current interview status across scheduled panels.",
            structured_input={"action": "check_status"},
            persist_telemetry=False,
        )
        assert res_track["execution_status"] == "completed"
        assert len(res_track["validated_output"]["tracked_interviews"]) >= 2

        # 3. Out-of-domain medical query blocked cleanly
        res_bad = run_agent_workflow(
            agent=agent,
            toolbox=toolbox,
            db=db,
            tenant_id=acme.id,
            actor_user_id=ananya.id,
            actor_role="business_owner",
            rental_id=screener.id,
            user_input="What dosage of antibiotic should I prescribe for fever and rash?",
            persist_telemetry=False,
        )
        assert res_bad["classifier_result"] == "rejected_out_of_domain"
        assert res_bad["suggested_category"] == "Healthcare"
        assert res_bad.get("tool_results", []) == []
