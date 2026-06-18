# Explicacao da Aplicacao

## Visao Geral

Esta aplicacao implementa a ideia de "AI as Judge" para apoiar revisoes sistematicas. Em vez de usar o modelo apenas para gerar conteudo, o sistema usa um LLM como avaliador de dois tipos de saida:

1. Strings de busca usadas em bases como Scopus.
2. Decisoes de classificacao de artigos feitas por outro modelo.

O objetivo e verificar se essas saidas fazem sentido do ponto de vista metodologico, com criterios mais consistentes e retorno estruturado em JSON.

## Arquitetura Geral

Os arquivos principais sao:

- [app/main.py](C:/Users/Jamue/Documents/mestrado/aplEngSoftware/ia-judge/ia-judge/app/main.py:1): expoe a API FastAPI e define os endpoints.
- [app/judges.py](C:/Users/Jamue/Documents/mestrado/aplEngSoftware/ia-judge/ia-judge/app/judges.py:1): contem a logica principal de julgamento.
- [app/llm_client.py](C:/Users/Jamue/Documents/mestrado/aplEngSoftware/ia-judge/ia-judge/app/llm_client.py:1): faz a chamada ao modelo usando API compativel com OpenAI.
- [app/schemas.py](C:/Users/Jamue/Documents/mestrado/aplEngSoftware/ia-judge/ia-judge/app/schemas.py:1): define os modelos de entrada e saida com Pydantic.
- [app/config.py](C:/Users/Jamue/Documents/mestrado/aplEngSoftware/ia-judge/ia-judge/app/config.py:1): le configuracoes do `.env`.

## Como o Fluxo Funciona

### 1. Requisicao HTTP

O usuario envia um `POST` para um dos endpoints:

- `/judge/string`
- `/judge/articles`

O FastAPI recebe o corpo da requisicao e valida os dados de entrada usando os modelos definidos em `schemas.py`.

### 2. Montagem do Prompt

Em `judges.py`, a aplicacao monta um prompt em ingles com:

- contexto da tarefa;
- criterios de avaliacao;
- formato JSON esperado;
- regras de decisao.

O uso de prompt em ingles ajuda a manter maior consistencia na obediencia estrutural dos modelos.

### 3. Chamada ao LLM

Em `llm_client.py`, a funcao `ask_llm()` envia:

- uma mensagem `system`, com instrucoes fixas;
- uma mensagem `user`, com o prompt montado dinamicamente.

A chamada usa:

- `temperature=0`, para reduzir variacao;
- um modelo local ou remoto compativel com a API OpenAI;
- configuracao via `.env`.

Exemplo atual de configuracao:

```env
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.2
```

## Julgamento de Strings de Busca

### Objetivo

Avaliar se uma string de busca esta adequada para uma revisao sistematica.

### Criterios usados

O modelo pontua de `0` a `5` em seis criterios:

1. `conceptual_coverage`
2. `synonym_quality`
3. `boolean_operators`
4. `database_compatibility`
5. `recall_potential`
6. `precision`

### Problema que existia

Inicialmente, o sistema pedia ao proprio LLM para:

- atribuir as notas;
- calcular a media final;
- decidir entre `APPROVE`, `REVISE` e `REJECT`.

Na pratica, isso gerava erros como:

- `final_score` vindo como texto, por exemplo `"(0 + 2 + 3) / 6"`;
- decisao incoerente com as notas;
- JSON encapsulado como string.

### Como isso foi melhorado

Agora o backend trata o modelo como avaliador dos criterios, mas nao confia nele para a conta final.

Em [app/judges.py](C:/Users/Jamue/Documents/mestrado/aplEngSoftware/ia-judge/ia-judge/app/judges.py:37), a aplicacao:

1. extrai o JSON retornado pelo LLM;
2. valida os campos com Pydantic;
3. recalcula `final_score` com base nas seis notas;
4. define a `decision` no servidor.

As regras sao:

- `APPROVE` se `final_score >= 4`
- `REVISE` se `final_score >= 2.5` e `< 4`
- `REJECT` se `final_score < 2.5`

Isso deixa o sistema mais robusto, reproduzivel e auditavel.

### Exemplo de saida esperada

