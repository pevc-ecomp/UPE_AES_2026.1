import os

import httpx


IA_JUDGE_URL = os.getenv("IA_JUDGE_URL", "http://localhost:8002")


def get_ai_judge_status() -> tuple[bool, str]:
    try:
        response = httpx.get(IA_JUDGE_URL, timeout=5)
        response.raise_for_status()
        payload = response.json()
        return True, payload.get("message", "AI Judge online")
    except Exception as exc:
        return False, str(exc)


def judge_search_string(topic: str, search_string: str, database: str = "Scopus") -> dict:
    payload = {
        "topic": topic.strip(),
        "search_string": search_string.strip(),
        "database": database.strip() or "Scopus",
    }

    try:
        response = httpx.post(
            f"{IA_JUDGE_URL}/judge/string",
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        try:
            detail = exc.response.json()
        except Exception:
            pass
        raise RuntimeError(f"AI Judge retornou erro: {detail}") from exc
    except Exception as exc:
        raise RuntimeError(f"Falha ao conectar com o AI Judge: {exc}") from exc


def judge_article_classifications(
    review_objective: str,
    articles: list[dict],
    inclusion_criteria: str = "",
    exclusion_criteria: str = "",
    protocol_description: str = "",
    general_objectives: str = "",
    specific_objectives: str = "",
    inclusion_logic: str = "",
) -> dict:
    payload = {
        "review_objective": review_objective.strip(),
        "inclusion_criteria": inclusion_criteria.strip(),
        "exclusion_criteria": exclusion_criteria.strip(),
        "protocol_description": protocol_description.strip(),
        "general_objectives": general_objectives.strip(),
        "specific_objectives": specific_objectives.strip(),
        "inclusion_logic": inclusion_logic.strip(),
        "articles": articles,
    }

    try:
        response = httpx.post(
            f"{IA_JUDGE_URL}/judge/articles",
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        try:
            detail = exc.response.json()
        except Exception:
            pass
        raise RuntimeError(f"AI Judge retornou erro: {detail}") from exc
    except Exception as exc:
        raise RuntimeError(f"Falha ao conectar com o AI Judge: {exc}") from exc


def revise_article_classifications(
    review_objective: str,
    articles: list[dict],
    inclusion_criteria: str = "",
    exclusion_criteria: str = "",
    protocol_description: str = "",
    general_objectives: str = "",
    specific_objectives: str = "",
    inclusion_logic: str = "",
) -> dict:
    payload = {
        "review_objective": review_objective.strip(),
        "inclusion_criteria": inclusion_criteria.strip(),
        "exclusion_criteria": exclusion_criteria.strip(),
        "protocol_description": protocol_description.strip(),
        "general_objectives": general_objectives.strip(),
        "specific_objectives": specific_objectives.strip(),
        "inclusion_logic": inclusion_logic.strip(),
        "articles": articles,
    }

    try:
        response = httpx.post(
            f"{IA_JUDGE_URL}/judge/articles/revise",
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        try:
            detail = exc.response.json()
        except Exception:
            pass
        raise RuntimeError(f"AI Judge retornou erro: {detail}") from exc
    except Exception as exc:
        raise RuntimeError(f"Falha ao conectar com o AI Judge: {exc}") from exc
