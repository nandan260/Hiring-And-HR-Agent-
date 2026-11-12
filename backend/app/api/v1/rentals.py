from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.dependencies import (
    AuthenticatedPrincipal,
    get_current_principal,
    get_tenant_db,
    require_roles,
)
from ...core.security import encrypt_secret, mask_secret
from ...core.storage import resolve_tenant_file, save_tenant_upload
from ...db.models import (
    AgentCatalog,
    AgentConfiguration,
    AgentRental,
    AgentVersion,
    BillingRecord,
    KnowledgeDocument,
    SubscriptionPlan,
    TokenUsage,
    ToolPermission,
    ToolRegistry,
)
from ...schemas.rental import (
    AgentConfigurationResponse,
    AgentConfigurationUpdateRequest,
    KnowledgeDocumentResponse,
    RentAgentRequest,
    RentalResponse,
    ToolCredentialBindRequest,
    ToolPermissionResponse,
    ToolPermissionUpdateRequest,
)
from agents.framework.rag import extract_document_text, index_document_chunks
from ...services.audit import record_audit

router = APIRouter(prefix="/rentals", tags=["Agent Rentals"])

ROLE_LEVEL = {
    "business_employee": 1,
    "business_admin": 2,
    "business_owner": 3,
    "platform_admin": 4,
}


def _compute_config_hash(rental_id: uuid.UUID, persona: str, model_tier: str, blind: bool) -> str:
    raw = f"{rental_id}:{persona}:{model_tier}:{blind}".encode("utf-8")
    return "cfg_" + hashlib.sha256(raw).hexdigest()[:12]


def _get_tenant_rental(db: Session, tenant_id: uuid.UUID, rental_id: uuid.UUID) -> AgentRental:
    rental = db.scalars(
        select(AgentRental).where(AgentRental.id == rental_id, AgentRental.tenant_id == tenant_id)
    ).first()
    if rental is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rented agent not found for this tenant")
    return rental


def _build_rental_response(db: Session, rental: AgentRental) -> RentalResponse:
    agent = db.get(AgentCatalog, rental.agent_id)
    version = db.get(AgentVersion, rental.agent_version_id)
    plan = db.get(SubscriptionPlan, rental.subscription_plan_id)
    cfg = db.scalars(select(AgentConfiguration).where(AgentConfiguration.rental_id == rental.id)).first()

    perm_rows = db.execute(
        select(ToolPermission, ToolRegistry)
        .join(ToolRegistry, ToolPermission.tool_id == ToolRegistry.id)
        .where(ToolPermission.rental_id == rental.id, ToolPermission.tenant_id == rental.tenant_id)
        .order_by(ToolRegistry.slug.asc())
    ).all()

    docs = db.scalars(
        select(KnowledgeDocument)
        .where(KnowledgeDocument.rental_id == rental.id, KnowledgeDocument.tenant_id == rental.tenant_id)
        .order_by(KnowledgeDocument.created_at.desc())
    ).all()

    usage_agg = db.execute(
        select(
            func.coalesce(func.sum(TokenUsage.input_tokens + TokenUsage.output_tokens), 0),
            func.coalesce(func.sum(TokenUsage.cached_tokens), 0),
        ).where(TokenUsage.rental_id == rental.id, TokenUsage.tenant_id == rental.tenant_id)
    ).one()

    return RentalResponse(
        id=rental.id,
        tenant_id=rental.tenant_id,
        agent_id=rental.agent_id,
        agent_slug=agent.slug if agent else "unknown",
        agent_name=agent.name if agent else "Unknown Agent",
        version=version.version if version else "1.0.0",
        subscription_plan_slug=plan.slug if plan else "growth",
        subscription_plan_name=plan.name if plan else "Growth Demo Plan",
        display_name=rental.display_name,
        status=rental.status,
        activated_at=rental.activated_at,
        paused_at=rental.paused_at,
        cancelled_at=rental.cancelled_at,
        created_at=rental.created_at,
        tokens_used_this_month=int(usage_agg[0] or 0),
        tokens_saved_by_cache=int(usage_agg[1] or 0),
        configuration=AgentConfigurationResponse(
            id=cfg.id,
            rental_id=cfg.rental_id,
            custom_persona_prompt=cfg.custom_persona_prompt,
            config_hash=cfg.config_hash,
            kb_version_hash=cfg.kb_version_hash,
            model_routing_tier=cfg.model_routing_tier,
            monthly_token_quota=cfg.monthly_token_quota,
            allowed_domains=list(cfg.allowed_domains or []),
            blind_screening_mode=cfg.blind_screening_mode,
            strict_pii_masking=cfg.strict_pii_masking,
            require_hitl_approval=cfg.require_hitl_approval,
            max_steps=cfg.max_steps,
        ),
        tool_permissions=[
            ToolPermissionResponse(
                id=perm.id,
                tool_id=tool.id,
                tool_slug=tool.slug,
                tool_name=tool.name,
                mcp_server_slug=tool.mcp_server_slug,
                execution_mode=tool.execution_mode,
                requires_hitl=tool.requires_hitl,
                is_allowed=perm.is_allowed,
                credential_status=perm.credential_status,
                masked_secret_ref=perm.masked_secret_ref,
            )
            for perm, tool in perm_rows
        ],
        knowledge_documents=[
            KnowledgeDocumentResponse(
                id=d.id,
                rental_id=d.rental_id,
                title=d.title,
                original_filename=d.original_filename,
                source_type=d.source_type,
                mime_type=d.mime_type,
                file_size_bytes=d.file_size_bytes,
                sha256_checksum=d.sha256_checksum,
                chunk_count=d.chunk_count,
                min_role_access=d.min_role_access,
                status=d.status,
                created_at=d.created_at,
            )
            for d in docs
        ],
    )


