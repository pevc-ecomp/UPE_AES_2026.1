import json
import os

import httpx
import ollama
import streamlit as st

from ai_judge_client import get_ai_judge_status, judge_search_string
from scopus_agent import improve_query_with_judge_feedback, optimize_query, simulate_results, refine_query
from text_analysis import compute_tfidf, compute_term_weights

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
OLLAMA_HOST           = os.getenv("OLLAMA_HOST",            "http://ollama:11434")
BACKEND_URL           = os.getenv("BACKEND_URL",            "http://backend:8000")
IA_JUDGE_URL          = os.getenv("IA_JUDGE_URL",           "http://localhost:8002")
DEFAULT_MODEL         = os.getenv("OLLAMA_MODEL_PRIMARY",   "phi3:mini")
DEFAULT_FALLBACK_MODEL = os.getenv("OLLAMA_MODEL_FALLBACK", "llama3.2:1b")

with st.sidebar:
    st.header("🤖 Agente")

    selected_agent_id  = None
    system_prompt      = None  # None → optimize_query usa OPTIMIZE_PROMPT (curto, compatível com phi3:mini)
    agent_models       = [DEFAULT_MODEL, DEFAULT_FALLBACK_MODEL]
    agent_temperature  = 0.2

    backend_reachable = True
    backend_error = None
    try:
        agents_resp = httpx.get(f"{BACKEND_URL}/agents", timeout=10)
        all_agents  = agents_resp.json() if agents_resp.status_code == 200 else []
        agents_list = [a for a in all_agents if a.get("agent_type") == "scopus-agent"]
    except Exception as exc:
        agents_list = []
        backend_reachable = False
        backend_error = str(exc)

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
            system_prompt     = active_ver["system_prompt"]
            agent_models      = [active_ver["model_primary"], active_ver["model_fallback"]]
            agent_temperature = active_ver["temperature"]
            st.caption(
                f"Versão: **{active_ver['version_name']}**\n\n"
                f"Modelo: `{active_ver['model_primary']}`\n\n"
                f"Temp: `{active_ver['temperature']}`"
            )
        else:
            st.warning("Agente sem versão ativa — usando configuração padrão.")
    elif not backend_reachable:
        st.error(f"Backend offline em `{BACKEND_URL}` — usando configuração padrão. Detalhe: {backend_error}")
    else:
        st.warning(
            "Nenhum agente 'scopus-agent' encontrado no backend — usando configuração padrão. "
            "Para configurar, reinicie o container do backend: "
            "`docker compose build backend && docker compose up -d backend`"
        )

    st.caption(f"Host Ollama: `{OLLAMA_HOST}`")
    judge_ok, judge_message = get_ai_judge_status()
    st.caption(f"AI Judge: `{IA_JUDGE_URL}`")
    if judge_ok:
        st.success("AI Judge online")
    else:
        st.warning("AI Judge offline")
        st.caption(judge_message)
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
    "opt_result":        None,
    "sim_results":       [],
    "selected_ids":      [],
    "active_string":     "",
    "original_query":    "",
    "iteration":         0,
    "tfidf_data":        None,
    "term_weights":      [],
    "suggested_string":  "",
    "judge_result":      None,
    "judge_improved_result": None,
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
            result = optimize_query(
                get_llm(), agent_models, query,
                system_prompt=system_prompt,
                temperature=agent_temperature,
                on_step=st.write,
            )
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
            st.session_state.judge_result = None
            st.session_state.judge_improved_result = None
            status.update(label="String otimizada com sucesso!", state="complete", expanded=False)
        except Exception as e:
            status.update(label="Erro na otimização", state="error", expanded=True)
            st.error(f"Erro ao otimizar query: {e}")
            st.stop()
    st.rerun()

