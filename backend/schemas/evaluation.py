from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ResearchProtocol(BaseModel):
    description: str = Field(..., min_length=1, max_length=5000)
    general_objectives: str = ""
    specific_objectives: str = ""
    exclusion_criteria: list[str] = []
    inclusion_criteria: list[str] = []
    inclusion_logic: str = "ANY"


class EvaluationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=1000)
    abstract: str = Field(..., min_length=1, max_length=10000)
    keywords: list[str] = Field(..., min_length=1)
    research_protocol: ResearchProtocol
    agent_id: Optional[str] = None


class Verdict(str, Enum):
    NOT_RELATED = "NOT-RELATED"
    UNSURE = "UNSURE"
    RELATED = "RELATED"


class EvaluationResponse(BaseModel):
    score: int = Field(..., ge=0, le=100)
    verdict: Verdict
    reason: str
    article_name: str
    excluded_by_criterion: bool = False
    exclusion_triggered: list[str] = []
    inclusion_criteria_met: list[str] = []
