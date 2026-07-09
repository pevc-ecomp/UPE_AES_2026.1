# ═══════════════════════════════════════════════════════════
# Comandos de conveniência para o Research Assistant
# Uso: .\commands.ps1 <comando>
#
# Exemplos:
#   .\commands.ps1 up
#   .\commands.ps1 down
#   .\commands.ps1 logs
# ═══════════════════════════════════════════════════════════

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("up","down","restart","build","logs","status","models","clean")]
    [string]$Command
)

switch ($Command) {

    "up" {
        Write-Host "Subindo todos os containers..." -ForegroundColor Cyan
        docker compose up -d
        Write-Host ""
        Write-Host "Servicos disponiveis:" -ForegroundColor Green
        Write-Host "  Frontend  -> http://localhost:8501"
        Write-Host "  Backend   -> http://localhost:8000/docs"
        Write-Host "  AI Judge  -> http://localhost:8002/docs"
        Write-Host "  Ollama    -> http://localhost:11434"
        Write-Host "  Chroma    -> http://localhost:8001"
    }

    "down" {
        Write-Host "Derrubando todos os containers..." -ForegroundColor Yellow
        docker compose down
    }

    "restart" {
        Write-Host "Reiniciando containers..." -ForegroundColor Yellow
        docker compose restart
    }

    "build" {
        Write-Host "Rebuilding imagens backend e frontend..." -ForegroundColor Cyan
        docker compose build --no-cache
    }

    "logs" {
        Write-Host "Exibindo logs (Ctrl+C para sair)..." -ForegroundColor Cyan
        docker compose logs -f
    }

    "status" {
        Write-Host "Status dos containers:" -ForegroundColor Cyan
        docker compose ps
    }

    "models" {
        Write-Host "Baixando modelos Ollama..." -ForegroundColor Cyan
        & ".\scripts\pull_models.ps1"
    }

    "clean" {
        Write-Host "Removendo containers, imagens e volumes..." -ForegroundColor Red
        $confirm = Read-Host "Tem certeza? Isso apagara os modelos baixados. (s/N)"
        if ($confirm -eq "s") {
            docker compose down -v --rmi local
            Write-Host "Limpeza concluida." -ForegroundColor Green
        } else {
            Write-Host "Operacao cancelada." -ForegroundColor Yellow
        }
    }
}