# ── Step 2 — Optimized strings ────────────────────────────────────────────────
if st.session_state.opt_result:
    opt = st.session_state.opt_result
    st.divider()
    st.subheader("2️⃣ Strings Otimizadas")

    if not opt.get("string_core"):
        st.warning(
            "O modelo não gerou as strings de busca. "
            "Tente novamente ou verifique se o Ollama está respondendo corretamente."
        )
        with st.expander("Resposta bruta do modelo"):
            st.json(opt)

    st.info(f"**Estratégia:** {opt.get('strategy_explanation', '—')}")

    kw_col, auth_col = st.columns(2)
    with kw_col:
        st.markdown("**Keywords extraídas:**")
        st.write(", ".join(opt.get("keywords_extracted", [])))
    with auth_col:
        st.markdown("**Autores de referência:**")
        for a in opt.get("reference_authors", []):
            if isinstance(a, dict):
                name   = a.get("name") or a.get("author") or a.get("surname") or str(a)
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

    st.session_state.active_string = st.text_area(
        "String ativa (editável antes de simular):",
        value=st.session_state.active_string,
        height=80,
        key=f"active_string_input_{st.session_state.iteration}",
    )

    judge_col, simulate_col = st.columns(2)
    with judge_col:
        judge_btn = st.button(
            "⚖️ Julgar string com AI Judge",
            type="secondary",
            use_container_width=True,
            disabled=not judge_ok,
        )
    with simulate_col:
        simulate_btn = st.button(
            "📄 Simular resultados Scopus", type="secondary", use_container_width=True
        )

    if judge_btn:
        with st.status("Enviando string para julgamento...", expanded=True) as status:
            try:
                st.write("Avaliando cobertura conceitual, sinônimos e operadores booleanos...")
                st.session_state.judge_result = judge_search_string(
                    topic=st.session_state.original_query or query,
                    search_string=st.session_state.active_string,
                    database="Scopus",
                )
                st.session_state.judge_improved_result = None
                if st.session_state.judge_result.get("decision") == "REVISE":
                    st.write("O juiz sugeriu revisão; gerando automaticamente uma string_v2...")
                    st.session_state.judge_improved_result = improve_query_with_judge_feedback(
                        get_llm(),
                        agent_models,
                        st.session_state.original_query or query,
                        st.session_state.active_string,
                        st.session_state.judge_result,
                        system_prompt=system_prompt,
                        temperature=agent_temperature,
                        on_step=st.write,
                    )
                status.update(
                    label="Julgamento concluído com sucesso!",
                    state="complete",
                    expanded=False,
                )
            except Exception as e:
                st.session_state.judge_result = None
                st.session_state.judge_improved_result = None
                status.update(label="Erro no julgamento", state="error", expanded=True)
                st.error(str(e))

    if simulate_btn:
        with st.status("Simulando resultados Scopus...", expanded=True) as status:
            try:
                sim = simulate_results(
                    get_llm(), agent_models, st.session_state.active_string,
                    system_prompt=system_prompt,
                    temperature=agent_temperature,
                    on_step=st.write,
                )
                results = sim.get("results", [])
                if not results:
                    raise ValueError(f"O modelo não retornou artigos. Resposta recebida: {sim}")
                st.session_state.sim_results      = results
                st.session_state.selected_ids    = []
                st.session_state.term_weights    = []
                st.session_state.suggested_string = ""
                st.write("Aplicando lematização e remoção de stop words...")
                st.session_state.tfidf_data = compute_tfidf(results)
                st.write("TF-IDF calculado sobre os artigos retornados.")
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

    if st.session_state.judge_result:
        judge = st.session_state.judge_result
        st.markdown("---")
        st.subheader("Parecer do AI as Judge")
        st.success(
            f"Decisão: {judge.get('decision', '—')} · Score final: {judge.get('final_score', '—')}/5"
        )

        criteria = judge.get("criteria", {})
        if criteria:
            crit_cols = st.columns(2)
            for index, (name, values) in enumerate(criteria.items()):
                score = values.get("score", "—")
                justification = values.get("justification", "")
                with crit_cols[index % 2]:
                    with st.container(border=True):
                        st.markdown(f"**{name}**")
                        st.metric("Score", score)
                        st.caption(justification or "Sem justificativa informada.")

        problems = judge.get("identified_problems", [])
        suggestions = judge.get("improvement_suggestions", [])

        if problems:
            st.markdown("**Problemas identificados**")
            for problem in problems:
                st.warning(problem)

        if suggestions:
            st.markdown("**Sugestões de melhoria**")
            for suggestion in suggestions:
                st.info(suggestion)

        with st.expander("Ver JSON bruto do julgamento"):
            st.json(judge)

        improved = st.session_state.judge_improved_result
        if judge.get("decision") == "REVISE" and improved:
            st.markdown("---")
            st.subheader("String_v2 gerada com feedback do juiz")
            st.info(f"**Estratégia revisada:** {improved.get('strategy_explanation', '—')}")

            improved_rec_name = improved.get("recommended_string") or "expanded"
            improved_rec_string = (
                improved.get(f"string_{improved_rec_name}")
                or improved.get("string_expanded")
                or improved.get("string_core")
                or ""
            )

            v2_core, v2_expanded, v2_full = st.tabs(["Core v2", "Expanded v2", "Full v2"])
            with v2_core:
                st.code(improved.get("string_core", ""), language="text")
            with v2_expanded:
                st.code(improved.get("string_expanded", ""), language="text")
            with v2_full:
                st.code(improved.get("string_full", ""), language="text")

            with st.container(border=True):
                st.markdown(
                    f"**String_v2 recomendada** (`{improved_rec_name}`) — "
                    f"{improved.get('recommended_reason', '')}"
                )
                st.code(improved_rec_string, language="text")

            use_v2_btn = st.button(
                "Usar string_v2 como ativa",
                type="primary",
                use_container_width=True,
            )
            if use_v2_btn:
                st.session_state.opt_result = improved
                st.session_state.active_string = improved_rec_string
                st.session_state.sim_results = []
                st.session_state.selected_ids = []
                st.session_state.term_weights = []
                st.session_state.suggested_string = ""
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
        pid         = paper.get("id", "")
        year        = paper.get("year", "—")
        cites       = paper.get("citations", 0)
        title       = paper.get("title", "Sem título")
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

    analyze_btn = st.button(
        "📊 Calcular pesos dos termos", type="primary", use_container_width=True,
        disabled=(not st.session_state.tfidf_data),
    )

    if analyze_btn:
        if not st.session_state.selected_ids:
            st.warning("Selecione ao menos um artigo relevante antes de calcular os pesos.")
        else:
            weights = compute_term_weights(
                st.session_state.tfidf_data,
                st.session_state.sim_results,
                set(st.session_state.selected_ids),
            )
            st.session_state.term_weights = weights
            # Build suggested string from top positive-weight terms
            top_terms = [orig for _, w, orig in weights if w > 0][:8]
            if top_terms:
                terms_expr = " OR ".join(f'"{t}"' for t in top_terms)
                st.session_state.suggested_string = (
                    f"({st.session_state.active_string}) AND TITLE-ABS-KEY({terms_expr})"
                )
            else:
                st.session_state.suggested_string = st.session_state.active_string
            st.rerun()

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

