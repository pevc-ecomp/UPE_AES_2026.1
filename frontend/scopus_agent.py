"""
ScopusAgent — academic search strategist and bibliometric analyst.

Builds optimized Scopus query strings (core / expanded / full) and
simulates results. Supports iterative refinement based on paper selection
or full pivot when no results are relevant.

The system prompt, models and temperature are normally provided by the
"scopus-agent" agent configured via the backend /agents API (see
3_String_Optimizer.py). DEFAULT_SYSTEM_PROMPT is used only as a fallback when
no such agent is configured.
"""

import json
import re
from typing import Any

from json_repair import repair_json

# ── Default system prompt (fallback) ────────────────────────────────────────────

DEFAULT_SYSTEM_PROMPT = """You are ScopusAgent, an expert academic search strategist and bibliometric analyst specializing in constructing optimized Scopus queries.

## YOUR ROLE
You help researchers build, refine, and execute high-quality Scopus search strings that maximize recall and precision. You think like an experienced information specialist who understands Boolean logic, controlled vocabularies, and field-specific terminology.

## STRATEGY FOR STRING OPTIMIZATION
When a user provides an initial query, apply ALL of the following layers:

### Layer 1 — Keyword Extraction & Normalization
- Identify core concepts and noun phrases
- Normalize to preferred academic terminology
- Remove stop words and vague qualifiers
- Apply truncation (*) where appropriate for morphological variants

### Layer 2 — Synonym & Variant Expansion
- Map each core concept to its synonym cluster
- Include abbreviations, acronyms, and initialisms (e.g., NLP OR "natural language processing")
- Consider British/American spelling variants
- Include cross-disciplinary synonyms (the same concept named differently in adjacent fields)
- Use OR to join synonym clusters, AND to join concept clusters

### Layer 3 — Author Identification
- Identify 3–5 seminal authors who are recognized references for the topic
- Include their names in the optimized string using AU-ID or AUTHOR-NAME fields
- Prioritize authors with highly-cited foundational works, active publication records, and broad recognition in the community
- Format: AU-ID("Surname, Firstname") OR AUTHOR-NAME(surname firstname)

### Layer 4 — Scopus Field Codes
Apply field-specific operators for precision:
- TITLE-ABS-KEY(...) for broad coverage
- TITLE(...) for high-precision searches
- AF-ID(...) for institution-specific filters
- PUBYEAR > XXXX for recency filters
- DOCTYPE(ar) for articles only; DOCTYPE(re) for reviews

### FINAL STRING FORMAT
Always produce the string in three tiers:
1. **Core string** — essential concepts only, minimal but precise
2. **Expanded string** — with synonyms and variants
3. **Full string** — with synonyms + author filters + Scopus field codes

## RESPONSE FORMAT (JSON ONLY)
When optimizing a query, respond ONLY with valid JSON (no markdown, no preamble).
Replace every value below with real content derived from the user's query — do NOT copy the example values literally:
{
  "strategy_explanation": "Write 2-3 sentences explaining your strategy here",
  "keywords_extracted": ["actual keyword from query", "another keyword"],
  "synonyms_added": [{"term": "keyword", "synonyms": ["synonym1", "synonym2"]}],
  "reference_authors": [{"name": "Smith, John", "reason": "pioneered this field"}],
  "string_core": "TITLE-ABS-KEY(main concept AND secondary concept)",
  "string_expanded": "TITLE-ABS-KEY((main concept OR synonym1) AND (secondary concept OR synonym2))",
  "string_full": "TITLE-ABS-KEY((main concept OR synonym1) AND (secondary concept OR synonym2)) AND PUBYEAR > 2015",
  "recommended_string": "expanded",
  "recommended_reason": "Write a brief justification here"
}

## REFINEMENT FROM SELECTED PAPERS
When the user marks papers as relevant and requests refinement:
- Extract new keywords from titles and author keywords of selected papers
- Identify patterns (shared terminology, shared authors, shared journals)
- Expand the string to capture the semantic neighborhood of the selected papers
- Explain what changed and why in the strategy_explanation field

## EXPANSION FROM ZERO SELECTIONS
When the user finds NO results relevant:
- Pivot to adjacent/related topics
- Broaden the conceptual scope
- Suggest alternative framings of the research question
- Generate a new string that approaches the topic from a different angle
- Explain the pivot clearly in strategy_explanation

## CRITICAL RULES
- Respond ONLY with valid JSON when producing optimized strings or results
- Never hallucinate real DOIs or real author names — use plausible academic-style identifiers
- Always maintain academic rigor in terminology
- Never truncate JSON responses — always close all brackets
- Use realistic citation counts (recent papers: 0–30, older foundational papers: 50–500+)"""

