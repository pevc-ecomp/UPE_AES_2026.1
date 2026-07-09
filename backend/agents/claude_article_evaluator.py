import logging

from anthropic import AsyncAnthropic

from agents.evaluation_core import (
    DEFAULT_SYSTEM_PROMPT,
    _extract_json,
    run_revision_evaluation,
    run_two_step_evaluation,
)
from core.config import get_settings
from schemas.evaluation import EvaluationRequest, EvaluationResponse, EvaluationRevisionRequest

logger = logging.getLogger(__name__)

SEED_VERSION_NAME = "v3.0 - Triagem em Duas Etapas (Claude API)"

MAX_RESPONSE_TOKENS = 2048

__all__ = [
    "DEFAULT_SYSTEM_PROMPT",
    "SEED_VERSION_NAME",
    "evaluate_article",
    "revise_article_evaluation",
]

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    return _client


async def _invoke_llm(system_prompt: str, human_content: str, agent_version) -> dict:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured.")

    client = _get_client()
    # Anthropic accepts temperature in [0, 1]; agent versions may have been
    # authored with the wider [0, 2] range used by Ollama-backed agents.
    temperature = max(0.0, min(1.0, agent_version.temperature))

    last_error: Exception | None = None
    for model in [agent_version.model_primary, agent_version.model_fallback]:
        if not model:
            continue
        try:
            response = await client.messages.create(
                model=model,
                system=system_prompt,
                messages=[{"role": "user", "content": human_content}],
                temperature=temperature,
                max_tokens=MAX_RESPONSE_TOKENS,
            )
            text = "".join(
                block.text for block in response.content if block.type == "text"
            )
            return _extract_json(text)
        except Exception as exc:
            logger.warning("Model %s failed: %s", model, exc)
            last_error = exc

    raise RuntimeError(
        f"All LLM models failed to evaluate the article. Last error: {last_error}"
    )


async def evaluate_article(request: EvaluationRequest, agent_version) -> EvaluationResponse:
    """Two-step evaluation (title screening, then title+abstract+keywords) via the Claude API."""
    return await run_two_step_evaluation(request, agent_version, _invoke_llm)


async def revise_article_evaluation(
    request: EvaluationRevisionRequest, agent_version
) -> EvaluationResponse:
    """Re-evaluate an article via the Claude API, taking AI Judge feedback into account."""
    return await run_revision_evaluation(request, agent_version, _invoke_llm)
