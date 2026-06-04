# Query Enhancement Skill

## Descrição

A **Query Enhancement Skill** é um módulo que melhora automaticamente as buscas científicas usando **Claude AI** para incrementar consultas com informações relevantes. 

Quando o usuário digita uma query, a skill usa inteligência artificial para:

1. **Keywords**: Extrai palavras-chave principais específicas do tópico
2. **Sinônimos**: Gera sinônimos acadêmicos de termos importantes
3. **Pesquisadores de Referência**: Identifica pesquisadores influentes na área

## Como Funciona

### Fluxo de Processamento

```
Usuário digita query
    ↓
Ativa "Query Enhancement"
    ↓
Sistema chama Claude API para:
  - Analisar e extrair keywords relevantes
  - Gerar sinônimos acadêmicos
  - Identificar pesquisadores de referência
    ↓
Query expandida = Query original + Keywords + Sinônimos + Pesquisadores
    ↓
Busca vetorial usa query expandida para resultados melhores
```

### Exemplo de Transformação

**Input:**
```
"aprendizado de máquina para diagnóstico médico"
```

**Output da IA:**
```
Keywords: machine learning, classification, diagnosis, AI, neural networks
Sinônimos: {
  "aprendizado": ["ML", "algoritmos adaptativos"],
  "diagnóstico": ["clinical diagnosis", "medical detection"]
}
Pesquisadores: Yann LeCun, Geoffrey Hinton, Andrew Ng

Query Expandida:
"aprendizado de máquina para diagnóstico médico machine learning 
classification diagnosis AI neural networks ML algoritmos adaptativos 
clinical diagnosis medical detection Yann LeCun Geoffrey Hinton Andrew Ng"
```

## Configuração

### 1. Obter Chave API da Anthropic

1. Vá para https://console.anthropic.com/
2. Crie uma conta ou faça login
3. Gere uma API key
4. Copie a chave

### 2. Configurar Variável de Ambiente

**Opção A: Arquivo .env**
```bash
cp .env.example .env
```

Edite `.env` e adicione:
```env
ANTHROPIC_API_KEY=sk-ant-seu-key-aqui
```

**Opção B: Variável de Sistema (Windows)**
```powershell
[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-seu-key-aqui", "User")
```

**Opção C: Variável de Sistema (Linux/Mac)**
```bash
export ANTHROPIC_API_KEY="sk-ant-seu-key-aqui"
```

### 3. Verificar Funcionamento

```bash
# Com variável de ambiente configurada
python interface_demo.py

# Ou com arquivo .env no diretório
cd /c/Users/rafae/AplicaçõesWEngSoft
python interface_demo.py
```

## Como Usar

### Na Interface Flask Demo

1. Acesse http://localhost:5000
2. Na seção **Query Enhancement**:
   - Marque "Melhorar query automaticamente"
   - Selecione quais componentes incluir (Keywords, Sinônimos, Pesquisadores)
3. Digite sua busca
4. Clique em "Buscar"
5. Veja a query expandida e os detalhes da melhoria

### Na Aplicação Streamlit

1. Configure `ANTHROPIC_API_KEY` em .env
2. Inicie a aplicação Streamlit
3. Vá para página "Query Chroma"
4. No sidebar: ative "Query Enhancement"
5. Digite sua consulta e busque

## Arquitetura

### Módulo: `query_enhancer.py`

Funções principais:

```python
extract_keywords(query, max_keywords=5) -> list[str]
# Extrai keywords relevantes usando Claude

extract_synonyms(query) -> dict[str, list[str]]
# Gera sinônimos para termos principais
# Retorna: {"termo": ["sinônimo1", "sinônimo2"]}

extract_researchers(query, max_researchers=3) -> list[str]
# Identifica pesquisadores de referência

enhance_query(query, include_keywords, include_synonyms, 
              include_researchers) -> dict
# Função principal que orquestra tudo
# Retorna dicionário com query expandida e componentes
```

### Arquivo: `interface_demo.py`

API REST para testar o Query Enhancement:

