"""Avaliação de artigos em lote via a Batch API da Anthropic (50% de desconto).

O processamento acontece nos servidores da Anthropic — o container NÃO precisa
ficar ligado enquanto o batch executa. O estado do job (ids dos batches,
artigos, resultados parciais) é persistido em /app/data/batch_jobs/, e os
resultados ficam disponíveis na Anthropic por 29 dias, então o retrieve pode
ser feito a qualquer momento depois, mesmo após reiniciar os containers.

Fluxo em duas fases, espelhando a avaliação individual:
  fase 1 "screening"  — triagem por título (modelo barato de screening/Haiku)
  fase 2 "evaluating" — pente fino (título+abstract+keywords) só dos aprovados
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from anthropic import Anthropic

from agents.claude_article_evaluator import (
    MAX_RESPONSE_TOKENS,
    build_cached_message_content,
    pick_models,
)
from agents.evaluation_core import (
    TITLE_SCREENING_SYSTEM_PROMPT,
    _as_list,
    _build_human_message,
    _build_title_screening_message,
    _extract_json,
    _normalize_evaluation,
)
from core.config import get_settings
from schemas.evaluation import (
    BatchArticleResult,
    BatchEvaluationRequest,
    BatchJobStatus,
    EvaluationRequest,
    EvaluationResponse,
    ResearchProtocol,
    Verdict,
)

logger = logging.getLogger(__name__)

JOBS_DIR = Path("/app/data/batch_jobs")

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=get_settings().anthropic_api_key)
    return _client


def _job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def _save_job(job: dict) -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    _job_path(job["job_id"]).write_text(
        json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _load_job(job_id: str) -> dict | None:
    path = _job_path(job_id)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _build_request(article: dict, protocol: ResearchProtocol) -> EvaluationRequest:
    return EvaluationRequest(
        title=article["title"],
        abstract=article["abstract"],
        keywords=article["keywords"],
        year=article.get("year"),
        research_protocol=protocol,
    )


def _batch_params(model: str, system_prompt: str, human_content: str, temperature: float) -> dict:
    return {
        "model": model,
        "max_tokens": MAX_RESPONSE_TOKENS,
        "temperature": temperature,
        "system": system_prompt,
        "messages": [{"role": "user", "content": build_cached_message_content(human_content)}],
    }


def _screening_rejection(data: dict, title: str) -> EvaluationResponse | None:
    """Mirror of the step-1 rejection logic in evaluation_core._screen_by_title."""
    if not bool(data.get("reject", False)):
        return None
    exclusion_triggered = _as_list(data.get("exclusion_triggered"))
    reason = str(data.get("reason", "")).strip()
    if not reason:
        reason = (
            "Artigo rejeitado na triagem inicial por título "
            + (f"por violar: {'; '.join(exclusion_triggered)}." if exclusion_triggered
               else "por não guardar relação com o tema da pesquisa.")
        )
    return EvaluationResponse(
        score=0,
        verdict=Verdict.NOT_RELATED,
        reason=reason,
        article_name=title,
        excluded_by_criterion=bool(exclusion_triggered),
        exclusion_triggered=exclusion_triggered,
        inclusion_criteria_met=[],
    )


def _message_text(message) -> str:
    return "".join(block.text for block in message.content if block.type == "text")


def _collect_batch_results(batch_id: str) -> dict[int, dict]:
    """Map article index -> {"data": parsed_json} | {"error": str} for a finished batch."""
    out: dict[int, dict] = {}
    for result in _get_client().messages.batches.results(batch_id):
        idx = int(result.custom_id.split("-")[1])
        if result.result.type == "succeeded":
            try:
                out[idx] = {"data": _extract_json(_message_text(result.result.message))}
            except Exception as exc:
                out[idx] = {"error": f"Resposta do modelo não pôde ser interpretada: {exc}"}
        elif result.result.type == "errored":
            out[idx] = {"error": str(result.result.error)}
        else:
            out[idx] = {"error": f"Requisição {result.result.type} no batch."}
    return out


def start_batch_evaluation(request: BatchEvaluationRequest, agent_version) -> BatchJobStatus:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured.")

    temperature = max(0.0, min(1.0, agent_version.temperature))
    screening_model = pick_models(TITLE_SCREENING_SYSTEM_PROMPT, agent_version)[0]

    articles = []
    results: dict[str, dict] = {}
    batch_requests = []
    for i, art in enumerate(request.articles):
        article = {
            "title": art.title.strip(),
            "abstract": art.abstract.strip(),
            "keywords": [k for k in art.keywords if k.strip()],
            "year": art.year,
        }
        articles.append(article)
        try:
            eval_request = _build_request(article, request.research_protocol)
        except Exception:
            results[str(i)] = {
                "error": "Dados incompletos (título, abstract e palavras-chave são obrigatórios)."
            }
            continue
        batch_requests.append(
            {
                "custom_id": f"art-{i}",
                "params": _batch_params(
                    screening_model,
                    TITLE_SCREENING_SYSTEM_PROMPT,
                    _build_title_screening_message(eval_request),
                    temperature,
                ),
            }
        )

    if not batch_requests:
        raise RuntimeError("Nenhum artigo válido para enviar ao batch.")

    batch = _get_client().messages.batches.create(requests=batch_requests)

    job = {
        "job_id": f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "phase": "screening",
        "screening_batch_id": batch.id,
        "evaluation_batch_id": None,
        "agent": {
            "system_prompt": agent_version.system_prompt,
            "temperature": temperature,
            "model_primary": agent_version.model_primary,
            "screening_model": screening_model,
        },
        "research_protocol": request.research_protocol.model_dump(),
        "articles": articles,
        "results": results,
    }
    _save_job(job)
    return _job_to_status(job, message="Batch de triagem enviado à Anthropic.")


def get_batch_status(job_id: str) -> BatchJobStatus | None:
    job = _load_job(job_id)
    if job is None:
        return None

    if job["phase"] in ("completed", "failed"):
        return _job_to_status(job)

    settings = get_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured.")

    if job["phase"] == "screening":
        batch = _get_client().messages.batches.retrieve(job["screening_batch_id"])
        if batch.processing_status != "ended":
            return _job_to_status(
                job,
                message=(
                    f"Triagem por título em processamento na Anthropic "
                    f"({batch.request_counts.processing} pendente(s), "
                    f"{batch.request_counts.succeeded} concluída(s))."
                ),
            )
        _advance_from_screening(job)
        _save_job(job)

    if job["phase"] == "evaluating":
        batch = _get_client().messages.batches.retrieve(job["evaluation_batch_id"])
        if batch.processing_status != "ended":
            return _job_to_status(
                job,
                message=(
                    f"Avaliação completa (pente fino) em processamento na Anthropic "
                    f"({batch.request_counts.processing} pendente(s), "
                    f"{batch.request_counts.succeeded} concluída(s))."
                ),
            )
        _finish_from_evaluation(job)
        _save_job(job)

    return _job_to_status(job)


def _advance_from_screening(job: dict) -> None:
    protocol = ResearchProtocol(**job["research_protocol"])
    temperature = job["agent"]["temperature"]
    survivors = []

    for idx, outcome in _collect_batch_results(job["screening_batch_id"]).items():
        title = job["articles"][idx]["title"]
        if "error" in outcome:
            job["results"][str(idx)] = {"error": outcome["error"]}
            continue
        rejection = _screening_rejection(outcome["data"], title)
        if rejection is not None:
            job["results"][str(idx)] = {"evaluation": rejection.model_dump()}
        else:
            survivors.append(idx)

    if not survivors:
        job["phase"] = "completed"
        return

    batch_requests = [
        {
            "custom_id": f"art-{idx}",
            "params": _batch_params(
                job["agent"]["model_primary"],
                job["agent"]["system_prompt"],
                _build_human_message(_build_request(job["articles"][idx], protocol)),
                temperature,
            ),
        }
        for idx in survivors
    ]
    batch = _get_client().messages.batches.create(requests=batch_requests)
    job["evaluation_batch_id"] = batch.id
    job["phase"] = "evaluating"


def _finish_from_evaluation(job: dict) -> None:
    for idx, outcome in _collect_batch_results(job["evaluation_batch_id"]).items():
        title = job["articles"][idx]["title"]
        if "error" in outcome:
            job["results"][str(idx)] = {"error": outcome["error"]}
        else:
            evaluation = _normalize_evaluation(outcome["data"], title)
            job["results"][str(idx)] = {"evaluation": evaluation.model_dump()}
    job["phase"] = "completed"


def _job_to_status(job: dict, message: str = "") -> BatchJobStatus:
    results = []
    if job["phase"] == "completed":
        for i, article in enumerate(job["articles"]):
            stored = job["results"].get(str(i), {})
            results.append(
                BatchArticleResult(
                    index=i,
                    title=article["title"],
                    abstract=article["abstract"],
                    keywords=article["keywords"],
                    year=article.get("year"),
                    evaluation=(
                        EvaluationResponse(**stored["evaluation"])
                        if "evaluation" in stored else None
                    ),
                    error=stored.get("error"),
                )
            )
        if not message:
            message = "Avaliação em lote concluída."
    return BatchJobStatus(
        job_id=job["job_id"],
        phase=job["phase"],
        created_at=job["created_at"],
        total_articles=len(job["articles"]),
        message=message,
        results=results,
    )


def list_batch_jobs() -> list[BatchJobStatus]:
    if not JOBS_DIR.exists():
        return []
    jobs = []
    for path in sorted(JOBS_DIR.glob("*.json"), reverse=True):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
            jobs.append(
                BatchJobStatus(
                    job_id=job["job_id"],
                    phase=job["phase"],
                    created_at=job["created_at"],
                    total_articles=len(job["articles"]),
                )
            )
        except Exception as exc:
            logger.warning("Job de batch ilegível (%s): %s", path, exc)
    return jobs