OPTIMIZE_PROMPT = """You are a Scopus search expert. Given a research query, build optimized Scopus search strings.

Respond ONLY with the JSON below. Replace EVERY value with real content from the query. Do NOT output example text, do NOT output "...".

{
  "strategy_explanation": "1-2 sentences describing the search strategy",
  "keywords_extracted": ["keyword1", "keyword2", "keyword3"],
  "synonyms_added": [{"term": "keyword1", "synonyms": ["synonym1a", "synonym1b"]}],
  "reference_authors": [{"name": "Lastname, Firstname", "reason": "key researcher in this area"}],
  "string_core": "TITLE-ABS-KEY(\"keyword1\" AND \"keyword2\")",
  "string_expanded": "TITLE-ABS-KEY((\"keyword1\" OR \"synonym1a\") AND (\"keyword2\" OR \"synonym2a\"))",
  "string_full": "TITLE-ABS-KEY((\"keyword1\" OR \"synonym1a\") AND (\"keyword2\" OR \"synonym2a\")) AND PUBYEAR > 2015",
  "recommended_string": "expanded",
  "recommended_reason": "1 sentence justification"
}

Rules:
- Output ONLY the JSON above, no extra text.
- string_core: join the main keywords with AND inside TITLE-ABS-KEY().
- string_expanded: add synonyms with OR, keep AND between concepts.
- string_full: copy expanded and append AND PUBYEAR > 2015.
- recommended_string must be exactly one of: core, expanded, full.
- Never output placeholder text or "..."."""


SIMULATE_PROMPT = """You are an academic database assistant. Your ONLY task is to simulate Scopus search results.

Given a Scopus search string, return ONLY a JSON object in this exact format (no markdown, no preamble, no extra keys):
{
  "results": [
    {
      "id": "S001",
      "title": "Full paper title here",
      "authors": ["Surname, Firstname", "Surname2, Firstname2"],
      "journal": "Journal Name",
      "year": 2022,
      "citations": 34,
      "doi": "10.1016/example.2022.001",
      "keywords": ["keyword1", "keyword2", "keyword3"],
      "abstract_snippet": "Two-sentence summary of what this paper is about and its main finding."
    }
  ]
}

Rules:
- Return ONLY the JSON object above, nothing else.
- Generate exactly 5 results relevant to the search string.
- Vary years between 2015 and 2024, journals, and methodologies.
- Use realistic but fictional DOIs and author names.
- Never truncate — always close all brackets and braces."""


# ── LLM helpers ───────────────────────────────────────────────────────────────

_MAX_RETRIES = 3


def _chat(llm_client, model: str, messages: list[dict], temperature: float = 0.2, retries: int = _MAX_RETRIES) -> Any:
    """Send messages to Ollama with retry logic, returning parsed JSON."""
    last_exc: Exception = RuntimeError("No attempts made")
    for _ in range(1, retries + 1):
        raw = llm_client.chat(
            model=model,
            messages=messages,
            options={"temperature": temperature},
        )["message"]["content"]
        try:
            return _extract_json(raw)
        except (ValueError, json.JSONDecodeError) as exc:
            last_exc = exc
    raise ValueError(f"No JSON after {retries} attempts. Last error: {last_exc}")


def _chat_with_fallback(
    llm_client, models: list[str], messages: list[dict], temperature: float = 0.2
) -> Any:
    """Try each model in order, falling back to the next on failure."""
    last_error: Exception | None = None
    for model in models:
        if not model:
            continue
        try:
            return _chat(llm_client, model, messages, temperature)
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"All models failed: {last_error}")


def _normalize_models(models) -> list[str]:
    if isinstance(models, str):
        return [models]
    return list(models)


def _extract_json(text: str) -> Any:
    """Extract the first JSON object or array from a string."""
    text = re.sub(r"```(?:json)?", "", text).strip()
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = text.find(start_char)
        if start == -1:
            continue
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == start_char:
                depth += 1
            elif ch == end_char:
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        return json.loads(repair_json(candidate))
    raise ValueError("No JSON found in LLM response")


_STR_FIELDS = {
    "strategy_explanation", "string_core", "string_expanded", "string_full",
    "recommended_string", "recommended_reason",
}


def _normalise(data: Any) -> Any:
    """Coerce fields that must be strings but LLMs sometimes return as lists."""
    if isinstance(data, list):
        if len(data) == 1 and isinstance(data[0], dict):
            data = data[0]
        elif data and all(isinstance(item, dict) for item in data):
            data = {"results": data}
        else:
            data = {}
    if not isinstance(data, dict):
        return data
    for field in _STR_FIELDS:
        val = data.get(field)
        if isinstance(val, list):
            data[field] = val[0] if val else ""
        elif val is not None and not isinstance(val, str):
            data[field] = str(val)
    _fill_missing_strings(data)
    return data


_PLACEHOLDER_PATTERNS = {
    "...", "core | expanded | full",
    "TITLE-ABS-KEY(main concept AND secondary concept)",
    "TITLE-ABS-KEY((main concept OR synonym1) AND (secondary concept OR synonym2))",
}


def _is_placeholder(val: str) -> bool:
    return (
        not val
        or val.strip() in _PLACEHOLDER_PATTERNS
        or "main concept" in val
        or "secondary concept" in val
        or val.strip() == "..."
    )


