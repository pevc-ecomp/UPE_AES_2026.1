import os

import httpx
import streamlit as st

import ui

st.set_page_config(
    page_title="Research Assistant",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)
ui.apply_style()

# ── Cabeçalho ────────────────────────────────────────────────────────────────
st.title("🔬 Scientific Research Assistant")
st.markdown("Plataforma de apoio à revisão de literatura científica.")
st.divider()

# ── Status dos serviços ──────────────────────────────────────────────────────
st.subheader("🖥️ Status dos Serviços")

col_backend, col_ollama, col_judge = st.columns(3)

with col_backend:
    backend_url = os.getenv("BACKEND_URL", "http://backend:8000")
    try:
        _r = httpx.get(f"{backend_url}/health", timeout=3)
        if _r.status_code == 200:
            st.success(f"✅ Backend — online\n\n`{backend_url}`")
        else:
            st.warning(f"⚠️ Backend — erro\n\n`{backend_url}`")
    except Exception:
        st.error(f"❌ Backend — offline\n\n`{backend_url}`")

with col_ollama:
    ollama_host = os.getenv("OLLAMA_HOST", "http://ollama:11434")
    model = os.getenv("OLLAMA_MODEL_PRIMARY", "phi3:mini")
    try:
        _r = httpx.get(f"{ollama_host}/api/tags", timeout=3)
        if _r.status_code == 200:
            st.success(f"✅ Ollama — online\n\n`{model}`")
        else:
            st.warning(f"⚠️ Ollama — erro\n\n`{ollama_host}`")
    except Exception:
        st.error(f"❌ Ollama — offline\n\n`{ollama_host}`")

with col_judge:
    judge_url = os.getenv("IA_JUDGE_URL", "http://localhost:8002")
    try:
        _r = httpx.get(f"{judge_url}/status", timeout=3)
        if _r.status_code == 200:
            st.success(f"✅ AI Judge — online\n\n`{judge_url}`")
        else:
            st.warning(f"⚠️ AI Judge — erro\n\n`{judge_url}`")
    except Exception:
        st.error(f"❌ AI Judge — offline\n\n`{judge_url}`")

st.divider()

# ── Descrição das páginas ────────────────────────────────────────────────────
st.subheader("📋 Páginas disponíveis")

p1, p2, p3 = st.columns(3)
p4, p5, p6 = st.columns(3)

with p1:
    with st.container(border=True):
        st.markdown("### 🤖 Agentes")
        st.markdown(
            "Gerencie os agentes de IA da plataforma: versões, "
            "prompts, modelos e provedores (Ollama ou Claude API)."
        )

with p2:
    with st.container(border=True):
        st.markdown("### 🔎 String Optimizer")
        st.markdown(
            "Construa strings de busca otimizadas para o Scopus e "
            "refine-as iterativamente com simulação de resultados."
        )

with p3:
    with st.container(border=True):
        st.markdown("### 📋 Avaliador de Artigos")
        st.markdown(
            "Avalia a relevância de artigos científicos para um protocolo "
            "de pesquisa em duas etapas, com suporte a lote via CSV."
        )

with p4:
    with st.container(border=True):
        st.markdown("### ⚖️ AI Judge")
        st.markdown(
            "Revisa strings de busca e decisões de classificação feitas por "
            "outro modelo, retornando parecer estruturado e riscos."
        )

with p5:
    with st.container(border=True):
        st.markdown("### 🗂️ Histórico")
        st.markdown(
            "Consulte execuções anteriores do String Optimizer, do "
            "Avaliador de Artigos e do AI Judge, com entradas e saídas."
        )

with p6:
    st.empty()
