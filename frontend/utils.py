import os
import re
from typing import Optional

import chromadb
import streamlit as st
from chromadb.utils import embedding_functions

# ── Variáveis de ambiente ─────────────────────────────────────────────────────
CHROMA_HOST = os.getenv("CHROMA_HOST", "http://chroma:8000")
DEFAULT_COLLECTION = os.getenv("CHROMA_COLLECTION", "documents")


def _parse_url(url: str) -> tuple[str, int]:
    """Extrai host e porta de uma URL como http://chroma:8000"""
    url = url.replace("http://", "").replace("https://", "")
    parts = url.split(":")
    host = parts[0]
    port = int(parts[1]) if len(parts) > 1 else 8000
    return host, port


@st.cache_resource(show_spinner=False)
def get_client() -> Optional[chromadb.HttpClient]:
    """Retorna cliente Chroma ou None se indisponível."""
    try:
        host, port = _parse_url(CHROMA_HOST)
        client = chromadb.HttpClient(host=host, port=port)
        client.heartbeat()
        return client
    except Exception:
        return None


@st.cache_resource(show_spinner=False)
def get_embedding_function():
    """Embedding leve via ONNX (all-MiniLM-L6-v2, ~90 MB)."""
    return embedding_functions.DefaultEmbeddingFunction()


def get_or_create_collection(client, name: str):
    """Retorna ou cria uma coleção com cosine similarity."""
    ef = get_embedding_function()
    return client.get_or_create_collection(
        name=name,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )


def list_collections(client) -> list:
    """Lista todas as coleções disponíveis."""
    try:
        return [col.name for col in client.list_collections()]
    except Exception:
        return []


def clean_collection_name(name: str) -> str:
    """Garante que o nome da coleção seja válido para o Chroma."""
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", name.strip()).lower()
    if not clean or not clean[0].isalpha():
        clean = "col_" + clean
    clean = clean[:63]
    if len(clean) < 3:
        clean = clean + "_db"
    return clean
