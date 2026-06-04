from enum import Enum

from pydantic import BaseModel, Field


class EvaluationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=1000)
    abstract: str = Field(..., min_length=1, max_length=10000)
    keywords: list[str] = Field(..., min_length=1)
    research_synopsis: str | None = Field(default=None, max_length=5000)


class Verdict(str, Enum):
    NOT_RELATED = "NOT-RELATED"
    UNSURE = "UNSURE"
    RELATED = "RELATED"


class EvaluationResponse(BaseModel):
    score: int = Field(..., ge=0, le=100)
    verdict: Verdict
    reason: str
    article_name: str


class AgentInfo(BaseModel):
    name: str
    description: str
    endpoint: str
    active: bool
