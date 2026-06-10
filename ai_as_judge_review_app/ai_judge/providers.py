import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any


def load_dotenv_file(path: str | Path = ".env") -> None:
    """
    Carrega variáveis de ambiente a partir de um arquivo .env simples.

    Formato esperado:
    LLM_PROVIDER=openai-compatible
    LLM_API_KEY=sua-chave
    LLM_BASE_URL=https://api.openai.com/v1
    LLM_MODEL=gpt-4.1-mini

    Observações:
    - Linhas vazias e linhas iniciadas com # são ignoradas.
    - Variáveis já existentes no ambiente não são sobrescritas.
    - Aspas simples ou duplas ao redor do valor são removidas.
    """
    env_path = Path(path)

    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value



class LLMProvider:
    def complete_json(self, prompt: str, task: str) -> dict[str, Any]:
        raise NotImplementedError


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "sim", "yes"}:
            return True
        if normalized in {"false", "0", "nao", "não", "no"}:
            return False
    return default


def _as_score(value: Any, default: int = 0, minimum: int = 0, maximum: int = 5) -> int:
    try:
        score = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, score))


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            if text:
                result.append(text)
        elif isinstance(item, dict):
            text = str(
                item.get("descricao")
                or item.get("descrição")
                or item.get("texto")
                or item.get("justificativa")
                or ""
            ).strip()
            if text:
                result.append(text)
        elif item is not None:
            text = str(item).strip()
            if text:
                result.append(text)
    return result


def _infer_string_decision(nota_final: int) -> str:
    if nota_final >= 5:
        return "APROVADA"
    if nota_final >= 4:
        return "APROVADA_COM_RESSALVAS"
    if nota_final >= 3:
        return "REVISAR"
    return "REPROVADA"


def _normalize_string_response(data: dict[str, Any]) -> dict[str, Any]:
    expected_criteria = [
        "cobertura_conceitual",
        "qualidade_sinonimos",
        "operadores_booleanos",
        "compatibilidade_base",
        "potencial_recall",
        "precisao",
    ]
    raw_criteria = data.get("criterios")
    criteria: dict[str, dict[str, Any]] = {}
    criterion_scores: list[int] = []

    for name in expected_criteria:
        item = raw_criteria.get(name, {}) if isinstance(raw_criteria, dict) else {}
        nota = _as_score(item.get("nota"), default=0)
        justificativa = str(item.get("justificativa", "") or "").strip()
        criteria[name] = {
            "nota": nota,
            "justificativa": justificativa,
        }
        if nota > 0:
            criterion_scores.append(nota)

    nota_final = _as_score(data.get("nota_final"), default=0)
    if nota_final == 0 and criterion_scores:
        nota_final = max(1, round(sum(criterion_scores) / len(criterion_scores)))

    decisao = str(data.get("decisao", "") or "").strip().upper()
    valid_decisions = {"APROVADA", "APROVADA_COM_RESSALVAS", "REVISAR", "REPROVADA"}
    if decisao not in valid_decisions:
        decisao = _infer_string_decision(nota_final)

    problemas = _as_string_list(data.get("problemas_identificados"))
    termos_ausentes = _as_string_list(data.get("termos_ausentes"))

    return {
        "nota_final": nota_final,
        "decisao": decisao,
        "criterios": criteria,
        "termos_ausentes": termos_ausentes,
        "problemas_identificados": problemas,
        "string_sugerida": str(data.get("string_sugerida", "") or "").strip(),
        "recomendacao": str(data.get("recomendacao", "") or "").strip(),
    }


def _normalize_article_response(data: dict[str, Any]) -> dict[str, Any]:
    concorda = _as_bool(data.get("concorda_com_aplicacao"), default=False)
    human_review = _as_bool(data.get("necessita_revisao_humana"), default=False)
    decisao = str(data.get("decisao_do_judge", "") or "").strip().upper()
    if decisao not in {"INCLUIR", "EXCLUIR", "INCERTO"}:
        decisao = "INCERTO"

    criterios_inclusao = _as_string_list(data.get("criterios_inclusao_identificados"))
    criterios_exclusao = _as_string_list(data.get("criterios_exclusao_identificados"))
    evidencias = _as_string_list(data.get("evidencias_textuais"))
    problemas = _as_string_list(data.get("problemas_identificados"))

    nota_final = _as_score(data.get("nota_final"), default=0)
    if nota_final == 0:
        if concorda and not human_review and evidencias and not problemas:
            nota_final = 4
        elif concorda and evidencias:
            nota_final = 3
        elif decisao == "INCERTO" or human_review:
            nota_final = 2
        else:
            nota_final = 1

    return {
        "concorda_com_aplicacao": concorda,
        "decisao_do_judge": decisao,
        "necessita_revisao_humana": human_review,
        "nota_final": nota_final,
        "criterios_inclusao_identificados": criterios_inclusao,
        "criterios_exclusao_identificados": criterios_exclusao,
        "evidencias_textuais": evidencias,
        "problemas_identificados": problemas,
        "recomendacao": str(data.get("recomendacao", "") or "").strip(),
    }