def _fill_missing_strings(data: dict) -> None:
    """Clear placeholder values and derive missing strings from keywords."""
    # Clear known placeholders
    for f in ("string_core", "string_expanded", "string_full"):
        if _is_placeholder(data.get(f, "")):
            data[f] = ""

    if data.get("recommended_string") not in ("core", "expanded", "full"):
        data["recommended_string"] = "expanded"

    core = data.get("string_core", "").strip()
    expanded = data.get("string_expanded", "").strip()
    full = data.get("string_full", "").strip()

    # Build core from keywords if still missing
    if not core:
        keywords = [k for k in data.get("keywords_extracted", []) if isinstance(k, str) and k.strip()]
        if keywords:
            kw_str = " AND ".join(f'"{k.strip()}"' for k in keywords[:4])
            core = f"TITLE-ABS-KEY({kw_str})"
            data["string_core"] = core

    # Build expanded from core + synonyms
    if not expanded and core:
        synonyms: list[dict] = data.get("synonyms_added") or []
        base = core
        for entry in synonyms:
            term = (entry.get("term") or "").strip()
            syns = [s for s in (entry.get("synonyms") or []) if isinstance(s, str) and s.strip()]
            if term and syns:
                all_terms = " OR ".join(f'"{s}"' for s in [term] + syns)
                base = base.replace(f'"{term}"', f"({all_terms})", 1)
        data["string_expanded"] = base
        expanded = data["string_expanded"]

    # Build full from expanded
    if not full and expanded:
        data["string_full"] = f"({expanded}) AND PUBYEAR > 2015"


# ── Core agent functions ───────────────────────────────────────────────────────

def optimize_query(
    llm_client,
    models,
    user_query: str,
    system_prompt: str | None = None,
    temperature: float = 0.2,
    on_step=None,
) -> dict:
    """Return optimized Scopus strings for the given natural-language query."""
    def step(msg):
        if on_step:
            on_step(msg)

    step("Analisando a questão de pesquisa...")
    messages = [
        {"role": "system", "content": system_prompt or OPTIMIZE_PROMPT},
        {
            "role": "user",
            "content": f"Research query: {user_query}",
        },
    ]
    step("Consultando modelo de linguagem...")
    result = _chat_with_fallback(llm_client, _normalize_models(models), messages, temperature)
    step("Extraindo palavras-chave e autores de referência...")
    step("Construindo strings Core, Expanded e Full...")
    return _normalise(result)


def simulate_results(
    llm_client,
    models,
    search_string: str,
    system_prompt: str | None = None,
    temperature: float = 0.2,
    on_step=None,
) -> dict:
    """Simulate Scopus results for the given search string."""
    def step(msg):
        if on_step:
            on_step(msg)

    step("Processando string de busca ativa...")
    messages = [
        {"role": "system", "content": SIMULATE_PROMPT},
        {
            "role": "user",
            "content": f"Generate 5 results for this search string: {search_string}",
        },
    ]
    step("Gerando resultados acadêmicos simulados...")
    result = _chat_with_fallback(llm_client, _normalize_models(models), messages, temperature)
    step("Formatando lista de artigos...")
    return _normalise(result)


def refine_query(
    llm_client,
    models,
    original_query: str,
    current_string: str,
    selected_ids: list[str],
    results: list[dict],
    system_prompt: str | None = None,
    temperature: float = 0.2,
    on_step=None,
) -> dict:
    """Refine the search string based on papers the user marked as relevant."""
    def step(msg):
        if on_step:
            on_step(msg)

    selected_papers = [r for r in results if r["id"] in selected_ids]
    papers_text = json.dumps(selected_papers, ensure_ascii=False, indent=2)

    if not selected_papers:
        step("Nenhum artigo selecionado — preparando pivot de abordagem...")
        instruction = (
            "The user found NO relevant results. Pivot to adjacent/related topics, "
            "broaden the conceptual scope, and generate a new optimized string. "
            "Return ONLY valid JSON as specified."
        )
    else:
        step(f"Analisando {len(selected_papers)} artigo(s) marcado(s) como relevante(s)...")
        step("Identificando padrões, termos e coautores recorrentes...")
        instruction = (
            f"The user marked the following papers as relevant. Extract new keywords, "
            f"identify patterns, and refine the search string to capture their semantic "
            f"neighbourhood. Return ONLY valid JSON as specified.\n\n"
            f"Relevant papers:\n{papers_text}"
        )

    messages = [
        {"role": "system", "content": system_prompt or DEFAULT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Original research question: {original_query}\n"
                f"Current Scopus string: {current_string}\n\n"
                f"{instruction}"
            ),
        },
    ]
    step("Refinando string de busca com o modelo...")
    result = _chat_with_fallback(llm_client, _normalize_models(models), messages, temperature)
    step("Normalizando nova string otimizada...")
    return _normalise(result)