@router.get("", response_model=list[RentalResponse])
def list_tenant_rentals(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> list[RentalResponse]:
    rentals = db.scalars(
        select(AgentRental)
        .where(AgentRental.tenant_id == principal.tenant_id)
        .order_by(AgentRental.created_at.desc())
    ).all()
    return [_build_rental_response(db, r) for r in rentals]


@router.post("", response_model=RentalResponse, status_code=status.HTTP_201_CREATED)
def rent_agent(
    payload: RentAgentRequest,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> RentalResponse:
    agent = db.scalars(
        select(AgentCatalog).where(AgentCatalog.slug == payload.agent_slug, AgentCatalog.is_active.is_(True))
    ).first()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog agent not found")

    version = db.scalars(
        select(AgentVersion)
        .where(AgentVersion.agent_id == agent.id)
        .order_by(AgentVersion.is_latest.desc(), AgentVersion.created_at.desc())
    ).first()
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent version not found")

    plan = db.scalars(select(SubscriptionPlan).where(SubscriptionPlan.slug == payload.subscription_plan_slug)).first()
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription plan not found")

    now = datetime.now(timezone.utc)
    display_name = (payload.display_name or f"{principal.organization_name.split()[0]} {agent.name}").strip()

    rental = AgentRental(
        tenant_id=principal.tenant_id,
        agent_id=agent.id,
        agent_version_id=version.id,
        subscription_plan_id=plan.id,
        display_name=display_name[:150],
        status="active",
        rented_by_user_id=principal.user_id,
        activated_at=now,
    )
    db.add(rental)
    db.flush()

    persona = (payload.custom_persona_prompt or "").strip()
    quota = payload.monthly_token_quota or plan.included_tokens
    cfg = AgentConfiguration(
        tenant_id=principal.tenant_id,
        rental_id=rental.id,
        custom_persona_prompt=persona,
        config_hash=_compute_config_hash(rental.id, persona, version.default_model_tier, False),
        kb_version_hash="kb_v1_empty",
        model_routing_tier=version.default_model_tier,
        monthly_token_quota=quota,
        allowed_domains=["github.com", "gitlab.com"] if agent.browser_enabled else [],
        blind_screening_mode=(agent.slug == "recruitment-screening"),
        strict_pii_masking=True,
        require_hitl_approval=True,
        max_steps=12,
    )
    db.add(cfg)

    tool_slugs = list(version.default_tool_slugs or [])
    tools = db.scalars(select(ToolRegistry).where(ToolRegistry.slug.in_(tool_slugs))).all() if tool_slugs else []
    for tool in tools:
        db.add(
            ToolPermission(
                tenant_id=principal.tenant_id,
                rental_id=rental.id,
                tool_id=tool.id,
                is_allowed=True,
                credential_status="not_configured",
                encrypted_secret=None,
                masked_secret_ref="Not bound" if tool.auth_scheme != "none" else "No secret required",
            )
        )

    db.add(
        BillingRecord(
            tenant_id=principal.tenant_id,
            rental_id=rental.id,
            subscription_plan_id=plan.id,
            billing_period=now.strftime("%Y-%m"),
            base_amount_usd=plan.monthly_price_usd,
            token_overage_usd=Decimal("0.00"),
            total_amount_usd=plan.monthly_price_usd,
            status="demo_active",
            is_demo_subscription=True,
            description=f"DEMO SUBSCRIPTION ({plan.name}) — {display_name} (No real charge)",
        )
    )
    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        rental_id=rental.id,
        action="rental.created",
        resource_type="agent_rental",
        resource_id=str(rental.id),
        ip_address=principal.ip_address,
        metadata={"agent_slug": agent.slug, "plan_slug": plan.slug, "is_demo_subscription": True},
    )
    db.flush()

    resp = _build_rental_response(db, rental)
    db.commit()
    return resp


@router.get("/{rental_id}", response_model=RentalResponse)
def get_rental_detail(
    rental_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> RentalResponse:
    rental = _get_tenant_rental(db, principal.tenant_id, rental_id)
    return _build_rental_response(db, rental)


@router.post("/{rental_id}/activate", response_model=RentalResponse)
def activate_rental(
    rental_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> RentalResponse:
    rental = _get_tenant_rental(db, principal.tenant_id, rental_id)
    if rental.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cancelled rental cannot be reactivated")
    rental.status = "active"
    rental.activated_at = rental.activated_at or datetime.now(timezone.utc)
    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        rental_id=rental.id,
        action="rental.activated",
        resource_type="agent_rental",
        resource_id=str(rental.id),
        ip_address=principal.ip_address,
    )
    db.flush()
    resp = _build_rental_response(db, rental)
    db.commit()
    return resp


@router.post("/{rental_id}/pause", response_model=RentalResponse)
def pause_rental(
    rental_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> RentalResponse:
    rental = _get_tenant_rental(db, principal.tenant_id, rental_id)
    if rental.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cancelled rental cannot be paused")
    rental.status = "paused"
    rental.paused_at = datetime.now(timezone.utc)
    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        rental_id=rental.id,
        action="rental.paused",
        resource_type="agent_rental",
        resource_id=str(rental.id),
        ip_address=principal.ip_address,
    )
    db.flush()
    resp = _build_rental_response(db, rental)
    db.commit()
    return resp


@router.post("/{rental_id}/resume", response_model=RentalResponse)
def resume_rental(
    rental_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> RentalResponse:
    rental = _get_tenant_rental(db, principal.tenant_id, rental_id)
    if rental.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cancelled rental cannot be resumed")
    rental.status = "active"
    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        rental_id=rental.id,
        action="rental.resumed",
        resource_type="agent_rental",
        resource_id=str(rental.id),
        ip_address=principal.ip_address,
    )
    db.flush()
    resp = _build_rental_response(db, rental)
    db.commit()
    return resp


@router.post("/{rental_id}/cancel", response_model=RentalResponse)
def cancel_rental(
    rental_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> RentalResponse:
    rental = _get_tenant_rental(db, principal.tenant_id, rental_id)
    rental.status = "cancelled"
    rental.cancelled_at = datetime.now(timezone.utc)

    billing_rows = db.scalars(
        select(BillingRecord).where(
            BillingRecord.rental_id == rental.id,
            BillingRecord.tenant_id == principal.tenant_id,
            BillingRecord.status == "demo_active",
        )
    ).all()
    for row in billing_rows:
        row.status = "demo_cancelled"

    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        rental_id=rental.id,
        action="rental.cancelled",
        resource_type="agent_rental",
        resource_id=str(rental.id),
        ip_address=principal.ip_address,
    )
    db.flush()
    resp = _build_rental_response(db, rental)
    db.commit()
    return resp


@router.patch("/{rental_id}/configuration", response_model=RentalResponse)
def update_rental_configuration(
    rental_id: uuid.UUID,
    payload: AgentConfigurationUpdateRequest,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> RentalResponse:
    rental = _get_tenant_rental(db, principal.tenant_id, rental_id)
    if rental.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot configure a cancelled rental")

    cfg = db.scalars(
        select(AgentConfiguration).where(
            AgentConfiguration.rental_id == rental.id,
            AgentConfiguration.tenant_id == principal.tenant_id,
        )
    ).first()
    if cfg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration record missing")

    if payload.display_name is not None:
        rental.display_name = payload.display_name.strip()
    if payload.custom_persona_prompt is not None:
        cfg.custom_persona_prompt = payload.custom_persona_prompt
    if payload.model_routing_tier is not None:
        cfg.model_routing_tier = payload.model_routing_tier
    if payload.monthly_token_quota is not None:
        cfg.monthly_token_quota = payload.monthly_token_quota
    if payload.allowed_domains is not None:
        cfg.allowed_domains = [d.strip().lower() for d in payload.allowed_domains if d.strip()]
    if payload.blind_screening_mode is not None:
        cfg.blind_screening_mode = payload.blind_screening_mode
    if payload.strict_pii_masking is not None:
        cfg.strict_pii_masking = payload.strict_pii_masking
    if payload.require_hitl_approval is not None:
        cfg.require_hitl_approval = payload.require_hitl_approval
    if payload.max_steps is not None:
        cfg.max_steps = payload.max_steps

    cfg.config_hash = _compute_config_hash(
        rental.id, cfg.custom_persona_prompt, cfg.model_routing_tier, cfg.blind_screening_mode
    )

    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        rental_id=rental.id,
        action="rental.configuration_updated",
        resource_type="agent_configuration",
        resource_id=str(cfg.id),
        ip_address=principal.ip_address,
        metadata={"config_hash": cfg.config_hash, "model_tier": cfg.model_routing_tier},
    )
    db.flush()
    resp = _build_rental_response(db, rental)
    db.commit()
    return resp


@router.patch("/{rental_id}/tools/{tool_id}", response_model=ToolPermissionResponse)
def toggle_tool_permission(
    rental_id: uuid.UUID,
    tool_id: uuid.UUID,
    payload: ToolPermissionUpdateRequest,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> ToolPermissionResponse:
    _get_tenant_rental(db, principal.tenant_id, rental_id)
    row = db.execute(
        select(ToolPermission, ToolRegistry)
        .join(ToolRegistry, ToolPermission.tool_id == ToolRegistry.id)
        .where(
            ToolPermission.rental_id == rental_id,
            ToolPermission.tool_id == tool_id,
            ToolPermission.tenant_id == principal.tenant_id,
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool permission not found for this rental")

    perm, tool = row
    perm.is_allowed = payload.is_allowed
    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        rental_id=rental_id,
        action="tool.permission_updated",
        resource_type="tool_permission",
        resource_id=str(perm.id),
        ip_address=principal.ip_address,
        metadata={"tool_slug": tool.slug, "is_allowed": payload.is_allowed},
    )
    db.flush()
    resp = ToolPermissionResponse(
        id=perm.id,
        tool_id=tool.id,
        tool_slug=tool.slug,
        tool_name=tool.name,
        mcp_server_slug=tool.mcp_server_slug,
        execution_mode=tool.execution_mode,
        requires_hitl=tool.requires_hitl,
        is_allowed=perm.is_allowed,
        credential_status=perm.credential_status,
        masked_secret_ref=perm.masked_secret_ref,
    )
    db.commit()
    return resp


@router.post("/{rental_id}/tools/{tool_id}/credentials", response_model=ToolPermissionResponse)
def bind_encrypted_tool_credential(
    rental_id: uuid.UUID,
    tool_id: uuid.UUID,
    payload: ToolCredentialBindRequest,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> ToolPermissionResponse:
    _get_tenant_rental(db, principal.tenant_id, rental_id)
    row = db.execute(
        select(ToolPermission, ToolRegistry)
        .join(ToolRegistry, ToolPermission.tool_id == ToolRegistry.id)
        .where(
            ToolPermission.rental_id == rental_id,
            ToolPermission.tool_id == tool_id,
            ToolPermission.tenant_id == principal.tenant_id,
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool permission not found for this rental")

    perm, tool = row
    secret_plain = payload.api_key_or_token.strip()
    perm.encrypted_secret = encrypt_secret(secret_plain)
    perm.credential_status = "bound_encrypted"
    perm.masked_secret_ref = mask_secret(secret_plain, principal.tenant_id, tool.slug)

    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        rental_id=rental_id,
        action="tool.credential_bound",
        resource_type="tool_permission",
        resource_id=str(perm.id),
        ip_address=principal.ip_address,
        metadata={"tool_slug": tool.slug, "masked_ref": perm.masked_secret_ref},
    )
    db.flush()
    resp = ToolPermissionResponse(
        id=perm.id,
        tool_id=tool.id,
        tool_slug=tool.slug,
        tool_name=tool.name,
        mcp_server_slug=tool.mcp_server_slug,
        execution_mode=tool.execution_mode,
        requires_hitl=tool.requires_hitl,
        is_allowed=perm.is_allowed,
        credential_status=perm.credential_status,
        masked_secret_ref=perm.masked_secret_ref,
    )
    db.commit()
    return resp


@router.get("/{rental_id}/knowledge", response_model=list[KnowledgeDocumentResponse])
def list_knowledge_documents(
    rental_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> list[KnowledgeDocumentResponse]:
    _get_tenant_rental(db, principal.tenant_id, rental_id)
    docs = db.scalars(
        select(KnowledgeDocument)
        .where(KnowledgeDocument.rental_id == rental_id, KnowledgeDocument.tenant_id == principal.tenant_id)
        .order_by(KnowledgeDocument.created_at.desc())
    ).all()
    caller_lvl = ROLE_LEVEL.get(principal.role, 1)
    visible = [d for d in docs if ROLE_LEVEL.get(d.min_role_access, 1) <= caller_lvl]
    return [
        KnowledgeDocumentResponse(
            id=d.id,
            rental_id=d.rental_id,
            title=d.title,
            original_filename=d.original_filename,
            source_type=d.source_type,
            mime_type=d.mime_type,
            file_size_bytes=d.file_size_bytes,
            sha256_checksum=d.sha256_checksum,
            chunk_count=d.chunk_count,
            min_role_access=d.min_role_access,
            status=d.status,
            created_at=d.created_at,
        )
        for d in visible
    ]


@router.post("/{rental_id}/knowledge", response_model=KnowledgeDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_knowledge_document(
    rental_id: uuid.UUID,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    source_type: str = Form(default="handbook"),
    min_role_access: str = Form(default="business_employee"),
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> KnowledgeDocumentResponse:
    _get_tenant_rental(db, principal.tenant_id, rental_id)
    if min_role_access not in ROLE_LEVEL:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid min_role_access")

    doc_id = uuid.uuid4()
    rel_path, checksum, size_bytes, safe_name = await save_tenant_upload(
        tenant_id=principal.tenant_id,
        rental_id=rental_id,
        doc_id=doc_id,
        upload=file,
    )

    doc = KnowledgeDocument(
        id=doc_id,
        tenant_id=principal.tenant_id,
        rental_id=rental_id,
        uploaded_by_user_id=principal.user_id,
        title=(title or safe_name).strip()[:255],
        original_filename=safe_name,
        source_type=source_type[:40],
        mime_type=(file.content_type or "application/octet-stream")[:120],
        file_size_bytes=size_bytes,
        storage_rel_path=rel_path,
        sha256_checksum=checksum,
        chunk_count=max(1, size_bytes // 1024),
        min_role_access=min_role_access,
        status="indexed",
    )
    db.add(doc)
    db.flush()

    saved_path = resolve_tenant_file(principal.tenant_id, rel_path)
    raw_blob = saved_path.read_bytes()
    extracted_text = extract_document_text(
        raw_blob,
        filename=safe_name,
        mime_type=file.content_type or "",
    )
    import re as _re

    if len(_re.findall(r"[A-Za-z0-9]", extracted_text or "")) < 8:
        if saved_path.exists():
            saved_path.unlink(missing_ok=True)
        db.delete(doc)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded document or resume is empty, corrupted, or contains no readable text.",
        )

    from ...runtime.document_security import inspect_document_bytes

    sec_check = inspect_document_bytes(
        raw_blob,
        filename=safe_name,
        mime_type=file.content_type or "",
        extracted_text=extracted_text,
        allow_indirect_text_neutralization=False,
    )
    if not sec_check.is_safe_for_upload:
        if saved_path.exists():
            saved_path.unlink(missing_ok=True)
        db.delete(doc)
        record_audit(
            db,
            tenant_id=principal.tenant_id,
            actor_user_id=principal.user_id,
            rental_id=rental_id,
            action="security.malicious_document_blocked",
            resource_type="knowledge_document",
            resource_id=str(doc_id),
            ip_address=principal.ip_address,
            status="blocked",
            metadata={"filename": safe_name, "threats": sec_check.threats_detected},
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=sec_check.blocked_reason)

    index_document_chunks(db, doc=doc, text_content=extracted_text)

    cfg = db.scalars(
        select(AgentConfiguration).where(
            AgentConfiguration.rental_id == rental_id,
            AgentConfiguration.tenant_id == principal.tenant_id,
        )
    ).first()
    if cfg is not None:
        cfg.kb_version_hash = "kb_" + hashlib.sha256(f"{cfg.kb_version_hash}:{checksum}".encode()).hexdigest()[:10]

    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        rental_id=rental_id,
        action="knowledge.document_uploaded",
        resource_type="knowledge_document",
        resource_id=str(doc.id),
        ip_address=principal.ip_address,
        metadata={"filename": safe_name, "size_bytes": size_bytes, "sha256": checksum},
    )
    db.flush()
    resp = KnowledgeDocumentResponse(
        id=doc.id,
        rental_id=doc.rental_id,
        title=doc.title,
        original_filename=doc.original_filename,
        source_type=doc.source_type,
        mime_type=doc.mime_type,
        file_size_bytes=doc.file_size_bytes,
        sha256_checksum=doc.sha256_checksum,
        chunk_count=doc.chunk_count,
        min_role_access=doc.min_role_access,
        status=doc.status,
        created_at=doc.created_at,
    )
    db.commit()
    return resp


@router.get("/{rental_id}/knowledge/{doc_id}/download")
def download_knowledge_document(
    rental_id: uuid.UUID,
    doc_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> FileResponse:
    _get_tenant_rental(db, principal.tenant_id, rental_id)
    doc = db.scalars(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.rental_id == rental_id,
            KnowledgeDocument.tenant_id == principal.tenant_id,
        )
    ).first()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge document not found")

    if ROLE_LEVEL.get(principal.role, 1) < ROLE_LEVEL.get(doc.min_role_access, 1):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role privilege to access this document",
        )

    target = resolve_tenant_file(principal.tenant_id, doc.storage_rel_path)
    if not target.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document file blob not found on storage")

    return FileResponse(path=str(target), filename=doc.original_filename, media_type=doc.mime_type)


@router.delete("/{rental_id}/knowledge/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_document(
    rental_id: uuid.UUID,
    doc_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> None:
    _get_tenant_rental(db, principal.tenant_id, rental_id)
    doc = db.scalars(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.rental_id == rental_id,
            KnowledgeDocument.tenant_id == principal.tenant_id,
        )
    ).first()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge document not found")

    try:
        blob = resolve_tenant_file(principal.tenant_id, doc.storage_rel_path)
        if blob.exists():
            blob.unlink()
    except HTTPException:
        pass

    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        rental_id=rental_id,
        action="knowledge.document_deleted",
        resource_type="knowledge_document",
        resource_id=str(doc.id),
        ip_address=principal.ip_address,
        metadata={"filename": doc.original_filename},
    )
    db.delete(doc)
    db.commit()
