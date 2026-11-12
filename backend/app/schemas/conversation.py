from datetime import datetime
from typing import Any
import uuid
from pydantic import BaseModel, Field


class ConversationCreateRequest(BaseModel):
    title: str = Field(default="HR Workspace Session", min_length=1, max_length=200)


class MessageCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    structured_input: dict[str, Any] | None = None
    attachments: list[str] | None = None


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    classifier_result: str | None
    metadata_json: dict
    created_at: datetime


class ConversationResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    rental_id: uuid.UUID
    user_id: uuid.UUID | None
    title: str
    status: str
    created_at: datetime
    updated_at: datetime


class ConversationDetailResponse(ConversationResponse):
    messages: list[MessageResponse]


class MessageTurnResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse
    execution_log_id: uuid.UUID
    classifier_result: str
    status: str
