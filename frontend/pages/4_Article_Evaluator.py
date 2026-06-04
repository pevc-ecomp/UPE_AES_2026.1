import json
import os
from pathlib import Path

import httpx
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
if "presets" not in st.session_state:
    st.session_state.presets = _load_presets()
for _key, _default in [
    ("ev_title", ""),
    ("ev_abstract", ""),
    ("ev_keywords_raw", ""),
    ("ev_synopsis", ""),
]:
    if _key not in st.session_state:
        st.session_state[_key] = _default


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
        st.session_state.presets[name.strip()] = {
            "title": st.session_state.get("ev_title", ""),
            "abstract": st.session_state.get("ev_abstract", ""),
            "keywords": [k.strip() for k in raw.split(",") if k.strip()],
            "research_synopsis": st.session_state.get("ev_synopsis", ""),
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
            if preset.get("research_synopsis"):
                st.caption(f"Sinopse: {preset['research_synopsis'][:150]}")

        col_load, col_del = st.columns(2)
        with col_load:
            if st.button("Carregar", type="primary", use_container_width=True):
                st.session_state.ev_title = preset["title"]
                st.session_state.ev_abstract = preset["abstract"]
                st.session_state.ev_keywords_raw = ", ".join(preset["keywords"])
                st.session_state.ev_synopsis = preset.get("research_synopsis", "")
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
    n_presets = len(st.session_state.presets)
    st.metric("Presets salvos", n_presets)
    st.metric("Avaliações nesta sessão", len(st.session_state.evaluation_history))
    if st.session_state.evaluation_history:
        if st.button("🗑️ Limpar histórico", use_container_width=True):
            st.session_state.evaluation_history = []
            st.rerun()

# ── Cabeçalho ─────────────────────────────────────────────────────────────────
st.title("📋 Avaliador de Artigos Científicos")
st.markdown(
    "Avalia a relevância de um artigo para uma pesquisa usando um agente LLM. "
    "Informe os dados do artigo e, opcionalmente, uma sinopse da sua pesquisa."
)
st.divider()

# ── Botões de preset ──────────────────────────────────────────────────────────
col_save, col_load, _ = st.columns([1, 1, 4])
with col_save:
    if st.button("💾 Salvar Preset", use_container_width=True):
        _save_preset_dialog()
with col_load:
    if st.button("📂 Carregar Preset", use_container_width=True):
        _load_preset_dialog()

st.divider()

# ── Campos do formulário (sem st.form — necessário para st_tags funcionar) ────
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

st.text_area(
    "Sinopse da pesquisa * (o artigo será avaliado em relação a este texto)",
    placeholder=(
        "Descreva o tema da sua pesquisa. "
        "Ex: Esta pesquisa investiga o uso de redes neurais para previsão de "
        "emissões de CO2 em ambientes urbanos."
    ),
    height=100,
    max_chars=5000,
    key="ev_synopsis",
)

evaluate_btn = st.button("🔍 Avaliar Artigo", type="primary", use_container_width=True)

# ── Avaliação ─────────────────────────────────────────────────────────────────
if evaluate_btn:
    title    = st.session_state.ev_title
    abstract = st.session_state.ev_abstract
    keywords = [k.strip() for k in st.session_state.ev_keywords_raw.split(",") if k.strip()]
    synopsis = st.session_state.ev_synopsis

    errors = []
    if not title.strip():
        errors.append("O título é obrigatório.")
    if not abstract.strip():
        errors.append("O abstract é obrigatório.")
    if not keywords:
        errors.append("Informe ao menos uma palavra-chave.")
    if not synopsis.strip():
        errors.append("A sinopse da pesquisa é obrigatória.")
    if not backend_ok:
        errors.append("O backend está offline. Verifique os containers.")

    if errors:
        for e in errors:
            st.error(e)
        st.stop()

    payload = {
        "title": title.strip(),
        "abstract": abstract.strip(),
        "keywords": [kw.strip() for kw in keywords if kw.strip()],
        "research_synopsis": synopsis.strip(),
    }

    with st.spinner("Avaliando artigo com o agente LLM... (pode levar alguns segundos)"):
        try:
            resp = httpx.post(
                f"{BACKEND_URL}/agents/evaluate-article",
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            result = resp.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.json().get("detail", str(exc))
            st.error(f"Erro do backend: {detail}")
            st.stop()
        except Exception as exc:
            st.error(f"Erro de conexão: {exc}")
            st.stop()

    st.session_state.evaluation_history.insert(0, result)
    st.rerun()

# ── Resultado mais recente ────────────────────────────────────────────────────
if st.session_state.evaluation_history:
    latest  = st.session_state.evaluation_history[0]
    verdict = latest["verdict"]
    score   = latest["score"]

    if verdict == "RELATED":
        verdict_badge = ":green[**✅ RELATED**]"
    elif verdict == "UNSURE":
        verdict_badge = ":orange[**⚠️ UNSURE**]"
    else:
        verdict_badge = ":red[**❌ NOT-RELATED**]"

    st.subheader("Resultado")
    col_score, col_verdict = st.columns([3, 1])
    with col_score:
        st.markdown(f"**Score:** {score}/100")
        st.progress(score / 100)
    with col_verdict:
        st.markdown("**Veredicto:**")
        st.markdown(verdict_badge)

    with st.container(border=True):
        st.markdown(f"**Artigo:** {latest['article_name']}")
        st.markdown("**Justificativa:**")
        st.markdown(latest["reason"])

    st.divider()

# ── Histórico da sessão ───────────────────────────────────────────────────────
history = st.session_state.evaluation_history
if len(history) > 1:
    st.subheader(f"📜 Histórico da sessão ({len(history)} avaliação(ões))")

    for item in history[1:]:
        v = item["verdict"]
        s = item["score"]
        icon  = "✅" if v == "RELATED" else ("⚠️" if v == "UNSURE" else "❌")
        color = "green" if v == "RELATED" else ("orange" if v == "UNSURE" else "red")

        with st.expander(f"{icon} [{s}/100] {item['article_name'][:80]}"):
            st.markdown(f"**Veredicto:** :{color}[**{v}**]")
            st.progress(s / 100)
            st.markdown("**Justificativa:**")
            st.markdown(item["reason"])
