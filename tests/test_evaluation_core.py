import pytest

from agents.evaluation_core import (
    _as_list,
    _build_human_message,
    _build_title_screening_message,
    _derive_verdict,
    _extract_json,
    _normalize_evaluation,
)
from schemas.evaluation import EvaluationRequest, ResearchProtocol, Verdict


def _request(**overrides) -> EvaluationRequest:
    base = {
        "title": "Um artigo sobre grafos",
        "abstract": "Estudo de algoritmos em grafos aplicados a redes.",
        "keywords": ["grafos", "algoritmos"],
        "research_protocol": ResearchProtocol(
            description="Pesquisa sobre algoritmos em grafos",
            exclusion_criteria=["Artigos sem revisão por pares"],
            inclusion_criteria=["Aplicação em redes"],
        ),
    }
    base.update(overrides)
    return EvaluationRequest(**base)


# ── _derive_verdict ───────────────────────────────────────────────────────────

def test_limiares_do_veredito():
    assert _derive_verdict(80) is Verdict.RELATED
    assert _derive_verdict(79) is Verdict.UNSURE
    assert _derive_verdict(50) is Verdict.UNSURE
    assert _derive_verdict(49) is Verdict.NOT_RELATED


# ── _extract_json / _as_list ──────────────────────────────────────────────────

def test_extract_json_remove_cerca_markdown():
    assert _extract_json('```json\n{"score": 90}\n```') == {"score": 90}


def test_extract_json_sem_objeto_gera_erro():
    with pytest.raises(ValueError):
        _extract_json("sem json aqui")


def test_as_list_normaliza_valores():
    assert _as_list(["a"]) == ["a"]
    assert _as_list("a") == ["a"]
    assert _as_list(None) == []
    assert _as_list("") == []


# ── _normalize_evaluation ─────────────────────────────────────────────────────

def test_score_invalido_vira_zero():
    result = _normalize_evaluation({"score": "alto"}, "T")
    assert result.score == 0
    assert result.verdict is Verdict.NOT_RELATED
    assert result.reason  # nunca vazio


def test_score_e_limitado_a_100():
    assert _normalize_evaluation({"score": 250}, "T").score == 100


def test_exclusao_zera_o_score_mesmo_com_score_alto():
    result = _normalize_evaluation(
        {"score": 95, "exclusion_triggered": ["Sem revisão por pares"]}, "T"
    )
    assert result.score == 0
    assert result.excluded_by_criterion is True
    assert result.verdict is Verdict.NOT_RELATED
    assert "Sem revisão por pares" in result.reason


def test_titulo_de_fallback_e_usado():
    assert _normalize_evaluation({"score": 60}, "Título X").article_name == "Título X"


# ── construção de mensagens ───────────────────────────────────────────────────

def test_mensagem_completa_inclui_ano_quando_informado():
    msg = _build_human_message(_request(year=2021))
    assert "**Ano de publicação:** 2021" in msg
    assert "## PROTOCOLO DE PESQUISA" in msg
    assert "Critérios de Inclusão" in msg


def test_mensagem_completa_omite_ano_quando_ausente():
    assert "Ano de publicação" not in _build_human_message(_request())


def test_triagem_por_titulo_nao_expoe_abstract_nem_inclusao():
    msg = _build_title_screening_message(_request(year=2020))
    assert "Abstract" not in msg
    assert "Critérios de Inclusão" not in msg
    assert "**Ano de publicação:** 2020" in msg
