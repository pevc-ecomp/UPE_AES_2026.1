import pytest

from scopus_agent import (
    DEFAULT_SYSTEM_PROMPT,
    OPTIMIZE_PROMPT,
    _extract_json,
    _fill_missing_strings,
    _is_placeholder,
    _language_instruction,
    _normalise,
    _normalize_models,
)


# ── _extract_json ─────────────────────────────────────────────────────────────

def test_extract_json_com_cerca_markdown():
    raw = '```json\n{"string_core": "TITLE-ABS-KEY(x)"}\n```'
    assert _extract_json(raw) == {"string_core": "TITLE-ABS-KEY(x)"}


def test_extract_json_com_texto_ao_redor():
    raw = 'Claro! Aqui está: {"a": 1} espero ter ajudado'
    assert _extract_json(raw) == {"a": 1}


def test_extract_json_repara_json_malformado():
    raw = '{"a": 1,}'  # vírgula sobrando — json_repair deve consertar
    assert _extract_json(raw) == {"a": 1}


def test_extract_json_sem_json_gera_erro():
    with pytest.raises(ValueError):
        _extract_json("resposta sem nenhum objeto")


# ── _normalise / _fill_missing_strings ────────────────────────────────────────

def test_normalise_lista_com_um_dict_vira_dict():
    data = _normalise([{"string_core": "TITLE-ABS-KEY(x)"}])
    assert data["string_core"] == "TITLE-ABS-KEY(x)"


def test_normalise_coage_lista_para_string():
    data = _normalise({"string_core": ["TITLE-ABS-KEY(x)"], "recommended_string": "expanded"})
    assert data["string_core"] == "TITLE-ABS-KEY(x)"


def test_fill_missing_constroi_core_a_partir_de_keywords():
    data = {
        "keywords_extracted": ["machine learning", "saúde"],
        "string_core": "",
        "string_expanded": "",
        "string_full": "",
    }
    _fill_missing_strings(data)
    assert data["string_core"] == 'TITLE-ABS-KEY("machine learning" AND "saúde")'
    assert data["string_full"].endswith("AND PUBYEAR > 2015")


def test_fill_missing_expande_com_sinonimos():
    data = {
        "keywords_extracted": ["ml"],
        "synonyms_added": [{"term": "ml", "synonyms": ["machine learning"]}],
        "string_core": 'TITLE-ABS-KEY("ml")',
        "string_expanded": "",
        "string_full": "",
    }
    _fill_missing_strings(data)
    assert data["string_expanded"] == 'TITLE-ABS-KEY(("ml" OR "machine learning"))'


def test_placeholder_do_exemplo_e_descartado():
    assert _is_placeholder("TITLE-ABS-KEY(main concept AND secondary concept)")
    assert _is_placeholder("...")
    assert not _is_placeholder('TITLE-ABS-KEY("grafos")')


def test_recommended_string_invalida_vira_expanded():
    data = {"recommended_string": "qualquer coisa"}
    _fill_missing_strings(data)
    assert data["recommended_string"] == "expanded"


# ── idioma e regras do prompt ─────────────────────────────────────────────────

def test_instrucao_de_idioma_padrao_mantem_idioma():
    text = _language_instruction(False)
    assert "SAME language" in text


def test_instrucao_de_idioma_traduz_para_ingles():
    text = _language_instruction(True)
    assert "ENGLISH" in text


def test_prompts_nao_pedem_autores_de_referencia():
    for prompt in (DEFAULT_SYSTEM_PROMPT, OPTIMIZE_PROMPT):
        assert "reference_authors" not in prompt
        assert "Author Identification" not in prompt


def test_prompts_proibem_filtros_de_autor():
    assert "NEVER include author" in DEFAULT_SYSTEM_PROMPT


# ── _normalize_models ─────────────────────────────────────────────────────────

def test_normalize_models_string_vira_lista():
    assert _normalize_models("phi3:mini") == ["phi3:mini"]
    assert _normalize_models(["a", "b"]) == ["a", "b"]
