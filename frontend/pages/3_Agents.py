import os

import httpx
import streamlit as st

st.set_page_config(
    page_title="Agentes",
    page_icon="🤖",
    layout="wide",
)

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")

st.title("🤖 Agentes Disponíveis")
st.markdown("Lista de agentes de IA disponíveis nesta plataforma.")
st.divider()

# ── Busca lista de agentes ────────────────────────────────────────────────────
with st.spinner("Conectando ao backend..."):
    try:
        resp = httpx.get(f"{BACKEND_URL}/agents", timeout=10)
        resp.raise_for_status()
        agents = resp.json()
        backend_ok = True
    except Exception as exc:
        agents = []
        backend_ok = False
        backend_error = str(exc)

# ── Status do backend ─────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Status")
    if backend_ok:
        st.success(f"✅ Backend online\n\n`{BACKEND_URL}`")
    else:
        st.error(f"❌ Backend offline\n\n`{BACKEND_URL}`")
        st.caption("Verifique se o container está rodando.")

# ── Lista de agentes ──────────────────────────────────────────────────────────
if not backend_ok:
    st.error(f"Não foi possível conectar ao backend: `{backend_error}`")
    st.info("Execute `docker compose up backend` para iniciar o serviço.")
    st.stop()

if not agents:
    st.info("Nenhum agente cadastrado ainda.")
    st.stop()

st.subheader(f"{len(agents)} agente(s) cadastrado(s)")

for agent in agents:
    active = agent.get("active", False)
    status_badge = ":green[● Ativo]" if active else ":red[● Inativo]"

    with st.container(border=True):
        col_info, col_status = st.columns([5, 1])

        with col_info:
            st.markdown(f"### `{agent['name']}`")
            st.markdown(agent["description"])
            st.caption(f"Endpoint: `{agent['endpoint']}`")

        with col_status:
            st.markdown(status_badge)
