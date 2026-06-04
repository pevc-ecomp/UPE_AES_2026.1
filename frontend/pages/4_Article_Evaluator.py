import os

import httpx
import streamlit as st
from streamlit_tags import st_tags

st.set_page_config(
    page_title="Avaliador de Artigos",
    page_icon="📋",
    layout="wide",
)

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")

# ── Session state ─────────────────────────────────────────────────────────────
if "evaluation_history" not in st.session_state:
    st.session_state.evaluation_history = []

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Status")
    try:
        resp = httpx.get(f"{BACKEND_URL}/health", timeout=5)
        if resp.status_code == 200:
            st.success(f"✅ Backend online\n\n`{BACKEND_URL}`")
            backend_ok = True
        else:
            st.error("❌ Backend retornou erro")
            backend_ok = False
    except Exception:
        st.error(f"❌ Backend offline\n\n`{BACKEND_URL}`")
        backend_ok = False

    st.divider()
    if st.session_state.evaluation_history:
        st.metric("Avaliações nesta sessão", len(st.session_state.evaluation_history))
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

# ── Formulário ────────────────────────────────────────────────────────────────
with st.form("evaluation_form"):
    title = st.text_input(
        "Título do artigo *",
        placeholder="Ex: Deep learning approaches for climate change prediction",
        max_chars=1000,
    )

    abstract = st.text_area(
        "Abstract *",
        placeholder="Cole aqui o abstract do artigo...",
        height=200,
        max_chars=10000,
    )

    keywords = st_tags(
        label="Palavras-chave *",
        text="Digite e pressione Enter para adicionar",
        value=[],
        key="keywords_input",
    )

    research_synopsis = st.text_area(
        "Sinopse da pesquisa (opcional)",
        placeholder=(
            "Descreva em algumas frases o tema da sua pesquisa. "
            "Ex: Esta pesquisa investiga o uso de redes neurais para previsão de "
            "emissões de CO2 em ambientes urbanos."
        ),
        height=100,
        max_chars=5000,
    )

    submitted = st.form_submit_button(
        "🔍 Avaliar Artigo", type="primary", use_container_width=True
    )

# ── Avaliação ─────────────────────────────────────────────────────────────────
if submitted:
    errors = []
    if not title.strip():
        errors.append("O título é obrigatório.")
    if not abstract.strip():
        errors.append("O abstract é obrigatório.")
    if not keywords:
        errors.append("Informe ao menos uma palavra-chave.")
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
        "research_synopsis": research_synopsis.strip() or None,
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

# ── Resultado mais recente ────────────────────────────────────────────────────
if st.session_state.evaluation_history:
    latest = st.session_state.evaluation_history[0]

    st.subheader("Resultado")

    verdict = latest["verdict"]
    score = latest["score"]

    if verdict == "RELATED":
        verdict_badge = ":green[**✅ RELATED**]"
        bar_color = "normal"
    elif verdict == "UNSURE":
        verdict_badge = ":orange[**⚠️ UNSURE**]"
        bar_color = "normal"
    else:
        verdict_badge = ":red[**❌ NOT-RELATED**]"
        bar_color = "normal"

    col_score, col_verdict = st.columns([3, 1])

    with col_score:
        st.markdown(f"**Score:** {score}/100")
        st.progress(score / 100)

    with col_verdict:
        st.markdown(f"**Veredicto:**")
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

    for i, item in enumerate(history[1:], start=2):
        verdict = item["verdict"]
        score = item["score"]

        if verdict == "RELATED":
            icon = "✅"
            color = "green"
        elif verdict == "UNSURE":
            icon = "⚠️"
            color = "orange"
        else:
            icon = "❌"
            color = "red"

        with st.expander(f"{icon} [{score}/100] {item['article_name'][:80]}"):
            st.markdown(f"**Veredicto:** :{color}[**{verdict}**]")
            st.markdown(f"**Score:** {score}/100")
            st.progress(score / 100)
            st.markdown("**Justificativa:**")
            st.markdown(item["reason"])
