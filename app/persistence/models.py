from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class MemoryRecord(BaseModel):
    user_id: str = Field(description="Unique user identifier")
    memory_type: str = Field(description="Type of memory (architecture, preference, project, workflow, etc.)")
    title: str = Field(description="Short title of the memory")
    importance: int = Field(default=5, ge=1, le=10, description="Importance score from 1 to 10")
    source: str = Field(description="Source of the memory, e.g. conversation, document")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatHistoryRecord(BaseModel):
    conversation_id: str = Field(description="Conversation identifier")
    user_id: str = Field(description="Unique user identifier")
    role: str = Field(description="user, assistant or system")
    token_count: int = Field(description="Number of tokens in the raw message")


class TaskRecord(BaseModel):
    user_id: str
    project_id: Optional[str] = None
    title: str
    priority: str = Field(description="low, medium, high")
    status: str = Field(description="pending, in_progress, completed")
    due_date: Optional[str] = None


class ReminderRecord(BaseModel):
    user_id: str
    title: str
    reminder_time: str = Field(description="ISO datetime")
    recurrence: Optional[str] = None
    status: str = Field(default="pending")


class UserFactRecord(BaseModel):
    user_id: str
    fact_key: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: str
