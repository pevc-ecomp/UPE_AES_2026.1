from fastapi import APIRouter, HTTPException

from agents.article_evaluator import evaluate_article
from schemas.evaluation import AgentInfo, EvaluationRequest, EvaluationResponse

router = APIRouter()

_AGENTS: list[AgentInfo] = [
    AgentInfo(
        name="article-evaluator",
        description=(
            "Avalia a relevância de um artigo científico para uma pesquisa. "
            "Recebe título, abstract e palavras-chave do artigo e uma sinopse "
            "opcional da pesquisa. Retorna um score de 0–100, um veredicto "
            "(NOT-RELATED / UNSURE / RELATED) e a justificativa."
        ),
        endpoint="/agents/evaluate-article",
        active=True,
    ),
]


@router.get("", response_model=list[AgentInfo])
async def list_agents():
    return _AGENTS


@router.post("/evaluate-article", response_model=EvaluationResponse)
async def evaluate_article_endpoint(request: EvaluationRequest):
    try:
        return await evaluate_article(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
