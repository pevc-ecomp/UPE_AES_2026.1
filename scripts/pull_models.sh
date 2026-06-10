#!/bin/bash
# ─────────────────────────────────────────────────────────
# Baixa os modelos LLM no container Ollama
# Otimizado para i3-12100F + 16GB RAM (CPU only)
# Execute após o docker compose up
# Uso: bash scripts/pull_models.sh
# ─────────────────────────────────────────────────────────

echo ""
echo "Verificando se o Ollama está rodando..."

if ! docker ps --filter "name=research_ollama" --filter "status=running" -q | grep -q .; then
    echo "Erro: container research_ollama não encontrado."
    echo "Execute primeiro: docker compose up -d"
    exit 1
fi

echo "Ollama encontrado. Iniciando download dos modelos..."
echo ""

echo "Baixando phi3:mini (2.3 GB) — modelo principal..."
docker exec research_ollama ollama pull phi3:mini

echo ""
echo "Baixando llama3.2:1b (1.3 GB) — fallback leve..."
docker exec research_ollama ollama pull llama3.2:1b

echo ""
echo "Modelos prontos! Listando modelos instalados:"
docker exec research_ollama ollama list
