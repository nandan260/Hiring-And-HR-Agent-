"""Central AgentRegistry binding all 7 specialized Hiring & HR agents and shared toolboxes."""

from __future__ import annotations

from typing import Any, Optional
import uuid

from sqlalchemy.orm import Session

from .candidate_shortlisting_agent import CandidateShortlistingAgent
from .employee_onboarding_agent import EmployeeOnboardingAgent
from .employee_support_agent import EmployeeSupportAgent
from .framework.base_agent import BaseSpecializedAgent
from .framework.classifier import detect_hr_workflow_slug
from .framework.state import AgentExecutionState
from .framework.tools import AgentToolBox
from .framework.workflow import run_agent_workflow
from .hr_analytics_agent import HRAnalyticsAgent
from .interview_scheduling_agent import InterviewSchedulingAgent
from .jd_generator_agent import JobDescriptionGeneratorAgent
from .recruitment_agent import RecruitmentScreeningAgent

AGENT_ALIASES: dict[str, str] = {
    "recruitment_agent": "recruitment-screening",
    "recruitment-screening": "recruitment-screening",
    "jd_generator_agent": "jd-generator",
    "jd-generator": "jd-generator",
    "candidate_shortlisting_agent": "candidate-shortlisting",
    "candidate-shortlisting": "candidate-shortlisting",
    "interview_scheduling_agent": "interview-scheduling",
    "interview-scheduling": "interview-scheduling",
    "employee_onboarding_agent": "employee-onboarding",
    "employee-onboarding": "employee-onboarding",
    "employee_support_agent": "hr-policy-support",
    "hr-policy-support": "hr-policy-support",
    "hr_analytics_agent": "hr-analytics",
    "hr-analytics": "hr-analytics",
}


class HRAgentRegistry:
    """Singleton registry owning all 7 specialized agents and their registered tools."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseSpecializedAgent] = {}
        self._toolbox = AgentToolBox()
        for agent in [
            RecruitmentScreeningAgent(),
            JobDescriptionGeneratorAgent(),
            CandidateShortlistingAgent(),
            InterviewSchedulingAgent(),
            EmployeeOnboardingAgent(),
            EmployeeSupportAgent(),
            HRAnalyticsAgent(),
        ]:
            self._agents[agent.agent_id] = agent
            agent.register_tools(self._toolbox)

    def normalize_slug(self, slug: str) -> str:
        key = (slug or "").strip().lower()
        return AGENT_ALIASES.get(key, key)

    def get_agent(self, slug: str) -> BaseSpecializedAgent:
        canonical = self.normalize_slug(slug)
        if canonical not in self._agents:
            raise KeyError(f"Unknown HR agent slug '{slug}'. Available: {', '.join(self._agents.keys())}")
        return self._agents[canonical]

    def get_toolbox(self) -> AgentToolBox:
        return self._toolbox

    def list_specs(self) -> list[dict[str, Any]]:
        return [agent.describe() for agent in self._agents.values()]

    def resolve_workflow_slug(
        self,
        *,
        user_input: str,
        workflow_hint: Optional[str] = None,
        conversation_history: Optional[list[dict[str, str]]] = None,
        structured_input: Optional[dict[str, Any]] = None,
        fallback_slug: str = "hr-policy-support",
    ) -> str:
        if workflow_hint:
            canonical = self.normalize_slug(workflow_hint)
            if canonical in self._agents:
                return canonical
        detected = detect_hr_workflow_slug(
            user_input,
            conversation_history=conversation_history,
            default_slug=fallback_slug,
            structured_input=structured_input,
        )
        if detected and detected in self._agents:
            return detected
        return fallback_slug

    def execute(
        self,
        *,
        agent_slug: str,
        db: Session,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        actor_role: str,
        user_input: str,
        rental_id: Optional[uuid.UUID] = None,
        conversation_id: Optional[uuid.UUID] = None,
        structured_input: Optional[dict[str, Any]] = None,
        attachments: Optional[list[str]] = None,
        conversation_history: Optional[list[dict[str, str]]] = None,
        model_provider_override: Optional[str] = None,
        persist_telemetry: bool = True,
        enable_optimization: bool = True,
    ) -> AgentExecutionState:
        agent = self.get_agent(agent_slug)
        return run_agent_workflow(
            agent=agent,
            toolbox=self._toolbox,
            db=db,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            user_input=user_input,
            rental_id=rental_id,
            conversation_id=conversation_id,
            structured_input=structured_input,
            attachments=attachments,
            conversation_history=conversation_history,
            model_provider_override=model_provider_override,
            persist_telemetry=persist_telemetry,
            enable_optimization=enable_optimization,
            available_agents=self._agents,
        )


agent_registry = HRAgentRegistry()
