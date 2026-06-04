import argparse
import csv
import json
from pathlib import Path

from ai_judge.providers import get_provider
from ai_judge.judges import avaliar_string_com_judge, avaliar_classificacao_com_judge


def load_json(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str | Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def command_judge_string(args) -> None:
    provider = get_provider()
    protocolo = load_json(args.protocolo)
    string_input = load_json(args.string_input)

    resultado = avaliar_string_com_judge(
        provider=provider,
        protocolo=protocolo,
        string_gerada=string_input["string_gerada"]
    )

    save_json(args.out, resultado)
    print(f"Resultado salvo em: {args.out}")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


def command_judge_articles(args) -> None:
    provider = get_provider()
    protocolo = load_json(args.protocolo)

    output_rows = []

    with open(args.articles, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        required = {
            "id",
            "titulo",
            "resumo",
            "decisao_aplicacao",
            "justificativa_aplicacao"
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV sem colunas obrigatórias: {sorted(missing)}")

        for row in reader:
            artigo = {
                "titulo": row["titulo"],
                "resumo": row["resumo"]
            }
            classificacao = {
                "decisao": row["decisao_aplicacao"],
                "justificativa": row["justificativa_aplicacao"]
            }

            resultado = avaliar_classificacao_com_judge(
                provider=provider,
                protocolo=protocolo,
                artigo=artigo,
                classificacao_aplicacao=classificacao
            )

            avaliacao = resultado["avaliacao"]

            output_rows.append({
                "id": row["id"],
                "titulo": row["titulo"],
                "decisao_aplicacao": row["decisao_aplicacao"],
                "decisao_judge": avaliacao.get("decisao_do_judge", ""),
                "concorda_com_aplicacao": avaliacao.get("concorda_com_aplicacao", ""),
                "nota_final": avaliacao.get("nota_final", ""),
                "necessita_revisao_humana": avaliacao.get("necessita_revisao_humana", ""),
                "acao_recomendada": resultado["acao_recomendada"],
                "criterios_inclusao_identificados": json.dumps(
                    avaliacao.get("criterios_inclusao_identificados", []),
                    ensure_ascii=False
                ),
                "criterios_exclusao_identificados": json.dumps(
                    avaliacao.get("criterios_exclusao_identificados", []),
                    ensure_ascii=False
                ),
                "evidencias_textuais": json.dumps(
                    avaliacao.get("evidencias_textuais", []),
                    ensure_ascii=False
                ),
                "problemas_identificados": json.dumps(
                    avaliacao.get("problemas_identificados", []),
                    ensure_ascii=False
                ),
                "recomendacao": avaliacao.get("recomendacao", "")
            })

    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "id",
            "titulo",
            "decisao_aplicacao",
            "decisao_judge",
            "concorda_com_aplicacao",
            "nota_final",
            "necessita_revisao_humana",
            "acao_recomendada",
            "criterios_inclusao_identificados",
            "criterios_exclusao_identificados",
            "evidencias_textuais",
            "problemas_identificados",
            "recomendacao"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Resultado salvo em: {args.out}")
    print(f"Total de artigos avaliados: {len(output_rows)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aplicação Python de AI as Judge para revisões sistemáticas."
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    p_string = subparsers.add_parser(
        "judge-string",
        help="Avalia a string de busca gerada pela aplicação."
    )
    p_string.add_argument("--protocolo", required=True)
    p_string.add_argument("--string-input", required=True)
    p_string.add_argument("--out", required=True)
    p_string.set_defaults(func=command_judge_string)

    p_articles = subparsers.add_parser(
        "judge-articles",
        help="Avalia classificações de artigos em lote a partir de CSV."
    )
    p_articles.add_argument("--protocolo", required=True)
    p_articles.add_argument("--articles", required=True)
    p_articles.add_argument("--out", required=True)
    p_articles.set_defaults(func=command_judge_articles)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
