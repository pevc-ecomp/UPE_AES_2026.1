def acao_para_string(avaliacao: dict) -> str:
    decisao = str(avaliacao.get("decisao", "")).upper()

    if decisao == "APROVADA":
        return "USAR_STRING"
    if decisao == "APROVADA_COM_RESSALVAS":
        return "USAR_COM_RESSALVAS"
    if decisao == "REVISAR":
        return "REVISAR_STRING"
    return "GERAR_NOVA_STRING"


def acao_para_classificacao(avaliacao: dict) -> str:
    if avaliacao.get("necessita_revisao_humana") is True:
        return "ENVIAR_REVISAO_HUMANA"

    nota = float(avaliacao.get("nota_final", 0) or 0)
    concorda = bool(avaliacao.get("concorda_com_aplicacao", False))

    if concorda and nota >= 4:
        return "ACEITAR_DECISAO"

    if concorda and 3 <= nota < 4:
        return "ACEITAR_COM_RESSALVAS"

    return "ENVIAR_REVISAO_HUMANA"
