from datetime import datetime
from typing import Literal
import uuid
from pydantic import BaseModel, EmailStr, Field

MemberRoleLiteral = Literal[
    "business_owner",
    "business_admin",
    "business_employee",
]


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    industry: str
    status: str
    created_at: datetime


class OrganizationMemberResponse(BaseModel):
    member_id: uuid.UUID
    user_id: uuid.UUID
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class InviteMemberRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: MemberRoleLiteral = "business_employee"


class UpdateMemberRoleRequest(BaseModel):
    role: MemberRoleLiteral
    is_active: bool = True
