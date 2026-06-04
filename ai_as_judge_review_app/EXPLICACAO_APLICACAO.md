# Explicacao da Aplicacao AI as Judge

## Visao geral

Esta aplicacao implementa uma camada de auditoria para uma revisao sistematica apoiada por IA.
Ela nao executa a busca nem classifica os estudos por conta propria como processo principal da revisao.
O papel dela e atuar como "juiz" de outra aplicacao ou modelo que:

1. gera uma string de busca;
2. classifica artigos como `INCLUIR`, `EXCLUIR` ou `INCERTO`.

O sistema recebe a saida dessa outra aplicacao, compara com o protocolo da revisao e devolve uma avaliacao estruturada em JSON ou CSV.

Hoje existem dois juizes:

1. `judge-string`: audita a qualidade da string de busca.
2. `judge-articles`: audita a classificacao de artigos em lote.

## Estrutura do projeto

Arquivos principais:

1. [app.py](/abs/path/c:/Users/Jamue/Documents/mestrado/aplEngSoftware/iaAsJudge_v1/ai_as_judge/ai_as_judge_review_app/app.py)
   Ponto de entrada CLI. Le arquivos, chama os juizes e grava saidas.
2. [ai_judge/judges.py](/abs/path/c:/Users/Jamue/Documents/mestrado/aplEngSoftware/iaAsJudge_v1/ai_as_judge/ai_as_judge_review_app/ai_judge/judges.py)
   Monta os prompts com base no protocolo e delega a avaliacao ao provider.
3. [ai_judge/prompts.py](/abs/path/c:/Users/Jamue/Documents/mestrado/aplEngSoftware/iaAsJudge_v1/ai_as_judge/ai_as_judge_review_app/ai_judge/prompts.py)
   Define as instrucoes que o juiz deve seguir.
4. [ai_judge/providers.py](/abs/path/c:/Users/Jamue/Documents/mestrado/aplEngSoftware/iaAsJudge_v1/ai_as_judge/ai_as_judge_review_app/ai_judge/providers.py)
   Implementa os modos `mock` e `openai-compatible`.
5. [ai_judge/rules.py](/abs/path/c:/Users/Jamue/Documents/mestrado/aplEngSoftware/iaAsJudge_v1/ai_as_judge/ai_as_judge_review_app/ai_judge/rules.py)
   Traduz a avaliacao do juiz em uma acao recomendada para o fluxo.
6. [examples/protocolo.json](/abs/path/c:/Users/Jamue/Documents/mestrado/aplEngSoftware/iaAsJudge_v1/ai_as_judge/ai_as_judge_review_app/examples/protocolo.json)
   Exemplo do protocolo da revisao.
7. [examples/string_input.json](/abs/path/c:/Users/Jamue/Documents/mestrado/aplEngSoftware/iaAsJudge_v1/ai_as_judge/ai_as_judge_review_app/examples/string_input.json)
   Exemplo da string produzida pela aplicacao avaliada.
8. [examples/artigos.csv](/abs/path/c:/Users/Jamue/Documents/mestrado/aplEngSoftware/iaAsJudge_v1/ai_as_judge/ai_as_judge_review_app/examples/artigos.csv)
   Exemplo de lote de artigos ja classificados pela aplicacao avaliada.

## Como o fluxo funciona

## 1. Entrada metodologica

O centro do processo e o `protocolo.json`.
Ele contem o contexto que limita o julgamento:

1. `tema`
2. `objetivo`
3. `questoes_pesquisa`
4. `criterios_inclusao`
5. `criterios_exclusao`
6. `base_alvo`

Isso e importante porque o juiz foi desenhado para avaliar apenas com base no protocolo e no texto recebido.
Nos prompts ha a instrucao explicita para nao usar conhecimento externo e nao inventar informacoes.

## 2. Escolha do provider

Quando a aplicacao inicia, `get_provider()` em `providers.py`:

1. carrega automaticamente um `.env` simples, se existir;
2. le `LLM_PROVIDER`;
3. instancia o provider adequado.

Opcoes atuais:

1. `mock`
   Nao chama API externa. Usa heuristicas locais para simular o comportamento do juiz.
2. `openai-compatible`
   Envia o prompt para um endpoint compativel com `chat/completions`.

Variaveis usadas no modo real:

1. `LLM_PROVIDER`
2. `LLM_API_KEY`
3. `LLM_BASE_URL`
4. `LLM_MODEL`

## 3. Fluxo do juiz da string

Comando:

```bash
python app.py judge-string --protocolo examples/protocolo.json --string-input examples/string_input.json --out resultado_string.json
```

