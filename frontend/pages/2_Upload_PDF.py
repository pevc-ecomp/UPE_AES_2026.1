import io
import uuid

import streamlit as st
from pypdf import PdfReader

from utils import (
    get_client,
    get_or_create_collection,
    list_collections,
    clean_collection_name,
)

st.set_page_config(
    page_title="Upload PDF",
    page_icon="📄",
    layout="wide",
)

st.title("📄 Upload de PDF")
st.markdown("Indexe documentos PDF no vector store para busca semântica.")
st.divider()

# ── Conexão ───────────────────────────────────────────────────────────────────
client = get_client()
if not client:
    st.error("❌ Chroma indisponível. Verifique se o container está rodando.")
    st.stop()


# ── Funções auxiliares ────────────────────────────────────────────────────────
def extract_text(file) -> str:
    reader = PdfReader(io.BytesIO(file.read()))
    pages_text = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages_text).strip()


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configurações")

    existing = list_collections(client)
    dest = st.radio(
        "Coleção de destino:",
        options=["Criar nova coleção", "Usar coleção existente"],
        disabled=not existing,
    )

    if dest == "Usar coleção existente" and existing:
        collection_name = st.selectbox("Coleção:", options=existing)
    else:
        collection_name = st.text_input("Nome da nova coleção:", value="documents")

    st.divider()
    st.subheader("Chunking")
    chunk_size = st.slider(
        "Tamanho do chunk (palavras):",
        min_value=100,
        max_value=800,
        value=400,
        help="Quantidade de palavras por chunk indexado.",
    )
    overlap = st.slider(
        "Sobreposição (palavras):",
        min_value=0,
        max_value=150,
        value=50,
        help="Palavras repetidas entre chunks consecutivos.",
    )

# ── Upload ────────────────────────────────────────────────────────────────────
file_col, info_col = st.columns([3, 2])

with file_col:
    uploaded_file = st.file_uploader(
        "Selecione um arquivo PDF:",
        type=["pdf"],
        help="Tamanho máximo recomendado: 50 MB",
    )

with info_col:
    if uploaded_file:
        st.metric("Arquivo", uploaded_file.name)
        st.metric("Tamanho", f"{round(uploaded_file.size / 1024, 1)} KB")

# ── Formulário de metadados + preview ────────────────────────────────────────
if uploaded_file:
    st.divider()
    st.subheader("📝 Metadados")

    m1, m2 = st.columns(2)
    with m1:
        title  = st.text_input("Título:", value=uploaded_file.name.removesuffix(".pdf"))
        author = st.text_input("Autor(es):", placeholder="Ex: Silva, J.; Santos, M.")
    with m2:
        year = st.number_input("Ano de publicação:", min_value=1900, max_value=2100, value=2024)
        tags = st.text_input("Tags (separadas por vírgula):", placeholder="Ex: machine learning, climate")

    # Preview do texto
    with st.expander("👁️ Preview do texto extraído", expanded=False):
        with st.spinner("Lendo PDF..."):
            try:
                preview_text = extract_text(uploaded_file)
                uploaded_file.seek(0)
                word_count = len(preview_text.split())
                estimated_chunks = max(1, word_count // (chunk_size - overlap))

                p1, p2, p3 = st.columns(3)
                p1.metric("Palavras extraídas", f"~{word_count:,}")
                p2.metric("Chunks estimados", estimated_chunks)
                p3.metric("Chunk size", f"{chunk_size} palavras")

                st.text_area(
                    "Primeiros 1.000 caracteres:",
                    value=preview_text[:1000],
                    height=200,
                    disabled=True,
                )
            except Exception as e:
                st.error(f"Erro ao ler o PDF: {e}")
                preview_text = None

    st.divider()

    # ── Botão de indexação ────────────────────────────────────────────────────
    index_btn = st.button("⬆️ Indexar no Chroma", type="primary", use_container_width=True)

    if index_btn:
        with st.spinner("Extraindo texto do PDF..."):
            try:
                text = extract_text(uploaded_file)
            except Exception as e:
                st.error(f"Erro ao extrair texto: {e}")
                st.stop()

        if not text:
            st.error("Não foi possível extrair texto deste PDF. O arquivo pode ser uma imagem escaneada.")
            st.stop()

        # Chunking
        chunks = chunk_text(text, chunk_size, overlap)

        if not chunks:
            st.error("Nenhum chunk gerado. Verifique o arquivo.")
            st.stop()

        # Preparar metadados
        tag_list  = [t.strip() for t in tags.split(",") if t.strip()]
        safe_name = clean_collection_name(collection_name or "documents")
        doc_id    = str(uuid.uuid4())[:8]

        base_meta = {
            "title":        title,
            "author":       author,
            "year":         int(year),
            "tags":         ", ".join(tag_list),
            "source":       uploaded_file.name,
            "total_chunks": len(chunks),
        }

        # Indexação em batches
        progress_bar = st.progress(0, text="Indexando chunks no Chroma...")
        batch_size   = 50

        try:
            collection = get_or_create_collection(client, safe_name)

            for i in range(0, len(chunks), batch_size):
                batch  = chunks[i : i + batch_size]
                ids    = [f"{doc_id}_chunk_{i + j}" for j in range(len(batch))]
                metas  = [{**base_meta, "chunk_index": i + j} for j in range(len(batch))]

                collection.add(documents=batch, ids=ids, metadatas=metas)

                progress = (i + len(batch)) / len(chunks)
                progress_bar.progress(progress, text=f"Indexando chunk {i + len(batch)}/{len(chunks)}...")

            progress_bar.progress(1.0, text="Concluído!")

        except Exception as e:
            st.error(f"Erro ao indexar no Chroma: {e}")
            st.stop()

        # ── Resultado final ───────────────────────────────────────────────────
        st.success("✅ PDF indexado com sucesso!")
        st.balloons()

        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Chunks indexados",    len(chunks))
        r2.metric("Palavras no PDF",     f"~{len(text.split()):,}")
        r3.metric("Coleção",             safe_name)
        r4.metric("Total na coleção",    collection.count())
