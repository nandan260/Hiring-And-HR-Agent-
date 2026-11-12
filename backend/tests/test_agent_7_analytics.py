"""Tests for Agent 7: HR Analytics Agent (SQLGlot AST guard, tenant metrics, charts)."""

from __future__ import annotations

from sqlalchemy import select

from agents.framework.tools import AgentToolBox
from agents.framework.workflow import run_agent_workflow
from agents.hr_analytics_agent import HRAnalyticsAgent
from app.db.models import Organization, User
from app.db.session import get_session_factory


def test_hr_analytics_kpis_charts_sqlglot_and_tenant_isolation(test_environment):
    SessionFactory = get_session_factory()
    agent = HRAnalyticsAgent()
    toolbox = AgentToolBox()
    agent.register_tools(toolbox)

    with SessionFactory() as db:
        acme = db.execute(select(Organization).where(Organization.slug == "acme-cloud")).scalar_one()
        novabio = db.execute(select(Organization).where(Organization.slug == "novabio-healthtech")).scalar_one()
        ananya = db.execute(select(User).where(User.email == "ananya@acmecloud.io")).scalar_one()
        priya = db.execute(select(User).where(User.email == "priya@novabio.io")).scalar_one()

        # 1. Generate Acme HR pipeline metrics & chart specifications
        res = run_agent_workflow(
            agent=agent,
            toolbox=toolbox,
            db=db,
            tenant_id=acme.id,
            actor_user_id=ananya.id,
            actor_role="business_owner",
            rental_id=None,
            user_input="Generate hiring pipeline analytics report, time-to-hire KPIs, and onboarding charts.",
            structured_input={"report_focus": "full_hr_overview"},
            persist_telemetry=False,
        )
        assert res["execution_status"] == "completed"
        out = res["validated_output"]
        assert out["kpis"]["total_candidates"] >= 3
        assert out["kpis"]["estimated_time_to_hire_days"] >= 14
        assert len(out["charts"]) == 3
        chart_ids = {c["chart_id"] for c in out["charts"]}
        assert chart_ids == {"hiring_pipeline_funnel", "top_candidate_skills", "onboarding_progress_overview"}

        # 2. NovaBio gets only NovaBio's isolated metrics (1 seeded candidate, zero Acme candidates)
        res_nb = run_agent_workflow(
            agent=agent,
            toolbox=toolbox,
            db=db,
            tenant_id=novabio.id,
            actor_user_id=priya.id,
            actor_role="business_owner",
            rental_id=None,
            user_input="Show NovaBio hiring pipeline analytics and charts.",
            persist_telemetry=False,
        )
        nb_out = res_nb["validated_output"]
        assert nb_out["kpis"]["total_candidates"] == 1
        assert all(
            d["label"] != "Maya Chen"
            for ch in nb_out["charts"]
            for d in ch["data"]
        )

        # 3. Dangerous / non-whitelisted SQL query blocked by SQLGlot AST validator
        res_sql_block = run_agent_workflow(
            agent=agent,
            toolbox=toolbox,
            db=db,
            tenant_id=acme.id,
            actor_user_id=ananya.id,
            actor_role="business_owner",
            rental_id=None,
            user_input="Run custom analytics SQL query on hiring pipeline.",
            structured_input={"custom_sql_query": "DELETE FROM candidates; SELECT * FROM users;"},
            persist_telemetry=False,
        )
        sql_out = res_sql_block["validated_output"]
        assert "blocked" in sql_out["summary"].lower()
        assert sql_out["charts"] == []

        # 4. Out-of-domain legal litigation prompt rejected without tools
        res_bad = run_agent_workflow(
            agent=agent,
            toolbox=toolbox,
            db=db,
            tenant_id=acme.id,
            actor_user_id=ananya.id,
            actor_role="business_owner",
            rental_id=None,
            user_input="Draft a patent infringement lawsuit court filing to sue competitor.",
            persist_telemetry=False,
        )
        assert res_bad["classifier_result"] == "rejected_out_of_domain"
        assert res_bad["suggested_category"] == "Legal and Compliance"
        assert res_bad.get("tool_results", []) == []