class MockLLMProvider(LLMProvider):
    """
    Provider local para demonstração.
    Ele não substitui um LLM real, mas permite validar fluxo, arquivos e regras.
    """

    def complete_json(self, prompt: str, task: str) -> dict[str, Any]:
        if task == "string":
            return self._mock_string_judge(prompt)
        if task == "article":
            return self._mock_article_judge(prompt)
        raise ValueError(f"Tarefa desconhecida: {task}")

    def _mock_string_judge(self, prompt: str) -> dict[str, Any]:
        text = prompt.lower()
        has_ai = any(term in text for term in ["artificial intelligence", "machine learning", "large language model", "llm"])
        has_review = any(term in text for term in ["systematic review", "systematic mapping", "literature review"])
        has_automation_stage = any(term in text for term in ["screening", "classification", "extraction", "summarization", "study selection"])
        has_boolean = " and " in text and " or " in text
        has_scopus_field = "title-abs-key" in text

        score = 1
        if has_ai:
            score += 1
        if has_review:
            score += 1
        if has_automation_stage:
            score += 1
        if has_boolean:
            score += 0.7
        if has_scopus_field:
            score += 0.3

        nota = min(round(score, 1), 5)

        problemas = []
        termos_ausentes = []

        if not has_ai:
            problemas.append("A string não cobre claramente o conceito de inteligência artificial.")
            termos_ausentes.append("artificial intelligence")
        if not has_review:
            problemas.append("A string não cobre claramente revisões sistemáticas ou mapeamentos.")
            termos_ausentes.append("systematic review")
        if not has_automation_stage:
            problemas.append("A string não cobre etapas específicas da revisão, como triagem, extração ou sumarização.")
            termos_ausentes.extend(["study selection", "screening", "extraction"])
        if "scopus" in text and not has_scopus_field:
            problemas.append("Para Scopus, recomenda-se adaptar a string para TITLE-ABS-KEY.")

        if nota >= 4.5:
            decisao = "APROVADA"
        elif nota >= 3.5:
            decisao = "APROVADA_COM_RESSALVAS"
        elif nota >= 2.5:
            decisao = "REVISAR"
        else:
            decisao = "REPROVADA"

        return {
            "nota_final": nota,
            "decisao": decisao,
            "criterios": {
                "cobertura_conceitual": {
                    "nota": 5 if has_ai and has_review and has_automation_stage else 3,
                    "justificativa": "A string cobre os principais conceitos." if has_ai and has_review and has_automation_stage else "A string cobre apenas parte dos conceitos principais."
                },
                "qualidade_sinonimos": {
                    "nota": 4 if has_ai else 2,
                    "justificativa": "Há termos alternativos relevantes para IA." if has_ai else "Faltam sinônimos relevantes para IA."
                },
                "operadores_booleanos": {
                    "nota": 5 if has_boolean else 2,
                    "justificativa": "A string usa operadores booleanos." if has_boolean else "A string não usa operadores booleanos de forma clara."
                },
                "compatibilidade_base": {
                    "nota": 5 if has_scopus_field else 3,
                    "justificativa": "A string está adaptada ao campo da base." if has_scopus_field else "A string pode precisar de adaptação para a base alvo."
                },
                "potencial_recall": {
                    "nota": 4 if has_ai and has_review else 2,
                    "justificativa": "A string tende a recuperar estudos relevantes." if has_ai and has_review else "A string pode perder estudos relevantes."
                },
                "precisao": {
                    "nota": 3,
                    "justificativa": "A precisão depende dos termos usados e pode ser ajustada após busca piloto."
                }
            },
            "termos_ausentes": sorted(set(termos_ausentes)),
            "problemas_identificados": problemas,
            "string_sugerida": 'TITLE-ABS-KEY(("artificial intelligence" OR "machine learning" OR "large language model" OR "natural language processing") AND ("systematic review" OR "systematic mapping" OR "evidence synthesis") AND ("study selection" OR screening OR classification OR extraction OR summarization))',
            "recomendacao": "Revisar a string antes da execução final." if problemas else "A string pode ser utilizada."
        }

    def _mock_article_judge(self, prompt: str) -> dict[str, Any]:
        text = prompt.lower()

        app_decision_match = re.search(r"decisão da aplicação:\s*(.+?)\n", prompt, re.IGNORECASE)
        decisao_aplicacao = app_decision_match.group(1).strip().upper() if app_decision_match else "INCERTO"

        mentions_ai = any(term in text for term in ["large language model", "llm", "artificial intelligence", "machine learning", "natural language processing"])
        mentions_review = any(term in text for term in ["systematic review", "systematic literature review", "systematic mapping", "literature review"])
        mentions_support = any(term in text for term in ["support", "assist", "automat", "classifies", "screening", "study selection", "extraction", "summarization"])

        # Caso comum de falso positivo: artigo é uma revisão sobre IA em algum domínio, mas não apoia revisão.
        domain_review_only = mentions_ai and mentions_review and not mentions_support

        if mentions_ai and mentions_review and mentions_support:
            judge_decision = "INCLUIR"
            nota = 5
            cis = ["CI-1", "CI-2", "CI-3"]
            ces = []
            evidencias = [
                "O texto menciona IA ou LLM.",
                "O texto menciona revisão sistemática ou mapeamento.",
                "O texto menciona apoio/automação de etapa como triagem, classificação, extração ou sumarização."
            ]
            problemas = []
            human = False
        elif domain_review_only:
            judge_decision = "EXCLUIR"
            nota = 2
            cis = []
            ces = ["CE-1"]
            evidencias = [
                "O texto indica que o artigo usa revisão sistemática como método.",
                "Não há evidência de ferramenta, técnica ou abordagem para apoiar revisões sistemáticas."
            ]
            problemas = [
                "Possível confusão entre artigo que usa revisão sistemática e artigo que apoia a realização de revisões sistemáticas."
            ]
            human = True
        else:
            judge_decision = "INCERTO"
            nota = 3
            cis = []
            ces = []
            evidencias = [
                "As informações fornecidas são insuficientes para uma decisão segura."
            ]
            problemas = [
                "O título/resumo não apresenta evidência suficiente para incluir ou excluir com segurança."
            ]
            human = True

        concorda = decisao_aplicacao == judge_decision

        return {
            "concorda_com_aplicacao": concorda,
            "decisao_do_judge": judge_decision,
            "necessita_revisao_humana": human or not concorda or nota < 4,
            "nota_final": nota,
            "criterios_inclusao_identificados": cis,
            "criterios_exclusao_identificados": ces,
            "evidencias_textuais": evidencias,
            "problemas_identificados": problemas,
            "recomendacao": "Manter a decisão da aplicação." if concorda and nota >= 4 else "Enviar para revisão humana."
        }


