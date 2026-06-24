"""
Text preprocessing, TF-IDF and Rocchio-based term weighting for search refinement.

Pipeline:
  1. compute_tfidf(articles) — after each simulation round
  2. compute_term_weights(tfidf_data, articles, relevant_ids) — after user selection

Lemmatisation uses NLTK PorterStemmer (algorithm-only, no corpus download).
"""
import math
import re
from collections import Counter

try:
    from nltk.stem import PorterStemmer as _PS
    _stemmer = _PS()
    def _stem(word: str) -> str:
        return _stemmer.stem(word)
except ImportError:
    def _stem(word: str) -> str:  # no-op fallback
        return word.lower()

# ── Stopwords ─────────────────────────────────────────────────────────────────

_STOPWORDS = frozenset({
    # Function words
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "up", "about", "into", "as", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "will", "would", "could", "should", "may", "might", "this", "that",
    "these", "those", "it", "its", "we", "they", "them", "our", "their",
    "which", "who", "how", "what", "when", "where", "not", "no", "nor",
    "so", "yet", "both", "each", "more", "most", "other", "some", "such",
    "than", "too", "very", "can", "also", "if", "then", "i", "you", "he",
    "she", "me", "him", "her", "us", "my", "your", "his",
    # Academic boilerplate
    "use", "used", "using", "study", "paper", "result", "results", "show",
    "shown", "shows", "method", "approach", "proposed", "present", "presents",
    "analysis", "data", "model", "models", "based", "new", "two", "three",
    "one", "first", "second", "however", "well", "et", "al", "vs", "via",
    "identify", "provide", "address", "demonstrate", "evaluate", "review",
    "investigate", "explore", "highlight", "discuss", "compare", "apply",
})


# ── Tokenisation ──────────────────────────────────────────────────────────────

def _tokenize(text: str) -> list[tuple[str, str]]:
    """
    Returns (original_lower, stem) pairs after stopword removal.
    Minimum token length: 3 characters.
    """
    pairs = []
    for raw in re.findall(r'[a-zA-Z]{3,}', text.lower()):
        if raw not in _STOPWORDS:
            stem = _stem(raw)
            if len(stem) >= 3:
                pairs.append((raw, stem))
    return pairs


def _article_text(article: dict) -> str:
    return " ".join([
        article.get("title", ""),
        article.get("abstract_snippet", ""),
        " ".join(article.get("keywords", [])),
    ])


# ── TF-IDF ────────────────────────────────────────────────────────────────────

def compute_tfidf(articles: list[dict]) -> dict:
    """
    Compute TF-IDF for a list of article dicts.

    Returns:
        vocab         — list[str] of stems sorted by document-frequency desc
        original_form — dict[stem, str] most-common surface form per stem
        idf           — dict[stem, float]
        tfidf         — list[dict[stem, float]], one per article
    """
    n = len(articles)
    if n == 0:
        return {"vocab": [], "original_form": {}, "idf": {}, "tfidf": []}

    pairs_per_doc: list[list[tuple[str, str]]] = [
        _tokenize(_article_text(a)) for a in articles
    ]

    # Document frequency + surface-form tracking
    df: Counter = Counter()
    orig_counter: dict[str, Counter] = {}
    for pairs in pairs_per_doc:
        seen = set()
        for orig, stem in pairs:
            if stem not in orig_counter:
                orig_counter[stem] = Counter()
            orig_counter[stem][orig] += 1
            if stem not in seen:
                df[stem] += 1
                seen.add(stem)

    vocab = [t for t, _ in df.most_common()]

    # Smooth IDF (sklearn convention)
    idf = {t: math.log((n + 1) / (df[t] + 1)) + 1.0 for t in vocab}

    # Most common surface form per stem
    original_form = {t: cnt.most_common(1)[0][0] for t, cnt in orig_counter.items()}

    # TF-IDF per document
    tfidf: list[dict[str, float]] = []
    for pairs in pairs_per_doc:
        stem_counts = Counter(stem for _, stem in pairs)
        total = max(len(pairs), 1)
        tfidf.append({t: (stem_counts[t] / total) * idf[t] for t in vocab if stem_counts[t] > 0})

    return {"vocab": vocab, "original_form": original_form, "idf": idf, "tfidf": tfidf}


# ── Term weights (Rocchio) ────────────────────────────────────────────────────

def compute_term_weights(
    tfidf_data: dict,
    articles: list[dict],
    relevant_ids: set[str],
) -> list[tuple[str, float, str]]:
    """
    Rocchio-inspired weight per term:

        w(t) = (Σ_relevant tfidf(t, d) − Σ_non-relevant tfidf(t, d)) / n_relevant

    Returns list of (stem, weight, original_form) sorted by weight descending.
    Empty list when no relevant documents are provided.
    """
    n_rel = len(relevant_ids)
    if n_rel == 0:
        return []

    tfidf_list = tfidf_data["tfidf"]
    vocab = tfidf_data["vocab"]
    orig = tfidf_data["original_form"]

    rel_sum: Counter = Counter()
    non_rel_sum: Counter = Counter()

    for i, article in enumerate(articles):
        aid = article.get("id", str(i))
        doc = tfidf_list[i] if i < len(tfidf_list) else {}
        target = rel_sum if aid in relevant_ids else non_rel_sum
        for t, score in doc.items():
            target[t] += score

    weights = {t: (rel_sum[t] - non_rel_sum[t]) / n_rel for t in vocab}

    return sorted(
        [(t, weights[t], orig.get(t, t)) for t in vocab],
        key=lambda x: x[1],
        reverse=True,
    )
