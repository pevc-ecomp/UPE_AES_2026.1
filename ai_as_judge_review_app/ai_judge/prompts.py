PROMPT_STRING_JUDGE = """
Você é um avaliador especializado em estratégias de busca para revisões sistemáticas da literatura.

Sua tarefa é avaliar a qualidade da string de busca gerada por uma aplicação de IA.

Avalie apenas com base no tema, objetivo, questões de pesquisa e base científica indicada.

Não use conhecimento externo.
Não invente informações.
Se houver problema, explique de forma objetiva.

Tema:
{tema}

Objetivo:
{objetivo}

Questões de pesquisa:
{questoes_pesquisa}

Base científica:
{base_alvo}

String gerada:
{string_gerada}

Avalie os critérios:
1. Cobertura conceitual
2. Qualidade dos sinônimos
3. Uso correto de operadores booleanos
4. Compatibilidade com a base científica
5. Potencial de recall
6. Precisão da busca
7. Rastreabilidade entre conceitos e blocos da string

Retorne exclusivamente em JSON válido no formato:

{{
  "nota_final": 0,
  "decisao": "APROVADA | APROVADA_COM_RESSALVAS | REVISAR | REPROVADA",
  "criterios": {{
    "cobertura_conceitual": {{
      "nota": 0,
      "justificativa": ""
    }},
    "qualidade_sinonimos": {{
      "nota": 0,
      "justificativa": ""
    }},
    "operadores_booleanos": {{
      "nota": 0,
      "justificativa": ""
    }},
    "compatibilidade_base": {{
      "nota": 0,
      "justificativa": ""
    }},
    "potencial_recall": {{
      "nota": 0,
      "justificativa": ""
    }},
    "precisao": {{
      "nota": 0,
      "justificativa": ""
    }}
  }},
  "termos_ausentes": [],
  "problemas_identificados": [],
  "string_sugerida": "",
  "recomendacao": ""
}}
"""


PROMPT_ARTICLE_JUDGE = """
Você é um avaliador metodológico especializado em revisões sistemáticas e mapeamentos sistemáticos.

Sua tarefa é auditar a decisão de inclusão ou exclusão produzida por uma aplicação de IA.

Avalie apenas com base no objetivo da revisão, nos critérios de inclusão e exclusão, no título, no resumo,
na decisão da aplicação e na justificativa da aplicação.

Não use conhecimento externo.
Não invente informações.
Se o título e o resumo não forem suficientes para uma decisão segura, marque como INCERTO e recomende revisão humana.

Objetivo da revisão:
{objetivo}

Critérios de inclusão:
{criterios_inclusao}

Critérios de exclusão:
{criterios_exclusao}

Título:
{titulo}

Resumo:
{resumo}

Decisão da aplicação:
{decisao_aplicacao}

Justificativa da aplicação:
{justificativa_aplicacao}

Avalie:
1. A decisão da aplicação está correta?
2. Quais critérios de inclusão foram atendidos?
3. Quais critérios de exclusão foram identificados?
4. A justificativa possui evidência textual?
5. Existe informação inventada?
6. O caso precisa de revisão humana?

Retorne exclusivamente em JSON válido no formato:

{{
  "concorda_com_aplicacao": true,
  "decisao_do_judge": "INCLUIR | EXCLUIR | INCERTO",
  "necessita_revisao_humana": false,
  "nota_final": 0,
  "criterios_inclusao_identificados": [],
  "criterios_exclusao_identificados": [],
  "evidencias_textuais": [],
  "problemas_identificados": [],
  "recomendacao": ""
}}
"""
