from flask import Flask, render_template_string, request, jsonify
import json
import os
import re
import httpx

app = Flask(__name__)

CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-3-5-sonnet-20241022"

def call_claude(prompt: str) -> str:
    """Chama Claude API e retorna a resposta."""
    if not CLAUDE_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY não configurada")

    try:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": CLAUDE_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": CLAUDE_MODEL,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }

        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            return result["content"][0]["text"].strip()
    except Exception as e:
        raise RuntimeError(f"Erro ao chamar Claude API: {e}")

def extract_keywords(query: str, max_keywords: int = 5) -> list:
    """Extrai keywords principais da query usando Claude."""
    prompt = f"""Voce eh um especialista em buscas cientificas e indexacao de literatura.

Analise esta query de busca cientifica e extraia ate {max_keywords} palavras-chave principais que melhor descrevem o tema.
As keywords devem ser termos especificos e relevantes para encontrar artigos cientificos sobre o topico.

Query: "{query}"

Retorne APENAS as palavras-chave separadas por virgula, sem explicacoes, pontuacao ou numeros.
Exemplo de retorno: machine learning, neural networks, deep learning, classification, supervised learning"""

    try:
        response = call_claude(prompt)
        keywords = [k.strip() for k in response.split(",") if k.strip()]
        keywords = list(dict.fromkeys(keywords))[:max_keywords]
        return keywords
    except Exception:
        return []

def extract_synonyms(query: str) -> dict:
    """Extrai sinonimos relevantes dos termos principais da query usando Claude."""
    prompt = f"""Voce eh um especialista em terminologia cientifica e sinonimos em pesquisa academica.

Analise esta query e identifique os 3-4 termos principais. Para cada termo, liste 2-3 sinonimos relevantes usados na literatura cientifica.

Query: "{query}"

Retorne um JSON valido com este formato EXATO (sem markdown, sem explicacoes adicionais):
{{"termo_principal_1": ["sinonimo1", "sinonimo2"], "termo_principal_2": ["sinonimo1", "sinonimo2"]}}

Exemplo:
{{"machine learning": ["aprendizado de maquina", "ML", "algoritmos adaptativos"], "neural networks": ["redes neurais", "redes artificiais"]}}"""

    try:
        response = call_claude(prompt)
        response = response.replace("```json", "").replace("```", "").strip()
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            return json.loads(json_str)
    except Exception:
        pass

    return {}

def extract_researchers(query: str, max_researchers: int = 3) -> list:
    """Extrai pesquisadores de referencia na area usando Claude."""
    prompt = f"""Voce eh um especialista em historia da ciencia e pesquisadores influentes.

Para o seguinte topico cientifico, liste ate {max_researchers} pesquisadores ou autores de GRANDE importancia/impacto conhecidos na area.
Priorize pesquisadores vivos e/ou com contribuicoes seminais recentes (ultimos 20 anos).

Topico: "{query}"

Retorne APENAS os nomes separados por virgula, sem titulos, universidades ou explicacoes.
Exemplo de retorno: Geoffrey Hinton, Yann LeCun, Yoshua Bengio"""

    try:
        response = call_claude(prompt)
        researchers = [r.strip() for r in response.split(",") if r.strip()]
        researchers = list(dict.fromkeys(researchers))[:max_researchers]
        return researchers
    except Exception:
        return []

