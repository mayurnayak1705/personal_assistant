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


class EndSessionRequest(BaseModel):
    conversation_id: str
    user_id: Optional[str] = "mayur"


class EndSessionResponse(BaseModel):
    success: bool
    messages_saved: int


class ReminderAcknowledgeRequest(BaseModel):
    user_id: str = "mayur"
