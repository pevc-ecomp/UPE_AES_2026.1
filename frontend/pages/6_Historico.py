import json

import streamlit as st

import history_store
import ui

st.set_page_config(
    page_title="Histórico",
    page_icon="🗂️",
    layout="wide",
)
ui.apply_style()

st.title("🗂️ Histórico de Execuções")
st.markdown(
    "Consulte as execuções anteriores de cada ferramenta. Os registros são "
    "persistidos em disco (volume `data/`) e sobrevivem a reinícios dos containers."
)
st.divider()


def _fmt_timestamp(record: dict) -> str:
    return str(record.get("timestamp", "—")).replace("T", " ")


def _record_json_download(kind: str, record: dict) -> None:
    st.download_button(
        "⬇️ Baixar registro (JSON)",
        data=json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8"),
        file_name=f"{kind}_{record.get('id', 'registro')}.json",
        mime="application/json",
        key=f"dl_json_{kind}_{record.get('id')}",
    )


def _file_download_buttons(kind: str, record: dict) -> None:
    for filename in record.get("files", []):
        content = history_store.load_file(kind, record.get("id", ""), filename)
        if content is None:
            st.caption(f"⚠️ Arquivo `{filename}` não encontrado no disco.")
            continue
        st.download_button(
            f"⬇️ {filename}",
            data=content,
            file_name=filename,
            mime="text/csv" if filename.endswith(".csv") else "application/octet-stream",
            key=f"dl_{kind}_{record.get('id')}_{filename}",
        )


def _delete_button(kind: str, record: dict) -> None:
    if st.button(
        "🗑️ Excluir registro",
        key=f"del_{kind}_{record.get('id')}",
        type="secondary",
    ):
        history_store.delete_record(kind, record.get("id", ""))
        st.rerun()


def _protocol_summary(protocol: dict) -> None:
    if not protocol:
        st.caption("Sem protocolo registrado.")
        return
    st.markdown(f"**Descrição da pesquisa:** {protocol.get('description', '—')}")
    if protocol.get("general_objectives"):
        st.markdown(f"**Objetivos gerais:** {protocol['general_objectives']}")
    if protocol.get("specific_objectives"):
        st.markdown(f"**Objetivos específicos:** {protocol['specific_objectives']}")
    excl = protocol.get("exclusion_criteria", [])
    incl = protocol.get("inclusion_criteria", [])
    if excl:
        st.markdown("**Critérios de exclusão:**")
        for c in excl:
            st.markdown(f"- {c}")
    if incl:
        st.markdown(f"**Critérios de inclusão** (lógica: `{protocol.get('inclusion_logic', 'ANY')}`)**:**")
        for c in incl:
            st.markdown(f"- {c}")


tab_optimizer, tab_evaluator, tab_judge = st.tabs(
    ["🔎 String Optimizer", "📋 Article Evaluator", "⚖️ AI Judge"]
)

# ── Aba 1 — String Optimizer ──────────────────────────────────────────────────
with tab_optimizer:
    records = history_store.list_records(history_store.KIND_STRING_OPTIMIZER)
    if not records:
        st.info("Nenhuma execução do String Optimizer registrada ainda.")
    for record in records:
        action = record.get("action", "optimize")
        label = "🧠 Otimização" if action == "optimize" else f"🔁 Refinamento (iteração {record.get('iteration', '?')})"
        with st.expander(f"{label} — {_fmt_timestamp(record)}"):
            st.markdown(f"**Questão de pesquisa:** {record.get('research_question', '—')}")
            if action == "optimize":
                result = record.get("result", {}) or {}
                if result.get("strategy_explanation"):
                    st.markdown(f"**Estratégia:** {result['strategy_explanation']}")
                kws = result.get("keywords_extracted", [])
                if kws:
                    st.markdown(f"**Keywords extraídas:** {', '.join(kws)}")
                for name in ("core", "expanded", "full"):
                    value = result.get(f"string_{name}", "")
                    if value:
                        st.markdown(f"**String {name}:**")
                        st.code(value, language="text")
                if record.get("active_string"):
                    st.markdown("**String ativa escolhida:**")
                    st.code(record["active_string"], language="text")
            else:
                st.markdown("**String de busca usada:**")
                st.code(record.get("search_string", ""), language="text")
                st.markdown(f"**Artigos retornados na simulação:** {record.get('articles_returned', '—')}")
            col_a, col_b = st.columns([1, 1])
            with col_a:
                _record_json_download(history_store.KIND_STRING_OPTIMIZER, record)
            with col_b:
                _delete_button(history_store.KIND_STRING_OPTIMIZER, record)

