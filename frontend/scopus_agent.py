"""
ScopusAgent — academic search strategist and bibliometric analyst.

Builds optimized Scopus query strings (core / expanded / full) and
simulates 10 relevant results. Supports iterative refinement based on
paper selection or full pivot when no results are relevant.

This module exposes a single public function: run(llm_client, model).
The LLM is expected to respond with valid JSON matching the schemas
described in the system prompt below.
"""

import json
import re
from typing import Any

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are ScopusAgent, an expert academic search strategist and bibliometric analyst specializing in constructing optimized Scopus queries.

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
When optimizing a query, respond ONLY with valid JSON (no markdown, no preamble):
{
  "strategy_explanation": "2–3 sentence explanation of the search strategy chosen",
  "keywords_extracted": ["keyword1", "keyword2"],
  "synonyms_added": [{"term": "original", "synonyms": ["syn1", "syn2"]}],
  "reference_authors": [{"name": "Surname, Firstname", "reason": "why this author is relevant"}],
  "string_core": "...",
  "string_expanded": "...",
  "string_full": "...",
  "recommended_string": "core | expanded | full",
  "recommended_reason": "brief justification"
}

## SIMULATED SCOPUS RESULTS
Since you cannot call the real Scopus API, simulate 10 realistic academic results based on the search string. Each result must be plausible, academically formatted, and relevant to the query. Generate results that reflect diversity in year (2018–2024), journal, and methodology.

When returning results, respond ONLY with valid JSON:
{
  "results": [
    {
      "id": "S001",
      "title": "...",
      "authors": ["Surname A, Name", "Surname B, Name"],
      "journal": "...",
      "year": 2023,
      "citations": 45,
      "doi": "10.1016/...",
      "keywords": ["kw1", "kw2", "kw3"],
      "abstract_snippet": "Short 2-sentence summary of what the paper is about"
    }
  ]
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


# ── LLM helpers ───────────────────────────────────────────────────────────────

def _chat(llm_client, model: str, messages: list[dict]) -> str:
    """Send messages to Ollama and return the assistant content string."""
    response = llm_client.chat(model=model, messages=messages)
    return response["message"]["content"]


def _extract_json(text: str) -> Any:
    """Extract the first JSON object or array from a string."""
    # Strip markdown fences if present
    text = re.sub(r"```(?:json)?", "", text).strip()
    # Find outermost { ... } or [ ... ]
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
                    return json.loads(text[start : i + 1])
    raise ValueError("No JSON found in LLM response")


# ── Core agent functions ───────────────────────────────────────────────────────

def optimize_query(llm_client, model: str, user_query: str) -> dict:
    """Return optimized Scopus strings for the given natural-language query."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Optimize the following research query for Scopus and return "
                f"ONLY valid JSON as specified:\n\n{user_query}"
            ),
        },
    ]
    raw = _chat(llm_client, model, messages)
    return _extract_json(raw)


def simulate_results(llm_client, model: str, search_string: str) -> dict:
    """Simulate 10 Scopus results for the given search string."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Simulate 10 realistic Scopus results for the following search "
                f"string and return ONLY valid JSON as specified:\n\n{search_string}"
            ),
        },
    ]
    raw = _chat(llm_client, model, messages)
    return _extract_json(raw)


def refine_query(
    llm_client,
    model: str,
    original_query: str,
    current_string: str,
    selected_ids: list[str],
    results: list[dict],
) -> dict:
    """Refine the search string based on papers the user marked as relevant."""
    selected_papers = [r for r in results if r["id"] in selected_ids]
    papers_text = json.dumps(selected_papers, ensure_ascii=False, indent=2)

    if not selected_papers:
        instruction = (
            "The user found NO relevant results. Pivot to adjacent/related topics, "
            "broaden the conceptual scope, and generate a new optimized string. "
            "Return ONLY valid JSON as specified."
        )
    else:
        instruction = (
            f"The user marked the following papers as relevant. Extract new keywords, "
            f"identify patterns, and refine the search string to capture their semantic "
            f"neighbourhood. Return ONLY valid JSON as specified.\n\n"
            f"Relevant papers:\n{papers_text}"
        )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Original research question: {original_query}\n"
                f"Current Scopus string: {current_string}\n\n"
                f"{instruction}"
            ),
        },
    ]
    raw = _chat(llm_client, model, messages)
    return _extract_json(raw)
