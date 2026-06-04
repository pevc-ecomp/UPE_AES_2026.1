# AI as Judge para Revisões Sistemáticas

Aplicação Python mínima para demonstrar dois avaliadores baseados em IA as Judge:

1. **Judge da String de Busca**  
   Avalia cobertura conceitual, sinônimos, operadores booleanos, compatibilidade com a base, potencial de recall e precisão.

2. **Judge da Classificação dos Artigos**  
   Avalia se a decisão de `INCLUIR`, `EXCLUIR` ou `INCERTO` está coerente com critérios de inclusão/exclusão, título, resumo e justificativa da aplicação.

Por padrão, o projeto roda em modo `mock`, sem API externa. Isso permite testar o fluxo completo.

---

## 1. Estrutura

```text
ai_as_judge_review_app/
├── app.py
├── requirements.txt
├── README.md
├── ai_judge/
│   ├── __init__.py
│   ├── judges.py
│   ├── prompts.py
│   ├── providers.py
│   └── rules.py
└── examples/
    ├── protocolo.json
    ├── string_input.json
    └── artigos.csv
```

---

## 2. Rodar exemplo da string

```bash
python app.py judge-string \
  --protocolo examples/protocolo.json \
  --string-input examples/string_input.json \
  --out resultado_string.json
```

---

## 3. Rodar exemplo de classificação de artigos em lote

```bash
python app.py judge-articles \
  --protocolo examples/protocolo.json \
  --articles examples/artigos.csv \
  --out resultado_artigos.csv
```

---

## 4. CSV esperado para artigos

```csv
id,titulo,resumo,decisao_aplicacao,justificativa_aplicacao
A001,Using Large Language Models...,This paper presents...,INCLUIR,O artigo utiliza LLM...
```

---

## 5. Usar com LLM real futuramente

Por padrão:

```bash
export LLM_PROVIDER=mock
```

Para usar um endpoint compatível com Chat Completions:

```bash
export LLM_PROVIDER=openai-compatible
export LLM_API_KEY="sua-chave"
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_MODEL="gpt-4.1-mini"
```

Depois rode os mesmos comandos.

---

## 6. Papel metodológico

O AI Judge não é tratado como verdade absoluta. Ele atua como uma camada de auditoria que:

- identifica problemas na string;
- recomenda ajustes;
- verifica se a classificação aplicou corretamente CI/CE;
- exige evidência textual;
- marca casos incertos para revisão humana;
- gera saídas rastreáveis para comparação posterior com revisores humanos.


---

## Usando arquivo .env

O projeto já carrega automaticamente um arquivo `.env` localizado na raiz.

Exemplo de `.env` para testar sem API:

```env
LLM_PROVIDER=mock
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4.1-mini
LLM_API_KEY=
```

Exemplo de `.env` para usar um LLM real compatível com Chat Completions:

```env
LLM_PROVIDER=openai-compatible
LLM_API_KEY=sua-chave-aqui
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4.1-mini
```

Depois disso, basta rodar normalmente:

```bash
python app.py judge-string --protocolo examples/protocolo.json --string-input examples/string_input.json --out resultado_string.json
```

ou:

```bash
python app.py judge-articles --protocolo examples/protocolo.json --articles examples/artigos.csv --out resultado_artigos.csv
```

