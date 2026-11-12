"""Tests for Agent 2: Job Description Generator Agent."""

from __future__ import annotations

from sqlalchemy import select

from agents.framework.rag import semantic_search_knowledge
from agents.framework.tools import AgentToolBox
from agents.framework.workflow import run_agent_workflow
from agents.jd_generator_agent import JobDescriptionGeneratorAgent
from app.db.models import Organization, User
from app.db.session import get_session_factory


def test_jd_generator_structured_output_inclusive_linting_and_rbac_kb(test_environment):
    SessionFactory = get_session_factory()
    agent = JobDescriptionGeneratorAgent()
    toolbox = AgentToolBox()
    agent.register_tools(toolbox)

    with SessionFactory() as db:
        acme = db.execute(select(Organization).where(Organization.slug == "acme-cloud")).scalar_one()
        ananya = db.execute(select(User).where(User.email == "ananya@acmecloud.io")).scalar_one()
        maya = db.execute(select(User).where(User.email == "maya@acmecloud.io")).scalar_one()

        # 1. Owner prompt with biased buzzwords triggers inclusive linter + leveling guide
        res = run_agent_workflow(
            agent=agent,
            toolbox=toolbox,
            db=db,
            tenant_id=acme.id,
            actor_user_id=ananya.id,
            actor_role="business_owner",
            rental_id=None,
            user_input="Draft a job description for a young and energetic rockstar Senior Backend Engineer knowing Python, FastAPI, and PostgreSQL.",
            structured_input={
                "job_title": "Senior Backend Engineer",
                "required_skills": ["Python", "FastAPI", "PostgreSQL"],
                "preferred_skills": ["LangGraph", "Docker"],
            },
            persist_telemetry=False,
        )
        assert res["execution_status"] == "completed"
        out = res["validated_output"]
        assert out["job_title"] == "Senior Backend Engineer"
        assert "Senior" in out["suggested_experience_level"]
        assert len(out["responsibilities"]) >= 3
        assert len(out["must_have_qualifications"]) >= 3
        assert len(out["inclusive_language_findings"]) >= 2
        assert out["inclusive_language_score"] < 100
        assert "# Senior Backend Engineer" in out["formatted_job_description_markdown"]
        assert any("Compensation Guide" in c or "Acme" in c for c in out["citations"])

        # 2. Employee role is blocked by workflow RBAC from generating official JDs,
        # and direct KB retrieval enforces min_role_access against Admin-Only comp docs
        res_emp = run_agent_workflow(
            agent=agent,
            toolbox=toolbox,
            db=db,
            tenant_id=acme.id,
            actor_user_id=maya.id,
            actor_role="business_employee",
            rental_id=None,
            user_input="Create a Senior Backend Engineer job description for compensation bands.",
            persist_telemetry=False,
        )
        assert res_emp["execution_status"] == "blocked"
        assert res_emp["classifier_result"] == "blocked_permission"

        emp_rag = semantic_search_knowledge(
            db,
            tenant_id=acme.id,
            rental_id=None,
            actor_role="business_employee",
            query="Senior Backend Engineer compensation bands",
            top_k=5,
        )
        assert all("Admin Only" not in h["document_title"] for h in emp_rag)

        # 3. Out-of-domain personal shopping/travel request rejected without tool execution
        res_bad = run_agent_workflow(
            agent=agent,
            toolbox=toolbox,
            db=db,
            tenant_id=acme.id,
            actor_user_id=ananya.id,
            actor_role="business_owner",
            rental_id=None,
            user_input="Book flight and hotel reservation for a vacation itinerary.",
            persist_telemetry=False,
        )
        assert res_bad["classifier_result"] == "rejected_out_of_domain"
        assert res_bad.get("tool_results", []) == []
