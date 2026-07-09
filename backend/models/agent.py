from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class Agent(SQLModel, table=True):
    __tablename__ = "agent"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(unique=True, index=True)
    description: str = Field(default="", sa_column=Column("description", Text))
    agent_type: str = Field(default="general", index=True)
    active_version_id: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AgentVersion(SQLModel, table=True):
    __tablename__ = "agent_version"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    agent_id: str = Field(foreign_key="agent.id", index=True)
    version_name: str
    version_description: str = Field(default="", sa_column=Column("version_description", Text))
    system_prompt: str = Field(sa_column=Column("system_prompt", Text))
    temperature: float = 0.1
    provider: str = Field(default="ollama", index=True)
    model_primary: str = "phi3:mini"
    model_fallback: str = "llama3.2:1b"
    author: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