@app.route('/api/enhance-query', methods=['POST'])
def enhance_query_api():
    """API endpoint para melhorar queries."""
    try:
        data = request.json
        query = data.get('query', '')
        include_keywords = data.get('include_keywords', True)
        include_synonyms = data.get('include_synonyms', True)
        include_researchers = data.get('include_researchers', True)

        if not CLAUDE_API_KEY:
            return jsonify({
                'error': 'ANTHROPIC_API_KEY nao configurada',
                'message': 'Configure a variavel de ambiente ANTHROPIC_API_KEY para usar Query Enhancement'
            }), 500

        if not query.strip():
            return jsonify({'error': 'Query vazia'}), 400

        result = {
            'enhanced_query': query,
            'keywords': [],
            'synonyms': {},
            'researchers': [],
        }

        if include_keywords:
            result['keywords'] = extract_keywords(query)

        if include_synonyms:
            result['synonyms'] = extract_synonyms(query)

        if include_researchers:
            result['researchers'] = extract_researchers(query)

        # Constroi query expandida
        parts = [query]
        if result['keywords']:
            parts.append(" ".join(result['keywords']))
        if result['synonyms']:
            syn_terms = [syn for syns in result['synonyms'].values() for syn in syns]
            if syn_terms:
                parts.append(" ".join(syn_terms[:10]))
        if result['researchers']:
            parts.append(" ".join(result['researchers']))

        result['enhanced_query'] = " ".join(parts)

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width">
    <title>Query Chroma - Scientific Research Assistant</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        header {
            background: white;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        h1 { color: #1f77b4; margin-bottom: 10px; }
        .subtitle { color: #666; font-size: 14px; }

        .layout {
            display: grid;
            grid-template-columns: 280px 1fr;
            gap: 20px;
        }

        .sidebar {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            height: fit-content;
        }

        .sidebar h3 {
            font-size: 14px;
            font-weight: 600;
            color: #333;
            margin-bottom: 15px;
            text-transform: uppercase;
        }

        .sidebar-section {
            margin-bottom: 20px;
        }

        label {
            display: block;
            margin-bottom: 10px;
            font-size: 13px;
            color: #333;
        }

        select, input[type="range"] {
            width: 100%;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 13px;
        }

        input[type="checkbox"] {
            margin-right: 8px;
        }

        .checkbox-group {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-top: 10px;
            padding-left: 20px;
        }

        .main {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        textarea {
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-family: monospace;
            font-size: 13px;
            resize: vertical;
            margin-bottom: 15px;
        }

        button {
            background: #1f77b4;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            width: 100%;
        }

        button:hover { background: #1563a0; }
        button:disabled { background: #ccc; cursor: not-allowed; }

        .enhancement-info {
            background: #e8f4f8;
            border-left: 4px solid #1f77b4;
            padding: 15px;
            border-radius: 4px;
            margin: 20px 0;
            font-size: 13px;
        }

        .feature-list {
            list-style: none;
            margin: 15px 0;
        }

        .feature-list li {
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }

        .feature-list li:last-child { border-bottom: none; }

        .feature-list strong { color: #1f77b4; }

        .metric {
            background: #f9f9f9;
            padding: 10px;
            border-radius: 4px;
            text-align: center;
            margin-top: 10px;
            font-size: 12px;
        }

        .metric-value {
            font-size: 18px;
            font-weight: bold;
            color: #1f77b4;
        }

        .section-title {
            font-size: 12px;
            font-weight: 600;
            color: #666;
            text-transform: uppercase;
            margin-top: 15px;
            margin-bottom: 10px;
        }

        .loading {
            display: none;
            text-align: center;
            color: #1f77b4;
            padding: 20px;
        }

        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #1f77b4;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .error {
            background: #ffebee;
            border-left: 4px solid #f44336;
            padding: 15px;
            border-radius: 4px;
            margin: 20px 0;
            color: #c62828;
        }

        .success {
            background: #e8f5e9;
            border-left: 4px solid #4caf50;
            padding: 15px;
            border-radius: 4px;
            margin: 20px 0;
            color: #2e7d32;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Scientific Research Assistant</h1>
            <p class="subtitle">Query Chroma - Plataforma de apoio a revisao de literatura cientifica</p>
        </header>

        <div class="layout">
            <!-- SIDEBAR -->
            <div class="sidebar">
                <h3>Configuracoes</h3>

                <div class="sidebar-section">
                    <label for="collection">Colecao:</label>
                    <select id="collection">
                        <option>documents</option>
                    </select>
                    <div class="metric">
                        <div>Documentos na colecao</div>
                        <div class="metric-value">0</div>
                    </div>
                </div>

                <div class="sidebar-section">
                    <label for="results">Numero de resultados:</label>
                    <input type="range" id="results" min="1" max="20" value="5">
                    <div class="metric" id="results-display">5</div>
                </div>

                <hr style="margin: 15px 0; border: none; border-top: 1px solid #eee;">

                <h3>Query Enhancement</h3>

                <div class="sidebar-section">
                    <label>
                        <input type="checkbox" id="use-enhancement">
                        Melhorar query automaticamente
                    </label>
                    <p style="font-size: 11px; color: #999; margin-top: 5px;">
                        Adiciona keywords, sinonimos e pesquisadores com IA
                    </p>
                </div>

                <div class="checkbox-group" id="enhancement-options" style="display: none;">
                    <label>
                        <input type="checkbox" id="opt-keywords" checked>
                        Keywords
                    </label>
                    <label>
                        <input type="checkbox" id="opt-synonyms" checked>
                        Sinonimos
                    </label>
                    <label>
                        <input type="checkbox" id="opt-researchers" checked>
                        Pesquisadores
                    </label>
                </div>
            </div>

            <!-- MAIN CONTENT -->
            <div class="main">
                <div>
                    <label for="query" style="font-weight: 600;">Digite sua busca:</label>
                    <textarea id="query" rows="5" placeholder="Ex: redes neurais para previsao de emissoes de CO2"></textarea>
                    <button onclick="performSearch()" id="search-btn">Buscar</button>
                </div>

                <div id="loading" class="loading">
                    <div class="spinner"></div>
                    <p>Melhorando sua query com IA...</p>
                </div>

                <div id="error-container"></div>

                <div id="enhancement-info" style="display: none;">
                    <div class="enhancement-info">
                        <strong>Query expandida para melhor busca</strong>
                    </div>

                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                        <div>
                            <div class="section-title">Keywords extraidas:</div>
                            <ul class="feature-list" id="keywords-list"></ul>

                            <div class="section-title">Pesquisadores de referencia:</div>
                            <ul class="feature-list" id="researchers-list"></ul>
                        </div>

                        <div>
                            <div class="section-title">Sinonimos:</div>
                            <ul class="feature-list" id="synonyms-list"></ul>
                        </div>
                    </div>

                    <div class="section-title" style="margin-top: 20px;">Query expandida final:</div>
                    <textarea readonly rows="3" id="expanded-query"></textarea>
                </div>

                <div id="results-container" style="margin-top: 30px;"></div>
            </div>
        </div>
    </div>

    <script>
        document.getElementById('use-enhancement').addEventListener('change', function() {
            document.getElementById('enhancement-options').style.display =
                this.checked ? 'flex' : 'none';
        });

        document.getElementById('results').addEventListener('input', function() {
            document.getElementById('results-display').textContent = this.value;
        });

        async function performSearch() {
            const query = document.getElementById('query').value;
            if (!query.trim()) {
                showError('Digite algo para buscar');
                return;
            }

            const useEnhancement = document.getElementById('use-enhancement').checked;
            document.getElementById('error-container').innerHTML = '';

            if (useEnhancement) {
                await enhanceQuery(query);
            } else {
                showResults(query, null);
            }
        }

        async function enhanceQuery(query) {
            document.getElementById('loading').style.display = 'block';
            document.getElementById('enhancement-info').style.display = 'none';

            try {
                const response = await fetch('/api/enhance-query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: query,
                        include_keywords: document.getElementById('opt-keywords').checked,
                        include_synonyms: document.getElementById('opt-synonyms').checked,
                        include_researchers: document.getElementById('opt-researchers').checked,
                    })
                });

                document.getElementById('loading').style.display = 'none';

                if (!response.ok) {
                    const error = await response.json();
                    showError(error.message || error.error);
                    return;
                }

                const data = await response.json();
                showEnhancementInfo(data);
                showResults(query, data);

            } catch (error) {
                document.getElementById('loading').style.display = 'none';
                showError('Erro ao conectar com o servidor: ' + error.message);
            }
        }

        function showEnhancementInfo(data) {
            document.getElementById('enhancement-info').style.display = 'block';

            // Keywords
            const keywordsList = document.getElementById('keywords-list');
            keywordsList.innerHTML = data.keywords.length > 0
                ? data.keywords.map(k => `<li><strong>${k}</strong></li>`).join('')
                : '<li style="color: #999;">Nenhuma keyword extraida</li>';

            // Researchers
            const researchersList = document.getElementById('researchers-list');
            researchersList.innerHTML = data.researchers.length > 0
                ? data.researchers.map(r => `<li><strong>${r}</strong></li>`).join('')
                : '<li style="color: #999;">Nenhum pesquisador encontrado</li>';

            // Synonyms
            const synonymsList = document.getElementById('synonyms-list');
            if (Object.keys(data.synonyms).length > 0) {
                synonymsList.innerHTML = Object.entries(data.synonyms)
                    .map(([term, syns]) => `<li><strong>${term}:</strong> ${syns.join(', ')}</li>`)
                    .join('');
            } else {
                synonymsList.innerHTML = '<li style="color: #999;">Nenhum sinonimo encontrado</li>';
            }

            // Expanded query
            document.getElementById('expanded-query').value = data.enhanced_query;
        }

        function showResults(originalQuery, enhancedData) {
            const resultsContainer = document.getElementById('results-container');
            let html = `<div class="success"><strong>Resultado da busca</strong><br><strong>Query original:</strong> "${originalQuery}"`;

            if (enhancedData) {
                html += `<br><strong>Query expandida:</strong> Melhorada com ${enhancedData.keywords.length} keywords, ${enhancedData.researchers.length} pesquisadores e ${Object.keys(enhancedData.synonyms).length} termos sinonimos`;
            }

            html += '</div>';
            html += '<p style="color: #999; margin-top: 15px; font-size: 13px;">Para ver resultados reais, e necessario ter Chroma e Ollama rodando.<br>A interface do Query Enhancement esta pronta e funcionando com IA real!</p>';

            resultsContainer.innerHTML = html;
        }

        function showError(message) {
            const errorContainer = document.getElementById('error-container');
            errorContainer.innerHTML = `<div class="error"><strong>Erro:</strong> ${message}</div>`;
        }
    </script>
</body>
</html>
    """
    return html

if __name__ == '__main__':
    print("[INFO] Interface rodando em http://localhost:5000")
    print("[INFO] Configure ANTHROPIC_API_KEY para usar Query Enhancement")
    app.run(debug=False, port=5000, host='0.0.0.0')
