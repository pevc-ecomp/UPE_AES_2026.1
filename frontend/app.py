import os
import streamlit as st
from utils import get_client, list_collections

st.set_page_config(
    page_title="Research Assistant",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Cabeçalho ────────────────────────────────────────────────────────────────
st.title("🔬 Scientific Research Assistant")
st.markdown("Plataforma de apoio à revisão de literatura científica.")
st.divider()

# ── Status dos serviços ──────────────────────────────────────────────────────
st.subheader("🖥️ Status dos Serviços")

col_chroma, col_backend, col_ollama = st.columns(3)

with col_chroma:
    client = get_client()
    if client:
        collections = list_collections(client)
        st.success("✅ Chroma — online")
        st.caption(f"{len(collections)} coleção(ões) disponível(is)")
    else:
        st.error("❌ Chroma — offline")
        st.caption("Verifique se o container está rodando")

with col_backend:
    backend_url = os.getenv("BACKEND_URL", "http://backend:8000")
    st.info(f"⚙️ Backend\n\n`{backend_url}`")

with col_ollama:
    ollama_host = os.getenv("OLLAMA_HOST", "http://ollama:11434")
    model = os.getenv("OLLAMA_MODEL_PRIMARY", "phi3:mini")
    st.info(f"🦙 Ollama\n\n`{model}`")

st.divider()

# ── Coleções existentes ───────────────────────────────────────────────────────
if client:
    collections = list_collections(client)
    if collections:
        st.subheader("📚 Coleções no Vector Store")
        cols = st.columns(min(len(collections), 4))
        for i, name in enumerate(collections):
            with cols[i % 4]:
                col = client.get_collection(name)
                with st.container(border=True):
                    st.markdown(f"**{name}**")
                    st.caption(f"{col.count()} documento(s)")
        st.divider()

# ── Descrição das páginas ────────────────────────────────────────────────────
st.subheader("📋 Páginas disponíveis")

p1, p2, p3 = st.columns(3)

with p1:
    with st.container(border=True):
        st.markdown("### 🏠 Home")
        st.markdown(
            "Esta página. Mostra o status dos serviços e as "
            "coleções existentes no vector store."
        )

with p2:
    with st.container(border=True):
        st.markdown("### 🔍 Query Chroma")
        st.markdown(
            "Busca semântica em documentos indexados. "
            "Digite qualquer texto e veja os resultados mais similares."
        )

with p3:
    with st.container(border=True):
        st.markdown("### 📄 Upload PDF")
        st.markdown(
            "Faça upload de PDFs para indexar no Chroma. "
            "O texto é extraído, dividido em chunks e vetorizado automaticamente."
        )
