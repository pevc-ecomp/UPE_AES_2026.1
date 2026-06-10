# User Prompts

Histórico de prompts submetidos ao agente Claude Code neste projeto.

---

## 2026-06-08 — pevc-ecomp

| # | Prompt |
|---|---|
| 1 | Crie um documento chamado "Versões" com todas as versões das ferramentas que você utilizou (bibliotecas, frameworks, linguagens) |
| 2 | Agora altere o container para que ele tenha esses requerimentos fixos toda vez que rodar o container |
| 3 | Agora faça uma lógica de uso de um agente avaliador se um artigo científico obtido de uma revisão bibliográfica faz sentido ou não. O system prompt precisa: indicar o recebimento de 3 informações fundamentais no input (título + abstract + palavras-chave do artigo) e uma sinopse sobre do que trata a pesquisa (string de busca, opcional). O sistema tem que colocar guardrails para não permitir prompt injection e se limitar à sua função de avaliar a utilidade do artigo. A saída precisa ser um JSON no formato: `{score, verdict (NOT-RELATED / UNSURE / RELATED), reason, article_name}`. Também crie uma lógica frontend para visualizar os agentes disponíveis e uma página para chamá-lo com nossas strings. |
| 4 | No README, crie instruções para rodar o container para Windows e para Linux. |
| 5 | Coloque no .gitignore os arquivos temporários (ex.: modelos baixados), de forma que o usuário precise rodar a lógica do README para subir o ambiente. A pasta "historiamento de prompts" não pode ser ignorada, mas faça com que o agente Claude a ignore (é um historiamento manual). |
| 6 | Erro de conflito de nome de container ao subir com `.\commands.ps1 up`. Como remover os containers existentes? |
| 7 | O avaliador de artigos está indicando "Informe ao menos uma palavra-chave" mesmo quando a palavra foi inserida. Além disso, adapte a lógica para salvar e carregar presets de artigos para acelerar os testes (botão para abrir popup com presets salvos, seleção automática dos campos). |
| 8 | Ainda ocorre "Informe ao menos uma palavra-chave". As keywords são uma string com múltiplas vírgulas. |
| 9 | Como ver o log do agente? |
| 10 | Erro no log: `model 'phi3:mini' not found` e `model 'llama3.2:1b' not found`. Como verificar quais LLMs estão instalados no Ollama? |
| 11 | Ao testar o agente, o resultado foi 100/100 RELATED para um artigo sobre saúde geracional, sendo que a sinopse era sobre criação de strings de busca. O resultado correto seria NOT-RELATED. Verificar se a sinopse está sendo enviada ao agente e torná-la obrigatória, pois é o critério de comparação. |
| 12 | Os dados do preset não estão sendo salvos. Corrigir. Se necessário, usar um banco nos containers. |
| 13 | Quais comandos devo usar para atualizar o container? |
| 14 | Erro de encoding no script `pull_models.ps1`: caractere `—` (travessão) causando `ParseException` no PowerShell. |
| 15 | Criar um novo arquivo MD chamado "UserPrompts" salvando todos os prompts de forma organizada (data, usuário e ordem). |
