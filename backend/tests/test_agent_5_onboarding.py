"""Tests for Agent 5: Employee Onboarding Agent (EnterpriseFlow-inspired docs & HITL provisioning)."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import select

from agents.employee_onboarding_agent import EmployeeOnboardingAgent
from agents.framework.tools import AgentToolBox
from agents.framework.workflow import run_agent_workflow
from app.db.models import AgentRental, HitlApproval, OnboardingWorkflow, Organization, User
from app.db.session import get_session_factory


def test_onboarding_agent_docs_hitl_gates_and_resume_to_100_percent(test_environment):
    SessionFactory = get_session_factory()
    agent = EmployeeOnboardingAgent()
    toolbox = AgentToolBox()
    agent.register_tools(toolbox)

    with SessionFactory() as db:
        acme = db.execute(select(Organization).where(Organization.slug == "acme-cloud")).scalar_one()
        novabio = db.execute(select(Organization).where(Organization.slug == "novabio-healthtech")).scalar_one()
        ananya = db.execute(select(User).where(User.email == "ananya@acmecloud.io")).scalar_one()
        onboarder = db.execute(
            select(AgentRental).where(
                AgentRental.tenant_id == acme.id,
                AgentRental.display_name == "Acme Onboarding Orchestrator",
            )
        ).scalar_one()

        # 1. Start onboarding with partial docs -> pauses with HITL approvals & flags missing docs
        res1 = run_agent_workflow(
            agent=agent,
            toolbox=toolbox,
            db=db,
            tenant_id=acme.id,
            actor_user_id=ananya.id,
            actor_role="business_owner",
            rental_id=onboarder.id,
            user_input="Onboard Rohan Kulkarni as Backend Engineer in Engineering starting next Monday.",
            structured_input={
                "employee_name": "Rohan Kulkarni",
                "role_title": "Backend Engineer",
                "department": "Engineering",
                "submitted_documents": ["aadhar_card", "offer_letter_signed"],
            },
            persist_telemetry=True,
        )
        db.commit()

        assert res1["execution_status"] == "paused_hitl"
        out1 = res1["validated_output"]
        assert out1["documents_status"]["aadhar_card"] == "verified"
        assert out1["documents_status"]["degree_certificate"] == "pending_upload"
        assert out1["requires_human_approval"] is True
        action_types = {h["action_type"] for h in out1["hitl_requests"]}
        assert "it_provisioning_request" in action_types
        assert "team_allocation" in action_types
        assert out1["it_provisioning_plan"]["scim_status"] == "awaiting_human_approval"
        assert out1["progress_percent"] < 100

        # Approve both persistent HITL requests in DB as HR owner
        pending_rows = db.execute(
            select(HitlApproval).where(
                HitlApproval.tenant_id == acme.id,
                HitlApproval.agent_slug == "employee-onboarding",
                HitlApproval.status == "pending",
            )
        ).scalars().all()
        for ap in pending_rows:
            if (ap.payload_json or {}).get("employee_name") == "Rohan Kulkarni":
                ap.status = "approved"
                ap.resolved_by_user_id = ananya.id
                ap.resolved_at = datetime.now(timezone.utc)
        db.commit()

        # 2. Submit remaining docs and resume onboarding -> advances to 100% onboarding_ready
        res2 = run_agent_workflow(
            agent=agent,
            toolbox=toolbox,
            db=db,
            tenant_id=acme.id,
            actor_user_id=ananya.id,
            actor_role="business_owner",
            rental_id=onboarder.id,
            user_input="Verify degree certificate and bank details and complete onboarding progress for Rohan Kulkarni.",
            structured_input={
                "employee_name": "Rohan Kulkarni",
                "role_title": "Backend Engineer",
                "department": "Engineering",
                "submitted_documents": ["degree_certificate", "bank_details"],
            },
            persist_telemetry=True,
        )
        db.commit()

        assert res2["execution_status"] == "completed"
        out2 = res2["validated_output"]
        assert out2["current_stage"] == "onboarding_ready"
        assert out2["progress_percent"] == 100
        assert out2["it_provisioning_plan"]["scim_status"] == "provisioned"
        assert out2["team_allocation_plan"]["status"] == "confirmed"
        assert len(out2["training_recommendations"]) >= 3

        # NovaBio must never see Acme's OnboardingWorkflow
        nb_wfs = db.execute(select(OnboardingWorkflow).where(OnboardingWorkflow.tenant_id == novabio.id)).scalars().all()
        assert all(w.employee_name != "Rohan Kulkarni" for w in nb_wfs)

        # 3. Out-of-domain query blocked
        res_bad = run_agent_workflow(
            agent=agent,
            toolbox=toolbox,
            db=db,
            tenant_id=acme.id,
            actor_user_id=ananya.id,
            actor_role="business_owner",
            rental_id=onboarder.id,
            user_input="Buy Ethereum crypto and analyze RSI stock chart.",
            persist_telemetry=False,
        )
        assert res_bad["classifier_result"] == "rejected_out_of_domain"
        assert res_bad.get("tool_results", []) == []
