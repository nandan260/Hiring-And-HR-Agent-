from dataclasses import dataclass
from typing import Callable, Generator
import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Organization, OrganizationMember, RevokedToken, User
from ..db.session import apply_tenant_rls, get_session_factory
from .security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)

VALID_ROLES = {
    "platform_admin",
    "business_owner",
    "business_admin",
    "business_employee",
}


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str
    email: str
    full_name: str
    organization_name: str
    organization_slug: str
    is_platform_admin: bool
    jti: str
    token_exp_ts: int
    ip_address: str | None


def _extract_token(
    credentials: HTTPAuthorizationCredentials | None,
) -> str:
    if not credentials or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Bearer access token",
        )
    return credentials.credentials


def get_current_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedPrincipal:
    """
    Authenticate JWT access token and strictly bind tenant_id & role from verified claims
    and active organization membership. Never trusts frontend-supplied tenant_id headers or body fields.
    """
    token = _extract_token(credentials)
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(str(payload["sub"]))
        tenant_id = uuid.UUID(str(payload["tenant_id"]))
        jti = str(payload["jti"])
        exp_ts = int(payload["exp"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        ) from exc

    SessionFactory = get_session_factory()
    db = SessionFactory()
    try:
        # 1. Enforce Logout / Token Revocation
        revoked = db.get(RevokedToken, jti)
        if revoked is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been logged out / revoked",
            )

        # 2. Verify active User
        user = db.get(User, user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account inactive or not found",
            )

        # 3. Verify active Organization & Membership inside RLS context
        org = db.get(Organization, tenant_id)
        if not org or org.status != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization is inactive or missing",
            )

        apply_tenant_rls(db, tenant_id)
        member = db.scalars(
            select(OrganizationMember).where(
                OrganizationMember.tenant_id == tenant_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.is_active.is_(True),
            )
        ).first()
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not an active member of this organization tenant",
            )

        effective_role = "platform_admin" if user.is_platform_admin else member.role
        client_ip = request.client.host if request.client else None

        return AuthenticatedPrincipal(
            user_id=user.id,
            tenant_id=org.id,
            role=effective_role,
            email=user.email,
            full_name=user.full_name,
            organization_name=org.name,
            organization_slug=org.slug,
            is_platform_admin=user.is_platform_admin,
            jti=jti,
            token_exp_ts=exp_ts,
            ip_address=client_ip,
        )
    finally:
        db.close()


def get_tenant_db(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> Generator[Session, None, None]:
    """
    Provides a SQLAlchemy Session bound to the authenticated tenant via PostgreSQL RLS:
    SET LOCAL ROLE rent_agent_app + SET LOCAL app.current_tenant = <principal.tenant_id>.
    """
    SessionFactory = get_session_factory()
    db = SessionFactory()
    try:
        apply_tenant_rls(db, principal.tenant_id)
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def require_roles(*allowed_roles: str) -> Callable[[AuthenticatedPrincipal], AuthenticatedPrincipal]:
    def dependency(
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> AuthenticatedPrincipal:
        if principal.role not in allowed_roles and not principal.is_platform_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{principal.role}' lacks permission. Required: {', '.join(allowed_roles)}",
            )
        return principal

    return dependency
