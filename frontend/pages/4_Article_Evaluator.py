import json
import os
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st

from ai_judge_client import (
    get_ai_judge_status,
    judge_article_classifications,
)

st.set_page_config(
    page_title="Avaliador de Artigos",
    page_icon="📋",
    layout="wide",
)

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
PRESETS_FILE = Path("/app/data/article_presets.json")

CSV_EXPORT_SEP = ";;"


def _to_delimited_csv(df: pd.DataFrame, sep: str = CSV_EXPORT_SEP) -> bytes:
    """Serialize a DataFrame with a two-character delimiter instead of pandas'
    default single-character separator. Justification/reason columns are free
    text that may contain commas or semicolons, so a single-char delimiter
    risks false-positive column splits; every field is also quoted so the
    delimiter itself can never be mistaken for one inside a value."""
    def _escape(value) -> str:
        text = "" if pd.isna(value) else str(value)
        return '"' + text.replace('"', '""') + '"'

    lines = [sep.join(_escape(c) for c in df.columns)]
    for row in df.itertuples(index=False, name=None):
        lines.append(sep.join(_escape(v) for v in row))
    return ("\r\n".join(lines)).encode("utf-8")


def _read_uploaded_csv(uploaded) -> pd.DataFrame:
    """Read an uploaded CSV trying to auto-detect its separator/encoding.
    Real-world exports (Scopus, WoS, Excel "CSV UTF-8", our own ';;'-delimited
    export) use a variety of delimiters — hardcoding ',' broke on any file
    that used ';' or a multi-char separator, since commas inside abstract
    text get misread as extra column boundaries."""
    attempts = [
        {"sep": None, "engine": "python"},  # auto-sniff (comma, semicolon, tab, ...)
        {"sep": CSV_EXPORT_SEP, "engine": "python"},
        {"sep": ";"},
        {"sep": ","},
        {"sep": "\t"},
    ]
    last_error: Exception | None = None
    for encoding in ("utf-8", "latin-1"):
        for kwargs in attempts:
            uploaded.seek(0)
            try:
                df = pd.read_csv(uploaded, encoding=encoding, **kwargs)
            except Exception as exc:
                last_error = exc
                continue
            if len(df.columns) > 1:
                return df
            last_error = ValueError(
                "Apenas uma coluna foi detectada — o separador do arquivo provavelmente "
                "não pôde ser identificado automaticamente."
            )
    raise last_error