# ── Step 4 — Term weights & string suggestion ─────────────────────────────────
if st.session_state.term_weights:
    import pandas as pd

    st.divider()
    st.subheader("4️⃣ Pesos dos Termos e Refinamento de String")

    weights = st.session_state.term_weights
    positive = [(orig, w) for _, w, orig in weights if w > 0]
    negative = [(orig, w) for _, w, orig in weights if w <= 0]

    col_pos, col_neg = st.columns(2)

    with col_pos:
        st.markdown("**Termos com peso positivo** (favorecem relevância)")
        if positive:
            df_pos = pd.DataFrame(
                [{"Termo": orig, "Peso": round(w, 4)} for orig, w in positive[:15]],
            )
            st.dataframe(df_pos, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum termo com peso positivo.")

    with col_neg:
        st.markdown("**Termos com peso negativo** (associados a não-relevantes)")
        if negative:
            df_neg = pd.DataFrame(
                [{"Termo": orig, "Peso": round(w, 4)} for orig, w in negative[:15]],
            )
            st.dataframe(df_neg, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum termo com peso negativo.")

    st.markdown("---")
    st.markdown("**String de busca sugerida** (editável)")
    st.caption(
        "Os termos com maiores pesos positivos foram adicionados à string ativa. "
        "Edite abaixo antes de refazer a busca."
    )

    import streamlit.components.v1 as components

    col_text, col_btn = st.columns([10, 1])
    with col_text:
        new_string = st.text_area(
            "String sugerida:",
            value=st.session_state.suggested_string,
            height=100,
            key=f"suggested_string_input_{st.session_state.iteration}",
            label_visibility="collapsed",
        )
    with col_btn:
        st.write("")  # alinhamento vertical
        st.write("")
        copy_clicked = st.button(
            "📋",
            help="Copiar string para a área de transferência",
            use_container_width=True,
            key=f"copy_btn_{st.session_state.iteration}",
        )

    if copy_clicked:
        components.html(
            f"""<script>
            (async () => {{
                try {{
                    await window.parent.navigator.clipboard.writeText({json.dumps(new_string)});
                }} catch (e) {{
                    const el = window.parent.document.createElement('textarea');
                    el.value = {json.dumps(new_string)};
                    window.parent.document.body.appendChild(el);
                    el.select();
                    window.parent.document.execCommand('copy');
                    window.parent.document.body.removeChild(el);
                }}
            }})();
            </script>""",
            height=0,
        )
        st.toast("✅ String copiada para a área de transferência!")

    redo_btn = st.button(
        "🔄 Refazer busca com a nova string", type="primary", use_container_width=True
    )

    if redo_btn:
        with st.status("Simulando resultados com a nova string...", expanded=True) as status:
            try:
                st.session_state.active_string = new_string
                sim = simulate_results(
                    get_llm(), agent_models, new_string,
                    system_prompt=system_prompt,
                    temperature=agent_temperature,
                    on_step=st.write,
                )
                results = sim.get("results", [])
                if not results:
                    raise ValueError(f"O modelo não retornou artigos. Resposta: {sim}")
                st.session_state.sim_results      = results
                st.session_state.selected_ids    = []
                st.session_state.term_weights    = []
                st.session_state.suggested_string = ""
                st.write("Aplicando lematização e remoção de stop words...")
                st.session_state.tfidf_data = compute_tfidf(results)
                st.write("TF-IDF calculado sobre os novos artigos.")
                st.session_state.iteration += 1
                status.update(
                    label=f"Nova busca concluída! ({len(results)} artigos · iteração {st.session_state.iteration})",
                    state="complete",
                    expanded=False,
                )
            except Exception as e:
                status.update(label="Erro na simulação", state="error", expanded=True)
                st.error(f"Erro ao refazer busca: {e}")
                st.stop()
        st.rerun()
