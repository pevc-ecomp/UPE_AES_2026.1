import json
import os

import httpx
import streamlit as st

import history_store
import ui

st.set_page_config(
    page_title="AI Judge",
    page_icon="⚖️",
    layout="wide",
)
ui.apply_style()

IA_JUDGE_URL = os.getenv("IA_JUDGE_URL", "http://localhost:8002")


def _normalize_multiline(value: str) -> str:
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    return "\n".join(lines)


def _status_check() -> tuple[bool, str]:
    try:
        response = httpx.get(IA_JUDGE_URL, timeout=5)
        response.raise_for_status()
        payload = response.json()
        return True, payload.get("message", "AI Judge online")
    except Exception as exc:
        return False, str(exc)


def _post_json(path: str, payload: dict) -> dict | None:
    try:
        response = httpx.post(
            f"{IA_JUDGE_URL}{path}",
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        try:
            detail = exc.response.json()
        except Exception:
            pass
        st.error(f"Erro do AI Judge: {detail}")
    except Exception as exc:
        st.error(f"Erro de conexão com o AI Judge: {exc}")
    return None


def _init_article_state() -> None:
    if "judge_articles" not in st.session_state:
        st.session_state.judge_articles = [
            {
                "title": "",
                "abstract": "",
                "model_classification": "INCLUDE",
                "model_justification": "",
            }
        ]


def _render_article_inputs() -> None:
    articles = st.session_state.judge_articles
    to_remove = None

    for index, article in enumerate(articles):
        with st.container(border=True):
            top_left, top_right = st.columns([6, 1])
            with top_left:
                st.markdown(f"**Artigo {index + 1}**")
            with top_right:
                if len(articles) > 1 and st.button("Remover", key=f"judge_remove_{index}"):
                    to_remove = index

            st.text_input(
                "Título",
                key=f"judge_title_{index}",
                value=article["title"],
                max_chars=1000,
            )
            st.text_area(
                "Abstract",
                key=f"judge_abstract_{index}",
                value=article["abstract"],
                height=180,
                max_chars=10000,
            )

            col_class, col_reason = st.columns([1, 2])
            with col_class:
                current_class = article["model_classification"]
                options = ["RELATED", "UNSURE", "NOT-RELATED", "INCLUDE", "EXCLUDE", "MAYBE"]
                current_index = options.index(current_class) if current_class in options else 0
                st.selectbox(
                    "Classificação do modelo",
                    options=options,
                    index=current_index,
                    key=f"judge_classification_{index}",
                )
            with col_reason:
                st.text_area(
                    "Justificativa do modelo",
                    key=f"judge_justification_{index}",
                    value=article["model_justification"],
                    height=100,
                )

    if to_remove is not None:
        articles.pop(to_remove)
        st.rerun()


def _collect_articles() -> list[dict]:
    articles = []
    for index, original in enumerate(st.session_state.judge_articles):
        article = {
            "title": st.session_state.get(f"judge_title_{index}", original["title"]).strip(),
            "abstract": st.session_state.get(f"judge_abstract_{index}", original["abstract"]).strip(),
            "model_classification": st.session_state.get(
                f"judge_classification_{index}",
                original["model_classification"],
            ),
            "model_justification": st.session_state.get(
                f"judge_justification_{index}",
                original["model_justification"],
            ).strip(),
        }
        articles.append(article)
    st.session_state.judge_articles = articles
    return articles


_init_article_state()

st.title("⚖️ AI as Judge")
st.markdown(
    "Use o serviço de julgamento para revisar strings de busca e verificar "
    "decisões de classificação de artigos feitas por outro modelo."
)
st.divider()

with st.sidebar:
    st.header("Status")
    judge_ok, judge_message = _status_check()
    st.caption(f"URL configurada: `{IA_JUDGE_URL}`")
    if judge_ok:
        st.success("✅ AI Judge online")
        st.caption(judge_message)
    else:
        st.error("❌ AI Judge offline")
        st.caption(judge_message)

    st.divider()
    st.markdown(
        "**Fluxo sugerido**\n"
        "1. Gere uma string ou classificação no sistema principal\n"
        "2. Cole o resultado nesta aba\n"
        "3. Rode o julgamento\n"
        "4. Revise problemas, riscos e sugestões"
    )

tab_string, tab_articles = st.tabs(
    ["🔎 Julgar string de busca", "📚 Julgar classificação de artigos"]
)

with tab_string:
    st.subheader("Avaliação de string de busca")
    st.caption(
        "Envie a sua query para o AI Judge verificar cobertura conceitual, "
        "sinônimos, operadores booleanos, compatibilidade com a base, recall e precisão."
    )

    with st.form("judge_string_form"):
        topic = st.text_area(
            "Tema da revisão *",
            placeholder="Ex: Fault tolerance techniques applied to IoT systems",
            height=100,
        )
        col_database, _ = st.columns([1, 2])
        with col_database:
            database = st.selectbox(
                "Base-alvo",
                options=["Scopus", "IEEE", "ACM", "Web of Science", "Outra"],
                index=0,
            )
        search_string = st.text_area(
            "String de busca *",
            placeholder='Ex: ("fault tolerance" OR "fault tolerant") AND (IoT OR "Internet of Things")',
            height=180,
        )
        submit_string = st.form_submit_button(
            "Julgar string",
            type="primary",
            use_container_width=True,
        )

    if submit_string:
        errors = []
        if not topic.strip():
            errors.append("Informe o tema da revisão.")
        if not search_string.strip():
            errors.append("Informe a string de busca.")
        if not judge_ok:
            errors.append("O AI Judge está offline.")

        if errors:
            for error in errors:
                st.error(error)
        else:
            payload = {
                "topic": topic.strip(),
                "database": database.strip(),
                "search_string": search_string.strip(),
            }
            with st.spinner("Julgando string de busca..."):
                result = _post_json("/judge/string", payload)

            if result:
                history_store.save_record(
                    history_store.KIND_AI_JUDGE,
                    {
                        "mode": "search_string",
                        "source": "ai_judge_page",
                        "request": payload,
                        "judge_result": result,
                    },
                )
                st.success(
                    f"Decisão: {result.get('decision', '—')} · Score final: {result.get('final_score', '—')}/5"
                )

                criteria = result.get("criteria", {})
                if criteria:
                    st.markdown("**Critérios avaliados**")
                    cols = st.columns(2)
                    for index, (name, values) in enumerate(criteria.items()):
                        score = values.get("score", "—")
                        justification = values.get("justification", "")
                        with cols[index % 2]:
                            with st.container(border=True):
                                st.markdown(f"**{name}**")
                                st.metric("Score", score)
                                st.caption(justification or "Sem justificativa informada.")

                problems = result.get("identified_problems", [])
                suggestions = result.get("improvement_suggestions", [])

                if problems:
                    st.markdown("**Problemas identificados**")
                    for problem in problems:
                        st.warning(problem)

                if suggestions:
                    st.markdown("**Sugestões de melhoria**")
                    for suggestion in suggestions:
                        st.info(suggestion)

                with st.expander("Ver JSON bruto"):
                    st.json(result)

with tab_articles:
    st.subheader("Revisão de classificações de artigos")
    st.caption(
        "Informe o objetivo da revisão, os critérios e as decisões produzidas pelo seu modelo. "
        "O AI Judge retorna um parecer estruturado sobre a consistência dessas classificações."
    )

    objective = st.text_area(
        "Objetivo da revisão *",
        placeholder="Ex: Identify fault tolerance techniques applied to IoT systems.",
        height=100,
    )

    col_inc, col_exc = st.columns(2)
    with col_inc:
        inclusion_criteria = st.text_area(
            "Critérios de inclusão",
            placeholder="Um critério por linha",
            height=140,
        )
    with col_exc:
        exclusion_criteria = st.text_area(
            "Critérios de exclusão",
            placeholder="Um critério por linha",
            height=140,
        )

    st.markdown("**Artigos e classificações do modelo**")
    _render_article_inputs()

    controls_left, controls_right = st.columns([1, 2])
    with controls_left:
        if st.button("Adicionar artigo", use_container_width=True):
            _collect_articles()
            st.session_state.judge_articles.append(
                {
                    "title": "",
                    "abstract": "",
                    "model_classification": "INCLUDE",
                    "model_justification": "",
                }
            )
            st.rerun()
    with controls_right:
        run_article_judge = st.button(
            "Julgar classificações",
            type="primary",
            use_container_width=True,
        )

    if run_article_judge:
        articles = _collect_articles()
        errors = []

        if not objective.strip():
            errors.append("Informe o objetivo da revisão.")
        if not judge_ok:
            errors.append("O AI Judge está offline.")

        cleaned_articles = []
        for position, article in enumerate(articles, start=1):
            if not article["title"]:
                errors.append(f"O artigo {position} está sem título.")
            if not article["abstract"]:
                errors.append(f"O artigo {position} está sem abstract.")
            cleaned_articles.append(article)

        if errors:
            for error in errors:
                st.error(error)
        else:
            payload = {
                "review_objective": objective.strip(),
                "inclusion_criteria": _normalize_multiline(inclusion_criteria),
                "exclusion_criteria": _normalize_multiline(exclusion_criteria),
                "articles": cleaned_articles,
            }

            with st.spinner("Julgando classificações dos artigos..."):
                result = _post_json("/judge/articles", payload)

            if result:
                history_store.save_record(
                    history_store.KIND_AI_JUDGE,
                    {
                        "mode": "article_classifications",
                        "source": "ai_judge_page",
                        "request": payload,
                        "judge_result": result,
                    },
                )
                st.success(f"Resultado geral: {result.get('overall_result', '—')}")

                summary = result.get("summary", "")
                if summary:
                    st.info(summary)

                for article in result.get("articles", []):
                    with st.container(border=True):
                        st.markdown(f"**{article.get('title', 'Sem título')}**")
                        left, right = st.columns([1, 1])
                        with left:
                            st.markdown(
                                f"Classificação do modelo: `{article.get('model_classification', '—')}`"
                            )
                            st.markdown(
                                f"Veredito do juiz: `{article.get('judge_verdict', '—')}`"
                            )
                        with right:
                            st.metric(
                                "Confiança",
                                article.get("confidence_score", "—"),
                            )
                            st.markdown(
                                "Revisão humana recomendada: "
                                f"`{article.get('human_review_recommended', True)}`"
                            )

                        justification = article.get("judge_justification", "")
                        st.markdown("**Justificativa do juiz**")
                        st.write(justification or "Sem justificativa informada.")

                risks = result.get("main_risks", [])
                if risks:
                    st.markdown("**Principais riscos**")
                    for risk in risks:
                        st.warning(risk)

                with st.expander("Ver JSON bruto"):
                    st.json(result)

st.divider()
st.caption(
    "Dica: para integrar completamente com o fluxo principal, o próximo passo é fazer "
    "o backend enviar automaticamente para o AI Judge o resultado produzido pelos agentes."
)
