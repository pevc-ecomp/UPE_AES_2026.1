import json
import re

from app.llm_client import ask_llm
from app.schemas import (
    ArticleClassificationJudgeRequest,
    ArticleClassificationJudgeResponse,
    ArticleClassificationRevisionResponse,
    SearchStringJudgeCriteria,
    SearchStringJudgeRequest,
    SearchStringJudgeResponse,
)
from pydantic import ValidationError


def _extract_json_object(raw_response: str) -> dict:
    raw_response = raw_response.strip()

    if not raw_response:
        raise ValueError("Empty response from LLM")

    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError:
        start = raw_response.find("{")
        end = raw_response.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("LLM response does not contain valid JSON") from None
        parsed = json.loads(raw_response[start : end + 1])

    if isinstance(parsed, str):
        parsed = json.loads(parsed)

    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON must be an object")

    return parsed


def _normalize_judge_verdict(value: str) -> str:
    normalized = (value or "").strip().upper()
    verdict_map = {
        "CORRECT": "CORRECT",
        "APPROVE": "CORRECT",
        "RIGHT": "CORRECT",
        "OK": "CORRECT",
        "UNCERTAIN": "UNCERTAIN",
        "UNSURE": "UNCERTAIN",
        "MAYBE": "UNCERTAIN",
        "REVISE": "UNCERTAIN",
        "INCORRECT": "INCORRECT",
        "WRONG": "INCORRECT",
        "REJECT": "INCORRECT",
        "EXCLUDE": "INCORRECT",
    }
    return verdict_map.get(normalized, "UNCERTAIN")


def _normalize_model_classification(value: str) -> str:
    normalized = (value or "").strip().upper()
    verdict_map = {
        "RELATED": "RELATED",
        "INCLUDE": "RELATED",
        "APPROVE": "RELATED",
        "CORRECT": "RELATED",
        "UNSURE": "UNSURE",
        "UNCERTAIN": "UNSURE",
        "MAYBE": "UNSURE",
        "REVISE": "UNSURE",
        "NOT-RELATED": "NOT-RELATED",
        "NOT RELATED": "NOT-RELATED",
        "EXCLUDE": "NOT-RELATED",
        "REJECT": "NOT-RELATED",
        "INCORRECT": "NOT-RELATED",
    }
    return verdict_map.get(normalized, normalized or "UNSURE")


def _normalize_confidence_score(value) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(5.0, score))


def _normalize_article_score(value) -> int:
    try:
        score = int(float(value))
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, score))