# ── Aba 2 — Article Evaluator ─────────────────────────────────────────────────
with tab_evaluator:
    records = history_store.list_records(history_store.KIND_ARTICLE_EVALUATOR)
    if not records:
        st.info("Nenhuma avaliação de artigos registrada ainda.")
    for record in records:
        mode = record.get("mode", "csv")
        is_csv = mode.startswith("csv")
        if mode == "csv_batch_api":
            label = (
                f"📦 Lote via Batch API ({record.get('batch_job_id', 'job')}) — "
                f"{record.get('evaluated', '?')} avaliado(s), {record.get('skipped', 0)} com erro"
            )
        elif is_csv:
            label = (
                f"📂 Lote CSV ({record.get('input_filename', 'arquivo')}) — "
                f"{record.get('evaluated', '?')} avaliado(s), {record.get('skipped', 0)} ignorado(s)"
            )
        else:
            article = record.get("article", {}) or {}
            label = f"✍️ Manual — {str(article.get('title', 'artigo'))[:80]}"
        with st.expander(f"{label} — {_fmt_timestamp(record)}"):
            if record.get("agent_id"):
                st.caption(f"Agente: `{record['agent_id']}`")

            st.markdown("#### 📥 Entrada do usuário")
            with st.container(border=True):
                st.markdown("**Protocolo de pesquisa**")
                _protocol_summary(record.get("research_protocol", {}) or {})
            if mode == "manual":
                article = record.get("article", {}) or {}
                with st.container(border=True):
                    st.markdown("**Artigo avaliado**")
                    st.markdown(f"**Título:** {article.get('title', '—')}")
                    if article.get("year"):
                        st.markdown(f"**Ano:** {article['year']}")
                    st.markdown(f"**Palavras-chave:** {', '.join(article.get('keywords', []))}")
                    st.markdown(f"**Abstract:** {article.get('abstract', '—')}")

            st.markdown("#### 📤 Saída do agente")
            if is_csv:
                st.caption(
                    "`input_artigos.csv` = arquivo enviado pelo usuário · "
                    "`output_avaliacao.csv` = saída do agente · "
                    "`output_avaliacao_com_judge.csv` = saída após julgamento do AI Judge (se houver)."
                )
                _file_download_buttons(history_store.KIND_ARTICLE_EVALUATOR, record)
            else:
                result = record.get("result", {}) or {}
                st.markdown(
                    f"**Score:** {result.get('score', '—')}/100 · "
                    f"**Veredicto:** `{result.get('verdict', '—')}`"
                )
                st.markdown(f"**Justificativa:** {result.get('reason', '—')}")
                if result.get("exclusion_triggered"):
                    st.markdown(f"**Critérios de exclusão acionados:** {'; '.join(result['exclusion_triggered'])}")
                if result.get("inclusion_criteria_met"):
                    st.markdown(f"**Critérios de inclusão satisfeitos:** {'; '.join(result['inclusion_criteria_met'])}")

            col_a, col_b = st.columns([1, 1])
            with col_a:
                _record_json_download(history_store.KIND_ARTICLE_EVALUATOR, record)
            with col_b:
                _delete_button(history_store.KIND_ARTICLE_EVALUATOR, record)

# ── Aba 3 — AI Judge ──────────────────────────────────────────────────────────
with tab_judge:
    records = history_store.list_records(history_store.KIND_AI_JUDGE)
    if not records:
        st.info("Nenhum julgamento do AI Judge registrado ainda.")
    _mode_labels = {
        "search_string": "🔎 Julgamento de string de busca",
        "article_classifications": "📚 Julgamento de classificações",
        "csv_batch": "📂 Julgamento em lote (CSV do avaliador)",
        "manual": "✍️ Julgamento de avaliação manual",
    }
    for record in records:
        mode = record.get("mode", "")
        label = _mode_labels.get(mode, f"⚖️ {mode or 'Julgamento'}")
        source = record.get("source", "")
        with st.expander(f"{label} — {_fmt_timestamp(record)}"):
            if source:
                st.caption(f"Origem: `{source}`")

            if mode == "search_string":
                topic = record.get("topic") or (record.get("request", {}) or {}).get("topic", "—")
                search_string = (
                    record.get("search_string")
                    or (record.get("request", {}) or {}).get("search_string", "")
                )
                st.markdown(f"**Tópico:** {topic}")
                if search_string:
                    st.markdown("**String julgada:**")
                    st.code(search_string, language="text")
                judge = record.get("judge_result", {}) or {}
                st.markdown(
                    f"**Decisão:** `{judge.get('decision', '—')}` · "
                    f"**Score final:** {judge.get('final_score', '—')}/5"
                )
                if record.get("improved_result"):
                    st.markdown("**String v2 sugerida após o julgamento:**")
                    improved = record["improved_result"] or {}
                    v2 = (
                        improved.get("string_improved")
                        or improved.get("string_expanded")
                        or improved.get("string_core")
                        or ""
                    )
                    if v2:
                        st.code(v2, language="text")
            elif mode == "csv_batch":
                stats = record.get("judge_stats", {}) or {}
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("CORRECT", stats.get("correct", 0))
                c2.metric("UNCERTAIN", stats.get("uncertain", 0))
                c3.metric("INCORRECT", stats.get("incorrect", 0))
                c4.metric("Classification_v2", stats.get("revised", 0))
                st.markdown(f"**Artigos julgados:** {record.get('articles_judged', '—')}")
                _file_download_buttons(history_store.KIND_AI_JUDGE, record)
            else:
                judge = record.get("judge_result", {}) or {}
                overall = judge.get("overall_result") or judge.get("decision", "—")
                st.markdown(f"**Resultado geral:** `{overall}`")
                if judge.get("summary"):
                    st.markdown(f"**Resumo:** {judge['summary']}")
                articles = judge.get("articles", []) or []
                for judged in articles:
                    with st.container(border=True):
                        st.markdown(f"**{judged.get('title', 'Artigo')}**")
                        st.markdown(
                            f"Veredito do juiz: `{judged.get('judge_verdict', '—')}` · "
                            f"Confiança: {judged.get('confidence_score', '—')}"
                        )
                        if judged.get("judge_justification"):
                            st.caption(judged["judge_justification"])

            col_a, col_b = st.columns([1, 1])
            with col_a:
                _record_json_download(history_store.KIND_AI_JUDGE, record)
            with col_b:
                _delete_button(history_store.KIND_AI_JUDGE, record)
