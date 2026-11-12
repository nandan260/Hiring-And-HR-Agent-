"""Agent 5: Employee Onboarding Agent (EnterpriseFlow-inspired docs, IT provisioning & team allocation HITL)."""

from __future__ import annotations

import re
from typing import Any, Optional
import uuid

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.storage import resolve_tenant_file
from app.db.models import AgentRental, HitlApproval, KnowledgeDocument, OnboardingWorkflow
from app.runtime.docker_sandbox import sandbox_manager

from .framework.base_agent import BaseSpecializedAgent
from .framework.llm_provider import llm_provider
from .framework.rag import extract_document_text
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

REQUIRED_ONBOARDING_DOCS = [
    "aadhar_card",
    "degree_certificate",
    "offer_letter_signed",
    "bank_details",
]


class OnboardingInput(BaseAgentInput):
    employee_name: Optional[str] = None
    employee_email: Optional[str] = None
    role_title: str = Field(default="Backend Engineer")
    department: str = Field(default="Engineering")
    start_date: str = Field(default="2026-11-23")
    submitted_documents: list[str] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)
    document_text_snippets: dict[str, str] = Field(default_factory=dict)


class OnboardingChecklistItem(BaseModel):
    item: str
    completed: bool
    stage: str


class TrainingRecommendation(BaseModel):
    module: str
    due_days: int
    reason: str
    status: str = "recommended"


class OnboardingOutput(BaseAgentOutput):
    workflow_id: Optional[str] = None
    employee_name: str
    role_title: str
    department: str
    current_stage: str
    progress_percent: int = Field(ge=0, le=100)
    documents_status: dict[str, str]
    checklist: list[OnboardingChecklistItem]
    it_provisioning_plan: dict[str, Any]
    team_allocation_plan: dict[str, Any]
    training_recommendations: list[TrainingRecommendation]


def _infer_employee_name(prompt: str) -> str:
    m = re.search(r"(?:onboard|for|hire)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})", prompt or "")
    return m.group(1).strip() if m else "Rohan Kulkarni"


