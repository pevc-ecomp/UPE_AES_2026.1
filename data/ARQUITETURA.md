# Arquitetura do Sistema — UPE_AES_2026.1

Documento de referência da arquitetura da plataforma de apoio a Revisões Sistemáticas da Literatura (RSL).

> Os diagramas estão em **Mermaid** e renderizam como imagem no GitHub, no VS Code (preview de Markdown) e em https://mermaid.live. Cada feature tem duas versões do fluxo: uma **genérica** (papéis, sem citar modelos) e uma **com os modelos básicos** realmente configurados.

---

## 1. Arquitetura geral

O sistema é composto por **4 containers Docker** na rede `research_network`, orquestrados via `docker-compose.yml`, mais um provedor externo (API da Anthropic):

| Serviço | Tecnologia | Porta (host) | Papel |
|---|---|---|---|
| `frontend` | Streamlit | 8501 | Interface do usuário (multipage): Agentes, String Optimizer, Article Evaluator, AI Judge, Histórico |
| `backend` | FastAPI + SQLModel/SQLite | 8000 | CRUD de agentes/versões e avaliação de artigos (individual e em lote via Batch API) |
| `ia-judge` | FastAPI | 8002 | Serviço "IA como juíza": julga strings de busca e classificações de artigos |
| `ollama` | Ollama (limite 5 GB RAM) | 11434 | LLM local — `phi3:mini` (principal) e `llama3.2:1b` (fallback/juiz) |
| — | API Anthropic (externa) | — | Provedor alternativo de LLM: `claude-sonnet-5`, `claude-haiku-4-5` (individual, com prompt caching, e Batch API) |

> O container do **Chroma** (vector store) foi removido: as páginas que o usavam (Query Chroma / Upload PDF) já haviam sido descontinuadas. Quem atualizar de uma versão antiga deve rodar `docker compose up -d --remove-orphans` uma vez.

### Pontos-chave

- **Volume compartilhado `./data:/app/data`** entre `backend` e `frontend`. Nele ficam:
  - `research.db` — SQLite com agentes e versões (system prompt, modelos, temperatura, provider);
  - `history/` — histórico de execuções das três ferramentas (JSON + arquivos por registro);
  - `batch_jobs/` — estado persistido dos jobs da Batch API (sobrevive a reinícios de container);
  - `article_presets.json` — presets de protocolo de pesquisa.
- **Agentes versionados**: o backend guarda "agentes" com versões ativáveis. Cada versão define `system_prompt`, `model_primary`, `model_fallback`, `temperature` e `provider` (`ollama` ou `anthropic`). O frontend consulta `GET /agents` para saber qual configuração usar em cada ferramenta.
- **Dois provedores de LLM**: Ollama local (grátis, lento) e Anthropic (pago, rápido), escolhidos pelo campo `provider` da versão ativa do agente. Otimizações de custo no caminho Anthropic: modelo barato na triagem, prompt caching e Batch API (50% de desconto).
- **Resiliência**: todo fluxo tem fallback de modelo; erros retornam `detail` legível ao usuário; o histórico nunca quebra o fluxo principal (erros de persistência são apenas logados).

### Diagrama de containers

```mermaid
flowchart LR
    U([Usuário<br/>navegador])

    subgraph docker["Docker — rede research_network"]
        FE["frontend<br/>Streamlit :8501"]
        BE["backend<br/>FastAPI :8000"]
        JG["ia-judge<br/>FastAPI :8002"]
        OL["ollama<br/>:11434 · 5 GB"]
    end

    subgraph disk["Volume ./data"]
        DB[("research.db<br/>agentes/versões")]
        HIST[("history/")]
        BJ[("batch_jobs/")]
    end

    ANT["API Anthropic<br/>(externa)"]

    U --> FE
    FE -->|"REST /agents, /evaluate-article"| BE
    FE -->|"REST /judge/*"| JG
    FE -->|"chat direto (String Optimizer)"| OL
    BE --> OL
    BE --> ANT
    JG -->|"API compatível OpenAI"| OL
    BE --- DB
    BE --- BJ
    FE --- HIST
```