Passo a passo:

1. `app.py` carrega `protocolo.json` e `string_input.json`.
2. `command_judge_string()` extrai `string_gerada`.
3. `avaliar_string_com_judge()` monta `PROMPT_STRING_JUDGE`.
4. O provider executa `complete_json(prompt, task="string")`.
5. A resposta do juiz vai para `acao_para_string()`.
6. O resultado final e salvo em JSON.

### O que o juiz da string avalia

O prompt pede avaliacao de:

1. cobertura conceitual;
2. qualidade dos sinonimos;
3. operadores booleanos;
4. compatibilidade com a base;
5. potencial de recall;
6. precisao;
7. rastreabilidade entre conceitos e blocos da string.

### Estrutura da saida

O JSON final possui:

1. `tipo`
2. `avaliacao`
3. `acao_recomendada`

Dentro de `avaliacao`, a expectativa e receber:

1. `nota_final`
2. `decisao`
3. `criterios`
4. `termos_ausentes`
5. `problemas_identificados`
6. `string_sugerida`
7. `recomendacao`

### Regras de acao para string

Em `rules.py`:

1. `APROVADA` -> `USAR_STRING`
2. `APROVADA_COM_RESSALVAS` -> `USAR_COM_RESSALVAS`
3. `REVISAR` -> `REVISAR_STRING`
4. qualquer outro caso -> `GERAR_NOVA_STRING`

## 4. Fluxo do juiz de classificacao de artigos

Comando:

```bash
python app.py judge-articles --protocolo examples/protocolo.json --articles examples/artigos.csv --out resultado_artigos.csv
```

Passo a passo:

1. `app.py` carrega o protocolo.
2. O CSV e aberto com `utf-8-sig`.
3. O sistema valida as colunas obrigatorias:
   `id`, `titulo`, `resumo`, `decisao_aplicacao`, `justificativa_aplicacao`.
4. Cada linha vira:
   um objeto `artigo` e um objeto `classificacao_aplicacao`.
5. `avaliar_classificacao_com_judge()` monta `PROMPT_ARTICLE_JUDGE`.
6. O provider executa `complete_json(prompt, task="article")`.
7. `acao_para_classificacao()` converte a avaliacao em acao operacional.
8. O sistema grava um novo CSV com os resultados do juiz.

### O que o juiz dos artigos avalia

O prompt pede que o juiz responda:

1. se a decisao da aplicacao esta correta;
2. quais criterios de inclusao foram atendidos;
3. quais criterios de exclusao aparecem;
4. se a justificativa tem evidencia textual;
5. se ha informacao inventada;
6. se o caso precisa de revisao humana.

### Estrutura da saida intermediaria do juiz

Para cada artigo, o provider deve retornar algo no formato:

1. `concorda_com_aplicacao`
2. `decisao_do_judge`
3. `necessita_revisao_humana`
4. `nota_final`
5. `criterios_inclusao_identificados`
6. `criterios_exclusao_identificados`
7. `evidencias_textuais`
8. `problemas_identificados`
9. `recomendacao`

### Estrutura do CSV de saida

O arquivo final possui as colunas:

1. `id`
2. `titulo`
3. `decisao_aplicacao`
4. `decisao_judge`
5. `concorda_com_aplicacao`
6. `nota_final`
7. `necessita_revisao_humana`
8. `acao_recomendada`
9. `criterios_inclusao_identificados`
10. `criterios_exclusao_identificados`
11. `evidencias_textuais`
12. `problemas_identificados`
13. `recomendacao`

### Regras de acao para artigos

Em `rules.py`, a logica e:

1. se `necessita_revisao_humana == True` -> `ENVIAR_REVISAO_HUMANA`
2. se concorda com a aplicacao e `nota_final >= 4` -> `ACEITAR_DECISAO`
3. se concorda com a aplicacao e `3 <= nota_final < 4` -> `ACEITAR_COM_RESSALVAS`
4. nos demais casos -> `ENVIAR_REVISAO_HUMANA`

## Como o modo mock funciona

O modo `mock` existe para demonstrar o pipeline sem dependencia de API externa.

### Mock do juiz da string

Ele procura, dentro do texto do prompt, sinais simples de:

1. termos de IA;
2. termos de revisao sistematica;
3. termos de etapas automatizadas da revisao;
4. operadores booleanos `AND` e `OR`;
5. adaptacao para Scopus com `TITLE-ABS-KEY`.

Com base nisso, calcula uma nota, lista problemas, identifica termos ausentes e sugere uma string.

### Mock do juiz dos artigos

Ele procura, no prompt:

