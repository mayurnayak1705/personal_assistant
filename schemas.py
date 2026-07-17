from typing import Any, Optional
from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None   # frontend generates & persists this per tab; server generates one if absent
    user_id: Optional[str] = "mayur"        # single-user assistant for now


class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    success: bool = True
    artifact: Optional[dict[str, Any]] = None
    suggestion: Optional[dict[str, str]] = None


class EndSessionRequest(BaseModel):
    conversation_id: str
    user_id: Optional[str] = "mayur"


class EndSessionResponse(BaseModel):
    success: bool
    messages_saved: int


class ReminderAcknowledgeRequest(BaseModel):
    user_id: str = "mayur"
    conversation_id: Optional[str] = None


class TaskActionRequest(BaseModel):
    user_id: str = "mayur"
    conversation_id: Optional[str] = None


class WhatsAppToggleRequest(BaseModel):
    enabled: bool


class GmailActionRequest(BaseModel):
    user_id: str = "mayur"
    conversation_id: Optional[str] = None


class ExpenseImportActionRequest(BaseModel):
    action: str
    category: Optional[str] = None
    user_id: str = "mayur"
    conversation_id: Optional[str] = None


class GoogleOAuthConfigRequest(BaseModel):
    user_id: str = "mayur"
    client_config: dict[str, Any]