---

## 2. Arquitetura por feature

### 2.1 String Optimizer (`frontend/pages/2_String_Optimizer.py`)

**O que faz:** constrói strings de busca otimizadas para o Scopus a partir de uma questão de pesquisa, simula resultados e refina iterativamente com base nos artigos que o usuário marca como relevantes. Além da simulação, aceita um **CSV de artigos reais** (título, abstract, keywords, ano — ex.: export do Scopus): o usuário mapeia as colunas, seleciona os artigos relevantes numa tabela e o agente refina a string ativa para capturar melhor esse conjunto (até 10 artigos são enviados por refinamento, com abstracts truncados, para manter o prompt enxuto).

**Regras de geração da string:**
- As strings são construídas **apenas com keywords e sinônimos** — nunca incluem filtros de autores ou afiliação (`AU-ID`, `AUTHOR-NAME`, `AF-ID`). Os três níveis são: *core* (conceitos essenciais), *expanded* (+ sinônimos) e *full* (+ códigos de campo Scopus como `PUBYEAR`, `DOCTYPE`).
- **Idioma**: por padrão, keywords e strings saem **no mesmo idioma da questão de pesquisa**. Um checkbox na página ("🌐 Traduzir a string de busca para o inglês") permite gerar tudo em inglês; a escolha vale para a otimização, o refinamento e a string v2 pós-julgamento, e fica registrada no histórico.

**Particularidade arquitetural:** a lógica de LLM roda **no próprio frontend** (`frontend/scopus_agent.py`), chamando o Ollama diretamente — o backend participa apenas fornecendo a configuração do agente (`scopus-agent`: system prompt, modelos, temperatura). Isso mantém a iteração rápida e o estado (strings, seleções, TF-IDF) na sessão do Streamlit.

Componentes:

- `scopus_agent.py` — `optimize_query` (gera strings *core*, *expanded* e *full*), `simulate_results`, `refine_query` (refinamento a partir dos artigos selecionados), `improve_query_with_judge_feedback` (string v2 após julgamento). Todas com fallback de modelo, reparo de JSON (`json_repair`) e a instrução de idioma anexada à mensagem do usuário (assim ela vale mesmo com system prompts customizados vindos do backend).
- `text_analysis.py` — TF-IDF e pesos de termos sobre os artigos simulados, para apoiar o refinamento.
- `csv_utils.py` — leitura robusta de CSVs (detecção de separador/encoding, incluindo o export `;;` próprio) e serialização `;;`, compartilhado com o Article Evaluator.
- `ai_judge_client.py` — integração opcional com o serviço `ia-judge` (`POST /judge/string`) para avaliar a qualidade da string.
- `history_store.py` — registra otimizações e refinamentos em `data/history/string_optimizer/`.

#### Fluxo — versão genérica

```mermaid
flowchart TD
    A(["Questão de pesquisa<br/>+ idioma: original ou inglês"]) --> B["Buscar config do agente<br/>(backend /agents)"]
    B --> C{{"LLM otimizador"}}
    C --> D["3 strings só de keywords:<br/>core / expanded / full<br/>(sem filtros de autores)"]
    D --> E["Simulação de resultados<br/>(artigos fictícios)"]
    E --> F["Usuário marca<br/>artigos relevantes"]
    F --> G["Análise TF-IDF<br/>dos selecionados"]
    G --> H{{"LLM refinador"}}
    H -->|nova string| E
    D --> M["Upload de CSV com<br/>artigos reais (Scopus)"]
    M --> N["Usuário mapeia colunas e<br/>seleciona os relevantes"]
    N --> O{{"LLM refinador<br/>(artigos reais)"}}
    O -->|string refinada| D
    D -.->|opcional| J{{"LLM juíza<br/>(ia-judge /judge/string)"}}
    J -->|feedback + score| K{{"LLM otimizador<br/>(string v2)"}}
    D --> L[("Histórico<br/>data/history/")]
    O --> L
    K --> L
```

