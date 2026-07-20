# Versões das Ferramentas

Reflete os `requirements.*.txt` atuais (todas as dependências diretas, pinadas com `==`).

## Linguagem / Runtime

| Ferramenta | Versão |
|---|---|
| Python (containers Docker) | 3.12 |
| Python (host local) | 3.14.5 |

---

## Backend (`requirements.backend.txt`)

| Biblioteca | Versão |
|---|---|
| FastAPI | 0.136.3 |
| Uvicorn | 0.49.0 |
| LangChain Core | 1.4.0 |
| LangChain Ollama | 1.1.0 |
| Anthropic SDK | 0.116.0 |
| SQLModel | 0.0.38 |
| SQLAlchemy | 2.0.50 |
| Pydantic | 2.13.4 |
| Pydantic Settings | 2.14.1 |
| SQLite | built-in Python |

---

## Frontend (`requirements.frontend.txt`)

| Biblioteca | Versão |
|---|---|
| Streamlit | 1.58.0 |
| Ollama (cliente Python) | 0.6.2 |
| HTTPX | 0.28.1 |
| Pandas | 2.3.3 |
| json-repair | 0.30.3 |
| NLTK | 3.9.1 |

---

## Modelos LLM

| Uso | Modelo |
|---|---|
| Ollama — primário | phi3:mini |
| Ollama — fallback / juiz (ia-judge) | llama3.2:1b |
| Anthropic — avaliação (etapa 2) | claude-sonnet-5 |
| Anthropic — triagem (etapa 1) e fallback | claude-haiku-4-5 |
| Ollama (imagem Docker) | latest |

---

## Desenvolvimento / Testes (`requirements.dev.txt`)

| Biblioteca | Versão |
|---|---|
| Pytest | 8.4.2 |

---

## Infraestrutura

| Ferramenta | Versão |
|---|---|
| Docker | 29.4.2 |
| Docker Compose | 5.1.3 |
