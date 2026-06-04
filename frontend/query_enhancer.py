"""
Query Enhancement Skill
Melhora consultas de busca científica adicionando keywords, sinônimos e pesquisadores.
Usa Claude API para gerar melhorias baseadas em IA.
"""

import json
import os
import re
from typing import Optional
import httpx
import streamlit as st


CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-3-5-sonnet-20241022"


@st.cache_data(ttl=3600)
def _call_claude(prompt: str) -> str:
    """Chama Claude API e retorna a resposta."""
    if not CLAUDE_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY não configurada. "
            "Configure a variável de ambiente para usar Query Enhancement."
        )

    try:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": CLAUDE_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": CLAUDE_MODEL,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }

        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            return result["content"][0]["text"].strip()
    except Exception as e:
        raise RuntimeError(f"Erro ao chamar Claude API: {e}")


def extract_keywords(query: str, max_keywords: int = 5) -> list[str]:
    """Extrai keywords principais da query usando Claude."""
    prompt = f"""Você é um especialista em buscas científicas e indexação de literatura.

Analise esta query de busca científica e extraia até {max_keywords} palavras-chave principais que melhor descrevem o tema.
As keywords devem ser termos específicos e relevantes para encontrar artigos científicos sobre o tópico.

Query: "{query}"

Retorne APENAS as palavras-chave separadas por vírgula, sem explicações, pontuação ou números.
Exemplo de retorno: machine learning, neural networks, deep learning, classification, supervised learning"""

    try:
        response = _call_claude(prompt)
        keywords = [k.strip() for k in response.split(",") if k.strip()]
        # Remove duplicatas e limita
        keywords = list(dict.fromkeys(keywords))[:max_keywords]
        return keywords
    except Exception as e:
        st.warning(f"Erro ao extrair keywords: {e}")
        return []


def extract_synonyms(query: str) -> dict[str, list[str]]:
    """Extrai sinônimos relevantes dos termos principais da query usando Claude."""
    prompt = f"""Você é um especialista em terminologia científica e sinônimos em pesquisa acadêmica.

Analise esta query e identifique os 3-4 termos principais. Para cada termo, liste 2-3 sinônimos relevantes usados na literatura científica.

Query: "{query}"

Retorne um JSON válido com este formato EXATO (sem markdown, sem explicações adicionais):
{{"termo_principal_1": ["sinônimo1", "sinônimo2"], "termo_principal_2": ["sinônimo1", "sinônimo2"]}}

Exemplo:
{{"machine learning": ["aprendizado de máquina", "ML", "algoritmos adaptativos"], "neural networks": ["redes neurais", "redes artificiais"]}}"""

    try:
        response = _call_claude(prompt)
        # Remove markdown code blocks se houver
        response = response.replace("```json", "").replace("```", "").strip()

        # Tenta extrair JSON
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            return json.loads(json_str)
    except Exception as e:
        st.warning(f"Erro ao extrair sinônimos: {e}")

    return {}


def extract_researchers(query: str, max_researchers: int = 3) -> list[str]:
    """Extrai pesquisadores de referência na área usando Claude."""
    prompt = f"""Você é um especialista em história da ciência e pesquisadores influentes.

Para o seguinte tópico científico, liste até {max_researchers} pesquisadores ou autores de GRANDE importância/impacto conhecidos na área.
Priorize pesquisadores vivos e/ou com contribuições semináis recentes (últimos 20 anos).

Tópico: "{query}"

Retorne APENAS os nomes separados por vírgula, sem títulos, universidades ou explicações.
Exemplo de retorno: Geoffrey Hinton, Yann LeCun, Yoshua Bengio"""

    try:
        response = _call_claude(prompt)
        researchers = [r.strip() for r in response.split(",") if r.strip()]
        # Remove duplicatas e limita
        researchers = list(dict.fromkeys(researchers))[:max_researchers]
        return researchers
    except Exception as e:
        st.warning(f"Erro ao extrair pesquisadores: {e}")
        return []


def enhance_query(
    query: str,
    include_keywords: bool = True,
    include_synonyms: bool = True,
    include_researchers: bool = True,
) -> dict:
    """
    Incrementa a query com informações adicionais usando Claude API.

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

    if not CLAUDE_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY não configurada. "
            "Configure a variável de ambiente para usar Query Enhancement."
        )

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
        raise e

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