#### Fluxo — versão com os modelos básicos

```mermaid
flowchart TD
    A(["Questão de pesquisa<br/>+ checkbox 'traduzir p/ inglês'"]) --> B["backend /agents<br/>agente 'scopus-agent'"]
    B --> C{{"Ollama · phi3:mini<br/>fallback: llama3.2:1b"}}
    C --> D["strings core / expanded / full<br/>só keywords, no idioma escolhido"]
    D --> E["Simulação de resultados<br/>(Ollama · phi3:mini)"]
    E --> F["Seleção de relevantes<br/>+ TF-IDF"]
    F --> H{{"refine_query<br/>Ollama · phi3:mini"}}
    H -->|nova string| E
    D --> M["CSV real (csv_utils):<br/>título/abstract/keywords/ano"]
    M --> N["st.data_editor: seleção<br/>de até 10 relevantes"]
    N --> O{{"refine_query<br/>Ollama · phi3:mini"}}
    O -->|string refinada, iteração +1| D
    D -.->|opcional| J{{"ia-judge :8002<br/>llama3.2:1b via Ollama"}}
    J -->|score 0–5 + critérios| K{{"improve_query_with_judge_feedback<br/>Ollama · phi3:mini"}}
    D --> L[("data/history/string_optimizer/")]
    O --> L
    K --> L
```

---

### 2.2 Article Evaluator (`frontend/pages/3_Article_Evaluator.py`)

**O que faz:** avalia artigos (título, abstract, palavras-chave, ano) contra um protocolo de pesquisa (descrição, objetivos, critérios de inclusão/exclusão), retornando score 0–100, veredito (`RELATED` / `UNSURE` / `NOT-RELATED`) e justificativa. Aceita entrada **manual** (1 artigo) ou **CSV em lote** (importação robusta com detecção de separador/encoding; exportação com separador `;;`).

**Particularidade arquitetural:** aqui a lógica de LLM roda **no backend**, que é *provider-agnostic*:

- `backend/agents/evaluation_core.py` — núcleo compartilhado: monta os prompts, orquestra a avaliação em **duas etapas** e normaliza a resposta. As etapas:
  1. **Triagem por título ("pente grosso")** — decisão binária barata: rejeita de cara artigos claramente fora do escopo;
  2. **Avaliação completa ("pente fino")** — só para os aprovados, com título + abstract + keywords + ano.
- `backend/agents/article_evaluator.py` — provider **Ollama**.
- `backend/agents/claude_article_evaluator.py` — provider **Anthropic**, com duas otimizações de custo: modelo barato dedicado à etapa 1 (`ANTHROPIC_MODEL_SCREENING`) e **prompt caching** (o protocolo de pesquisa vira prefixo cacheado; leituras custam ~10% do preço de input).
- `backend/agents/claude_batch_evaluator.py` — alternativa via **Batch API** da Anthropic (50% de desconto): duas fases de batch (triagem → pente fino dos aprovados), com estado persistido em `data/batch_jobs/<job_id>.json`. O processamento ocorre nos servidores da Anthropic, então **o container pode ficar desligado** durante a execução; os resultados ficam recuperáveis por 29 dias.
- Endpoints (`backend/routers/agents.py`): `POST /agents/evaluate-article` (individual), `POST/GET /agents/evaluate-article/batch` (lote assíncrono), `POST /agents/evaluate-article/revise` (reavaliação com feedback do juiz).

O resultado em lote alimenta a mesma tabela da interface, o julgamento pelo AI Judge, a exportação CSV `;;` e o histórico (`data/history/article_evaluator/`, que guarda protocolo, CSV de entrada e CSV de saída).