```
POST /api/enhance-query
Content-Type: application/json

{
  "query": "redes neurais para diagnóstico",
  "include_keywords": true,
  "include_synonyms": true,
  "include_researchers": true
}
```

Response:
```json
{
  "enhanced_query": "query original + keywords + sinônimos + pesquisadores",
  "keywords": ["machine learning", "neural networks", ...],
  "synonyms": {"termo": ["sinônimo1", "sinônimo2"], ...},
  "researchers": ["Yann LeCun", "Geoffrey Hinton", ...]
}
```

## Dependências

```txt
streamlit>=1.38.0      # Streamlit app (se usar)
chromadb>=0.5.0        # Vector store
httpx>=0.27.0          # Cliente HTTP para Claude API
anthropic>=0.7.0       # SDK Anthropic (opcional)
flask>=2.3.0           # Para interface_demo.py
```

## Performance

- **Tempo de resposta**: 2-5 segundos por query (dependente da API)
- **Cache**: 1 hora (TTL) para mesmas queries
- **Modelo usado**: claude-3-5-sonnet-20241022
- **Max tokens**: 1024 por resposta

## Custo da API

A Anthropic cobra por tokens:
- **Input**: ~$3/M tokens
- **Output**: ~$15/M tokens

Estimativa para 100 queries:
- ~2000 tokens de input
- ~1000 tokens de output
- Custo: ~$0.02-0.03

## Troubleshooting

### "ANTHROPIC_API_KEY não configurada"
**Solução:**
```bash
# Windows (PowerShell)
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# Linux/Mac
export ANTHROPIC_API_KEY="sk-ant-..."

# Ou edite .env
ANTHROPIC_API_KEY=sk-ant-...
```

### "Erro ao chamar Claude API"
1. Verifique se a chave está correta
2. Verifique conexão com internet
3. Verifique se a conta tem saldo/créditos
4. Veja logs de erro completos

### Query demorada
- A Claude API pode levar 2-5s
- Isso é normal, especialmente para queries complexas
- O cache de 1 hora ajuda em queries repetidas

## Casos de Uso Recomendados

✅ **Bom para:**
- Buscas em linguagem natural
- Consultas vagas ou ambíguas
- Busca por tópicos interdisciplinares
- Queries em português
- Encontrar trabalhos de autores específicos

⚠️ **Cuidado:**
- Queries muito específicas podem ser sobre-expandidas
- Queries em idiomas pouco comuns podem ter qualidade reduzida
- Dependência da API (requer internet)

## Exemplos de Queries

### Ciência de Dados
```
Input: "análise preditiva em séries temporais"
→ Keywords: time series, forecasting, ARIMA, prediction
→ Sinônimos: forecast, temporal sequences, trend analysis
→ Pesquisadores: Rob Hyndman, Markus Hummelshoj
```

### Biologia
```
Input: "expressão gênica em câncer"
→ Keywords: gene expression, oncology, RNA, tumor
→ Sinônimos: molecular profiling, transcriptomics
→ Pesquisadores: David Botstein, Patrick Brown
```

### Engenharia de Software
```
Input: "testes automatizados em integração contínua"
→ Keywords: CI/CD, test automation, Jenkins, DevOps
→ Sinônimos: continuous integration, automated testing
→ Pesquisadores: Kent Beck, Martin Fowler
```

## Desenvolvimento Futuro

Possíveis melhorias:
- [ ] Suporte a múltiplos idiomas
- [ ] Cache com Redis distribuído
- [ ] Integração com APIs acadêmicas (ORCID, Scopus)
- [ ] Peso diferente para cada tipo de expansão
- [ ] Aprendizado por feedback dos usuários
- [ ] Fallback automático se Claude API falhar
- [ ] Integração com LLMs locais (Ollama) como fallback

## Referências

- [Anthropic API Docs](https://docs.anthropic.com/)
- [Claude 3.5 Sonnet](https://www.anthropic.com/news/claude-3-5-sonnet)
- [API Pricing](https://www.anthropic.com/pricing)
