# UPE_AES_2026.1

Plataforma de apoio à revisão de literatura científica com agentes LLM locais (Ollama) e via API (Anthropic/Claude).

## Serviços

| Serviço | URL local | Descrição |
|---|---|---|
| Frontend (Streamlit) | http://localhost:8501 | Interface web |
| Backend (FastAPI) | http://localhost:8000/docs | API REST + Swagger |
| AI Judge (FastAPI) | http://localhost:8002/docs | Serviço "IA como juíza" |
| Ollama | http://localhost:11434 | Servidor LLM local |

## Funcionalidades

- **🔎 String Optimizer** — constrói strings de busca otimizadas para o Scopus a partir de uma questão de pesquisa, com simulação de resultados e refinamento iterativo (TF-IDF sobre os artigos marcados como relevantes). As strings são construídas **apenas com keywords e sinônimos** (sem filtros de autores como `AU-ID`/`AUTHOR-NAME`) e saem, por padrão, **no mesmo idioma da questão de pesquisa** — com opção de traduzi-las para o inglês via checkbox na página. Também aceita um **CSV de artigos reais** (título, abstract, keywords, ano — ex.: export do Scopus): o usuário marca os artigos relevantes e o agente refina a string ativa para capturar melhor esse conjunto.
- **📋 Article Evaluator** — avalia artigos (título, abstract, keywords, ano) contra um protocolo de pesquisa, em duas etapas (triagem por título + avaliação completa). Entrada manual ou CSV em lote; provider Ollama (local) ou Anthropic (com prompt caching, modelo barato na triagem e opção de Batch API com 50% de desconto). Exporta CSV separado por `;;`.
- **⚖️ AI Judge** — microserviço independente que julga strings de busca (score 0–5 por critério) e classificações de artigos (`CORRECT`/`UNCERTAIN`/`INCORRECT`), podendo disparar uma string v2 ou uma `classification_v2` revisada.
- **🤖 Agentes** — gestão centralizada de agentes e versões (system prompt, modelos, temperatura, provider), com ativação de versão sem alterar código.
- **🗂️ Histórico** — registro persistente (volume `data/`) das execuções das três ferramentas, incluindo arquivos de entrada/saída.

> Detalhes de arquitetura e diagramas de fluxo: [data/ARQUITETURA.md](data/ARQUITETURA.md).

---

## Pré-requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows ou Mac) ou Docker Engine + Docker Compose Plugin (Linux)
- ~10 GB de espaço livre em disco (imagens + modelos LLM)
- ~8 GB de RAM disponível para os containers

---

## Configuração inicial

### 1. Clone o repositório

**Windows (PowerShell) e Linux (Bash):**
```bash
git clone <url-do-repositório>
cd UPE_AES_2026.1
```

### 2. Crie o arquivo de variáveis de ambiente

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**Linux (Bash):**
```bash
cp .env.example .env
```

> Edite o `.env` se precisar ajustar configurações (chaves de API externas, modelos, etc.).

---

## Subindo os containers

### Windows (PowerShell) — script de conveniência

O projeto inclui `commands.ps1` com todos os comandos necessários:

```powershell
# Subir todos os containers em background
.\commands.ps1 up

# Rebuildar imagens (após mudanças no código)
.\commands.ps1 build

# Ver logs em tempo real
.\commands.ps1 logs

# Ver status dos containers
.\commands.ps1 status

# Rodar os testes unitários (requer pip install -r requirements.dev.txt)
.\commands.ps1 test
```

### Linux (Bash) — Docker Compose direto

```bash
# Subir todos os containers em background
docker compose up -d

# Se você atualizou de uma versão que ainda tinha o container do Chroma,
# use --remove-orphans uma vez para removê-lo:
docker compose up -d --remove-orphans

# Rebuildar imagens (após mudanças no código)
docker compose build --no-cache && docker compose up -d

# Ver logs em tempo real
docker compose logs -f

# Ver status dos containers
docker compose ps
```

---

## Baixar os modelos LLM

Os modelos precisam ser baixados **uma única vez** após o primeiro `up`. Eles ficam persistidos no volume `ollama_data`.

**Windows (PowerShell):**
```powershell
.\commands.ps1 models
```

**Linux (Bash):**
```bash
bash scripts/pull_models.sh
```

Modelos baixados:
- `phi3:mini` — ~2,3 GB — modelo principal
- `llama3.2:1b` — ~1,3 GB — fallback leve

> O download pode levar vários minutos dependendo da conexão.

---

## Parando os containers

**Windows (PowerShell):**
```powershell
# Parar (mantém volumes e imagens)
.\commands.ps1 down

# Parar e remover tudo (volumes e imagens locais)
.\commands.ps1 clean
```

**Linux (Bash):**
```bash
# Parar (mantém volumes e imagens)
docker compose down

# Parar e remover tudo (volumes e imagens locais)
docker compose down -v --rmi local
```

> `clean` / `down -v` apaga os modelos baixados e os dados do vector store. Use apenas se quiser um reset completo.

---

## Reiniciando um serviço específico

**Windows (PowerShell):**
```powershell
.\commands.ps1 restart
```

**Linux (Bash):**
```bash
# Reiniciar todos
docker compose restart

# Reiniciar apenas o backend
docker compose restart backend

# Reiniciar apenas o frontend
docker compose restart frontend
```

---

## Testes unitários

Os testes cobrem as funções puras dos módulos principais (`scopus_agent`, `csv_utils`, `evaluation_core`) e rodam no host, sem containers:

```bash
pip install -r requirements.dev.txt
python -m pytest tests/ -v
```

---

## GPU NVIDIA (opcional)

Para usar aceleração de GPU no Ollama, edite o `docker-compose.yml` e descomente o bloco `deploy` no serviço `ollama`:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

> Requer [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) instalado no host.