def _normalize_human_review_recommended(value, judge_verdict: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1", "sim"}:
            return True
        if normalized in {"false", "no", "n", "0", "nao", "não"}:
            return False
    return judge_verdict != "CORRECT"


def _normalize_article_judge_response(parsed_response: dict, request: ArticleClassificationJudgeRequest) -> dict:
    raw_articles = parsed_response.get("articles", [])
    if not isinstance(raw_articles, list):
        raw_articles = []

    normalized_articles = []
    for index, source_article in enumerate(request.articles):
        raw_article = raw_articles[index] if index < len(raw_articles) and isinstance(raw_articles[index], dict) else {}
        judge_verdict = _normalize_judge_verdict(raw_article.get("judge_verdict", ""))
        normalized_articles.append(
            {
                "title": str(raw_article.get("title") or source_article.title),
                "model_classification": _normalize_model_classification(
                    raw_article.get("model_classification") or source_article.model_classification
                ),
                "judge_verdict": judge_verdict,
                "confidence_score": _normalize_confidence_score(raw_article.get("confidence_score", 0)),
                "judge_justification": str(raw_article.get("judge_justification") or ""),
                "human_review_recommended": _normalize_human_review_recommended(
                    raw_article.get("human_review_recommended"),
                    judge_verdict,
                ),
            }
        )

    parsed_response["type"] = "ARTICLE_CLASSIFICATION_JUDGE"
    parsed_response["articles"] = normalized_articles
    parsed_response["overall_result"] = "REVISE"
    parsed_response["summary"] = str(parsed_response.get("summary") or "")

    main_risks = parsed_response.get("main_risks", [])
    if not isinstance(main_risks, list):
        main_risks = [str(main_risks)] if main_risks else []
    parsed_response["main_risks"] = [str(risk) for risk in main_risks if str(risk).strip()]

    return parsed_response


def _normalize_article_revision_response(parsed_response: dict, request: ArticleClassificationJudgeRequest) -> dict:
    raw_articles = parsed_response.get("articles", [])
    if not isinstance(raw_articles, list):
        raw_articles = []

    normalized_articles = []
    for index, source_article in enumerate(request.articles):
        raw_article = raw_articles[index] if index < len(raw_articles) and isinstance(raw_articles[index], dict) else {}
        revised_classification = _normalize_model_classification(
            raw_article.get("revised_classification") or source_article.model_classification
        )
        if revised_classification not in {"RELATED", "UNSURE", "NOT-RELATED"}:
            revised_classification = _normalize_model_classification(source_article.model_classification)
            if revised_classification not in {"RELATED", "UNSURE", "NOT-RELATED"}:
                revised_classification = "UNSURE"

        revised_excluded = bool(raw_article.get("revised_excluded_by_criterion", source_article.excluded_by_criterion))

        exclusion_triggered = raw_article.get("revised_exclusion_triggered", source_article.exclusion_triggered)
        if not isinstance(exclusion_triggered, list):
            exclusion_triggered = [str(exclusion_triggered)] if exclusion_triggered else []

        inclusion_met = raw_article.get(
            "revised_inclusion_criteria_met",
            source_article.inclusion_criteria_met,
        )
        if not isinstance(inclusion_met, list):
            inclusion_met = [str(inclusion_met)] if inclusion_met else []

        revised_score = _normalize_article_score(
            raw_article.get("revised_score", source_article.model_score or 0)
        )
        if revised_excluded or exclusion_triggered:
            revised_excluded = True
            revised_score = 0
            revised_classification = "NOT-RELATED"

        normalized_articles.append(
            {
                "title": str(raw_article.get("title") or source_article.title),
                "original_classification": _normalize_model_classification(source_article.model_classification),
                "revised_classification": revised_classification,
                "revised_score": revised_score,
                "revised_justification": str(raw_article.get("revised_justification") or ""),
                "revised_excluded_by_criterion": revised_excluded,
                "revised_exclusion_triggered": [str(item) for item in exclusion_triggered if str(item).strip()],
                "revised_inclusion_criteria_met": [str(item) for item in inclusion_met if str(item).strip()],
                "changes_summary": str(raw_article.get("changes_summary") or ""),
                "human_review_recommended": _normalize_human_review_recommended(
                    raw_article.get("human_review_recommended"),
                    "CORRECT" if revised_classification == _normalize_model_classification(source_article.model_classification) else "UNCERTAIN",
                ),
            }
        )

    parsed_response["type"] = "ARTICLE_CLASSIFICATION_REVISION"
    parsed_response["articles"] = normalized_articles
    parsed_response["summary"] = str(parsed_response.get("summary") or "")
    return parsed_response


def _compute_search_string_final_score(criteria) -> float:
    scores = [
        criteria.conceptual_coverage.score,
        criteria.synonym_quality.score,
        criteria.boolean_operators.score,
        criteria.database_compatibility.score,
        criteria.recall_potential.score,
        criteria.precision.score,
    ]
    return round(sum(scores) / len(scores), 2)


def _normalize_search_string_for_analysis(search_string: str) -> str:
    normalized = search_string or ""
    field_patterns = [
        r"TITLE-ABS-KEY\s*\(",
        r"TITLE-KEY-ABS\s*\(",
        r"TITLE-ABS\s*\(",
        r"TITLE\s*\(",
        r"ABS\s*\(",
        r"KEY\s*\(",
        r"TS\s*=\s*\(",
        r"ALL\s*\(",
    ]

    for pattern in field_patterns:
        normalized = re.sub(pattern, "(", normalized, flags=re.IGNORECASE)

    return normalized


def _extract_search_terms(search_string: str) -> list[str]:
    normalized = _normalize_search_string_for_analysis(search_string)
    quoted_terms = [term.strip() for term in re.findall(r'"([^"]+)"', normalized) if term.strip()]
    unquoted_source = re.sub(r'"[^"]+"', " ", normalized)
    raw_tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", unquoted_source)
    filtered_tokens = [
        token
        for token in raw_tokens
        if token.upper() not in {"AND", "OR", "NOT"}
    ]
    return quoted_terms + filtered_tokens


def _count_boolean_operators(search_string: str) -> dict[str, int]:
    return {
        "AND": len(re.findall(r"\bAND\b", search_string, flags=re.IGNORECASE)),
        "OR": len(re.findall(r"\bOR\b", search_string, flags=re.IGNORECASE)),
        "NOT": len(re.findall(r"\bNOT\b", search_string, flags=re.IGNORECASE)),
    }


def _has_balanced_parentheses(search_string: str) -> bool:
    balance = 0
    for char in search_string:
        if char == "(":
            balance += 1
        elif char == ")":
            balance -= 1
            if balance < 0:
                return False
    return balance == 0


def _score_with_justification(score: float, justification: str) -> dict:
    return {"score": round(max(0.0, min(5.0, score)), 2), "justification": justification}


def _infer_database_compatibility(search_string: str, database: str) -> tuple[float, str]:
    database_name = (database or "").strip().lower()
    upper_string = search_string.upper()

    compatibility_rules = {
        "scopus": ["TITLE-ABS-KEY("],
        "web of science": ["TS="],
        "wos": ["TS="],
        "ieee": ["\"Document Title\":"],
        "acm": ["Title:(", "Abstract:(", "Keyword:("],
    }

    expected_patterns = []
    for key, patterns in compatibility_rules.items():
        if key in database_name:
            expected_patterns = patterns
            break

    if not expected_patterns:
        return 4.0, "Uses standard boolean structure compatible with most databases."

    if any(pattern.upper() in upper_string for pattern in expected_patterns):
        return 5.0, f"Uses field syntax expected by {database or 'the selected database'}."

    if re.search(r"\bAND\b|\bOR\b|\bNOT\b", search_string, flags=re.IGNORECASE):
        return 3.5, f"Boolean syntax is valid, but field tags are not specific to {database or 'the database'}."

    return 2.0, f"String does not clearly match the expected syntax for {database or 'the database'}."


def _build_search_string_fallback(data: SearchStringJudgeRequest) -> dict:
    terms = _extract_search_terms(data.search_string)
    unique_terms = list(dict.fromkeys(term.lower() for term in terms))
    boolean_counts = _count_boolean_operators(data.search_string)
    total_boolean_ops = sum(boolean_counts.values())
    has_quotes = '"' in data.search_string
    balanced_parentheses = _has_balanced_parentheses(data.search_string)
    normalized = _normalize_search_string_for_analysis(data.search_string)
    top_level_groups = [
        group.strip()
        for group in re.split(r"\bAND\b", normalized, flags=re.IGNORECASE)
        if group.strip()
    ]

    concept_score = 4.5 if len(top_level_groups) >= 2 and len(unique_terms) >= 2 else 2.5
    concept_justification = (
        "Covers more than one core concept of the topic."
        if concept_score >= 4
        else "Covers few core concepts and may miss part of the topic."
    )

    synonym_score = 4.5 if boolean_counts["OR"] >= 1 else 2.0
    synonym_justification = (
        "Includes alternative terms with OR."
        if synonym_score >= 4
        else "Does not show many synonyms or alternative spellings."
    )

    boolean_score = 5.0 if total_boolean_ops >= 1 and balanced_parentheses else 2.0
    boolean_justification = (
        "Uses boolean operators and balanced grouping correctly."
        if boolean_score >= 4
        else "Boolean structure is weak or grouping is unbalanced."
    )

    compatibility_score, compatibility_justification = _infer_database_compatibility(
        data.search_string,
        data.database or "",
    )

    recall_score = 4.0 if boolean_counts["OR"] >= 2 else 3.0 if boolean_counts["OR"] >= 1 else 2.0
    recall_justification = (
        "Recall is helped by alternative terms."
        if recall_score >= 3
        else "Recall may be limited because few alternatives are present."
    )

    precision_score = 4.5 if has_quotes and len(unique_terms) >= 2 else 3.0
    precision_justification = (
        "Quoted phrases and field restrictions improve precision."
        if precision_score >= 4
        else "Precision is acceptable but could be improved with more specific phrasing."
    )

    identified_problems = []
    improvement_suggestions = []

    if boolean_counts["OR"] == 0:
        identified_problems.append("Few or no synonyms were included.")
        improvement_suggestions.append("Add synonyms or variant expressions with OR.")

    if not balanced_parentheses:
        identified_problems.append("Parentheses are unbalanced.")
        improvement_suggestions.append("Review grouping parentheses to avoid syntax errors.")

    if not has_quotes:
        improvement_suggestions.append("Use quotes for multi-word phrases when supported by the database.")

    return {
        "type": "SEARCH_STRING_JUDGE",
        "criteria": {
            "conceptual_coverage": _score_with_justification(concept_score, concept_justification),
            "synonym_quality": _score_with_justification(synonym_score, synonym_justification),
            "boolean_operators": _score_with_justification(boolean_score, boolean_justification),
            "database_compatibility": _score_with_justification(
                compatibility_score,
                compatibility_justification,
            ),
            "recall_potential": _score_with_justification(recall_score, recall_justification),
            "precision": _score_with_justification(precision_score, precision_justification),
        },
        "identified_problems": identified_problems,
        "improvement_suggestions": improvement_suggestions,
    }


def _normalize_search_string_judge_response(parsed_response: dict, request: SearchStringJudgeRequest) -> dict:
    fallback_response = _build_search_string_fallback(request)

    raw_criteria = parsed_response.get("criteria", {})
    if not isinstance(raw_criteria, dict):
        raw_criteria = {}

    normalized_criteria = {}
    fallback_criteria = fallback_response["criteria"]

    for criterion_name, fallback_criterion in fallback_criteria.items():
        raw_criterion = raw_criteria.get(criterion_name, {})
        if not isinstance(raw_criterion, dict):
            raw_criterion = {}

        score = _normalize_confidence_score(raw_criterion.get("score", fallback_criterion["score"]))
        justification = str(raw_criterion.get("justification") or fallback_criterion["justification"])

        if score == 0 and fallback_criterion["score"] > 0:
            score = fallback_criterion["score"]
            justification = fallback_criterion["justification"]

        normalized_criteria[criterion_name] = {
            "score": score,
            "justification": justification,
        }

    identified_problems = parsed_response.get("identified_problems", [])
    if not isinstance(identified_problems, list):
        identified_problems = fallback_response["identified_problems"]

    improvement_suggestions = parsed_response.get("improvement_suggestions", [])
    if not isinstance(improvement_suggestions, list):
        improvement_suggestions = fallback_response["improvement_suggestions"]

    parsed_response["type"] = "SEARCH_STRING_JUDGE"
    parsed_response["criteria"] = normalized_criteria
    parsed_response["identified_problems"] = [str(item) for item in identified_problems if str(item).strip()]
    parsed_response["improvement_suggestions"] = [
        str(item) for item in improvement_suggestions if str(item).strip()
    ]

    if not parsed_response["identified_problems"]:
        parsed_response["identified_problems"] = fallback_response["identified_problems"]

    if not parsed_response["improvement_suggestions"]:
        parsed_response["improvement_suggestions"] = fallback_response["improvement_suggestions"]

    return parsed_response


def _decision_from_score(final_score: float) -> str:
    if final_score >= 4:
        return "APPROVE"
    if final_score >= 2.5:
        return "REVISE"
    return "REJECT"


def _overall_article_result(articles) -> str:
    incorrect_count = sum(1 for article in articles if article.judge_verdict == "INCORRECT")
    uncertain_count = sum(1 for article in articles if article.judge_verdict == "UNCERTAIN")

    if incorrect_count >= max(2, len(articles) / 2):
        return "REJECT"
    if incorrect_count > 0 or uncertain_count > 0:
        return "REVISE"
    return "APPROVE"


def _article_summary(articles, overall_result: str) -> str:
    correct_count = sum(1 for article in articles if article.judge_verdict == "CORRECT")
    uncertain_count = sum(1 for article in articles if article.judge_verdict == "UNCERTAIN")
    incorrect_count = sum(1 for article in articles if article.judge_verdict == "INCORRECT")
    return (
        f"Overall result is {overall_result}. "
        f"Correct: {correct_count}, uncertain: {uncertain_count}, incorrect: {incorrect_count}."
    )


def _article_risks(articles) -> list[str]:
    risks = []
    uncertain_titles = [article.title for article in articles if article.judge_verdict == "UNCERTAIN"]
    incorrect_titles = [article.title for article in articles if article.judge_verdict == "INCORRECT"]
    blank_justifications = [
        article.title for article in articles if not article.judge_justification.strip()
    ]

    if uncertain_titles:
        risks.append(
            "Human review recommended for uncertain classifications: "
            + "; ".join(uncertain_titles)
        )
    if incorrect_titles:
        risks.append(
            "Potential classification errors identified in: " + "; ".join(incorrect_titles)
        )
    if blank_justifications:
        risks.append(
            "Some judge justifications were empty or too weak: " + "; ".join(blank_justifications)
        )

    return risks


def _article_revision_summary(articles) -> str:
    changed = sum(
        1
        for article in articles
        if article.original_classification != article.revised_classification
    )
    human_review = sum(1 for article in articles if article.human_review_recommended)
    return (
        f"Revision generated for {len(articles)} article(s). "
        f"Changed classifications: {changed}. "
        f"Human review recommended for {human_review}."
    )


def judge_search_string(data: SearchStringJudgeRequest) -> dict:
    normalized_search_string = _normalize_search_string_for_analysis(data.search_string)
    prompt = f"""
Evaluate the search string below for a systematic literature review.

Review topic:
{data.topic}

Target database:
{data.database}

Search string:
{data.search_string}

Equivalent plain form for analysis:
{normalized_search_string}

Evaluation criteria:
1. Conceptual coverage
2. Synonym quality
3. Boolean operator usage
4. Database compatibility
5. Recall potential
6. Precision

Give a score from 0 to 5 for each criterion.

Return only this JSON structure:

{{
  "type": "SEARCH_STRING_JUDGE",
  "final_score": 0,
  "decision": "APPROVE | REVISE | REJECT",
  "criteria": {{
    "conceptual_coverage": {{"score": 0, "justification": ""}},
    "synonym_quality": {{"score": 0, "justification": ""}},
    "boolean_operators": {{"score": 0, "justification": ""}},
    "database_compatibility": {{"score": 0, "justification": ""}},
    "recall_potential": {{"score": 0, "justification": ""}},
    "precision": {{"score": 0, "justification": ""}}
  }},
  "identified_problems": [],
  "improvement_suggestions": []
}}

Rules:
- final_score must be a numeric value from 0 to 5.
- APPROVE if final_score >= 4.
- REVISE if final_score >= 2.5 and < 4.
- REJECT if final_score < 2.5.
- Keep justifications short and direct.
- If the string is too generic, penalize precision and conceptual coverage.
- If the string lacks synonyms, penalize synonym quality and recall potential.
- Database field operators such as TITLE-ABS-KEY(...), TS=(...), TITLE(...), ABS(...), and KEY(...)
  are valid search syntax and must not be treated as noise or as an error by themselves.
"""

    try:
        parsed_response = _extract_json_object(ask_llm(prompt))
    except Exception:
        parsed_response = {}

    parsed_response = _normalize_search_string_judge_response(parsed_response, data)

    try:
        criteria = SearchStringJudgeCriteria.model_validate(parsed_response["criteria"])
    except ValidationError:
        criteria = SearchStringJudgeCriteria.model_validate(_build_search_string_fallback(data)["criteria"])

    final_score = _compute_search_string_final_score(criteria)

    result = SearchStringJudgeResponse(
        type="SEARCH_STRING_JUDGE",
        final_score=final_score,
        decision=_decision_from_score(final_score),
        criteria=criteria,
        identified_problems=parsed_response.get("identified_problems", []),
        improvement_suggestions=parsed_response.get("improvement_suggestions", []),
    )
    return result.model_dump()


def judge_article_classification(data: ArticleClassificationJudgeRequest) -> dict:
    articles_text = ""

    for index, article in enumerate(data.articles, start=1):
        keywords = ", ".join(article.keywords) if article.keywords else ""
        exclusion_triggered = "; ".join(article.exclusion_triggered) if article.exclusion_triggered else ""
        inclusion_criteria_met = "; ".join(article.inclusion_criteria_met) if article.inclusion_criteria_met else ""
        articles_text += f"""
Article {index}
Title: {article.title}
Abstract: {article.abstract}
Keywords: {keywords}
Classification made by the model: {article.model_classification}
Score produced by the model: {article.model_score}
Excluded by criterion: {article.excluded_by_criterion}
Triggered exclusion criteria: {exclusion_triggered}
Satisfied inclusion criteria: {inclusion_criteria_met}
Justification given by the model: {article.model_justification}
"""

    protocol_context = f"""
Review objective:
{data.review_objective}

Protocol description:
{data.protocol_description}

General objectives:
{data.general_objectives}

Specific objectives:
{data.specific_objectives}

Inclusion criteria:
{data.inclusion_criteria}

Inclusion logic:
{data.inclusion_logic}

Exclusion criteria:
{data.exclusion_criteria}
"""

    prompt = f"""
Judge whether the article classification decisions made by another model are adequate for a systematic literature review.

Review protocol and objectives:
{protocol_context}

Articles and model decisions:
{articles_text}

For each article, evaluate:
1. Whether the classification is coherent with the review objective and protocol.
2. Whether the score, exclusion decision, and inclusion evidence are coherent.
3. Whether the justification is sufficient.
4. Whether there is risk of classification error.
5. Whether human review is recommended.

Return only this JSON structure:

{{
  "type": "ARTICLE_CLASSIFICATION_JUDGE",
  "overall_result": "APPROVE | REVISE | REJECT",
  "articles": [
    {{
      "title": "",
      "model_classification": "",
      "judge_verdict": "CORRECT | UNCERTAIN | INCORRECT",
      "confidence_score": 0,
      "judge_justification": "",
      "human_review_recommended": true
    }}
  ],
  "summary": "",
  "main_risks": []
}}

Rules:
- confidence_score must be from 0 to 5.
- Use UNCERTAIN when the abstract, criteria, or evidence are insufficient.
- Be conservative.
- Recommend human review when there is uncertainty.
- Keep justifications short and direct.
- Preserve the model classification label style when possible, especially RELATED, UNSURE, and NOT-RELATED.
- If the model says an article was excluded by criteria, verify whether that exclusion appears justified by the protocol.
- overall_result should be APPROVE only when most classifications are correct with high confidence.
- overall_result should be REVISE when there are uncertain cases.
- overall_result should be REJECT when many classifications appear incorrect.
"""

    try:
        parsed_response = _extract_json_object(ask_llm(prompt))
    except Exception:
        parsed_response = {}

    parsed_response = _normalize_article_judge_response(parsed_response, data)
    result = ArticleClassificationJudgeResponse.model_validate(parsed_response)
    result.overall_result = _overall_article_result(result.articles)

    if not result.summary.strip():
        result.summary = _article_summary(result.articles, result.overall_result)

    generated_risks = _article_risks(result.articles)
    if generated_risks:
        result.main_risks = list(dict.fromkeys([*result.main_risks, *generated_risks]))

    return result.model_dump()


def revise_article_classification(data: ArticleClassificationJudgeRequest) -> dict:
    articles_text = ""

    for index, article in enumerate(data.articles, start=1):
        keywords = ", ".join(article.keywords) if article.keywords else ""
        exclusion_triggered = "; ".join(article.exclusion_triggered) if article.exclusion_triggered else ""
        inclusion_criteria_met = "; ".join(article.inclusion_criteria_met) if article.inclusion_criteria_met else ""
        articles_text += f"""
Article {index}
Title: {article.title}
Abstract: {article.abstract}
Keywords: {keywords}
Original model classification: {article.model_classification}
Original model score: {article.model_score}
Original model justification: {article.model_justification}
Original exclusion flag: {article.excluded_by_criterion}
Original triggered exclusion criteria: {exclusion_triggered}
Original satisfied inclusion criteria: {inclusion_criteria_met}
Judge verdict: {article.judge_verdict}
Judge justification: {article.judge_justification}
Judge recommends human review: {article.human_review_recommended}
"""

    protocol_context = f"""
Review objective:
{data.review_objective}

Protocol description:
{data.protocol_description}

General objectives:
{data.general_objectives}

Specific objectives:
{data.specific_objectives}

Inclusion criteria:
{data.inclusion_criteria}

Inclusion logic:
{data.inclusion_logic}

Exclusion criteria:
{data.exclusion_criteria}
"""

    prompt = f"""
Revise the article classification decisions below using the AI judge feedback.

Review protocol and objectives:
{protocol_context}

Articles, original model decisions, and judge feedback:
{articles_text}

For each article, produce a classification_v2 that:
1. Preserves the original decision when it appears well supported.
2. Changes the classification only when the judge feedback shows a strong problem.
3. Recomputes a score from 0 to 100.
4. Marks exclusion criteria only when clearly justified by the protocol.
5. Recommends human review when uncertainty remains.

Return only this JSON structure:

{{
  "type": "ARTICLE_CLASSIFICATION_REVISION",
  "articles": [
    {{
      "title": "",
      "original_classification": "",
      "revised_classification": "RELATED | UNSURE | NOT-RELATED",
      "revised_score": 0,
      "revised_justification": "",
      "revised_excluded_by_criterion": false,
      "revised_exclusion_triggered": [],
      "revised_inclusion_criteria_met": [],
      "changes_summary": "",
      "human_review_recommended": true
    }}
  ],
  "summary": ""
}}

Rules:
- revised_score must be an integer from 0 to 100.
- If revised_excluded_by_criterion is true, revised_classification must be NOT-RELATED and revised_score must be 0.
- Keep justifications short and direct.
- Be conservative when evidence is weak.
- Use UNSURE when the judge feedback indicates unresolved ambiguity.
"""

    try:
        parsed_response = _extract_json_object(ask_llm(prompt))
    except Exception:
        parsed_response = {}

    parsed_response = _normalize_article_revision_response(parsed_response, data)
    result = ArticleClassificationRevisionResponse.model_validate(parsed_response)

    if not result.summary.strip():
        result.summary = _article_revision_summary(result.articles)

    return result.model_dump()