def _load_presets() -> dict:
    try:
        if PRESETS_FILE.exists():
            return json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_presets(presets: dict) -> None:
    PRESETS_FILE.write_text(
        json.dumps(presets, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── Session state ─────────────────────────────────────────────────────────────
if "evaluation_history" not in st.session_state:
    st.session_state.evaluation_history = []
if "csv_results" not in st.session_state:
    st.session_state.csv_results = []
if "presets" not in st.session_state:
    st.session_state.presets = _load_presets()
if "manual_article_context" not in st.session_state:
    st.session_state.manual_article_context = None
if "manual_protocol_context" not in st.session_state:
    st.session_state.manual_protocol_context = None
if "manual_judge_result" not in st.session_state:
    st.session_state.manual_judge_result = None
if "manual_revision_result" not in st.session_state:
    st.session_state.manual_revision_result = None
if "csv_judge_summary" not in st.session_state:
    st.session_state.csv_judge_summary = None

for _key, _default in [
    ("ev_title", ""),
    ("ev_abstract", ""),
    ("ev_keywords_raw", ""),
    ("ev_protocol_description", ""),
    ("ev_general_objectives", ""),
    ("ev_specific_objectives", ""),
    ("ev_inclusion_logic", "ANY"),
]:
    if _key not in st.session_state:
        st.session_state[_key] = _default

for _list_key in ["ev_exclusion_criteria", "ev_inclusion_criteria"]:
    if _list_key not in st.session_state:
        st.session_state[_list_key] = []


# ── Dynamic criteria list helpers ─────────────────────────────────────────────

def _sync_list_from_widgets(state_key: str) -> None:
    """Sync widget values back into the session state list (no widget clearing)."""
    items = st.session_state.get(state_key, [])
    result = [
        st.session_state.get(f"{state_key}_{i}", items[i])
        for i in range(len(items))
    ]
    st.session_state[state_key] = result


def _clear_list_widgets(state_key: str, count: int) -> None:
    """Remove indexed widget keys so they reinitialize from value= on next render."""
    for i in range(count):
        st.session_state.pop(f"{state_key}_{i}", None)


def _get_current_criteria(state_key: str) -> list[str]:
    """Read criteria from live widget values, falling back to session state list."""
    items = st.session_state.get(state_key, [])
    return [
        st.session_state.get(f"{state_key}_{i}", items[i])
        for i in range(len(items))
    ]


def _render_criteria_list(
    state_key: str,
    item_label: str,
    add_label: str,
    placeholder: str = "",
) -> None:
    items = st.session_state.get(state_key, [])
    n = len(items)
    to_remove = None

    for i, item in enumerate(items):
        col_txt, col_btn = st.columns([12, 1])
        with col_txt:
            st.text_input(
                f"{item_label} {i + 1}",
                value=item,
                key=f"{state_key}_{i}",
                placeholder=placeholder,
            )
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("✕", key=f"rm_{state_key}_{i}", help="Remover"):
                to_remove = i

    if to_remove is not None:
        _sync_list_from_widgets(state_key)
        _clear_list_widgets(state_key, n)
        st.session_state[state_key].pop(to_remove)
        st.rerun()

    if st.button(f"+ {add_label}", key=f"add_{state_key}"):
        _sync_list_from_widgets(state_key)
        _clear_list_widgets(state_key, n)
        st.session_state[state_key].append("")
        st.rerun()


# ── Research protocol helpers ─────────────────────────────────────────────────

def _build_protocol_payload() -> dict:
    _sync_list_from_widgets("ev_exclusion_criteria")
    _sync_list_from_widgets("ev_inclusion_criteria")
    exclusion_criteria = [c.strip() for c in st.session_state.ev_exclusion_criteria if c.strip()]
    inclusion_criteria = [c.strip() for c in st.session_state.ev_inclusion_criteria if c.strip()]
    inclusion_logic = st.session_state.get("ev_inclusion_logic", "ANY").strip() or "ANY"
    return {
        "description": st.session_state.ev_protocol_description.strip(),
        "general_objectives": st.session_state.get("ev_general_objectives", "").strip(),
        "specific_objectives": st.session_state.get("ev_specific_objectives", "").strip(),
        "exclusion_criteria": exclusion_criteria,
        "inclusion_criteria": inclusion_criteria,
        "inclusion_logic": inclusion_logic,
    }


def _protocol_errors(backend_ok: bool) -> list[str]:
    errors = []
    if not st.session_state.ev_protocol_description.strip():
        errors.append("A descrição da pesquisa (Protocolo) é obrigatória.")
    if not backend_ok:
        errors.append("O backend está offline. Verifique os containers.")
    return errors


def _format_error_detail(exc: httpx.HTTPStatusError) -> str:
    try:
        detail = exc.response.json().get("detail", exc.response.text or str(exc))
    except Exception:
        detail = exc.response.text or str(exc)
    if isinstance(detail, list):
        # FastAPI/pydantic validation errors: list of {"loc", "msg", ...} dicts
        detail = "; ".join(
            f"{'.'.join(str(p) for p in d.get('loc', []))}: {d.get('msg', d)}"
            if isinstance(d, dict) else str(d)
            for d in detail
        )
    return str(detail)


def _call_evaluate(payload: dict) -> dict | None:
    try:
        resp = httpx.post(
            f"{BACKEND_URL}/agents/evaluate-article",
            json=payload,
            timeout=300,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        st.error(f"Erro do backend: {_format_error_detail(exc)}")
        return None
    except Exception as exc:
        st.error(f"Erro de conexão: {exc}")
        return None


def _call_evaluate_revision(payload: dict) -> dict | None:
    try:
        resp = httpx.post(
            f"{BACKEND_URL}/agents/evaluate-article/revise",
            json=payload,
            timeout=300,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        st.error(f"Erro do backend: {_format_error_detail(exc)}")
        return None
    except Exception as exc:
        st.error(f"Erro de conexão: {exc}")
        return None


def _criteria_to_multiline(criteria: list[str]) -> str:
    return "\n".join(item.strip() for item in criteria if item.strip())


def _build_manual_judge_article(article_context: dict, model_result: dict, judge_article: dict | None = None) -> dict:
    payload = {
        "title": article_context["title"],
        "abstract": article_context["abstract"],
        "keywords": article_context["keywords"],
        "model_classification": model_result["verdict"],
        "model_score": model_result["score"],
        "model_justification": model_result["reason"],
        "excluded_by_criterion": model_result.get("excluded_by_criterion", False),
        "exclusion_triggered": model_result.get("exclusion_triggered", []),
        "inclusion_criteria_met": model_result.get("inclusion_criteria_met", []),
    }
    if judge_article:
        payload["judge_verdict"] = judge_article.get("judge_verdict")
        payload["judge_justification"] = judge_article.get("judge_justification")
        payload["human_review_recommended"] = judge_article.get("human_review_recommended")
    return payload


def _build_manual_judge_request(protocol_context: dict, article_payload: dict) -> dict:
    return {
        "review_objective": protocol_context.get("description", ""),
        "protocol_description": protocol_context.get("description", ""),
        "general_objectives": protocol_context.get("general_objectives", ""),
        "specific_objectives": protocol_context.get("specific_objectives", ""),
        "inclusion_criteria": _criteria_to_multiline(protocol_context.get("inclusion_criteria", [])),
        "exclusion_criteria": _criteria_to_multiline(protocol_context.get("exclusion_criteria", [])),
        "inclusion_logic": protocol_context.get("inclusion_logic", "ANY"),
        "articles": [article_payload],
    }


def _build_evaluation_revision_payload(
    article_context: dict,
    protocol_context: dict,
    original_evaluation: dict,
    judge_article: dict,
    agent_id: str | None,
) -> dict:
    return {
        "title": article_context["title"],
        "abstract": article_context["abstract"],
        "keywords": article_context["keywords"],
        "research_protocol": protocol_context,
        "original_evaluation": {
            "score": original_evaluation.get("score", 0),
            "verdict": original_evaluation.get("verdict", "UNSURE"),
            "reason": original_evaluation.get("reason", ""),
            "article_name": original_evaluation.get("article_name", article_context["title"]),
            "excluded_by_criterion": original_evaluation.get("excluded_by_criterion", False),
            "exclusion_triggered": original_evaluation.get("exclusion_triggered", []),
            "inclusion_criteria_met": original_evaluation.get("inclusion_criteria_met", []),
        },
        "judge_feedback": {
            "judge_verdict": judge_article.get("judge_verdict", "UNCERTAIN"),
            "confidence_score": judge_article.get("confidence_score", 0),
            "judge_justification": judge_article.get("judge_justification", ""),
            "human_review_recommended": judge_article.get("human_review_recommended", True),
        },
        "agent_id": agent_id,
    }


def _evaluation_result_to_revision_view(result: dict, original_verdict: str) -> dict:
    return {
        "title": result.get("article_name", ""),
        "original_classification": original_verdict,
        "revised_classification": result.get("verdict", "UNSURE"),
        "revised_score": result.get("score", 0),
        "revised_justification": result.get("reason", ""),
        "revised_excluded_by_criterion": result.get("excluded_by_criterion", False),
        "revised_exclusion_triggered": result.get("exclusion_triggered", []),
        "revised_inclusion_criteria_met": result.get("inclusion_criteria_met", []),
        "changes_summary": "Classification_v2 gerada pelo próprio Article Evaluator com base no feedback do AI Judge.",
        "human_review_recommended": True,
    }


def _revision_to_evaluation_result(revision_article: dict) -> dict:
    return {
        "score": revision_article.get("revised_score", 0),
        "verdict": revision_article.get("revised_classification", "UNSURE"),
        "reason": revision_article.get("revised_justification", ""),
        "article_name": revision_article.get("title", ""),
        "excluded_by_criterion": revision_article.get("revised_excluded_by_criterion", False),
        "exclusion_triggered": revision_article.get("revised_exclusion_triggered", []),
        "inclusion_criteria_met": revision_article.get("revised_inclusion_criteria_met", []),
    }


def _build_csv_judge_article(result_row: dict, judge_article: dict | None = None) -> dict:
    article_payload = {
        "title": result_row.get("_article_title") or result_row.get("article_name", ""),
        "abstract": result_row.get("_article_abstract", ""),
        "keywords": result_row.get("_article_keywords", []),
        "model_classification": result_row.get("verdict", "UNSURE"),
        "model_score": result_row.get("score", 0),
        "model_justification": result_row.get("reason", ""),
        "excluded_by_criterion": result_row.get("excluded_by_criterion", False),
        "exclusion_triggered": result_row.get("_exclusion_triggered_raw")
        or result_row.get("exclusion_triggered")
        or [],
        "inclusion_criteria_met": result_row.get("_inclusion_criteria_met_raw")
        or result_row.get("inclusion_criteria_met")
        or [],
    }
    if judge_article:
        article_payload["judge_verdict"] = judge_article.get("judge_verdict")
        article_payload["judge_justification"] = judge_article.get("judge_justification")
        article_payload["human_review_recommended"] = judge_article.get("human_review_recommended")
    return article_payload


def _build_protocol_judge_request(protocol_context: dict, articles: list[dict]) -> dict:
    return {
        "review_objective": protocol_context.get("description", ""),
        "protocol_description": protocol_context.get("description", ""),
        "general_objectives": protocol_context.get("general_objectives", ""),
        "specific_objectives": protocol_context.get("specific_objectives", ""),
        "inclusion_criteria": _criteria_to_multiline(protocol_context.get("inclusion_criteria", [])),
        "exclusion_criteria": _criteria_to_multiline(protocol_context.get("exclusion_criteria", [])),
        "inclusion_logic": protocol_context.get("inclusion_logic", "ANY"),
        "articles": articles,
    }


def _apply_csv_judge_and_revision(
    results: list[dict],
    protocol_context: dict,
    agent_id: str | None,
) -> tuple[list[dict], dict]:
    enriched_results = []
    judge_stats = {
        "correct": 0,
        "uncertain": 0,
        "incorrect": 0,
        "revised": 0,
        "errors": 0,
    }

    for row in results:
        try:
            article_payload = _build_csv_judge_article(row)
            judge_request = _build_protocol_judge_request(protocol_context, [article_payload])
            judge_result = judge_article_classifications(**judge_request)
            judge_article = (judge_result.get("articles") or [{}])[0]
        except Exception as exc:
            # Isolate per-row failures (e.g. AI Judge timeout on one article) so a
            # single bad row doesn't discard every row already judged in this batch.
            judge_stats["errors"] += 1
            enriched_row = dict(row)
            enriched_row["judge_overall_result"] = f"ERRO: {exc}"
            enriched_row["judge_verdict"] = ""
            enriched_row["judge_confidence_score"] = ""
            enriched_row["judge_justification"] = ""
            enriched_row["judge_human_review_recommended"] = ""
            enriched_row["v2_verdict"] = ""
            enriched_row["v2_score"] = ""
            enriched_row["v2_reason"] = ""
            enriched_row["v2_changes_summary"] = ""
            enriched_row["v2_human_review_recommended"] = ""
            enriched_results.append(enriched_row)
            continue

        enriched_row = dict(row)
        enriched_row["judge_overall_result"] = judge_result.get("overall_result", "")
        enriched_row["judge_verdict"] = judge_article.get("judge_verdict", "")
        enriched_row["judge_confidence_score"] = judge_article.get("confidence_score", "")
        enriched_row["judge_justification"] = judge_article.get("judge_justification", "")
        enriched_row["judge_human_review_recommended"] = judge_article.get(
            "human_review_recommended",
            True,
        )

        verdict = judge_article.get("judge_verdict")
        if verdict == "CORRECT":
            judge_stats["correct"] += 1
        elif verdict == "INCORRECT":
            judge_stats["incorrect"] += 1
        else:
            judge_stats["uncertain"] += 1

        if verdict != "CORRECT":
            revision_payload = _build_evaluation_revision_payload(
                {
                    "title": row.get("_article_title") or row.get("article_name", ""),
                    "abstract": row.get("_article_abstract", ""),
                    "keywords": row.get("_article_keywords", []),
                },
                protocol_context,
                {
                    "score": row.get("score", 0),
                    "verdict": row.get("verdict", "UNSURE"),
                    "reason": row.get("reason", ""),
                    "article_name": row.get("article_name", ""),
                    "excluded_by_criterion": row.get("excluded_by_criterion", False),
                    "exclusion_triggered": row.get("_exclusion_triggered_raw") or row.get("exclusion_triggered") or [],
                    "inclusion_criteria_met": row.get("_inclusion_criteria_met_raw") or row.get("inclusion_criteria_met") or [],
                },
                judge_article,
                agent_id,
            )
            revision_result = _call_evaluate_revision(revision_payload)
            if revision_result:
                enriched_row["v2_verdict"] = revision_result.get("verdict", "")
                enriched_row["v2_score"] = revision_result.get("score", "")
                enriched_row["v2_reason"] = revision_result.get("reason", "")
                enriched_row["v2_changes_summary"] = (
                    "Classification_v2 gerada pelo Article Evaluator com feedback do AI Judge."
                )
                enriched_row["v2_human_review_recommended"] = True
                judge_stats["revised"] += 1
            else:
                enriched_row["v2_verdict"] = ""
                enriched_row["v2_score"] = ""
                enriched_row["v2_reason"] = ""
                enriched_row["v2_changes_summary"] = ""
                enriched_row["v2_human_review_recommended"] = ""
        else:
            enriched_row["v2_verdict"] = ""
            enriched_row["v2_score"] = ""
            enriched_row["v2_reason"] = ""
            enriched_row["v2_changes_summary"] = ""
            enriched_row["v2_human_review_recommended"] = ""

        enriched_results.append(enriched_row)

    return enriched_results, judge_stats


# ── Dialogs ───────────────────────────────────────────────────────────────────

@st.dialog("Salvar Preset")
def _save_preset_dialog():
    preview = st.session_state.get("ev_title", "") or "(sem título)"
    st.caption(f"Artigo: {preview[:80]}")

    name = st.text_input(
        "Nome do preset",
        placeholder="Ex: Artigo sobre redes neurais climáticas",
    )
    if st.button("Salvar", type="primary", use_container_width=True, disabled=not name.strip()):
        raw = st.session_state.get("ev_keywords_raw", "")
        excl = [c.strip() for c in _get_current_criteria("ev_exclusion_criteria") if c.strip()]
        incl = [c.strip() for c in _get_current_criteria("ev_inclusion_criteria") if c.strip()]
        st.session_state.presets[name.strip()] = {
            "title": st.session_state.get("ev_title", ""),
            "abstract": st.session_state.get("ev_abstract", ""),
            "keywords": [k.strip() for k in raw.split(",") if k.strip()],
            "research_protocol": {
                "description": st.session_state.get("ev_protocol_description", ""),
                "general_objectives": st.session_state.get("ev_general_objectives", ""),
                "specific_objectives": st.session_state.get("ev_specific_objectives", ""),
                "exclusion_criteria": excl,
                "inclusion_criteria": incl,
                "inclusion_logic": st.session_state.get("ev_inclusion_logic", "ANY"),
            },
        }
        _save_presets(st.session_state.presets)
        st.success(f"Preset '{name.strip()}' salvo!")
        st.rerun()


@st.dialog("Carregar Preset")
def _load_preset_dialog():
    if not st.session_state.presets:
        st.info("Nenhum preset salvo ainda. Use 'Salvar Preset' para criar um.")
        return

    name = st.selectbox("Selecione um preset", options=list(st.session_state.presets.keys()))

    if name:
        preset = st.session_state.presets[name]
        with st.container(border=True):
            st.markdown(f"**Título:** {preset['title'][:120] or '—'}")
            st.markdown(f"**Keywords:** {', '.join(preset['keywords']) or '—'}")
            if "research_protocol" in preset:
                p = preset["research_protocol"]
                if p.get("description"):
                    st.caption(f"Pesquisa: {p['description'][:150]}")
                ne = len([c for c in p.get("exclusion_criteria", []) if c])
                ni = len([c for c in p.get("inclusion_criteria", []) if c])
                if ne:
                    st.caption(f"Exclusão: {ne} critério(s)")
                if ni:
                    st.caption(
                        f"Inclusão: {ni} critério(s) · Lógica: {p.get('inclusion_logic', 'ANY')}"
                    )
            elif preset.get("research_synopsis"):
                st.caption(f"Sinopse (legado): {preset['research_synopsis'][:150]}")

        col_load, col_del = st.columns(2)
        with col_load:
            if st.button("Carregar", type="primary", use_container_width=True):
                # Clear old dynamic widget keys before overwriting lists
                _clear_list_widgets(
                    "ev_exclusion_criteria",
                    len(st.session_state.ev_exclusion_criteria),
                )
                _clear_list_widgets(
                    "ev_inclusion_criteria",
                    len(st.session_state.ev_inclusion_criteria),
                )

                st.session_state.ev_title = preset["title"]
                st.session_state.ev_abstract = preset["abstract"]
                st.session_state.ev_keywords_raw = ", ".join(preset["keywords"])

                if "research_protocol" in preset:
                    p = preset["research_protocol"]
                    st.session_state.ev_protocol_description = p.get("description", "")
                    st.session_state.ev_general_objectives = p.get("general_objectives", "")
                    st.session_state.ev_specific_objectives = p.get("specific_objectives", "")
                    st.session_state.ev_exclusion_criteria = list(
                        p.get("exclusion_criteria", [])
                    )
                    st.session_state.ev_inclusion_criteria = list(
                        p.get("inclusion_criteria", [])
                    )
                    st.session_state.ev_inclusion_logic = p.get("inclusion_logic", "ANY")
                else:
                    # Backward compatibility with old synopsis-only presets
                    st.session_state.ev_protocol_description = preset.get(
                        "research_synopsis", ""
                    )
                    st.session_state.ev_general_objectives = ""
                    st.session_state.ev_specific_objectives = ""
                    st.session_state.ev_exclusion_criteria = []
                    st.session_state.ev_inclusion_criteria = []
                    st.session_state.ev_inclusion_logic = "ANY"
                st.rerun()

        with col_del:
            if st.button("Excluir preset", use_container_width=True):
                del st.session_state.presets[name]
                _save_presets(st.session_state.presets)
                st.rerun()


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Status")
    try:
        _r = httpx.get(f"{BACKEND_URL}/health", timeout=5)
        backend_ok = _r.status_code == 200
        if backend_ok:
            st.success(f"✅ Backend online\n\n`{BACKEND_URL}`")
        else:
            st.error("❌ Backend retornou erro")
    except Exception:
        st.error(f"❌ Backend offline\n\n`{BACKEND_URL}`")
        backend_ok = False

    judge_ok, judge_message = get_ai_judge_status()
    if judge_ok:
        st.success("✅ AI Judge online")
    else:
        st.warning("AI Judge offline")
        st.caption(judge_message)

    st.divider()

    # ── Agent selector ────────────────────────────────────────────────────────
    st.subheader("🤖 Agente")
    selected_agent_id = None
    try:
        agents_resp = httpx.get(
            f"{BACKEND_URL}/agents", params={"agent_type": "article-evaluator"}, timeout=10
        )
        agents_list = agents_resp.json() if agents_resp.status_code == 200 else []
    except Exception:
        agents_list = []

    if agents_list:
        agent_options = {
            f"{a['name']} — {(a.get('active_version') or {}).get('version_name', 'sem versão ativa')}": a["id"]
            for a in agents_list
        }
        selected_label = st.selectbox(
            "Agente a usar:",
            options=list(agent_options.keys()),
            index=0,
        )
        selected_agent_id = agent_options[selected_label]
        active_ver = next(
            (a.get("active_version") for a in agents_list if a["id"] == selected_agent_id),
            None,
        )
        if active_ver:
            st.caption(
                f"Versão: **{active_ver['version_name']}**\n\n"
                f"Provedor: `{active_ver.get('provider', 'ollama')}`\n\n"
                f"Modelo: `{active_ver['model_primary']}`\n\n"
                f"Temp: `{active_ver['temperature']}`"
            )
        else:
            st.warning("Agente sem versão ativa.")
    else:
        st.warning("Nenhum agente disponível.")

    st.divider()
    n_presets = len(st.session_state.presets)
    st.metric("Presets salvos", n_presets)
    st.metric("Avaliações manuais (sessão)", len(st.session_state.evaluation_history))
    st.metric("Artigos avaliados via CSV", len(st.session_state.csv_results))
    if st.session_state.evaluation_history:
        if st.button("🗑️ Limpar histórico manual", use_container_width=True):
            st.session_state.evaluation_history = []
            st.rerun()
    if st.session_state.csv_results:
        if st.button("🗑️ Limpar resultados do CSV", use_container_width=True):
            st.session_state.csv_results = []
            st.session_state.csv_judge_summary = None
            st.rerun()


# ── Cabeçalho ─────────────────────────────────────────────────────────────────
st.title("📋 Avaliador de Artigos Científicos")
st.markdown(
    "Avalia a relevância de um conjunto de artigos para um protocolo de pesquisa, "
    "aplicando critérios de exclusão eliminatórios e critérios de inclusão configuráveis."
)
st.divider()

# ── Protocolo de pesquisa ─────────────────────────────────────────────────────
st.subheader("🔬 Protocolo de Pesquisa")

col_save, col_load, _ = st.columns([1, 1, 4])
with col_save:
    if st.button("💾 Salvar Preset", use_container_width=True):
        _save_preset_dialog()
with col_load:
    if st.button("📂 Carregar Preset", use_container_width=True):
        _load_preset_dialog()

st.text_area(
    "Descrição da pesquisa *",
    placeholder=(
        "Descreva o tema e escopo da sua pesquisa. "
        "Ex: Esta pesquisa investiga o uso de redes neurais para previsão de "
        "emissões de CO2 em ambientes urbanos."
    ),
    height=100,
    max_chars=5000,
    key="ev_protocol_description",
)

col_obj1, col_obj2 = st.columns(2)
with col_obj1:
    st.text_area(
        "Objetivos gerais",
        placeholder="Descreva os objetivos gerais da pesquisa...",
        height=100,
        max_chars=2000,
        key="ev_general_objectives",
    )
with col_obj2:
    st.text_area(
        "Objetivos específicos",
        placeholder="Descreva os objetivos específicos da pesquisa...",
        height=100,
        max_chars=2000,
        key="ev_specific_objectives",
    )

# ── Critérios de exclusão ─────────────────────────────────────────────────────
st.markdown(
    "**⛔ Critérios de Exclusão** — "
    "qualquer critério satisfeito exclui o artigo imediatamente (score = 0)"
)
st.caption(
    "Ex: Artigos em espanhol · Artigos anteriores a 2020 · "
    "Artigos sem metodologia definida"
)
_render_criteria_list(
    "ev_exclusion_criteria",
    "Critério de exclusão",
    "Adicionar critério de exclusão",
    placeholder="Ex: Artigos publicados antes de 2020",
)

st.markdown("")

# ── Critérios de inclusão ─────────────────────────────────────────────────────
st.markdown(
    "**✅ Critérios de Inclusão** — "
    "critérios desejáveis avaliados conforme a lógica definida"
)
st.caption(
    "Ex: Artigos de 2023 para cá · Artigos da revista Nature · "
    "Artigos com 'Machine Learning' no título"
)
_render_criteria_list(
    "ev_inclusion_criteria",
    "Critério de inclusão",
    "Adicionar critério de inclusão",
    placeholder="Ex: Artigos publicados a partir de 2023",
)

if st.session_state.ev_inclusion_criteria:
    st.text_input(
        "Lógica de inclusão",
        placeholder="ANY, ALL, ou expressão como: 1 AND (2 OR 3)",
        key="ev_inclusion_logic",
        help=(
            "ANY = qualquer critério satisfeito é suficiente\n"
            "ALL = todos os critérios devem ser satisfeitos\n"
            "Expressão: use os números (base 1) com AND, OR, NOT e parênteses\n"
            "Ex: 1 AND (2 OR 3)"
        ),
    )

st.divider()

# ── Dados dos artigos ─────────────────────────────────────────────────────────
st.subheader("📄 Artigos para Avaliação")

input_mode = st.radio(
    "Modo de entrada dos artigos",
    options=["📂 Importar CSV (recomendado)", "✍️ Manual (apenas para testes)"],
    horizontal=True,
)

# ── Modo CSV (lote) ────────────────────────────────────────────────────────────
if input_mode.startswith("📂"):
    st.caption(
        "O arquivo deve conter colunas com **título**, **abstract** e "
        "**palavras-chave** de cada artigo. Mapeie as colunas abaixo."
    )

    uploaded = st.file_uploader("Arquivo CSV", type=["csv"])

    if uploaded is not None:
        try:
            df = _read_uploaded_csv(uploaded)
        except pd.errors.EmptyDataError:
            st.error("O arquivo CSV está vazio.")
            st.stop()
        except pd.errors.ParserError as exc:
            st.error(f"Não foi possível interpretar o CSV — verifique o formato/separador do arquivo. Detalhe: {exc}")
            st.stop()
        except Exception as exc:
            st.error(f"Erro ao ler o CSV: {exc}")
            st.stop()

        if df.empty or not len(df.columns):
            st.error("O arquivo CSV não contém dados ou colunas.")
            st.stop()

        st.success(f"{len(df)} linha(s) carregada(s).")
        st.dataframe(df.head(10), use_container_width=True)

        cols = list(df.columns)

        def _guess_col(candidates: list[str]) -> str:
            for c in cols:
                if c.strip().lower() in candidates:
                    return c
            return cols[0]

        col_t, col_a, col_k = st.columns(3)
        with col_t:
            title_col = st.selectbox(
                "Coluna do título", cols,
                index=cols.index(_guess_col(["title", "título", "titulo"])),
            )
        with col_a:
            abstract_col = st.selectbox(
                "Coluna do abstract", cols,
                index=cols.index(_guess_col(["abstract", "resumo"])),
            )
        with col_k:
            keywords_col = st.selectbox(
                "Coluna de palavras-chave", cols,
                index=cols.index(_guess_col(["keywords", "palavras-chave", "palavras_chave"])),
            )

        col_sep, col_limit = st.columns(2)
        with col_sep:
            kw_sep = st.text_input("Separador de palavras-chave", value=";")
        with col_limit:
            limit = st.number_input(
                "Limitar a N artigos (0 = todos)", min_value=0, value=0, step=1,
            )

        evaluate_csv_btn = st.button(
            "🔍 Avaliar artigos do CSV", type="primary", use_container_width=True
        )

        if evaluate_csv_btn:
            errors = _protocol_errors(backend_ok)
            if errors:
                for e in errors:
                    st.error(e)
                st.stop()

            protocol_payload = _build_protocol_payload()

            rows = df if limit == 0 else df.head(int(limit))
            n = len(rows)
            results = []
            progress = st.progress(0.0, text=f"Avaliando 0/{n}...")
            skipped = 0

            for idx, (_, row) in enumerate(rows.iterrows()):
                title = str(row.get(title_col, "")).strip()
                abstract = str(row.get(abstract_col, "")).strip()
                kw_raw = str(row.get(keywords_col, ""))
                keywords = [k.strip() for k in kw_raw.split(kw_sep) if k.strip()]

                if not title or not abstract or not keywords:
                    skipped += 1
                    progress.progress((idx + 1) / n, text=f"Avaliando {idx + 1}/{n}...")
                    continue

                payload = {
                    "title": title[:1000],
                    "abstract": abstract[:10000],
                    "keywords": keywords,
                    "research_protocol": protocol_payload,
                    "agent_id": selected_agent_id,
                }
                result = _call_evaluate(payload)
                if result:
                    raw_exclusion_triggered = result.get("exclusion_triggered", [])
                    raw_inclusion_met = result.get("inclusion_criteria_met", [])
                    if isinstance(result.get("exclusion_triggered"), list):
                        result["exclusion_triggered"] = "; ".join(result["exclusion_triggered"])
                    if isinstance(result.get("inclusion_criteria_met"), list):
                        result["inclusion_criteria_met"] = "; ".join(result["inclusion_criteria_met"])
                    results.append(
                        {
                            **row.to_dict(),
                            **result,
                            "_article_title": title[:1000],
                            "_article_abstract": abstract[:10000],
                            "_article_keywords": keywords,
                            "_exclusion_triggered_raw": raw_exclusion_triggered,
                            "_inclusion_criteria_met_raw": raw_inclusion_met,
                        }
                    )
                else:
                    skipped += 1

                progress.progress((idx + 1) / n, text=f"Avaliando {idx + 1}/{n}...")

            progress.empty()
            if skipped:
                st.warning(f"{skipped} linha(s) ignorada(s) (dados incompletos ou erro de avaliação).")

            st.session_state.csv_results = results
            st.session_state.csv_judge_summary = None
            st.rerun()

# ── Modo manual (testes) ───────────────────────────────────────────────────────
else:
    st.info("Modo manual destinado a testes pontuais com um único artigo.")

    st.text_input(
        "Título do artigo *",
        placeholder="Ex: Deep learning approaches for climate change prediction",
        max_chars=1000,
        key="ev_title",
    )
    st.text_area(
        "Abstract *",
        placeholder="Cole aqui o abstract do artigo...",
        height=200,
        max_chars=10000,
        key="ev_abstract",
    )
    st.text_input(
        "Palavras-chave * (separadas por vírgula)",
        placeholder="Ex: machine learning, neural networks, climate change",
        key="ev_keywords_raw",
    )

    evaluate_btn = st.button("🔍 Avaliar Artigo", type="primary", use_container_width=True)

    if evaluate_btn:
        title    = st.session_state.ev_title
        abstract = st.session_state.ev_abstract
        keywords = [k.strip() for k in st.session_state.ev_keywords_raw.split(",") if k.strip()]

        errors = _protocol_errors(backend_ok)
        if not title.strip():
            errors.append("O título é obrigatório.")
        if not abstract.strip():
            errors.append("O abstract é obrigatório.")
        if not keywords:
            errors.append("Informe ao menos uma palavra-chave.")

        if errors:
            for e in errors:
                st.error(e)
            st.stop()

        payload = {
            "title": title.strip(),
            "abstract": abstract.strip(),
            "keywords": keywords,
            "research_protocol": _build_protocol_payload(),
            "agent_id": selected_agent_id,
        }

        with st.spinner("Avaliando artigo com o agente LLM... (pode levar alguns segundos)"):
            result = _call_evaluate(payload)
            if result is None:
                st.stop()

        st.session_state.manual_article_context = {
            "title": title.strip(),
            "abstract": abstract.strip(),
            "keywords": keywords,
        }
        st.session_state.manual_protocol_context = payload["research_protocol"]
        st.session_state.manual_judge_result = None
        st.session_state.manual_revision_result = None
        st.session_state.evaluation_history.insert(0, result)
        st.rerun()


st.divider()

# ── Resultados do CSV (lote) ───────────────────────────────────────────────────
if st.session_state.csv_results:
    results = st.session_state.csv_results
    protocol_context = _build_protocol_payload()

    st.subheader("📊 Resultados da Avaliação em Lote")

    n_related = sum(1 for r in results if r["verdict"] == "RELATED")
    n_unsure = sum(1 for r in results if r["verdict"] == "UNSURE")
    n_excluded = sum(1 for r in results if r.get("excluded_by_criterion"))
    n_not_related = len(results) - n_related - n_unsure

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("✅ RELATED", n_related)
    c2.metric("⚠️ UNSURE", n_unsure)
    c3.metric("❌ NOT-RELATED", n_not_related)
    c4.metric("⛔ Excluídos por critério", n_excluded)

    csv_judge_col, _ = st.columns([1, 2])
    with csv_judge_col:
        judge_csv_btn = st.button(
            "⚖️ Julgar resultados do CSV com AI Judge",
            type="secondary",
            use_container_width=True,
            disabled=(not judge_ok),
        )

    if judge_csv_btn:
        with st.status("Julgando resultados em lote...", expanded=True) as status:
            try:
                st.write("Revisando coerência das classificações produzidas pelo avaliador...")
                enriched_results, judge_stats = _apply_csv_judge_and_revision(
                    results,
                    protocol_context,
                    selected_agent_id,
                )
                st.session_state.csv_results = enriched_results
                st.session_state.csv_judge_summary = judge_stats
                n_errors = judge_stats.get("errors", 0)
                status.update(
                    label=(
                        f"Julgamento em lote concluído com {n_errors} erro(s) por linha."
                        if n_errors else "Julgamento em lote concluído com sucesso!"
                    ),
                    state="error" if n_errors else "complete",
                    expanded=bool(n_errors),
                )
                st.rerun()
            except Exception as exc:
                status.update(label="Erro no julgamento em lote", state="error", expanded=True)
                st.error(str(exc))

    if st.session_state.csv_judge_summary:
        judge_stats = st.session_state.csv_judge_summary
        st.markdown("**Resumo do AI Judge**")
        j1, j2, j3, j4, j5 = st.columns(5)
        j1.metric("CORRECT", judge_stats.get("correct", 0))
        j2.metric("UNCERTAIN", judge_stats.get("uncertain", 0))
        j3.metric("INCORRECT", judge_stats.get("incorrect", 0))
        j4.metric("Classification_v2", judge_stats.get("revised", 0))
        j5.metric("Erros", judge_stats.get("errors", 0))
        if judge_stats.get("errors", 0):
            st.warning(
                f"{judge_stats['errors']} linha(s) não puderam ser julgadas — veja a coluna "
                "'judge_overall_result' no CSV exportado para o detalhe do erro em cada uma. "
                "As demais linhas foram julgadas normalmente."
            )

    results_df = pd.DataFrame(results)
    visible_cols = [c for c in results_df.columns if not c.startswith("_")]

    base_cols = [
        "article_name", "score", "verdict", "excluded_by_criterion",
        "exclusion_triggered", "inclusion_criteria_met", "reason",
    ]
    base_show_cols = [c for c in base_cols if c in visible_cols]
    base_show_cols += [
        c for c in visible_cols
        if c not in base_show_cols
        and not c.startswith("judge_")
        and not c.startswith("v2_")
    ]

    st.markdown("**Tabela da primeira avaliação**")
    st.dataframe(results_df[base_show_cols], use_container_width=True)

    if st.session_state.csv_judge_summary:
        judge_cols = [
            "article_name",
            "verdict",
            "score",
            "judge_overall_result",
            "judge_verdict",
            "judge_confidence_score",
            "judge_human_review_recommended",
            "judge_justification",
            "v2_verdict",
            "v2_score",
            "v2_human_review_recommended",
            "v2_changes_summary",
            "v2_reason",
        ]
        judge_show_cols = [c for c in judge_cols if c in visible_cols]
        st.markdown("**Tabela do AI Judge e classification_v2**")
        st.dataframe(results_df[judge_show_cols], use_container_width=True)

    csv_bytes = _to_delimited_csv(results_df[visible_cols])
    st.download_button(
        "⬇️ Baixar resultados (CSV, separador ';;')",
        data=csv_bytes,
        file_name="resultados_avaliacao.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.caption(
        "O CSV exportado usa `;;` como separador de colunas (em vez de `,`) para evitar "
        "que vírgulas ou ponto-e-vírgulas dentro dos textos de justificativa sejam "
        "interpretados como quebra de coluna."
    )

    st.divider()


# ── Resultado mais recente (modo manual) ───────────────────────────────────────
if st.session_state.evaluation_history:
    latest   = st.session_state.evaluation_history[0]
    verdict  = latest["verdict"]
    score    = latest["score"]
    excluded = latest.get("excluded_by_criterion", False)
    exclusion_triggered = latest.get("exclusion_triggered", [])
    inclusion_met = latest.get("inclusion_criteria_met", [])

    st.subheader("Resultado (avaliação manual)")

    if excluded:
        st.error("⛔ **Artigo excluído por critério(s) de exclusão** — pontuação zerada")
        if exclusion_triggered:
            st.markdown("**Critério(s) violado(s):**")
            for t in exclusion_triggered:
                st.error(f"• {t}")

    if verdict == "RELATED":
        verdict_badge = ":green[**✅ RELATED**]"
    elif verdict == "UNSURE":
        verdict_badge = ":orange[**⚠️ UNSURE**]"
    else:
        verdict_badge = ":red[**❌ NOT-RELATED**]"

    col_score, col_verdict = st.columns([3, 1])
    with col_score:
        st.markdown(f"**Score:** {score}/100")
        st.progress(score / 100)
    with col_verdict:
        st.markdown("**Veredicto:**")
        st.markdown(verdict_badge)

    if inclusion_met and not excluded:
        with st.container(border=True):
            st.markdown("**Critérios de inclusão satisfeitos:**")
            for c in inclusion_met:
                st.markdown(f"✅ {c}")

    with st.container(border=True):
        st.markdown(f"**Artigo:** {latest['article_name']}")
        st.markdown("**Justificativa:**")
        st.markdown(latest["reason"])

    article_context = st.session_state.manual_article_context
    protocol_context = st.session_state.manual_protocol_context

    judge_col, _ = st.columns([1, 2])
    with judge_col:
        judge_manual_btn = st.button(
            "⚖️ Julgar decisão com AI Judge",
            type="secondary",
            use_container_width=True,
            disabled=(not judge_ok or not article_context or not protocol_context),
        )

    if judge_manual_btn and article_context and protocol_context:
        with st.status("Enviando avaliação ao AI Judge...", expanded=True) as status:
            try:
                article_payload = _build_manual_judge_article(article_context, latest)
                judge_request = _build_manual_judge_request(protocol_context, article_payload)
                st.write("Verificando coerência entre veredito, score, exclusões e critérios...")
                judge_result = judge_article_classifications(**judge_request)
                st.session_state.manual_judge_result = judge_result
                st.session_state.manual_revision_result = None

                judge_article = (judge_result.get("articles") or [{}])[0]
                if judge_article.get("judge_verdict") != "CORRECT":
                    st.write("O juiz encontrou inconsistências; gerando classification_v2...")
                    revision_payload = _build_evaluation_revision_payload(
                        article_context,
                        protocol_context,
                        latest,
                        judge_article,
                        selected_agent_id,
                    )
                    revision_result = _call_evaluate_revision(revision_payload)
                    if revision_result:
                        st.session_state.manual_revision_result = {
                            "summary": "Classification_v2 gerada pelo próprio Article Evaluator com base no feedback do AI Judge.",
                            "articles": [
                                _evaluation_result_to_revision_view(
                                    revision_result,
                                    latest.get("verdict", "UNSURE"),
                                )
                            ],
                        }

                status.update(
                    label="Julgamento concluído com sucesso!",
                    state="complete",
                    expanded=False,
                )
            except Exception as exc:
                st.session_state.manual_judge_result = None
                st.session_state.manual_revision_result = None
                status.update(label="Erro no julgamento", state="error", expanded=True)
                st.error(str(exc))

    judge_result = st.session_state.manual_judge_result
    if judge_result:
        st.markdown("---")
        st.subheader("Parecer do AI as Judge")
        st.success(f"Resultado geral: {judge_result.get('overall_result', '—')}")

        summary = judge_result.get("summary", "")
        if summary:
            st.info(summary)

        judge_article = (judge_result.get("articles") or [{}])[0]
        with st.container(border=True):
            left, right = st.columns(2)
            with left:
                st.markdown(f"Classificação do avaliador: `{judge_article.get('model_classification', '—')}`")
                st.markdown(f"Veredito do juiz: `{judge_article.get('judge_verdict', '—')}`")
            with right:
                st.metric("Confiança do juiz", judge_article.get("confidence_score", "—"))
                st.markdown(
                    "Revisão humana recomendada: "
                    f"`{judge_article.get('human_review_recommended', True)}`"
                )

            st.markdown("**Justificativa do juiz**")
            st.write(judge_article.get("judge_justification", "") or "Sem justificativa informada.")

        risks = judge_result.get("main_risks", [])
        if risks:
            st.markdown("**Principais riscos**")
            for risk in risks:
                st.warning(risk)

    revision_result = st.session_state.manual_revision_result
    if revision_result:
        revision_article = (revision_result.get("articles") or [{}])[0]
        st.markdown("---")
        st.subheader("Classification_v2 gerada com feedback do juiz")

        summary = revision_result.get("summary", "")
        if summary:
            st.info(summary)

        revised_verdict = revision_article.get("revised_classification", "UNSURE")
        revised_score = revision_article.get("revised_score", 0)
        revised_excluded = revision_article.get("revised_excluded_by_criterion", False)
        revised_inclusion = revision_article.get("revised_inclusion_criteria_met", [])
        revised_exclusion = revision_article.get("revised_exclusion_triggered", [])

        top_left, top_right = st.columns([3, 1])
        with top_left:
            st.markdown(
                f"**Classificação original:** `{revision_article.get('original_classification', '—')}`"
            )
            st.markdown(f"**Classification_v2:** `{revised_verdict}`")
            st.markdown("**Resumo das mudanças**")
            st.write(revision_article.get("changes_summary", "") or "Sem resumo informado.")
        with top_right:
            st.metric("Score v2", revised_score)
            st.markdown(
                "Revisão humana recomendada: "
                f"`{revision_article.get('human_review_recommended', True)}`"
            )

        if revised_excluded:
            st.error("⛔ A classification_v2 marcou exclusão por critério.")
        if revised_exclusion:
            st.markdown("**Critérios de exclusão acionados na v2**")
            for item in revised_exclusion:
                st.error(f"• {item}")

        if revised_inclusion and not revised_excluded:
            st.markdown("**Critérios de inclusão satisfeitos na v2**")
            for item in revised_inclusion:
                st.markdown(f"✅ {item}")

        with st.container(border=True):
            st.markdown("**Justificativa da classification_v2**")
            st.write(revision_article.get("revised_justification", "") or "Sem justificativa informada.")

        use_v2_btn = st.button(
            "Usar classification_v2 como resultado atual",
            type="primary",
            use_container_width=True,
        )
        if use_v2_btn:
            st.session_state.evaluation_history.insert(
                0,
                _revision_to_evaluation_result(revision_article),
            )
            st.session_state.manual_judge_result = None
            st.session_state.manual_revision_result = None
            st.rerun()

    st.divider()


# ── Histórico da sessão (modo manual) ───────────────────────────────────────────
history = st.session_state.evaluation_history
if len(history) > 1:
    st.subheader(f"📜 Histórico de avaliações manuais ({len(history)})")

    for item in history[1:]:
        v = item["verdict"]
        s = item["score"]
        excl = item.get("excluded_by_criterion", False)

        if excl:
            icon    = "⛔"
            color   = "red"
            v_label = "EXCLUÍDO"
        elif v == "RELATED":
            icon    = "✅"
            color   = "green"
            v_label = v
        elif v == "UNSURE":
            icon    = "⚠️"
            color   = "orange"
            v_label = v
        else:
            icon    = "❌"
            color   = "red"
            v_label = v

        with st.expander(f"{icon} [{s}/100] {item['article_name'][:80]}"):
            st.markdown(f"**Veredicto:** :{color}[**{v_label}**]")
            st.progress(s / 100)
            if excl and item.get("exclusion_triggered"):
                st.markdown("**Critérios violados:**")
                for t in item["exclusion_triggered"]:
                    st.error(f"• {t}")
            if item.get("inclusion_criteria_met") and not excl:
                st.markdown("**Inclusão satisfeita:**")
                for c in item["inclusion_criteria_met"]:
                    st.markdown(f"✅ {c}")
            st.markdown("**Justificativa:**")
            st.markdown(item["reason"])
