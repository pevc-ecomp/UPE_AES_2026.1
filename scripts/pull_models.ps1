# ─────────────────────────────────────────────────────────
# Baixa os modelos LLM no container Ollama
# Otimizado para i3-12100F + 16GB RAM (CPU only)
# Execute após o docker compose up
# Uso: .\scripts\pull_models.ps1
# ─────────────────────────────────────────────────────────

Write-Host ""
Write-Host "Verificando se o Ollama está rodando..." -ForegroundColor Cyan

$ollamaRunning = docker ps --filter "name=research_ollama" --filter "status=running" -q

if (-not $ollamaRunning) {
    Write-Host "Erro: container research_ollama nao encontrado." -ForegroundColor Red
    Write-Host "Execute primeiro: docker compose up -d" -ForegroundColor Yellow
    exit 1
}

Write-Host "Ollama encontrado. Iniciando download dos modelos..." -ForegroundColor Green
Write-Host ""

Write-Host "Baixando phi3:mini (~2.3 GB) — modelo principal..." -ForegroundColor Cyan
docker exec research_ollama ollama pull phi3:mini

Write-Host ""
Write-Host "Baixando llama3.2:1b (~1.3 GB) — fallback leve..." -ForegroundColor Cyan
docker exec research_ollama ollama pull llama3.2:1b

Write-Host ""
Write-Host "Modelos prontos! Listando modelos instalados:" -ForegroundColor Green
docker exec research_ollama ollama list
