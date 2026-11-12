from datetime import datetime, timezone
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.dependencies import AuthenticatedPrincipal, get_current_principal
from ...core.security import create_access_token, hash_password, verify_password
from ...db.models import Organization, OrganizationMember, RevokedToken, User
from ...db.session import get_db
from ...schemas.auth import (
    AuthenticatedUserResponse,
    BusinessRegisterRequest,
    LoginRequest,
    LogoutResponse,
    TokenResponse,
)
from ...services.audit import record_audit

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:70] or f"org-{uuid.uuid4().hex[:6]}"


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_business(
    payload: BusinessRegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    email = payload.email.strip().lower()
    existing_user = db.scalars(select(User).where(User.email == email)).first()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    base_slug = _slugify(payload.organization_name)
    slug = base_slug
    if db.scalars(select(Organization).where(Organization.slug == slug)).first() is not None:
        slug = f"{base_slug[:60]}-{uuid.uuid4().hex[:6]}"

    org = Organization(
        name=payload.organization_name.strip(),
        slug=slug,
        industry=payload.industry.strip() or "SaaS & Tech",
        status="active",
    )
    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        is_platform_admin=False,
        is_active=True,
    )
    db.add(org)
    db.add(user)
    db.flush()

    member = OrganizationMember(
        tenant_id=org.id,
        user_id=user.id,
        role="business_owner",
        is_active=True,
    )
    db.add(member)

    client_ip = request.client.host if request.client else None
    record_audit(
        db,
        tenant_id=org.id,
        actor_user_id=user.id,
        action="auth.business_registered",
        resource_type="organization",
        resource_id=str(org.id),
        ip_address=client_ip,
        metadata={"organization_slug": org.slug, "role": "business_owner"},
    )
    db.commit()

    token, _jti, expires_at = create_access_token(
        user_id=user.id,
        tenant_id=org.id,
        role="business_owner",
        email=user.email,
    )
    return TokenResponse(
        access_token=token,
        expires_at=expires_at,
        user=AuthenticatedUserResponse(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            tenant_id=org.id,
            organization_name=org.name,
            organization_slug=org.slug,
            role="business_owner",
            is_platform_admin=False,
        ),
    )


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    email = payload.email.strip().lower()
    user = db.scalars(select(User).where(User.email == email)).first()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    stmt = (
        select(OrganizationMember, Organization)
        .join(Organization, OrganizationMember.tenant_id == Organization.id)
        .where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.is_active.is_(True),
            Organization.status == "active",
        )
        .order_by(OrganizationMember.created_at.asc())
    )
    if payload.organization_slug:
        stmt = stmt.where(Organization.slug == payload.organization_slug.strip().lower())

    row = db.execute(stmt).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active organization membership found for this user",
        )

    member, org = row
    effective_role = "platform_admin" if user.is_platform_admin else member.role
    client_ip = request.client.host if request.client else None

    record_audit(
        db,
        tenant_id=org.id,
        actor_user_id=user.id,
        action="auth.login",
        resource_type="user",
        resource_id=str(user.id),
        ip_address=client_ip,
        metadata={"role": effective_role, "organization_slug": org.slug},
    )
    db.commit()

    token, _jti, expires_at = create_access_token(
        user_id=user.id,
        tenant_id=org.id,
        role=effective_role,
        email=user.email,
    )
    return TokenResponse(
        access_token=token,
        expires_at=expires_at,
        user=AuthenticatedUserResponse(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            tenant_id=org.id,
            organization_name=org.name,
            organization_slug=org.slug,
            role=effective_role,
            is_platform_admin=user.is_platform_admin,
        ),
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> LogoutResponse:
    existing = db.get(RevokedToken, principal.jti)
    if existing is None:
        db.add(
            RevokedToken(
                jti=principal.jti,
                user_id=principal.user_id,
                expires_at=datetime.fromtimestamp(principal.token_exp_ts, tz=timezone.utc),
            )
        )
    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action="auth.logout",
        resource_type="token",
        resource_id=principal.jti,
        ip_address=principal.ip_address,
    )
    db.commit()
    return LogoutResponse(revoked_jti=principal.jti)


@router.get("/me", response_model=AuthenticatedUserResponse)
def get_me(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> AuthenticatedUserResponse:
    return AuthenticatedUserResponse(
        user_id=principal.user_id,
        email=principal.email,
        full_name=principal.full_name,
        tenant_id=principal.tenant_id,
        organization_name=principal.organization_name,
        organization_slug=principal.organization_slug,
        role=principal.role,
        is_platform_admin=principal.is_platform_admin,
    )