class OpenAICompatibleProvider(LLMProvider):
    """
    Provider para endpoints compatíveis com Chat Completions.

    Variáveis:
    - LLM_API_KEY
    - LLM_BASE_URL, padrão: https://api.openai.com/v1
    - LLM_MODEL, padrão: gpt-4.1-mini
    """

    def __init__(self) -> None:
        self.api_key = os.environ.get("LLM_API_KEY", "")
        self.base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.model = os.environ.get("LLM_MODEL", "gpt-4.1-mini")

        if not self.api_key:
            raise RuntimeError("LLM_API_KEY não configurada.")

    def complete_json(self, prompt: str, task: str) -> dict[str, Any]:
        print(f"[LLM] Usando provider=openai-compatible | modelo={self.model} | url={self.base_url}")
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Você é um avaliador rigoroso. "
                        "Retorne apenas JSON válido, sem markdown, sem comentários e sem texto extra. "
                        "Nunca use nota 0: use escala inteira de 1 a 5 quando houver campo de nota."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "response_format": {"type": "json_object"}
        }

        req = urllib.request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=90) as response:
            raw = response.read().decode("utf-8")

        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)

        if task == "string":
            return _normalize_string_response(parsed)
        if task == "article":
            return _normalize_article_response(parsed)
        return parsed


def get_provider() -> LLMProvider:
    load_dotenv_file()
    provider = os.environ.get("LLM_PROVIDER", "mock").lower().strip()

    if provider == "mock":
        return MockLLMProvider()

    if provider in {"openai", "openai-compatible", "chat-completions"}:
        return OpenAICompatibleProvider()

    raise ValueError(f"LLM_PROVIDER inválido: {provider}")