#### Fluxo — versão genérica

```mermaid
flowchart TD
    A([Protocolo de pesquisa<br/>+ artigos: manual ou CSV]) --> B{Modo de envio}
    B -->|individual| C["backend<br/>POST /evaluate-article"]
    B -->|"lote (opcional, só Anthropic)"| D["backend<br/>POST /evaluate-article/batch"]

    C --> E{{"Etapa 1 · LLM barato<br/>triagem por título"}}
    E -->|rejeitado| R["NOT-RELATED · score 0"]
    E -->|aprovado| F{{"Etapa 2 · LLM principal<br/>avaliação completa"}}
    F --> G["score 0–100 + veredito<br/>+ justificativa + critérios"]

    D --> H{{"Batch fase 1<br/>triagem (na nuvem)"}}
    H -->|aprovados| I{{"Batch fase 2<br/>avaliação (na nuvem)"}}
    I --> G
    H -->|job persistido| P[("data/batch_jobs/")]

    G --> J["Tabela de resultados<br/>+ export CSV ';;'"]
    J -.->|opcional| K{{"LLM juíza<br/>(AI Judge)"}}
    K -.->|se INCORRECT| L{{"LLM reavaliador<br/>POST /evaluate-article/revise"}}
    J --> M[("Histórico<br/>data/history/")]
```

#### Fluxo — versão com os modelos básicos

```mermaid
flowchart TD
    A([Protocolo + artigos]) --> B{Provider da versão<br/>ativa do agente}

    B -->|ollama| C1{{"Etapa 1 e 2<br/>phi3:mini<br/>fallback llama3.2:1b"}}
    C1 --> G

    B -->|anthropic · individual| C2{{"Etapa 1: claude-haiku-4-5<br/>+ prompt caching do protocolo"}}
    C2 -->|aprovado| C3{{"Etapa 2: claude-sonnet-5<br/>fallback claude-haiku-4-5"}}
    C2 -->|rejeitado| R["NOT-RELATED · score 0"]
    C3 --> G

    B -->|anthropic · Batch API −50%| D1{{"Fase 1 (batch):<br/>claude-haiku-4-5"}}
    D1 -->|aprovados| D2{{"Fase 2 (batch):<br/>claude-sonnet-5"}}
    D1 --> P[("data/batch_jobs/<job>.json<br/>sobrevive a restart")]
    D2 --> G

    G["score + veredito + justificativa"] --> J["Tabela + CSV ';;'"]
    J -.->|opcional| K{{"ia-judge · llama3.2:1b"}}
    K -.->|INCORRECT → classification_v2| L{{"revise: claude-sonnet-5<br/>ou phi3:mini"}}
    J --> M[("data/history/article_evaluator/")]
```

---

### 2.3 AI Judge (`ia-judge/` + `frontend/pages/4_AI_Judge.py`)

**O que faz:** atua como uma "segunda opinião" automatizada (padrão *LLM-as-a-judge*) sobre os artefatos produzidos pelas outras ferramentas:

1. **Julgamento de string de busca** (`POST /judge/string`) — avalia a string em critérios (cobertura, precisão, sintaxe booleana, compatibilidade com a base) e devolve score final 0–5 + decisão (`approved` / `needs_revision` / `rejected`), com heurísticas determinísticas de fallback (parênteses balanceados, operadores booleanos, compatibilidade Scopus) caso o LLM falhe.
2. **Julgamento de classificações de artigos** (`POST /judge/articles`) — para cada avaliação do Article Evaluator, emite veredito `CORRECT` / `UNCERTAIN` / `INCORRECT`, confiança 0–5 e recomendação de revisão humana.
3. **Revisão de classificações** (`POST /judge/articles/revise`) — propõe uma `classification_v2` para os casos julgados incorretos.

