from flask import Flask, render_template_string
import json

app = Flask(__name__)

HTML = """
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

        .badge {
            display: inline-block;
            background: #4caf50;
            color: white;
            padding: 4px 8px;
            border-radius: 3px;
            font-size: 11px;
            margin-left: 10px;
        }

        .section-title {
            font-size: 12px;
            font-weight: 600;
            color: #666;
            text-transform: uppercase;
            margin-top: 15px;
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔬 Scientific Research Assistant</h1>
            <p class="subtitle">Plataforma de apoio à revisão de literatura científica</p>
        </header>

        <div class="layout">
            <!-- SIDEBAR -->
            <div class="sidebar">
                <h3>⚙️ Configurações</h3>

                <div class="sidebar-section">
                    <label for="collection">Coleção:</label>
                    <select id="collection">
                        <option>documents</option>
                    </select>
                    <div class="metric">
                        <div>Documentos na coleção</div>
                        <div class="metric-value">0</div>
                    </div>
                </div>

                <div class="sidebar-section">
                    <label for="results">Número de resultados:</label>
                    <input type="range" id="results" min="1" max="20" value="5">
                    <div class="metric" id="results-display">5</div>
                </div>

                <hr style="margin: 15px 0; border: none; border-top: 1px solid #eee;">

                <h3>🚀 Query Enhancement</h3>

                <div class="sidebar-section">
                    <label>
                        <input type="checkbox" id="use-enhancement">
                        Melhorar query automaticamente
                    </label>
                    <p style="font-size: 11px; color: #999; margin-top: 5px;">
                        Adiciona keywords, sinônimos e pesquisadores à sua busca
                    </p>
                </div>

                <div class="checkbox-group" id="enhancement-options" style="display: none;">
                    <label>
                        <input type="checkbox" checked>
                        Keywords
                    </label>
                    <label>
                        <input type="checkbox" checked>
                        Sinônimos
                    </label>
                    <label>
                        <input type="checkbox" checked>
                        Pesquisadores
                    </label>
                </div>
            </div>

            <!-- MAIN CONTENT -->
            <div class="main">
                <div>
                    <label for="query" style="font-weight: 600;">Digite sua busca:</label>
                    <textarea id="query" rows="5" placeholder="Ex: redes neurais para previsão de emissões de CO2"></textarea>
                    <button onclick="performSearch()">🔍 Buscar</button>
                </div>

                <div class="enhancement-info" id="enhancement-info" style="display: none;">
                    <strong>✨ Query expandida para melhor busca</strong>
                    <div class="section-title" style="margin-top: 10px;">Keywords extraídas:</div>
                    <ul class="feature-list" id="keywords-list"></ul>

                    <div class="section-title">Pesquisadores de referência:</div>
                    <ul class="feature-list" id="researchers-list"></ul>

                    <div class="section-title">Sinônimos:</div>
                    <ul class="feature-list" id="synonyms-list"></ul>
                </div>

                <div id="results-container" style="margin-top: 30px;">
                    <p style="color: #999; font-size: 14px;">Resultados aparecerão aqui...</p>
                </div>
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

        function performSearch() {
            const query = document.getElementById('query').value;
            if (!query.trim()) {
                alert('Digite algo para buscar');
                return;
            }

            const useEnhancement = document.getElementById('use-enhancement').checked;

            if (useEnhancement) {
                document.getElementById('enhancement-info').style.display = 'block';

                // Simular dados de enhancement
                const mockData = {
                    keywords: ['machine learning', 'neural networks', 'prediction', 'emissions'],
                    researchers: ['Geoffrey Hinton', 'Yann LeCun', 'Andrew Ng'],
                    synonyms: {
                        'redes neurais': ['neural networks', 'deep learning', 'artificial neural networks'],
                        'previsão': ['forecast', 'prediction', 'estimation']
                    }
                };

                // Preencher keywords
                const keywordsList = document.getElementById('keywords-list');
                keywordsList.innerHTML = mockData.keywords
                    .map(k => `<li><strong>${k}</strong></li>`)
                    .join('');

                // Preencher researchers
                const researchersList = document.getElementById('researchers-list');
                researchersList.innerHTML = mockData.researchers
                    .map(r => `<li><strong>${r}</strong></li>`)
                    .join('');

                // Preencher synonyms
                const synonymsList = document.getElementById('synonyms-list');
                synonymsList.innerHTML = Object.entries(mockData.synonyms)
                    .map(([term, syns]) => `<li><strong>${term}:</strong> ${syns.join(', ')}</li>`)
                    .join('');
            }

            // Mostrar resultado
            const resultsContainer = document.getElementById('results-container');
            resultsContainer.innerHTML = `
                <h3>✅ Resultado simulado</h3>
                <p><strong>Query original:</strong> "${query}"</p>
                ${useEnhancement ? `<p><strong>Query expandida:</strong> Inclui keywords, sinônimos e pesquisadores</p>` : ''}
                <p style="color: #999; margin-top: 15px; font-size: 13px;">
                    ⚠️ Para ver resultados reais, é necessário Chroma e Ollama rodando.<br>
                    A interface do Query Enhancement está pronta para uso!
                </p>
            `;
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

if __name__ == '__main__':
    print("[INFO] Interface rodando em http://localhost:5000")
    app.run(debug=False, port=5000, host='0.0.0.0')
