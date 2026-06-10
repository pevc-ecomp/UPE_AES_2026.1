# UPE_AES_2026.1

Plataforma de apoio à revisão de literatura científica com agentes LLM locais.

## Serviços

| Serviço | URL local | Descrição |
|---|---|---|
| Frontend (Streamlit) | http://localhost:8501 | Interface web |
| Backend (FastAPI) | http://localhost:8000/docs | API REST + Swagger |
| Ollama | http://localhost:11434 | Servidor LLM local |
| Chroma | http://localhost:8001 | Vector store |

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
```

### Linux (Bash) — Docker Compose direto

```bash
# Subir todos os containers em background
docker compose up -d

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