**Particularidade arquitetural:** é um **microserviço FastAPI independente** (`ia-judge`, porta 8002), deliberadamente separado do backend para que o juiz use um LLM diferente do avaliador (evita o viés de "se autoavaliar"). Fala com o Ollama pela API compatível com OpenAI (`LLM_BASE_URL=http://ollama:11434/v1`, `LLM_MODEL=llama3.2:1b`). É consumido de três lugares: da página dedicada 4_AI_Judge, do String Optimizer (julgar string) e do Article Evaluator (julgar lote de classificações). Julgamentos são registrados em `data/history/ai_judge/`.

#### Fluxo — versão genérica

```mermaid
flowchart TD
    A1([String de busca<br/>do String Optimizer]) --> B1["ia-judge<br/>POST /judge/string"]
    A2([Classificações<br/>do Article Evaluator]) --> B2["ia-judge<br/>POST /judge/articles"]

    B1 --> C{{"LLM juíza"}}
    B2 --> C
    C -->|falha do LLM| F["Heurísticas determinísticas<br/>(fallback)"]

    C --> D1["String: score 0–5 por critério<br/>+ decisão final"]
    C --> D2["Artigos: CORRECT / UNCERTAIN /<br/>INCORRECT + confiança"]
    F --> D1

    D1 -.->|needs_revision| E1{{"LLM otimizador<br/>gera string v2"}}
    D2 -.->|INCORRECT| E2["POST /judge/articles/revise<br/>ou reavaliação no backend"]
    E2 --> G["classification_v2"]

    D1 --> H[("Histórico<br/>data/history/ai_judge/")]
    D2 --> H
    G --> H
```

#### Fluxo — versão com os modelos básicos

```mermaid
flowchart TD
    A1([String · Scopus]) --> B1["ia-judge :8002<br/>/judge/string"]
    A2([CSV de avaliações<br/>phi3:mini ou claude-sonnet-5]) --> B2["ia-judge :8002<br/>/judge/articles"]

    B1 --> C{{"llama3.2:1b<br/>(via Ollama, API OpenAI-compat)"}}
    B2 --> C
    C -->|JSON inválido / timeout| F["Fallback heurístico:<br/>parênteses, AND/OR/NOT,<br/>códigos de campo Scopus"]

    C --> D1["decisão approved /<br/>needs_revision / rejected"]
    C --> D2["veredito por artigo<br/>+ confiança 0–5"]
    F --> D1

    D1 -.->|needs_revision| E1{{"phi3:mini gera string v2<br/>(improve_query_with_judge_feedback)"}}
    D2 -.->|INCORRECT| E2{{"backend /evaluate-article/revise<br/>claude-sonnet-5 ou phi3:mini"}}
    E2 --> G["classification_v2 no CSV"]

    D1 --> H[("data/history/ai_judge/")]
    D2 --> H
    G --> H
```

---

## 3. Componentes de apoio

- **Agentes (`frontend/pages/1_Agents.py` + backend)** — gestão de agentes e versões (prompt, modelos, temperatura, provider), com ativação de versão. É o que permite trocar Ollama ↔ Anthropic sem alterar código.
- **Histórico (`frontend/pages/5_Historico.py` + `frontend/history_store.py`)** — três abas (String Optimizer, Article Evaluator, AI Judge) lendo `data/history/<ferramenta>/<id>/` (JSON do registro + arquivos, ex.: CSV de entrada/saída). Persistência em disco: sobrevive a reinícios.
- **Estilo (`frontend/ui.py` + `.streamlit/config.toml`)** — tema e CSS compartilhados entre as páginas.
- **Testes unitários (`tests/`)** — cobrem as funções puras dos módulos principais (`scopus_agent`: extração/normalização de JSON, construção de strings, regra de idioma; `csv_utils`: leitura/serialização `;;`; `evaluation_core`: normalização de avaliações, invariante de exclusão, construção de mensagens). Rodam no host: `pip install -r requirements.dev.txt && python -m pytest tests/`.
