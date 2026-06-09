from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AgentVersionCreate(BaseModel):
    version_name: str = Field(..., min_length=1, max_length=200)
    version_description: str = ""
    system_prompt: str = Field(..., min_length=1)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    model_primary: str = "phi3:mini"
    model_fallback: str = "llama3.2:1b"
    author: str = Field(..., min_length=1, max_length=200)


class AgentVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    version_name: str
    version_description: str
    system_prompt: str
    temperature: float
    model_primary: str
    model_fallback: str
    author: str
    created_at: datetime


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    initial_version: AgentVersionCreate


class AgentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None


class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    active_version_id: Optional[str]
    active_version: Optional[AgentVersionRead]
    versions: list[AgentVersionRead]
    created_at: datetime
    updated_at: datetime