1. mencoes a IA;
2. mencoes a revisao sistematica;
3. mencoes a apoio, automacao, screening, classificacao, extracao ou sumarizacao.

Regras principais:

1. se houver IA + revisao + apoio operacional, tende a `INCLUIR`;
2. se o texto parecer apenas uma revisao sobre IA em algum dominio, tende a `EXCLUIR`;
3. se faltar evidencia suficiente, retorna `INCERTO`.

Esse mock e util para validar integracao, mas nao representa um julgamento metodologico robusto.

## Como o modo real funciona

No provider `OpenAICompatibleProvider`:

1. o sistema envia um `system prompt` pedindo "apenas JSON valido";
2. envia o prompt especifico da tarefa como mensagem `user`;
3. usa `temperature = 0`;
4. pede `response_format = json_object`;
5. converte a resposta textual em dicionario Python.

Na pratica, isso permite trocar o modelo mantendo o restante da aplicacao igual, desde que o endpoint seja compativel com `chat/completions`.

## Papel de cada camada

### `app.py`

Responsavel por:

1. interface de linha de comando;
2. leitura e escrita de arquivos;
3. validacao do CSV de entrada;
4. iteracao sobre os artigos;
5. transformacao da avaliacao em arquivos finais.

### `judges.py`

Responsavel por:

1. converter os dados do protocolo em prompt;
2. padronizar listas com `_format_list`;
3. chamar o provider com a tarefa certa;
4. acoplar a resposta do juiz a uma acao recomendada.

### `prompts.py`

Responsavel por definir o contrato do julgamento.
Aqui esta a principal ideia de "AI as judge": o modelo nao responde livremente; ele recebe um papel, limites metodologicos e um schema de saida.

### `providers.py`

Responsavel por abstrair a fonte da avaliacao.
Essa separacao permite:

1. testar localmente com `mock`;
2. trocar de modelo sem mudar o fluxo;
3. evoluir para novos providers no futuro.

### `rules.py`

Responsavel por transformar uma avaliacao em uma decisao operacional de pipeline.
Ou seja, o juiz produz uma analise; as regras convertem essa analise em uma proxima acao.

## Entradas e saidas da aplicacao

## Entrada da string

Arquivo JSON com:

```json
{
  "string_gerada": "..."
}
```

## Entrada dos artigos

CSV com:

```csv
id,titulo,resumo,decisao_aplicacao,justificativa_aplicacao
```

## Saida do judge-string

Arquivo JSON estruturado para auditoria da string.

## Saida do judge-articles

CSV enriquecido com o parecer do juiz e a acao recomendada.

## O que a aplicacao faz bem hoje

1. separa claramente protocolo, prompts, providers e regras;
2. permite executar o fluxo sem dependencia externa via `mock`;
3. gera saidas rastreaveis;
4. ja esta pronta para comparar "decisao da aplicacao" versus "decisao do juiz";
5. trata o juiz como auditor, nao como verdade absoluta.

## Limitacoes atuais

1. O `mock` usa heuristicas simples baseadas em palavras-chave.
2. A qualidade real do julgamento depende fortemente do prompt e do modelo configurado.
3. Nao ha camada de validacao estrutural forte do JSON retornado pelo LLM.
4. Nao ha testes automatizados no repositorio atual.
5. Nao ha persistencia de historico de julgamentos alem dos arquivos gerados.
6. Nao ha metricas comparando o judge com revisores humanos.
7. Os arquivos [resultado_string.json](/abs/path/c:/Users/Jamue/Documents/mestrado/aplEngSoftware/iaAsJudge_v1/ai_as_judge/ai_as_judge_review_app/resultado_string.json) e [resultado_artigos.csv](/abs/path/c:/Users/Jamue/Documents/mestrado/aplEngSoftware/iaAsJudge_v1/ai_as_judge/ai_as_judge_review_app/resultado_artigos.csv) parecem ter sido gerados por uma versao anterior ou por outro provider, porque nao batem com a estrutura esperada do `mock` atual em alguns campos.

## Resumo conceitual

Em termos de arquitetura, a aplicacao funciona assim:

1. o protocolo define o criterio metodologico;
2. outra IA ou aplicacao produz uma string ou uma classificacao;
3. o judge recebe essa saida como objeto auditavel;
4. o provider executa o julgamento;
5. as regras transformam a avaliacao em uma acao de pipeline;
6. o sistema grava artefatos rastreaveis para revisao posterior.

Em outras palavras, o projeto implementa bem a ideia de "IA como juiz" porque separa:

1. quem produz a decisao inicial;
2. quem audita essa decisao;
3. quais regras definem a acao seguinte.
