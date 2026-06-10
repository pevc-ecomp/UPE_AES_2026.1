import json
import os
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Avaliador de Artigos",
    page_icon="📋",
    layout="wide",
)

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
PRESETS_FILE = Path("/app/data/article_presets.json")


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
        detail = exc.response.json().get("detail", str(exc))
        st.error(f"Erro do backend: {detail}")
        return None
    except Exception as exc:
        st.error(f"Erro de conexão: {exc}")
        return None


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
            df = pd.read_csv(uploaded)
        except UnicodeDecodeError:
            uploaded.seek(0)
            df = pd.read_csv(uploaded, encoding="latin-1")

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
                    if isinstance(result.get("exclusion_triggered"), list):
                        result["exclusion_triggered"] = "; ".join(result["exclusion_triggered"])
                    if isinstance(result.get("inclusion_criteria_met"), list):
                        result["inclusion_criteria_met"] = "; ".join(result["inclusion_criteria_met"])
                    results.append({**row.to_dict(), **result})
                else:
                    skipped += 1

                progress.progress((idx + 1) / n, text=f"Avaliando {idx + 1}/{n}...")

            progress.empty()
            if skipped:
                st.warning(f"{skipped} linha(s) ignorada(s) (dados incompletos ou erro de avaliação).")

            st.session_state.csv_results = results
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

        st.session_state.evaluation_history.insert(0, result)
        st.rerun()


st.divider()

# ── Resultados do CSV (lote) ───────────────────────────────────────────────────
if st.session_state.csv_results:
    results = st.session_state.csv_results

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

    results_df = pd.DataFrame(results)
    preferred_cols = [
        "article_name", "score", "verdict", "excluded_by_criterion",
        "exclusion_triggered", "inclusion_criteria_met", "reason",
    ]
    show_cols = [c for c in preferred_cols if c in results_df.columns]
    show_cols += [c for c in results_df.columns if c not in show_cols]
    st.dataframe(results_df[show_cols], use_container_width=True)

    csv_bytes = results_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Baixar resultados (CSV)",
        data=csv_bytes,
        file_name="resultados_avaliacao.csv",
        mime="text/csv",
        use_container_width=True,
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
