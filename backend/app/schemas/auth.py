from datetime import datetime
import uuid
from pydantic import BaseModel, EmailStr, Field


class BusinessRegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    organization_name: str = Field(min_length=2, max_length=150)
    industry: str = Field(default="SaaS & Tech", max_length=80)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    organization_slug: str | None = None


class AuthenticatedUserResponse(BaseModel):
    user_id: uuid.UUID
    email: EmailStr
    full_name: str
    tenant_id: uuid.UUID
    organization_name: str
    organization_slug: str
    role: str
    is_platform_admin: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: AuthenticatedUserResponse


class LogoutResponse(BaseModel):
    status: str = "logged_out"
    revoked_jti: str
