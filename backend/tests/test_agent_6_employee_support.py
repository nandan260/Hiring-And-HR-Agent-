"""Tests for Agent 6: Employee Support & HR Policy Agent (pgvector RAG + RBAC + Citations)."""

from __future__ import annotations

from sqlalchemy import select

from agents.employee_support_agent import EmployeeSupportAgent
from agents.framework.tools import AgentToolBox
from agents.framework.workflow import run_agent_workflow
from app.db.models import AgentRental, Organization, User
from app.db.session import get_session_factory


def test_employee_support_rag_citations_rbac_and_tenant_isolation(test_environment):
    SessionFactory = get_session_factory()
    agent = EmployeeSupportAgent()
    toolbox = AgentToolBox()
    agent.register_tools(toolbox)

    with SessionFactory() as db:
        acme = db.execute(select(Organization).where(Organization.slug == "acme-cloud")).scalar_one()
        novabio = db.execute(select(Organization).where(Organization.slug == "novabio-healthtech")).scalar_one()
        ananya = db.execute(select(User).where(User.email == "ananya@acmecloud.io")).scalar_one()
        maya = db.execute(select(User).where(User.email == "maya@acmecloud.io")).scalar_one()
        priya = db.execute(select(User).where(User.email == "priya@novabio.io")).scalar_one()

        acme_policy_desk = db.execute(
            select(AgentRental).where(
                AgentRental.tenant_id == acme.id,
                AgentRental.display_name == "Acme HR Policy Desk",
            )
        ).scalar_one()
        novabio_helpdesk = db.execute(
            select(AgentRental).where(
                AgentRental.tenant_id == novabio.id,
                AgentRental.display_name == "NovaBio Compliance & HR Helpdesk",
            )
        ).scalar_one()

        # 1. Employee asks about PTO & parental leave -> grounded in Acme Employee Handbook with citations
        res_pto = run_agent_workflow(
            agent=agent,
            toolbox=toolbox,
            db=db,
            tenant_id=acme.id,
            actor_user_id=maya.id,
            actor_role="business_employee",
            rental_id=acme_policy_desk.id,
            user_input="How many days of PTO and paid parental leave do Acme employees get?",
            persist_telemetry=True,
        )
        db.commit()

        assert res_pto["execution_status"] == "completed"
        out = res_pto["validated_output"]
        assert out["grounded_in_tenant_docs"] is True
        assert out["policy_category"] == "leave"
        assert len(out["citations"]) >= 1
        assert "Acme Cloud Employee Handbook" in out["citations"][0]
        assert "22 days" in out["answer"] or "16 weeks" in out["answer"]

        # 2. Employee asks about confidential Admin Compensation/Bonus policy -> NOT allowed for employee role
        res_secret = run_agent_workflow(
            agent=agent,
            toolbox=toolbox,
            db=db,
            tenant_id=acme.id,
            actor_user_id=maya.id,
            actor_role="business_employee",
            rental_id=acme_policy_desk.id,
            user_input="What is the confidential executive retention bonus ARR trigger?",
            persist_telemetry=False,
        )
        sec_out = res_secret["validated_output"]
        assert "125%" not in sec_out["answer"]

        # 3. Admin/Owner can access Admin Compensation policy chunk
        res_owner = run_agent_workflow(
            agent=agent,
            toolbox=toolbox,
            db=db,
            tenant_id=acme.id,
            actor_user_id=ananya.id,
            actor_role="business_owner",
            rental_id=acme_policy_desk.id,
            user_input="Explain the L5 compensation band and confidential executive retention bonus policy.",
            persist_telemetry=False,
        )
        owner_out = res_owner["validated_output"]
        assert owner_out["grounded_in_tenant_docs"] is True
        assert any("Compensation Guide" in c for c in owner_out["citations"])

        # 4. NovaBio user asking same PTO policy must NEVER receive Acme handbook chunks
        res_nb = run_agent_workflow(
            agent=agent,
            toolbox=toolbox,
            db=db,
            tenant_id=novabio.id,
            actor_user_id=priya.id,
            actor_role="business_owner",
            rental_id=novabio_helpdesk.id,
            user_input="What is our bio-safety recovery leave and PTO policy?",
            persist_telemetry=False,
        )
        nb_out = res_nb["validated_output"]
        assert all("Acme" not in c for c in nb_out["citations"])
        assert "Acme" not in nb_out["answer"]

        # 5. Unrelated policy with zero matching docs refuses cleanly instead of fabricating
        res_unknown = run_agent_workflow(
            agent=agent,
            toolbox=toolbox,
            db=db,
            tenant_id=acme.id,
            actor_user_id=maya.id,
            actor_role="business_employee",
            rental_id=acme_policy_desk.id,
            user_input="Does our company policy include helicopter yacht reimbursement policy?",
            persist_telemetry=False,
        )
        # Ensure it doesn't fabricate a yacht policy!
        assert "helicopter" not in res_unknown["validated_output"]["answer"].lower()
