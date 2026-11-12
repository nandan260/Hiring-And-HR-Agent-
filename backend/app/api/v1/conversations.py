import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.registry import agent_registry
from ...core.dependencies import (
    AuthenticatedPrincipal,
    get_current_principal,
    get_tenant_db,
)
from ...db.models import (
    AgentCatalog,
    AgentConversation,
    AgentRental,
    Message,
)
from ...schemas.conversation import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationResponse,
    MessageCreateRequest,
    MessageResponse,
    MessageTurnResponse,
)
from ...services.audit import record_audit

router = APIRouter(tags=["Conversations"])


def _to_msg_resp(msg: Message) -> MessageResponse:
    return MessageResponse(
        id=msg.id,
        conversation_id=msg.conversation_id,
        role=msg.role,
        content=msg.content,
        classifier_result=msg.classifier_result,
        metadata_json=dict(msg.metadata_json or {}),
        created_at=msg.created_at,
    )


def _get_tenant_rental(db: Session, tenant_id: uuid.UUID, rental_id: uuid.UUID) -> AgentRental:
    rental = db.scalars(
        select(AgentRental).where(AgentRental.id == rental_id, AgentRental.tenant_id == tenant_id)
    ).first()
    if rental is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rented agent not found for this tenant")
    return rental


@router.get("/rentals/{rental_id}/conversations", response_model=list[ConversationResponse])
def list_rental_conversations(
    rental_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> list[ConversationResponse]:
    _get_tenant_rental(db, principal.tenant_id, rental_id)
    rows = db.scalars(
        select(AgentConversation)
        .where(
            AgentConversation.rental_id == rental_id,
            AgentConversation.tenant_id == principal.tenant_id,
        )
        .order_by(AgentConversation.updated_at.desc())
    ).all()
    return [
        ConversationResponse(
            id=c.id,
            tenant_id=c.tenant_id,
            rental_id=c.rental_id,
            user_id=c.user_id,
            title=c.title,
            status=c.status,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in rows
    ]


@router.post(
    "/rentals/{rental_id}/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_rental_conversation(
    rental_id: uuid.UUID,
    payload: ConversationCreateRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> ConversationResponse:
    rental = _get_tenant_rental(db, principal.tenant_id, rental_id)
    if rental.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot open a conversation on a cancelled agent rental",
        )

    conv = AgentConversation(
        tenant_id=principal.tenant_id,
        rental_id=rental.id,
        user_id=principal.user_id,
        title=payload.title.strip(),
        status="active",
        summary_memory="",
    )
    db.add(conv)
    db.flush()

    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        rental_id=rental.id,
        action="conversation.created",
        resource_type="agent_conversation",
        resource_id=str(conv.id),
        ip_address=principal.ip_address,
        metadata={"title": conv.title},
    )
    db.flush()
    resp = ConversationResponse(
        id=conv.id,
        tenant_id=conv.tenant_id,
        rental_id=conv.rental_id,
        user_id=conv.user_id,
        title=conv.title,
        status=conv.status,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )
    db.commit()
    return resp


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation_detail(
    conversation_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> ConversationDetailResponse:
    conv = db.scalars(
        select(AgentConversation).where(
            AgentConversation.id == conversation_id,
            AgentConversation.tenant_id == principal.tenant_id,
        )
    ).first()
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    msgs = db.scalars(
        select(Message)
        .where(
            Message.conversation_id == conv.id,
            Message.tenant_id == principal.tenant_id,
        )
        .order_by(Message.created_at.asc())
    ).all()

    return ConversationDetailResponse(
        id=conv.id,
        tenant_id=conv.tenant_id,
        rental_id=conv.rental_id,
        user_id=conv.user_id,
        title=conv.title,
        status=conv.status,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[_to_msg_resp(m) for m in msgs],
    )


@router.post("/conversations/{conversation_id}/messages", response_model=MessageTurnResponse, status_code=status.HTTP_201_CREATED)
def post_conversation_message(
    conversation_id: uuid.UUID,
    payload: MessageCreateRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> MessageTurnResponse:
    conv = db.scalars(
        select(AgentConversation).where(
            AgentConversation.id == conversation_id,
            AgentConversation.tenant_id == principal.tenant_id,
        )
    ).first()
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    rental = _get_tenant_rental(db, principal.tenant_id, conv.rental_id)
    if rental.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agent rental is currently '{rental.status}'. Activate or resume the rental to send messages.",
        )

    agent_row = db.get(AgentCatalog, rental.agent_id)
    agent_slug = agent_row.slug if agent_row else "recruitment-screening"

    prior_rows = db.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id, Message.tenant_id == principal.tenant_id)
        .order_by(Message.created_at.asc())
    ).all()
    history = [
        {
            "role": m.role,
            "content": m.content,
            "workflow_slug": str((m.metadata_json or {}).get("workflow_slug") or (m.metadata_json or {}).get("agent_id") or ""),
        }
        for m in prior_rows
    ]

    state = agent_registry.execute(
        agent_slug=agent_slug,
        db=db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        actor_role=principal.role,
        user_input=payload.content.strip(),
        rental_id=rental.id,
        conversation_id=conv.id,
        structured_input=getattr(payload, "structured_input", None),
        attachments=getattr(payload, "attachments", None),
        conversation_history=history,
        persist_telemetry=True,
    )

    classifier_res = state.get("classifier_result", "in_domain")
    if classifier_res == "blocked_permission":
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=state.get("rejection_reason") or "Access denied for your current workspace role.",
        )
    if classifier_res == "blocked_quota":
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=state.get("rejection_reason") or "Monthly token quota exceeded for this workspace.",
        )
    exec_status = state.get("execution_status", "completed")
    assistant_role = "assistant" if classifier_res == "in_domain" else "system_guardrail"

    user_msg = Message(
        tenant_id=principal.tenant_id,
        conversation_id=conv.id,
        role="user",
        content=payload.content.strip(),
        classifier_result=classifier_res,
        metadata_json={"actor_role": principal.role},
    )
    db.add(user_msg)
    db.flush()

    assistant_msg = Message(
        tenant_id=principal.tenant_id,
        conversation_id=conv.id,
        role=assistant_role,
        content=state.get("final_response_text", ""),
        classifier_result=classifier_res,
        metadata_json={
            "is_foundation_stub": False,
            "agent_id": state.get("selected_agent_id", agent_slug),
            "agent_version": state.get("selected_agent_version", "1.0.0"),
            "provider_used": state.get("llm_provider_used", "deterministic"),
            "model_used": state.get("model_used", "deterministic"),
            "citations": state.get("citations", []),
            "charts": state.get("charts", []),
            "hitl_requests": state.get("hitl_requests", []),
            "structured_output": state.get("validated_output", {}),
            "trace_steps": state.get("trace_steps", []),
            "suggested_category": state.get("suggested_category"),
            "latency_ms": state.get("latency_ms", 0),
        },
    )
    db.add(assistant_msg)
    if state.get("conversation_summary"):
        conv.summary_memory = str(state["conversation_summary"])
    db.flush()

    exec_log_id_str = state.get("execution_log_id")
    exec_log_uuid = uuid.UUID(exec_log_id_str) if exec_log_id_str else uuid.uuid4()

    resp = MessageTurnResponse(
        user_message=_to_msg_resp(user_msg),
        assistant_message=_to_msg_resp(assistant_msg),
        execution_log_id=exec_log_uuid,
        classifier_result=classifier_res,
        status=exec_status,
    )
    db.commit()
    return resp
