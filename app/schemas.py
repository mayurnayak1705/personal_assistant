from typing import Any, Optional
from pydantic import BaseModel, Field

from app.features.profile.store import DEFAULT_USER_ID


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None   # frontend generates & persists this per tab; server generates one if absent
    user_id: Optional[str] = DEFAULT_USER_ID


class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    success: bool = True
    artifact: Optional[dict[str, Any]] = None
    suggestion: Optional[dict[str, str]] = None


class EndSessionRequest(BaseModel):
    conversation_id: str
    user_id: Optional[str] = DEFAULT_USER_ID


class EndSessionResponse(BaseModel):
    success: bool
    messages_saved: int


class ReminderAcknowledgeRequest(BaseModel):
    user_id: str = DEFAULT_USER_ID
    conversation_id: Optional[str] = None


class TaskActionRequest(BaseModel):
    user_id: str = DEFAULT_USER_ID
    conversation_id: Optional[str] = None


class WhatsAppToggleRequest(BaseModel):
    enabled: bool


class GmailActionRequest(BaseModel):
    user_id: str = DEFAULT_USER_ID
    conversation_id: Optional[str] = None


class ExpenseImportActionRequest(BaseModel):
    action: str
    category: Optional[str] = None
    user_id: str = DEFAULT_USER_ID
    conversation_id: Optional[str] = None


class GoogleOAuthConfigRequest(BaseModel):
    user_id: str = DEFAULT_USER_ID
    client_config: dict[str, Any]


class UserProfileUpdateRequest(BaseModel):
    user_id: str = DEFAULT_USER_ID
    display_name: str = Field(min_length=1, max_length=120)

class WellnessProfileRequest(BaseModel):
    user_id: str = DEFAULT_USER_ID
    data: dict[str, Any]

class WellnessLogRequest(BaseModel):
    user_id: str = DEFAULT_USER_ID
    kind: str
    data: dict[str, Any] = Field(default_factory=dict)
    notes: str = ""
    log_date: Optional[str] = None
