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
        raise RuntimeError("ANTHROPIC_API_KEY nao configurada")

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
        if response.status_code != 200:
            error = response.json() if response.headers.get("content-type") == "application/json" else response.text
            raise RuntimeError(f"Claude API error {response.status_code}: {error}")
        result = response.json()
        return result["content"][0]["text"].strip()

def extract_keywords(query: str, max_keywords: int = 5) -> list:
    """Extrai keywords principais da query usando Claude."""
    prompt = f"""Você é um especialista em buscas científicas.

Analise esta query e extraia até {max_keywords} palavras-chave principais.

Query: "{query}"

Retorne APENAS as palavras-chave separadas por vírgula, sem explicações."""

    response = call_claude(prompt)
    keywords = [k.strip() for k in response.split(",") if k.strip()]
    return list(dict.fromkeys(keywords))[:max_keywords]

def extract_synonyms(query: str) -> dict:
    """Extrai sinônimos dos termos principais usando Claude."""
    prompt = f"""Você é um especialista em terminologia científica.

Analise esta query e identifique 2-3 termos principais. Para cada termo, liste 2-3 sinônimos acadêmicos.

Query: "{query}"

Retorne um JSON válido com este formato (sem markdown):
{{"termo1": ["sinônimo1", "sinônimo2"], "termo2": ["sinônimo1", "sinônimo2"]}}"""

    response = call_claude(prompt)
    response = response.replace("```json", "").replace("```", "").strip()
    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except:
            pass
    return {}

def extract_researchers(query: str, max_researchers: int = 3) -> list:
    """Extrai pesquisadores de referência usando Claude."""
    prompt = f"""Você é um especialista em pesquisadores influentes.

Para este tópico, liste até {max_researchers} pesquisadores de GRANDE importância conhecidos na área.

Tópico: "{query}"

Retorne APENAS os nomes separados por vírgula, sem títulos ou explicações."""

    response = call_claude(prompt)
    researchers = [r.strip() for r in response.split(",") if r.strip()]
    return list(dict.fromkeys(researchers))[:max_researchers]

