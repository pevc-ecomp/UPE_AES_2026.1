# 🚀 Query Enhancement Skill

## Descrição

A **Query Enhancement Skill** é um módulo que melhora automaticamente as buscas científicas ao incrementar consultas com informações relevantes. Quando o usuário digita uma query, a skill expande o texto com:

1. **Keywords**: Palavras-chave principais extraídas da consulta
2. **Sinônimos**: Sinônimos de termos-chave encontrados na área científica
3. **Pesquisadores de Referência**: Nomes de pesquisadores conhecidos no tópico da query

## Como Funciona

### Fluxo de Uso

```
┌─────────────────┐
│  Usuário digita │
│     query       │
└────────┬────────┘
         │
         v
┌─────────────────────────────────┐
│  Ativa "Query Enhancement" no   │
│  painel lateral (checkbox)      │
└────────┬────────────────────────┘
         │
         v
┌──────────────────────────────────────────────┐
│ Sistema chama Ollama para processar:         │
│  - Extrair keywords                          │
│  - Gerar sinônimos                           │
│  - Identificar pesquisadores                 │
└────────┬─────────────────────────────────────┘
         │
         v
┌───────────────────────────────────┐
│ Query expandida é usada na busca  │
│ (Query + Keywords + Sinônimos +   │
│  Pesquisadores)                   │
└────────┬────────────────────────────┘
         │
         v
┌──────────────────────────────────┐
│ Resultados mais relevantes são   │
│ retornados do vector store       │
└──────────────────────────────────┘
```

## Usando a Skill

### Na Interface

1. Vá para a página **🔍 Query Chroma**
2. No painel lateral, encontre a seção **🚀 Query Enhancement**
3. Marque o checkbox **"Melhorar query automaticamente"**
4. Selecione quais componentes incluir:
   - ☑️ Keywords
   - ☑️ Sinônimos
   - ☑️ Pesquisadores

5. Digite sua consulta normalmente
6. Clique em **🔍 Buscar**

A skill irá:
- Melhorar sua query automaticamente
- Exibir um resumo das melhorias em um expansor
- Usar a query expandida para buscar resultados mais relevantes

### Exemplo

**Query Original:**
```
aprendizado de máquina para diagnóstico médico
```

**Query Expandida (exemplo):**
```
aprendizado de máquina para diagnóstico médico machine learning 
clinical diagnosis deep learning classification health artificial intelligence 
Geoffrey Hinton Yann LeCun Andrew Ng
```

## Arquitetura

### Arquivo: `query_enhancer.py`

Funções principais:

```python
extract_keywords(query, max_keywords=5)
# Extrai até 5 palavras-chave principais

extract_synonyms(query)
# Retorna dicionário: {"termo": ["sinônimo1", "sinônimo2"]}

extract_researchers(query, max_researchers=3)
# Retorna lista de 3 pesquisadores de referência

enhance_query(query, include_keywords, include_synonyms, include_researchers)
# Retorna: {
#   "enhanced_query": "query expandida",
#   "keywords": [...],
#   "synonyms": {...},
#   "researchers": [...]
# }

display_enhancement_info(enhancement_result)
# Exibe UI com detalhes das melhorias
```

## Dependências

A skill utiliza:
- **Ollama**: API local para processamento de linguagem natural
- **httpx**: Cliente HTTP para comunicar com Ollama
- **Streamlit**: Framework web para UI

Variáveis de ambiente:
```env
OLLAMA_HOST=http://ollama:11434  # URL do Ollama
OLLAMA_MODEL_PRIMARY=phi3:mini   # Modelo LLM a usar
```

## Performance

- **Cache**: Resultados são cacheados por 1 hora (TTL=3600)
- **Timeout**: 60 segundos para chamadas ao Ollama
- **Modelo**: phi3:mini (~1.3GB) - leve e rápido
- **Temperatura**: 0.3 (determinístico)

## Casos de Uso

### ✅ Recomendado

- Buscas em linguagem natural/conversacional
- Consultas vagas ou com termos técnicos variados
- Busca por tópicos interdisciplinares
- Queries em português ou linguagem natural

### ⚠️ Cuidado

- Queries muito específicas podem ser sobre-expandidas
- Dependente da qualidade do modelo Ollama
- Pode aumentar tempo de busca (2-5s para melhoria)

## Exemplos de Queries

### Ciência de Dados
```
❓ Análise preditiva em séries temporais
✨ Query expandida com: time series forecasting, ARIMA, LSTM, 
   Prophet, Holt-Winters, Rob Hyndman, Markus Hummelshoj
```

### Biologia
```
❓ Expressão gênica em câncer
✨ Query expandida com: gene expression, oncology, RNA-seq, 
   tumor, mutation, David Botstein, Patrick Brown
```

### Engenharia de Software
```
❓ Testes automatizados em integração contínua
✨ Query expandida com: automated testing, CI/CD, Jenkins, GitHub Actions,
   test automation, Kent Beck, Martin Fowler
```

## Troubleshooting

### "Erro ao chamar Ollama"
- Verifique se o container Ollama está rodando
- Confirme `OLLAMA_HOST` nas variáveis de ambiente
- Teste: `curl http://ollama:11434/api/generate`

### "Nenhuma melhoria aplicada"
- O modelo Ollama pode estar indisponível
- Tente novamente (cache de 1 hora)
- Alternativamente, desmarque a opção e busque normalmente

### Query muito lenta
- Diminua o número de keywords/sinônimos
- Use um modelo mais leve (ex: tinyllama)
- Reduza n_results

## Desenvolvimento Futuro

### Melhorias Potenciais
- [ ] Integração com bases de dados de pesquisadores (ORCID, Scopus)
- [ ] Aprendizado por feedback (melhoria iterativa)
- [ ] Suporte a múltiplos idiomas
- [ ] Cache distribuído com Redis
- [ ] Weighted expansion (peso diferente para cada tipo)
- [ ] Integração com API externa de ontologias científicas
