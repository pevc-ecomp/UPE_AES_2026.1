import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from agents.evaluation_core import (
    DEFAULT_SYSTEM_PROMPT,
    _extract_json,
    run_revision_evaluation,
    run_two_step_evaluation,
)
from core.config import get_settings
from schemas.evaluation import EvaluationRequest, EvaluationResponse, EvaluationRevisionRequest

logger = logging.getLogger(__name__)

SEED_VERSION_NAME = "v3.0 - Triagem em Duas Etapas (Título + Abstract)"

__all__ = [
    "DEFAULT_SYSTEM_PROMPT",
    "SEED_VERSION_NAME",
    "evaluate_article",
    "revise_article_evaluation",
]


async def _invoke_llm(system_prompt: str, human_content: str, agent_version) -> dict:
    settings = get_settings()
    last_error: Exception | None = None
    for model in [agent_version.model_primary, agent_version.model_fallback]:
        try:
            llm = ChatOllama(
                base_url=settings.ollama_host,
                model=model,
                temperature=agent_version.temperature,
                format="json",
            )
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_content),
            ]
            response = await llm.ainvoke(messages)
            return _extract_json(response.content)
        except Exception as exc:
            logger.warning("Model %s failed: %s", model, exc)
            last_error = exc

    raise RuntimeError(
        f"All LLM models failed to evaluate the article. Last error: {last_error}"
    )


async def evaluate_article(request: EvaluationRequest, agent_version) -> EvaluationResponse:
    """Two-step evaluation (title screening, then title+abstract+keywords) via Ollama."""
    return await run_two_step_evaluation(request, agent_version, _invoke_llm)


async def revise_article_evaluation(
    request: EvaluationRevisionRequest, agent_version
) -> EvaluationResponse:
    """Re-evaluate an article via Ollama, taking AI Judge feedback into account."""
    return await run_revision_evaluation(request, agent_version, _invoke_llm)