@app.route('/api/enhance-query', methods=['POST'])
def enhance_query_api():
    """API endpoint para melhorar queries com Claude."""
    try:
        data = request.json
        query = data.get('query', '').strip()

        if not query:
            return jsonify({'error': 'Query vazia'}), 400

        if not CLAUDE_API_KEY:
            return jsonify({
                'error': 'ANTHROPIC_API_KEY nao configurada',
                'message': 'Configure a variável de ambiente ANTHROPIC_API_KEY'
            }), 500

        result = {
            'enhanced_query': query,
            'keywords': [],
            'synonyms': {},
            'researchers': [],
        }

        try:
            if data.get('include_keywords', True):
                result['keywords'] = extract_keywords(query)
        except Exception as e:
            return jsonify({'error': f'Erro ao extrair keywords: {str(e)}'}), 500

        try:
            if data.get('include_synonyms', True):
                result['synonyms'] = extract_synonyms(query)
        except Exception as e:
            return jsonify({'error': f'Erro ao extrair sinônimos: {str(e)}'}), 500

        try:
            if data.get('include_researchers', True):
                result['researchers'] = extract_researchers(query)
        except Exception as e:
            return jsonify({'error': f'Erro ao extrair pesquisadores: {str(e)}'}), 500

        # Monta query expandida
        parts = [query]
        if result['keywords']:
            parts.append(" ".join(result['keywords']))
        if result['synonyms']:
            syn_terms = [syn for syns in result['synonyms'].values() for syn in syns]
            if syn_terms:
                parts.append(" ".join(syn_terms))
        if result['researchers']:
            parts.append(" ".join(result['researchers']))

        result['enhanced_query'] = " ".join(parts)
        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width">
    <title>Query Enhancement - Claude AI</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        header {
            background: white;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        h1 { color: #1f77b4; margin-bottom: 10px; }
        .content {
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
            font-size: 14px;
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

        .loading { display: none; color: #1f77b4; padding: 20px; text-align: center; }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #1f77b4;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

        .error {
            background: #ffebee;
            border-left: 4px solid #f44336;
            padding: 15px;
            border-radius: 4px;
            margin: 20px 0;
            color: #c62828;
            display: none;
        }

        .result {
            background: #e8f5e9;
            border-left: 4px solid #4caf50;
            padding: 15px;
            border-radius: 4px;
            margin: 20px 0;
            display: none;
        }

        .result-item { margin: 10px 0; }
        .result-item strong { color: #1f77b4; }

        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }
        .grid > div { padding: 15px; background: #f9f9f9; border-radius: 4px; }

        label { display: block; margin-bottom: 10px; }
        input[type="checkbox"] { margin-right: 8px; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Query Enhancement com Claude AI</h1>
            <p>Melhore suas buscas científicas com inteligência artificial</p>
        </header>

        <div class="content">
            <div>
                <label>Digite sua consulta:</label>
                <textarea id="query" rows="4" placeholder="Exemplo: Jogos digitais para formacao de criancas"></textarea>

                <div style="margin-bottom: 15px;">
                    <label><input type="checkbox" id="keywords" checked> Extrair Keywords</label>
                    <label><input type="checkbox" id="synonyms" checked> Extrair Sinônimos</label>
                    <label><input type="checkbox" id="researchers" checked> Extrair Pesquisadores</label>
                </div>

                <button onclick="search()" id="search-btn">Buscar com IA</button>
            </div>

            <div id="loading" class="loading">
                <div class="spinner"></div>
                <p>Processando com Claude AI...</p>
            </div>

            <div id="error" class="error"></div>

            <div id="result" class="result">
                <h3>Resultado</h3>
                <div id="result-content"></div>
            </div>
        </div>
    </div>

    <script>
        async function search() {
            const query = document.getElementById('query').value.trim();
            if (!query) {
                showError('Digite uma consulta');
                return;
            }

            document.getElementById('loading').style.display = 'block';
            document.getElementById('error').style.display = 'none';
            document.getElementById('result').style.display = 'none';

            try {
                const response = await fetch('/api/enhance-query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: query,
                        include_keywords: document.getElementById('keywords').checked,
                        include_synonyms: document.getElementById('synonyms').checked,
                        include_researchers: document.getElementById('researchers').checked,
                    })
                });

                document.getElementById('loading').style.display = 'none';

                const data = await response.json();

                if (!response.ok) {
                    showError(data.error || 'Erro desconhecido');
                    return;
                }

                showResult(data);
            } catch (error) {
                document.getElementById('loading').style.display = 'none';
                showError('Erro: ' + error.message);
            }
        }

        function showError(msg) {
            const el = document.getElementById('error');
            el.textContent = msg;
            el.style.display = 'block';
        }

        function showResult(data) {
            let html = '<div class="grid">';

            // Keywords
            html += '<div><strong>Keywords:</strong><br>';
            if (data.keywords.length > 0) {
                html += data.keywords.map(k => `<div class="result-item">• ${k}</div>`).join('');
            } else {
                html += '<div class="result-item" style="color: #999;">Nenhuma</div>';
            }
            html += '</div>';

            // Researchers
            html += '<div><strong>Pesquisadores:</strong><br>';
            if (data.researchers.length > 0) {
                html += data.researchers.map(r => `<div class="result-item">• ${r}</div>`).join('');
            } else {
                html += '<div class="result-item" style="color: #999;">Nenhum</div>';
            }
            html += '</div>';

            // Synonyms
            if (Object.keys(data.synonyms).length > 0) {
                html += '<div style="grid-column: 1 / -1;"><strong>Sinônimos:</strong><br>';
                for (const [term, syns] of Object.entries(data.synonyms)) {
                    html += `<div class="result-item"><strong>${term}:</strong> ${syns.join(', ')}</div>`;
                }
                html += '</div>';
            }

            // Query expandida
            html += '<div style="grid-column: 1 / -1;"><strong>Query Expandida:</strong><br>';
            html += `<div style="background: #fff; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-family: monospace; font-size: 12px; word-break: break-word;">${data.enhanced_query}</div>`;
            html += '</div>';

            html += '</div>';

            document.getElementById('result-content').innerHTML = html;
            document.getElementById('result').style.display = 'block';
        }

        // Enter key to search
        document.getElementById('query').addEventListener('keypress', (e) => {
            if (e.ctrlKey && e.key === 'Enter') search();
        });
    </script>
</body>
</html>"""
    return html

if __name__ == '__main__':
    if not CLAUDE_API_KEY:
        print("[ERROR] ANTHROPIC_API_KEY nao configurada!")
        print("Configure com: export ANTHROPIC_API_KEY='sk-ant-...'")
        print("Ou edite .env")
        exit(1)

    print(f"[INFO] Iniciando servidor em http://localhost:5000")
    print(f"[INFO] API Key configurada: {CLAUDE_API_KEY[:30]}...")
    app.run(debug=False, port=5000, host='0.0.0.0')
