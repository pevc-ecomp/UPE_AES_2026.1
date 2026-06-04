from .prompts import PROMPT_STRING_JUDGE, PROMPT_ARTICLE_JUDGE
from .providers import LLMProvider
from .rules import acao_para_string, acao_para_classificacao


def _format_list(values: list[str]) -> str:
    return "\n".join(f"- {item}" for item in values)


def avaliar_string_com_judge(
    provider: LLMProvider,
    protocolo: dict,
    string_gerada: str
) -> dict:
    prompt = PROMPT_STRING_JUDGE.format(
        tema=protocolo.get("tema", ""),
        objetivo=protocolo.get("objetivo", ""),
        questoes_pesquisa=_format_list(protocolo.get("questoes_pesquisa", [])),
        base_alvo=protocolo.get("base_alvo", ""),
        string_gerada=string_gerada
    )

    avaliacao = provider.complete_json(prompt=prompt, task="string")
    acao = acao_para_string(avaliacao)

    return {
        "tipo": "STRING_JUDGE",
        "avaliacao": avaliacao,
        "acao_recomendada": acao
    }


def avaliar_classificacao_com_judge(
    provider: LLMProvider,
    protocolo: dict,
    artigo: dict,
    classificacao_aplicacao: dict
) -> dict:
    prompt = PROMPT_ARTICLE_JUDGE.format(
        objetivo=protocolo.get("objetivo", ""),
        criterios_inclusao=_format_list(protocolo.get("criterios_inclusao", [])),
        criterios_exclusao=_format_list(protocolo.get("criterios_exclusao", [])),
        titulo=artigo.get("titulo", ""),
        resumo=artigo.get("resumo", ""),
        decisao_aplicacao=classificacao_aplicacao.get("decisao", ""),
        justificativa_aplicacao=classificacao_aplicacao.get("justificativa", "")
    )

    avaliacao = provider.complete_json(prompt=prompt, task="article")
    acao = acao_para_classificacao(avaliacao)

    return {
        "tipo": "ARTICLE_CLASSIFICATION_JUDGE",
        "avaliacao": avaliacao,
        "acao_recomendada": acao
    }
