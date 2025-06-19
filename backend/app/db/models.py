from sqlmodel import SQLModel, Field
from typing import Optional
import datetime
from uuid import uuid4

class Session(SQLModel, table=True):
    session_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, nullable=False)
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    title: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="session.session_id")
    role: str
    content: str
    timestamp_ms: int
    tool_calls_json: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

class UserStats(SQLModel, table=True):
    id: int = Field(default=1, primary_key=True)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    deleted_prompt_tokens: int = 0
    deleted_completion_tokens: int = 0
    deleted_total_tokens: int = 0
