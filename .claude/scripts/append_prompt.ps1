# Hook chamado em UserPromptSubmit — adiciona o prompt ao UserPrompts.md
$raw = [Console]::In.ReadToEnd()

$prompt = ""
try {
    $data = $raw | ConvertFrom-Json
    $prompt = if ($data.prompt) { $data.prompt } `
              elseif ($data.message) { $data.message } `
              else { $raw.Trim() }
} catch {
    $prompt = $raw.Trim()
}

if (-not $prompt -or $prompt.Trim().Length -eq 0) { exit 0 }

$today = Get-Date -Format 'yyyy-MM-dd'
$user  = 'pevc-ecomp'
$file  = "UserPrompts.md"

if (-not (Test-Path $file)) { exit 0 }

# Sanitiza o prompt para célula de tabela Markdown
$safe = $prompt.Trim() -replace '[\r\n]+', ' ' -replace '\|', '-'
if ($safe.Length -gt 400) { $safe = $safe.Substring(0, 397) + '...' }

# Determina o próximo número sequencial (global no arquivo)
$content = Get-Content $file -Raw -Encoding UTF8
$nums = [regex]::Matches($content, '(?m)^\| (\d+) \|') |
        ForEach-Object { [int]$_.Groups[1].Value }
$next = if ($nums.Count -gt 0) { ($nums | Measure-Object -Maximum).Maximum + 1 } else { 1 }

$header = "## $today — $user"

if ($content.Contains($header)) {
    Add-Content -Path $file -Value "| $next | $safe |" -Encoding UTF8
} else {
    $section = "`r`n---`r`n`r`n$header`r`n`r`n| # | Prompt |`r`n|---|---|`r`n| $next | $safe |"
    Add-Content -Path $file -Value $section -Encoding UTF8
}
