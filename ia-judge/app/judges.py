import json

from app.llm_client import ask_llm
from app.schemas import (
    ArticleClassificationJudgeRequest,
    ArticleClassificationJudgeResponse,
    SearchStringJudgeCriteria,
    SearchStringJudgeRequest,
    SearchStringJudgeResponse,
)


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


def _normalize_confidence_score(value) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(5.0, score))


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
                "model_classification": str(
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


def judge_search_string(data: SearchStringJudgeRequest) -> dict:
    prompt = f"""
Evaluate the search string below for a systematic literature review.

Review topic:
{data.topic}

Target database:
{data.database}

Search string:
{data.search_string}

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
"""
    parsed_response = _extract_json_object(ask_llm(prompt))
    criteria = SearchStringJudgeCriteria.model_validate(parsed_response["criteria"])
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
        articles_text += f"""
Article {index}
Title: {article.title}
Abstract: {article.abstract}
Classification made by the model: {article.model_classification}
Justification given by the model: {article.model_justification}
"""

    prompt = f"""
Judge whether the article classification decisions made by another model are adequate for a systematic literature review.

Review objective:
{data.review_objective}

Inclusion criteria:
{data.inclusion_criteria}

Exclusion criteria:
{data.exclusion_criteria}

Articles and model decisions:
{articles_text}

For each article, evaluate:
1. Whether the classification is coherent with the review objective.
2. Whether the justification is sufficient.
3. Whether there is risk of classification error.
4. Whether human review is recommended.

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
- overall_result should be APPROVE only when most classifications are correct with high confidence.
- overall_result should be REVISE when there are uncertain cases.
- overall_result should be REJECT when many classifications appear incorrect.
"""
    parsed_response = _extract_json_object(ask_llm(prompt))
    parsed_response = _normalize_article_judge_response(parsed_response, data)
    result = ArticleClassificationJudgeResponse.model_validate(parsed_response)
    result.overall_result = _overall_article_result(result.articles)

    if not result.summary.strip():
        result.summary = _article_summary(result.articles, result.overall_result)

    generated_risks = _article_risks(result.articles)
    if generated_risks:
        result.main_risks = list(dict.fromkeys([*result.main_risks, *generated_risks]))

    return result.model_dump()
