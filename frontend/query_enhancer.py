"""
Query Enhancement Skill
Melhora consultas de busca científica adicionando keywords, sinônimos e pesquisadores.
"""

import json
import os
from typing import Optional
import httpx
import streamlit as st


OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL_PRIMARY", "phi3:mini")


@st.cache_data(ttl=3600)
def _call_ollama(prompt: str, model: str = OLLAMA_MODEL) -> str:
    """Chama o Ollama com um prompt e retorna a resposta."""
    try:
        url = f"{OLLAMA_HOST}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.3,
        }

        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "").strip()
    except Exception as e:
        raise RuntimeError(f"Erro ao chamar Ollama: {e}")


def extract_keywords(query: str, max_keywords: int = 5) -> list[str]:
    """Extrai keywords principais da query usando LLM."""
    prompt = f"""Você é um especialista em buscas científicas.
Analise a seguinte query e extraia até {max_keywords} palavras-chave principais (separadas por vírgula).
Retorne APENAS as palavras-chave, sem explicações.

Query: {query}

Palavras-chave:"""

    try:
        response = _call_ollama(prompt)
        keywords = [k.strip() for k in response.split(",") if k.strip()]
        return keywords[:max_keywords]
    except Exception:
        return []


def extract_synonyms(query: str) -> dict[str, list[str]]:
    """Extrai sinônimos dos termos principais da query."""
    prompt = f"""Você é um especialista em terminologia científica.
Para a seguinte query, identifique os 3-4 termos principais e liste sinônimos relevantes para cada um.
Retorne em formato JSON com a estrutura: {{"termo": ["sinônimo1", "sinônimo2", ...]}}

Query: {query}

Sinônimos (JSON):"""

    try:
        response = _call_ollama(prompt)
        # Tenta extrair JSON da resposta
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = response[start:end]
            return json.loads(json_str)
    except Exception:
        pass

    return {}


def extract_researchers(query: str, max_researchers: int = 3) -> list[str]:
    """Extrai pesquisadores de referência na área da query."""
    prompt = f"""Você é um especialista em pesquisa científica.
Para o seguinte tópico, liste até {max_researchers} pesquisadores ou autores de referência conhecidos na área.
Retorne APENAS os nomes separados por vírgula, sem explicações.

Tópico: {query}

Pesquisadores:"""

    try:
        response = _call_ollama(prompt)
        researchers = [r.strip() for r in response.split(",") if r.strip()]
        return researchers[:max_researchers]
    except Exception:
        return []


def enhance_query(
    query: str,
    include_keywords: bool = True,
    include_synonyms: bool = True,
    include_researchers: bool = True,
) -> dict:
    """
    Incrementa a query com informações adicionais.

    Args:
        query: Texto original da busca
        include_keywords: Se deve adicionar keywords
        include_synonyms: Se deve adicionar sinônimos
        include_researchers: Se deve adicionar pesquisadores

    Returns:
        Dicionário com:
        - enhanced_query: Query melhorada como texto
        - keywords: Lista de keywords extraídas
        - synonyms: Dict de sinônimos
        - researchers: Lista de pesquisadores
    """
    result = {
        "enhanced_query": query,
        "keywords": [],
        "synonyms": {},
        "researchers": [],
    }

    try:
        # Extrai keywords
        if include_keywords:
            result["keywords"] = extract_keywords(query)

        # Extrai sinônimos
        if include_synonyms:
            result["synonyms"] = extract_synonyms(query)

        # Extrai pesquisadores
        if include_researchers:
            result["researchers"] = extract_researchers(query)

        # Constrói query expandida
        parts = [query]

        if result["keywords"]:
            parts.append(" ".join(result["keywords"]))

        if result["synonyms"]:
            syn_terms = [syn for syns in result["synonyms"].values() for syn in syns]
            if syn_terms:
                parts.append(" ".join(syn_terms[:10]))  # Limita a 10 sinônimos

        if result["researchers"]:
            parts.append(" ".join(result["researchers"]))

        result["enhanced_query"] = " ".join(parts)

    except Exception as e:
        st.warning(f"⚠️ Erro ao melhorar query: {e}")

    return result


def display_enhancement_info(enhancement_result: dict):
    """Exibe informações sobre o incremento da query na UI."""
    with st.expander("📊 Detalhes da melhoria da query"):
        col1, col2 = st.columns(2)

        with col1:
            if enhancement_result["keywords"]:
                st.markdown("**Keywords extraídas:**")
                st.write(", ".join(enhancement_result["keywords"]))

            if enhancement_result["researchers"]:
                st.markdown("**Pesquisadores de referência:**")
                st.write(", ".join(enhancement_result["researchers"]))

        with col2:
            if enhancement_result["synonyms"]:
                st.markdown("**Sinônimos:**")
                for term, syns in enhancement_result["synonyms"].items():
                    st.write(f"- **{term}:** {', '.join(syns)}")