```json
{
  "type": "SEARCH_STRING_JUDGE",
  "final_score": 4.17,
  "decision": "APPROVE",
  "criteria": {
    "conceptual_coverage": {
      "score": 4,
      "justification": "Covers the main review concepts."
    },
    "synonym_quality": {
      "score": 4,
      "justification": "Includes relevant term variations."
    },
    "boolean_operators": {
      "score": 5,
      "justification": "Logical grouping is clear and correct."
    },
    "database_compatibility": {
      "score": 4,
      "justification": "Compatible with Scopus syntax."
    },
    "recall_potential": {
      "score": 4,
      "justification": "Likely to retrieve relevant studies."
    },
    "precision": {
      "score": 4,
      "justification": "Reasonably focused query."
    }
  },
  "identified_problems": [],
  "improvement_suggestions": []
}
```

## Julgamento de Classificacao de Artigos

### Objetivo

Avaliar se a classificacao de artigos feita por outro modelo esta coerente com:

- o objetivo da revisao;
- os criterios de inclusao;
- os criterios de exclusao.

### O que o modelo avalia

Para cada artigo, o sistema pede ao LLM que verifique:

1. se a classificacao faz sentido;
2. se a justificativa fornecida e suficiente;
3. se existe risco de erro;
4. se revisao humana e recomendada.

### Estrutura da resposta

Cada artigo retorna algo como:

```json
{
  "title": "Example article",
  "model_classification": "INCLUDE",
  "judge_verdict": "CORRECT",
  "confidence_score": 4,
  "judge_justification": "Aligned with the review objective.",
  "human_review_recommended": false
}
```

O resultado geral tambem inclui:

- `overall_result`
- `summary`
- `main_risks`

## Validacao Estrutural com Pydantic

Em [app/schemas.py](C:/Users/Jamue/Documents/mestrado/aplEngSoftware/ia-judge/ia-judge/app/schemas.py:25), foram definidos modelos de resposta para garantir que:

- notas estejam entre `0` e `5`;
- campos obrigatorios existam;
- os tipos estejam corretos;
- os valores aceitos sejam limitados, por exemplo `APPROVE`, `REVISE` ou `REJECT`.

Isso e importante porque LLMs podem responder com estrutura parcialmente correta, mas sem confiabilidade suficiente para uso direto sem validacao.

## Por Que Essa Abordagem Faz Sentido

Esta arquitetura separa responsabilidades:

- o LLM faz julgamento semantico;
- o backend faz validacao estrutural;
- o backend tambem faz regras deterministicas, como media e decisao final.

Essa separacao melhora:

- confiabilidade;
- repetibilidade;
- facilidade de depuracao;
- capacidade de justificar os resultados em contexto academico.

## Limitacoes Atuais

Mesmo com a melhoria, ainda existem limitacoes:

- modelos pequenos podem produzir justificativas pobres;
- o julgamento depende fortemente da qualidade do prompt;
- a classificacao de artigos ainda depende de resumo e metadados curtos;
- `overall_result` dos artigos ainda pode ser refinado com regras no backend, se voce quiser aumentar consistencia.

## Possiveis Melhorias Futuras

Algumas evolucoes interessantes para o projeto:

1. Calcular `overall_result` dos artigos no backend, assim como foi feito com `final_score`.
2. Exigir pelo menos uma sugestao de melhoria quando a nota final for baixa.
3. Criar testes automatizados com exemplos bons, medianos e ruins.
4. Salvar historico de julgamentos para comparacao entre modelos.
5. Adicionar explicacoes mais detalhadas para apoiar a reescrita da string de busca.
6. Medir concordancia entre julgamento automatico e avaliacao humana.

## Resumo

Em termos simples, a aplicacao funciona assim:

1. recebe uma entrada da revisao sistematica;
2. envia essa entrada para um LLM com instrucoes rigidamente definidas;
3. recebe uma resposta JSON;
4. valida essa resposta;
5. corrige e calcula no backend o que for deterministico;
6. devolve um resultado estruturado e mais confiavel para o usuario.

Essa ideia e especialmente util quando voce quer usar LLMs nao apenas como geradores, mas como avaliadores controlados dentro de um pipeline metodologico.