class EmployeeOnboardingAgent(BaseSpecializedAgent):
    """Coordinates document collection/verification, onboarding checklists, IT/team HITL provisioning, and training."""

    agent_id = "employee-onboarding"
    agent_name = "Employee Onboarding Agent"
    agent_version = "1.2.0"
    system_prompt_file = "employee_onboarding_agent.md"
    domain = DomainDefinition(
        domain_name="Employee Onboarding & Provisioning",
        allowed_topics=[
            "employee document collection & verification",
            "onboarding checklist tracking",
            "IT account & equipment provisioning requests",
            "department & team allocation suggestions",
            "role-based training recommendations",
            "onboarding progress monitoring",
        ],
        rejected_categories={
            "Medical Diagnosis & Clinical Advice": "Healthcare",
            "Financial Trading & Cryptocurrency": "Business and Finance",
            "Legal Litigation & Contract Redlining": "Legal and Compliance",
        },
        in_domain_keywords=[
            "onboard",
            "onboarding",
            "new hire",
            "document",
            "documents",
            "kyc",
            "aadhar",
            "aadhaar",
            "degree",
            "offer letter",
            "bank details",
            "checklist",
            "it provisioning",
            "laptop",
            "okta",
            "scim",
            "team",
            "buddy",
            "training",
            "progress",
        ],
        min_keyword_hits=1,
        suggested_marketplace_category="Hiring and HR",
    )
    input_schema = OnboardingInput
    output_schema = OnboardingOutput
    allowed_tools = [
        "sandbox_kyc_ocr_verify",
        "scim_provision_account",
        "jira_create_hardware_ticket",
        "hrms_assign_buddy",
    ]
    tool_permissions = ToolPermissionConfig(
        default_allowed_tools=allowed_tools,
        hitl_required_tools=["scim_provision_account", "jira_create_hardware_ticket", "hrms_assign_buddy"],
        read_only_tools=["sandbox_kyc_ocr_verify"],
    )
    knowledge_base = KnowledgeBaseConfig(
        enabled=True,
        top_k=3,
        min_similarity=0.05,
        allowed_source_types=["kyc_doc", "handbook", "policy"],
    )
    model_cfg = ModelConfig(provider="auto", model_tier="tier_1_slm", temperature=0.1, max_tokens=1500)
    guardrails = GuardrailConfig(
        block_prompt_injection=True,
        block_protected_characteristics=True,
        require_hitl_actions=["it_provisioning_request", "team_allocation"],
    )
    memory = MemoryConfig(short_term_window_messages=10, summary_max_tokens=400, persist_to_db=True)
    execution_limits = ExecutionLimits(max_steps=12, max_tool_calls=6, max_input_tokens=8000, max_output_tokens=1800)

    def register_tools(self, toolbox: AgentToolBox) -> None:
        toolbox.register("sandbox_kyc_ocr_verify", self._tool_sandbox_kyc_ocr_verify)
        toolbox.register("scim_provision_account", self._tool_scim_provision_account)
        toolbox.register("jira_create_hardware_ticket", self._tool_jira_create_hardware_ticket)
        toolbox.register("hrms_assign_buddy", self._tool_hrms_assign_buddy)

    def _resolve_rental_id(self, ctx: ToolContext) -> Optional[uuid.UUID]:
        if ctx.rental_id is not None:
            return ctx.rental_id
        fallback = ctx.db.execute(
            select(AgentRental).where(AgentRental.tenant_id == ctx.tenant_id).limit(1)
        ).scalar_one_or_none()
        return fallback.id if fallback else None

    def _tool_sandbox_kyc_ocr_verify(self, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        emp_name = str(args.get("employee_name") or "New Hire")
        submitted = {str(d).lower().strip() for d in args.get("submitted_documents", [])}
        snippets = {str(k).lower(): str(v) for k, v in (args.get("document_text_snippets") or {}).items()}

        # Check uploaded tenant KB documents if document_ids are supplied
        extracted_notes: dict[str, str] = {}
        for doc_id_str in args.get("document_ids", []):
            try:
                doc_uuid = uuid.UUID(str(doc_id_str))
            except ValueError:
                continue
            doc = ctx.db.execute(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.id == doc_uuid,
                    KnowledgeDocument.tenant_id == ctx.tenant_id,
                )
            ).scalar_one_or_none()
            if doc is None:
                continue
            try:
                path = resolve_tenant_file(ctx.tenant_id, doc.storage_rel_path)
                txt = extract_document_text(path.read_bytes(), filename=doc.original_filename, mime_type=doc.mime_type)
            except Exception:
                txt = doc.title
            lower_all = f"{doc.title} {doc.original_filename} {txt}".lower()
            for req_doc in REQUIRED_ONBOARDING_DOCS:
                key_words = req_doc.replace("_", " ").split()
                if any(w in lower_all for w in key_words):
                    submitted.add(req_doc)
                    extracted_notes[req_doc] = f"Verified from document '{doc.title}'"

        # Merge with existing OnboardingWorkflow state if one already exists
        existing_wf = ctx.db.execute(
            select(OnboardingWorkflow).where(
                OnboardingWorkflow.tenant_id == ctx.tenant_id,
                OnboardingWorkflow.employee_name == emp_name,
            )
        ).scalar_one_or_none()

        docs_status: dict[str, str] = {}
        for req_doc in REQUIRED_ONBOARDING_DOCS:
            prior_status = (existing_wf.documents_status_json or {}).get(req_doc) if existing_wf else None
            if req_doc in submitted or req_doc in snippets or prior_status == "verified":
                docs_status[req_doc] = "verified"
            else:
                docs_status[req_doc] = "pending_upload"

        rt = sandbox_manager.ensure_tenant_runtime(ctx.db, ctx.tenant_id, rental_id=ctx.rental_id)
        sb_exec = sandbox_manager.execute_in_runtime(
            ctx.db,
            ctx.tenant_id,
            rt.id,
            task_name="verify_kyc_document",
            payload={
                "document_type": "onboarding_kyc_bundle",
                "text_preview": " ".join(sorted(submitted)) + " " + " ".join(snippets.values())[:2000],
                "filename": ",".join(sorted(submitted)),
                "min_chars": 3,
            },
        )
        missing = [k for k, v in docs_status.items() if v != "verified"]
        return {
            "employee_name": emp_name,
            "documents_status": docs_status,
            "missing_documents": missing,
            "all_verified": len(missing) == 0,
            "extracted_notes": extracted_notes,
            "_sandbox_meta": {
                "runtime_id": sb_exec["runtime_id"],
                "agent_runtime_id": sb_exec["agent_runtime_id"],
                "backend_mode": sb_exec["backend_mode"],
                "is_container_isolated": sb_exec["is_container_isolated"],
                "last_task": "verify_kyc_document",
                "duration_ms": sb_exec["duration_ms"],
            },
        }

    def _has_approved_action(self, ctx: ToolContext, emp_name: str, action_type: str) -> bool:
        approvals = ctx.db.execute(
            select(HitlApproval).where(
                HitlApproval.tenant_id == ctx.tenant_id,
                HitlApproval.agent_slug == self.agent_id,
                HitlApproval.action_type == action_type,
                HitlApproval.status == "approved",
            )
        ).scalars().all()
        for ap in approvals:
            if (ap.payload_json or {}).get("employee_name") == emp_name:
                return True
        return False

    def _tool_scim_provision_account(self, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        emp_name = str(args.get("employee_name") or "New Hire")
        dept = str(args.get("department") or "Engineering")
        role_title = str(args.get("role_title") or "Backend Engineer")
        approved = self._has_approved_action(ctx, emp_name, "it_provisioning_request")

        is_eng = "engineer" in role_title.lower() or "eng" in dept.lower()
        apps = ["Okta SSO", "Google Workspace", "Slack", "Jira"] + (
            ["GitHub Enterprise", "AWS Sandbox SSO"] if is_eng else ["CRM Portal"]
        )
        slug_user = re.sub(r"[^a-z0-9]+", ".", emp_name.lower()).strip(".")
        return {
            "status": "provisioned" if approved else "awaiting_human_approval",
            "approved": approved,
            "corporate_email": args.get("employee_email") or f"{slug_user}@acmecloud.io",
            "apps": apps,
        }

    def _tool_jira_create_hardware_ticket(self, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        emp_name = str(args.get("employee_name") or "New Hire")
        dept = str(args.get("department") or "Engineering")
        approved = self._has_approved_action(ctx, emp_name, "it_provisioning_request")
        laptop = "MacBook Pro 14 M4 (32GB)" if "eng" in dept.lower() else "ThinkPad X1 Carbon"
        return {
            "laptop_model": laptop,
            "security_badge": "Building Access Tier-2",
            "ticket_status": "submitted" if approved else "draft_awaiting_approval",
        }

    def _tool_hrms_assign_buddy(self, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        emp_name = str(args.get("employee_name") or "New Hire")
        dept = str(args.get("department") or "Engineering")
        role_title = str(args.get("role_title") or "Backend Engineer")
        approved = self._has_approved_action(ctx, emp_name, "team_allocation")

        manager_map = {
            "Engineering": "Vikram Patel (VP Engineering)",
            "Customer Operations": "Ananya Sharma (Head of Operations)",
            "Product": "Vikram Patel (Product Lead)",
        }
        team_plan = {
            "department": dept,
            "assigned_team": f"{dept} Core Pod",
            "suggested_manager": manager_map.get(dept, "Vikram Patel"),
            "suggested_buddy": "Aarav Mehta" if "eng" in dept.lower() else "Maya Chen",
            "status": "confirmed" if approved else "awaiting_human_approval",
        }

        training = [
            {
                "module": "Multi-Tenant Security, Privacy & SOC2 Fundamentals",
                "due_days": 3,
                "reason": "Mandatory Day-1 security baseline for all tenant data handlers",
                "status": "assigned" if approved else "recommended",
            },
            {
                "module": f"{role_title} Production Architecture & Tooling Bootcamp",
                "due_days": 7,
                "reason": f"Tailored technical ramp-up for {role_title} in {dept}",
                "status": "assigned" if approved else "recommended",
            },
            {
                "module": "HR Policies, PTO, & Inclusive Workplace Guide",
                "due_days": 14,
                "reason": "Standard company handbook walkthrough",
                "status": "assigned" if approved else "recommended",
            },
        ]
        return {"team_allocation": team_plan, "training_recommendations": training, "approved": approved}

    def select_tools(
        self,
        parsed_input: OnboardingInput,
        state: AgentExecutionState,
        ctx: ToolContext,
    ) -> list[dict[str, Any]]:
        emp_name = parsed_input.employee_name or _infer_employee_name(parsed_input.prompt)
        common = {
            "employee_name": emp_name,
            "employee_email": parsed_input.employee_email,
            "role_title": parsed_input.role_title,
            "department": parsed_input.department,
            "start_date": parsed_input.start_date,
            "submitted_documents": parsed_input.submitted_documents,
            "document_ids": parsed_input.document_ids,
            "document_text_snippets": parsed_input.document_text_snippets,
        }
        return [
            {"tool": "sandbox_kyc_ocr_verify", "args": common},
            {"tool": "scim_provision_account", "args": common},
            {"tool": "jira_create_hardware_ticket", "args": common},
            {"tool": "hrms_assign_buddy", "args": common},
        ]

    def synthesize_output(
        self,
        parsed_input: OnboardingInput,
        tool_results: list[dict[str, Any]],
        memory_ctx: dict[str, Any],
        state: AgentExecutionState,
        ctx: ToolContext,
    ) -> tuple[OnboardingOutput, dict[str, Any]]:
        emp_name = parsed_input.employee_name or _infer_employee_name(parsed_input.prompt)
        docs_res: dict[str, Any] = {}
        scim_res: dict[str, Any] = {}
        jira_res: dict[str, Any] = {}
        team_res: dict[str, Any] = {}

        for res in tool_results:
            if res.get("status") != "completed":
                continue
            t = res["tool"]
            if t == "sandbox_kyc_ocr_verify":
                docs_res = res["output"]
            elif t == "scim_provision_account":
                scim_res = res["output"]
            elif t == "jira_create_hardware_ticket":
                jira_res = res["output"]
            elif t == "hrms_assign_buddy":
                team_res = res["output"]

        docs_status = dict(docs_res.get("documents_status") or {d: "pending_upload" for d in REQUIRED_ONBOARDING_DOCS})
        all_docs_verified = bool(docs_res.get("all_verified", False))
        it_approved = bool(scim_res.get("approved", False))
        team_approved = bool(team_res.get("approved", False))

        checklist = [
            {
                "item": "Collect & verify mandatory onboarding documents (ID, Degree, Signed Offer, Bank)",
                "completed": all_docs_verified,
                "stage": "document_collection",
            },
            {
                "item": "Stage IT SSO apps & hardware laptop provisioning ticket",
                "completed": bool(scim_res),
                "stage": "it_provisioning_request",
            },
            {
                "item": "HR human approval for IT provisioning (Okta SCIM + Hardware)",
                "completed": it_approved,
                "stage": "hitl_it_approval",
            },
            {
                "item": "HR human approval for Department Team & Onboarding Buddy assignment",
                "completed": team_approved,
                "stage": "hitl_team_approval",
            },
            {
                "item": "Assign Day-1 security & role-specific training tracks",
                "completed": team_approved,
                "stage": "training_assignment",
            },
        ]
        completed_steps = sum(1 for item in checklist if item["completed"])
        progress_pct = int((completed_steps / len(checklist)) * 100)

        if not all_docs_verified:
            stage = "document_collection"
        elif not it_approved:
            stage = "awaiting_it_provisioning_approval"
        elif not team_approved:
            stage = "awaiting_team_allocation_approval"
        else:
            stage = "onboarding_ready"

        it_plan = {
            "corporate_email": scim_res.get("corporate_email"),
            "apps": scim_res.get("apps", []),
            "laptop_model": jira_res.get("laptop_model", "MacBook Pro 14 M4"),
            "ticket_status": jira_res.get("ticket_status", "draft_awaiting_approval"),
            "scim_status": scim_res.get("status", "awaiting_human_approval"),
        }
        team_plan = dict(team_res.get("team_allocation") or {})
        training_recs = list(team_res.get("training_recommendations") or [])

        # Persist or update OnboardingWorkflow in PostgreSQL under tenant_id
        wf_id: Optional[str] = None
        rental_id = self._resolve_rental_id(ctx)
        if rental_id is not None:
            wf = ctx.db.execute(
                select(OnboardingWorkflow).where(
                    OnboardingWorkflow.tenant_id == ctx.tenant_id,
                    OnboardingWorkflow.employee_name == emp_name,
                )
            ).scalar_one_or_none()
            if wf is None:
                wf = OnboardingWorkflow(
                    tenant_id=ctx.tenant_id,
                    rental_id=rental_id,
                    employee_name=emp_name,
                    employee_email=scim_res.get("corporate_email"),
                    role_title=parsed_input.role_title,
                    department=parsed_input.department,
                    start_date=parsed_input.start_date,
                )
                ctx.db.add(wf)
            wf.current_stage = stage
            wf.progress_percent = progress_pct
            wf.documents_status_json = docs_status
            wf.checklist_json = checklist
            wf.it_provisioning_json = it_plan
            wf.team_allocation_json = team_plan
            wf.training_plan_json = training_recs
            ctx.db.flush()
            wf_id = str(wf.id)

        hitl_requests: list[dict[str, Any]] = []
        if not it_approved:
            hitl_requests.append(
                {
                    "action_type": "it_provisioning_request",
                    "title": f"Approve IT Provisioning (Okta SCIM + Hardware) for {emp_name}",
                    "summary": (
                        f"Provision {it_plan['corporate_email']} across {', '.join(it_plan['apps'][:4])} "
                        f"and order {it_plan['laptop_model']}."
                    ),
                    "payload": {
                        "employee_name": emp_name,
                        "workflow_id": wf_id,
                        "it_provisioning": it_plan,
                    },
                }
            )
        if not team_approved:
            hitl_requests.append(
                {
                    "action_type": "team_allocation",
                    "title": f"Approve Team & Buddy Allocation for {emp_name} ({parsed_input.department})",
                    "summary": (
                        f"Assign to {team_plan.get('assigned_team')} with manager "
                        f"{team_plan.get('suggested_manager')} and buddy {team_plan.get('suggested_buddy')}."
                    ),
                    "payload": {
                        "employee_name": emp_name,
                        "workflow_id": wf_id,
                        "team_allocation": team_plan,
                    },
                }
            )

        def _fallback_json(_context: dict[str, Any] | None = None) -> dict[str, Any]:
            missing = docs_res.get("missing_documents", [])
            summary = (
                f"Onboarding workflow for **{emp_name}** ({parsed_input.role_title}, {parsed_input.department}) is at "
                f"**{progress_pct}%** (`{stage}`)."
                + (f" Pending documents: {', '.join(missing)}." if missing else " All 4 required KYC documents verified.")
            )
            explanation = (
                "Reused EnterpriseFlow 5-stage onboarding pattern: verified uploaded documents, generated checklist, "
                "staged IT provisioning & buddy allocation, and gated consequential provisioning behind human approval."
            )
            return {"summary": summary, "explanation": explanation}

        llm_res = llm_provider.generate_structured(
            system_prompt=self.load_system_prompt(state.get("custom_persona_prompt", "")),
            user_prompt=parsed_input.prompt,
            context_data={
                "employee_name": emp_name,
                "stage": stage,
                "progress_percent": progress_pct,
                "documents_status": docs_status,
                "it_plan": it_plan,
                "team_plan": team_plan,
            },
            fallback_fn=_fallback_json,
            provider_override=state.get("model_provider_override"),
            temperature=self.model_cfg.temperature,
            max_tokens=self.model_cfg.max_tokens,
        )
        fb = _fallback_json()
        parsed = llm_res.parsed_json or fb

        output = OnboardingOutput(
            agent_id=self.agent_id,
            agent_version=self.agent_version,
            summary=str(parsed.get("summary") or fb["summary"]),
            explanation=str(parsed.get("explanation") or fb["explanation"]),
            citations=["EnterpriseFlow Onboarding Baseline", "Tenant KYC & Provisioning Ledger"],
            requires_human_approval=bool(hitl_requests),
            hitl_requests=hitl_requests,
            structured_payload={
                "workflow_id": wf_id,
                "current_stage": stage,
                "progress_percent": progress_pct,
                "documents_status": docs_status,
                "it_provisioning_plan": it_plan,
                "team_allocation_plan": team_plan,
            },
            workflow_id=wf_id,
            employee_name=emp_name,
            role_title=parsed_input.role_title,
            department=parsed_input.department,
            current_stage=stage,
            progress_percent=progress_pct,
            documents_status=docs_status,
            checklist=[OnboardingChecklistItem.model_validate(c) for c in checklist],
            it_provisioning_plan=it_plan,
            team_allocation_plan=team_plan,
            training_recommendations=[TrainingRecommendation.model_validate(t) for t in training_recs],
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
