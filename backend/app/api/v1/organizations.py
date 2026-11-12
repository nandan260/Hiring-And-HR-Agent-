import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.dependencies import (
    AuthenticatedPrincipal,
    get_current_principal,
    get_tenant_db,
    require_roles,
)
from ...core.security import hash_password
from ...db.models import Organization, OrganizationMember, User
from ...schemas.organization import (
    InviteMemberRequest,
    OrganizationMemberResponse,
    OrganizationResponse,
    UpdateMemberRoleRequest,
)
from ...services.audit import record_audit

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.get("/current", response_model=OrganizationResponse)
def get_current_organization(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> OrganizationResponse:
    org = db.get(Organization, principal.tenant_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        industry=org.industry,
        status=org.status,
        created_at=org.created_at,
    )


@router.get("/members", response_model=list[OrganizationMemberResponse])
def list_organization_members(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> list[OrganizationMemberResponse]:
    rows = db.execute(
        select(OrganizationMember, User)
        .join(User, OrganizationMember.user_id == User.id)
        .where(OrganizationMember.tenant_id == principal.tenant_id)
        .order_by(OrganizationMember.created_at.asc())
    ).all()

    return [
        OrganizationMemberResponse(
            member_id=member.id,
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=member.role,
            is_active=member.is_active,
            created_at=member.created_at,
        )
        for member, user in rows
    ]


@router.post("/members", response_model=OrganizationMemberResponse, status_code=status.HTTP_201_CREATED)
def invite_organization_member(
    payload: InviteMemberRequest,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> OrganizationMemberResponse:
    if payload.role == "business_owner" and principal.role not in {"business_owner", "platform_admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a Business Owner or Platform Admin can assign the business_owner role",
        )

    email = payload.email.strip().lower()
    if db.scalars(select(User).where(User.email == email)).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        is_platform_admin=False,
        is_active=True,
    )
    db.add(user)
    db.flush()

    member = OrganizationMember(
        tenant_id=principal.tenant_id,
        user_id=user.id,
        role=payload.role,
        is_active=True,
    )
    db.add(member)
    db.flush()

    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action="organization.member_invited",
        resource_type="organization_member",
        resource_id=str(member.id),
        ip_address=principal.ip_address,
        metadata={"invited_email": email, "assigned_role": payload.role},
    )

    resp = OrganizationMemberResponse(
        member_id=member.id,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=member.role,
        is_active=member.is_active,
        created_at=member.created_at,
    )
    db.commit()
    return resp


@router.patch("/members/{member_id}/role", response_model=OrganizationMemberResponse)
def update_member_role(
    member_id: uuid.UUID,
    payload: UpdateMemberRoleRequest,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> OrganizationMemberResponse:
    row = db.execute(
        select(OrganizationMember, User)
        .join(User, OrganizationMember.user_id == User.id)
        .where(
            OrganizationMember.id == member_id,
            OrganizationMember.tenant_id == principal.tenant_id,
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization member not found")

    member, user = row
    if payload.role == "business_owner" and principal.role not in {"business_owner", "platform_admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a Business Owner or Platform Admin can assign the business_owner role",
        )
    if member.user_id == principal.user_id and not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own active membership",
        )

    member.role = payload.role
    member.is_active = payload.is_active
    db.flush()

    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action="organization.member_updated",
        resource_type="organization_member",
        resource_id=str(member.id),
        ip_address=principal.ip_address,
        metadata={"role": payload.role, "is_active": payload.is_active},
    )

    resp = OrganizationMemberResponse(
        member_id=member.id,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=member.role,
        is_active=member.is_active,
        created_at=member.created_at,
    )
    db.commit()
    return resp
