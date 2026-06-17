import json

import ollama
import streamlit as st

from scopus_agent import optimize_query, simulate_results, refine_query

st.set_page_config(
    page_title="String Optimizer",
    page_icon="🔎",
    layout="wide",
)

st.title("🔎 String Optimizer")
st.markdown(
    "Construa strings de busca otimizadas para o Scopus e simule resultados "
    "com refinamento iterativo por seleção de artigos relevantes."
)
st.divider()

# ── LLM config (sidebar) ──────────────────────────────────────────────────────
import os

OLLAMA_HOST  = os.getenv("OLLAMA_HOST",          "http://ollama:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL_PRIMARY", "phi3:mini")

with st.sidebar:
    st.header("⚙️ Configurações do LLM")
    model = st.text_input("Modelo Ollama:", value=DEFAULT_MODEL)
    st.caption(f"Host: `{OLLAMA_HOST}`")
    st.divider()
    st.markdown(
        "**Fluxo de uso:**\n"
        "1. Digite sua questão de pesquisa\n"
        "2. Gere as strings otimizadas\n"
        "3. Simule resultados\n"
        "4. Marque artigos relevantes\n"
        "5. Refine a busca (repetir)"
    )

# ── Session state ─────────────────────────────────────────────────────────────
for key, default in {
    "opt_result":     None,
    "sim_results":    [],
    "selected_ids":   [],
    "active_string":  "",
    "original_query": "",
    "iteration":      0,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def get_llm():
    return ollama.Client(host=OLLAMA_HOST)


# ── Step 1 — Research question ────────────────────────────────────────────────
st.subheader("1️⃣ String de Busca")

query = st.text_area(
    "Descreva sua questão de pesquisa em linguagem natural:",
    placeholder="Ex: machine learning techniques for predicting hospital readmission in elderly patients",
    height=100,
)

optimize_btn = st.button("🧠 Otimizar query para Scopus", type="primary", use_container_width=True)

if optimize_btn:
    if not query.strip():
        st.warning("Digite uma questão de pesquisa.")
        st.stop()

    with st.status("Otimizando string de busca...", expanded=True) as status:
        try:
            result = optimize_query(get_llm(), model, query, on_step=st.write)
            st.session_state.opt_result     = result
            st.session_state.original_query = query
            _rec = result.get("recommended_string") or "expanded"
            st.session_state.active_string = (
                result.get(f"string_{_rec}")
                or result.get("string_expanded")
                or result.get("string_core")
                or ""
            )
            st.session_state.sim_results  = []
            st.session_state.selected_ids = []
            st.session_state.iteration    = 1
            status.update(label="String otimizada com sucesso!", state="complete", expanded=False)
        except Exception as e:
            status.update(label="Erro na otimização", state="error", expanded=True)
            st.error(f"Erro ao otimizar query: {e}")
            st.stop()

# ── Step 2 — Optimized strings ────────────────────────────────────────────────
if st.session_state.opt_result:
    opt = st.session_state.opt_result
    st.divider()
    st.subheader("2️⃣ Strings Otimizadas")

    st.info(f"**Estratégia:** {opt.get('strategy_explanation', '')}")

    kw_col, auth_col = st.columns(2)
    with kw_col:
        st.markdown("**Keywords extraídas:**")
        st.write(", ".join(opt.get("keywords_extracted", [])))
    with auth_col:
        st.markdown("**Autores de referência:**")
        for a in opt.get("reference_authors", []):
            if isinstance(a, dict):
                name = a.get("name") or a.get("author") or a.get("surname") or str(a)
                reason = a.get("reason") or a.get("justification") or ""
                st.caption(f"• **{name}** — {reason}")

    st.markdown("---")
    tab_core, tab_exp, tab_full = st.tabs(["Core", "Expanded", "Full"])

    with tab_core:
        st.code(opt.get("string_core", ""), language="text")
    with tab_exp:
        st.code(opt.get("string_expanded", ""), language="text")
    with tab_full:
        st.code(opt.get("string_full", ""), language="text")

    rec_name = opt.get("recommended_string") or "expanded"
    rec_string = (
        opt.get(f"string_{rec_name}")
        or opt.get("string_expanded")
        or opt.get("string_core")
        or ""
    )
    with st.container(border=True):
        st.markdown(
            f"**String recomendada** (`{rec_name}`) — {opt.get('recommended_reason', '')}"
        )
        st.code(rec_string, language="text")

    # Allow the user to edit the active string before simulating
    st.session_state.active_string = st.text_area(
        "String ativa (editável antes de simular):",
        value=st.session_state.active_string,
        height=80,
        key=f"active_string_input_{st.session_state.iteration}",
    )

    simulate_btn = st.button(
        "📄 Simular resultados Scopus", type="secondary", use_container_width=True
    )

    if simulate_btn:
        with st.status("Simulando resultados Scopus...", expanded=True) as status:
            try:
                sim = simulate_results(get_llm(), model, st.session_state.active_string, on_step=st.write)
                results = sim.get("results", [])
                if not results:
                    raise ValueError(f"O modelo não retornou artigos. Resposta recebida: {sim}")
                st.session_state.sim_results  = results
                st.session_state.selected_ids = []
                status.update(
                    label=f"Resultados simulados com sucesso! ({len(results)} artigos)",
                    state="complete",
                    expanded=False,
                )
            except Exception as e:
                status.update(label="Erro na simulação", state="error", expanded=True)
                st.error(f"Erro ao simular resultados: {e}")
                st.stop()
        st.rerun()

# ── Step 3 — Simulated results ────────────────────────────────────────────────
if st.session_state.sim_results:
    st.divider()
    st.subheader("3️⃣ Resultados Simulados")
    st.caption(
        f"Iteração {st.session_state.iteration} · "
        f"{len(st.session_state.sim_results)} resultado(s)"
    )

    selected = []
    for paper in st.session_state.sim_results:
        pid   = paper.get("id", "")
        year  = paper.get("year", "—")
        cites = paper.get("citations", 0)
        title = paper.get("title", "Sem título")
        authors_str = "; ".join(paper.get("authors", []))
        journal     = paper.get("journal", "—")
        snippet     = paper.get("abstract_snippet", "")
        kws         = ", ".join(paper.get("keywords", []))
        doi         = paper.get("doi", "")

        with st.container(border=True):
            left, right = st.columns([5, 1])
            with left:
                checked = st.checkbox(
                    f"**{title}**",
                    key=f"paper_{pid}_{st.session_state.iteration}",
                    value=(pid in st.session_state.selected_ids),
                )
                st.caption(
                    f"{authors_str} · *{journal}* · {year} · "
                    f"DOI: `{doi}` · Citações: {cites}"
                )
                st.markdown(snippet)
                if kws:
                    st.caption(f"Keywords: {kws}")
            with right:
                if cites >= 100:
                    st.metric("Citações", cites, delta="alta")
                else:
                    st.metric("Citações", cites)
            if checked:
                selected.append(pid)

    st.session_state.selected_ids = selected

    st.divider()

    n_sel = len(selected)
    if n_sel:
        st.success(f"{n_sel} artigo(s) marcado(s) como relevante(s).")
    else:
        st.warning(
            "Nenhum artigo selecionado. Ao refinar, o agente fará um pivot de abordagem."
        )

    refine_btn = st.button(
        "🔁 Refinar busca com base na seleção", type="primary", use_container_width=True
    )

    if refine_btn:
        with st.status("Refinando string de busca...", expanded=True) as status:
            try:
                refined = refine_query(
                    get_llm(),
                    model,
                    st.session_state.original_query,
                    st.session_state.active_string,
                    st.session_state.selected_ids,
                    st.session_state.sim_results,
                    on_step=st.write,
                )
                st.session_state.opt_result    = refined
                _rec = refined.get("recommended_string") or "expanded"
                st.session_state.active_string = (
                    refined.get(f"string_{_rec}")
                    or refined.get("string_expanded")
                    or refined.get("string_core")
                    or ""
                )
                st.session_state.sim_results  = []
                st.session_state.selected_ids = []
                st.session_state.iteration   += 1
                status.update(label="String refinada com sucesso!", state="complete", expanded=False)
                st.rerun()
            except Exception as e:
                status.update(label="Erro no refinamento", state="error", expanded=True)
                st.error(f"Erro ao refinar query: {e}")

    # ── Export ────────────────────────────────────────────────────────────────
    st.divider()
    export_data = {
        "iteration":      st.session_state.iteration,
        "original_query": st.session_state.original_query,
        "active_string":  st.session_state.active_string,
        "optimization":   st.session_state.opt_result,
        "results":        st.session_state.sim_results,
        "selected_ids":   st.session_state.selected_ids,
    }
    st.download_button(
        label="⬇️ Exportar sessão (JSON)",
        data=json.dumps(export_data, ensure_ascii=False, indent=2),
        file_name="scopus_agent_session.json",
        mime="application/json",
        use_container_width=True,
    )
