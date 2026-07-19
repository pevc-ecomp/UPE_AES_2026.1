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
    year: Optional[int] = Field(default=None, ge=1500, le=2100)
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


class BatchArticleInput(BaseModel):
    title: str = ""
    abstract: str = ""
    keywords: list[str] = []
    year: Optional[int] = None


class BatchEvaluationRequest(BaseModel):
    articles: list[BatchArticleInput] = Field(..., min_length=1)
    research_protocol: ResearchProtocol
    agent_id: Optional[str] = None


class BatchArticleResult(BaseModel):
    index: int
    title: str
    abstract: str = ""
    keywords: list[str] = []
    year: Optional[int] = None
    evaluation: Optional[EvaluationResponse] = None
    error: Optional[str] = None


class BatchJobStatus(BaseModel):
    job_id: str
    phase: str  # screening | evaluating | completed | failed
    created_at: str = ""
    total_articles: int = 0
    message: str = ""
    results: list[BatchArticleResult] = []


class JudgeFeedback(BaseModel):
    judge_verdict: str
    confidence_score: float = Field(..., ge=0, le=5)
    judge_justification: str = ""
    human_review_recommended: bool = True


class EvaluationRevisionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=1000)
    abstract: str = Field(..., min_length=1, max_length=10000)
    keywords: list[str] = Field(..., min_length=1)
    year: Optional[int] = Field(default=None, ge=1500, le=2100)
    research_protocol: ResearchProtocol
    original_evaluation: EvaluationResponse
    judge_feedback: JudgeFeedback
    agent_id: Optional[str] = None
