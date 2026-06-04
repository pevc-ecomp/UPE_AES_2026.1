import streamlit as st
from utils import get_client, get_or_create_collection, list_collections
from query_enhancer import enhance_query, display_enhancement_info

st.set_page_config(
    page_title="Query Chroma",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 Busca no Vector Store")
st.markdown("Busca semântica por similaridade entre documentos indexados.")
st.divider()

# ── Conexão ───────────────────────────────────────────────────────────────────
client = get_client()
if not client:
    st.error("❌ Chroma indisponível. Verifique se o container está rodando.")
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configurações")

    collections = list_collections(client)

    if not collections:
        st.warning("Nenhuma coleção encontrada.\nFaça upload de um PDF primeiro.")
        collection_name = "documents"
    else:
        collection_name = st.selectbox("Coleção:", options=collections)

    n_results = st.slider("Número de resultados:", min_value=1, max_value=20, value=5)

    st.divider()
    st.subheader("🚀 Query Enhancement")
    use_enhancement = st.checkbox(
        "Melhorar query automaticamente",
        value=False,
        help="Adiciona keywords, sinônimos e pesquisadores à sua busca",
    )

    if use_enhancement:
        col_keywords = st.checkbox("Keywords", value=True)
        col_synonyms = st.checkbox("Sinônimos", value=True)
        col_researchers = st.checkbox("Pesquisadores", value=True)
    else:
        col_keywords = col_synonyms = col_researchers = False

    st.divider()
    if collections:
        col = client.get_collection(collection_name)
        st.metric("Documentos na coleção", col.count())

# ── Query ─────────────────────────────────────────────────────────────────────
query = st.text_area(
    "Digite sua busca:",
    placeholder="Ex: redes neurais para previsão de emissões de CO2",
    height=120,
)

search_btn = st.button("🔍 Buscar", type="primary", use_container_width=True)

if search_btn:
    if not query.strip():
        st.warning("Digite algo para buscar.")
        st.stop()

    if not collections:
        st.warning("Nenhuma coleção disponível. Faça upload de um PDF primeiro.")
        st.stop()

    # ── Melhoria da query (se ativado) ────────────────────────────────────────
    enhancement_result = None
    search_query = query

    if use_enhancement:
        with st.spinner("🚀 Melhorando sua query..."):
            try:
                enhancement_result = enhance_query(
                    query,
                    include_keywords=col_keywords,
                    include_synonyms=col_synonyms,
                    include_researchers=col_researchers,
                )
                search_query = enhancement_result["enhanced_query"]
                st.info(f"✨ Query expandida para melhor busca")
            except Exception as e:
                st.warning(f"Não foi possível melhorar a query: {e}")
                search_query = query

    # ── Busca ─────────────────────────────────────────────────────────────────
    with st.spinner("Buscando documentos similares..."):
        try:
            collection = get_or_create_collection(client, collection_name)
            total = collection.count()

            if total == 0:
                st.info("A coleção está vazia. Faça upload de um PDF primeiro.")
                st.stop()

            results = collection.query(
                query_texts=[search_query],
                n_results=min(n_results, total),
                include=["documents", "metadatas", "distances"],
            )

            docs      = results["documents"][0]
            metas     = results["metadatas"][0]
            distances = results["distances"][0]

        except Exception as e:
            st.error(f"Erro ao buscar: {e}")
            st.stop()

    # ── Exibe detalhes da melhoria ────────────────────────────────────────────
    if enhancement_result:
        display_enhancement_info(enhancement_result)
        st.divider()

    # ── Resultados ────────────────────────────────────────────────────────────
    if not docs:
        st.info("Nenhum resultado encontrado.")
        st.stop()

    st.success(f"**{len(docs)} resultado(s)** para: *{query[:80]}*")
    if enhancement_result:
        st.caption(f"Query expandida: *{enhancement_result['enhanced_query'][:100]}...*")
    st.divider()

    for i, (doc, meta, dist) in enumerate(zip(docs, metas, distances)):
        similarity = round((1 - dist) * 100, 1)

        # Cor do badge de similaridade
        if similarity >= 70:
            badge = f":green[**{similarity}% similar**]"
        elif similarity >= 40:
            badge = f":orange[**{similarity}% similar**]"
        else:
            badge = f":red[**{similarity}% similar**]"

        with st.container(border=True):
            header_col, score_col = st.columns([5, 1])

            with header_col:
                title  = meta.get("title", f"Documento {i + 1}")
                source = meta.get("source", "—")
                author = meta.get("author", "—")
                year   = meta.get("year", "—")
                chunk  = meta.get("chunk_index", "—")
                st.markdown(f"**{title}**")
                st.caption(f"Fonte: `{source}` · Autor: {author} · Ano: {year} · Chunk: {chunk}")

            with score_col:
                st.markdown(badge)

            # Trecho do documento
            preview = doc[:600] + ("…" if len(doc) > 600 else "")
            st.markdown(preview)

            with st.expander("Ver metadados completos"):
                st.json(meta)
