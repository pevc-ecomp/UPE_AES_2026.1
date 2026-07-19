"""Estilo visual compartilhado entre as páginas do frontend.

Chame `ui.apply_style()` logo após `st.set_page_config()` em cada página para
aplicar o mesmo refinamento visual (tipografia, botões, métricas, expanders)
por cima do tema definido em `.streamlit/config.toml`.
"""

import streamlit as st

_CSS = """
<style>
/* ── Tipografia ─────────────────────────────────────────────────────────── */
h1 {
    letter-spacing: -0.02em;
    font-weight: 750;
    padding-bottom: 0.2rem;
}
h2, h3 {
    letter-spacing: -0.01em;
    font-weight: 650;
}

/* ── Espaçamento geral ──────────────────────────────────────────────────── */
.block-container {
    padding-top: 2.4rem;
    padding-bottom: 3rem;
}

/* ── Botões ─────────────────────────────────────────────────────────────── */
.stButton > button,
.stDownloadButton > button {
    border-radius: 8px;
    font-weight: 600;
    transition: transform 0.05s ease-in-out, box-shadow 0.15s ease-in-out;
}
.stButton > button:hover,
.stDownloadButton > button:hover {
    box-shadow: 0 2px 8px rgba(30, 36, 48, 0.12);
}
.stButton > button:active,
.stDownloadButton > button:active {
    transform: scale(0.99);
}

/* ── Métricas como cartões ──────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: var(--secondary-background-color, #EEF1F6);
    border: 1px solid rgba(30, 36, 48, 0.08);
    border-radius: 10px;
    padding: 0.7rem 1rem;
}

/* ── Expanders e containers ─────────────────────────────────────────────── */
details[data-testid="stExpander"] {
    border-radius: 10px;
    overflow: hidden;
}
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 10px;
}

/* ── Sidebar ────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    border-right: 1px solid rgba(30, 36, 48, 0.08);
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    font-size: 1.05rem;
}

/* ── Tabelas / dataframes ───────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border: 1px solid rgba(30, 36, 48, 0.08);
    border-radius: 10px;
}

/* ── Abas ───────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] button[role="tab"] {
    font-weight: 600;
}

/* ── Rodapé padrão do Streamlit ─────────────────────────────────────────── */
footer {
    visibility: hidden;
}
</style>
"""


def apply_style() -> None:
    """Injeta o CSS compartilhado da plataforma na página atual."""
    st.markdown(_CSS, unsafe_allow_html=True)
