# AI as Judge for Systematic Reviews

This is a simple FastAPI application that uses a local LLM through an OpenAI-compatible API, such as Ollama, to judge:

1. Search strings generated for systematic literature reviews.
2. Article classification decisions made during a systematic review.

The prompts are written in English to improve consistency with most LLM instruction-following patterns.

## Requirements

- Python 3.10+
- Ollama installed
- Local model available, for example:

```bash
ollama pull llama3.2:1b
ollama run llama3.2:1b
```

## Environment

Create a `.env` file based on `.env.example`:

```env
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.2:1b
```

## Install

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

Open the API documentation:

```txt
http://localhost:8000/docs
```

## Endpoints

### Judge search string

`POST /judge/string`

Example body:

```json
{
  "topic": "Fault tolerance in IoT devices",
  "database": "Scopus",
  "search_string": "(\"fault tolerance\" OR \"fault tolerant\") AND (IoT OR \"Internet of Things\")"
}
```

### Judge article classification

`POST /judge/articles`

Example body:

```json
{
  "review_objective": "Identify fault tolerance techniques applied to IoT systems.",
  "inclusion_criteria": "Studies that present techniques, methods, mechanisms, or architectures for fault tolerance in IoT.",
  "exclusion_criteria": "Studies unrelated to IoT or without an explicit fault tolerance technique.",
  "articles": [
    {
      "title": "Energy-efficient fault tolerance in IoT",
      "abstract": "The paper proposes a routing strategy for fault tolerance in IoT networks.",
      "model_classification": "INCLUDE",
      "model_justification": "The paper presents a fault-tolerant routing technique."
    }
  ]
}
```

## Notes for weak local models

Because `llama3.2:1b` is a small model, this system uses rigid prompts, low temperature, short criteria, and JSON-only output. For better stability, evaluate small batches of articles, preferably 5 to 10 articles per request.
