#!/usr/bin/env python
"""
Script interativo para configurar ANTHROPIC_API_KEY e testar Query Enhancement
"""

import os
import sys
import getpass

print("\n" + "=" * 70)
print("CONFIGURAR QUERY ENHANCEMENT - CLAUDE API")
print("=" * 70)

# Verificar se já tem chave
existing_key = os.getenv("ANTHROPIC_API_KEY", "")
if existing_key and existing_key.startswith("sk-ant-"):
    print(f"\n[OK] Chave ja existe no ambiente: {existing_key[:30]}...")
    use_existing = input("Usar esta chave? (s/n): ").strip().lower()
    if use_existing == 's':
        api_key = existing_key
    else:
        api_key = None
else:
    api_key = None

# Solicitar chave se nao existir
if not api_key:
    print("\n[INFO] Digite sua API Key da Anthropic")
    print("(obtenha em: https://console.anthropic.com/api-keys)")
    api_key = getpass.getpass("API Key (sk-ant-...): ").strip()

# Validar formato
if not api_key.startswith("sk-ant-"):
    print("\n[ERROR] Chave invalida! Deve comeco com 'sk-ant-'")
    sys.exit(1)

# Salvar em .env se desejar
print("\n[INFO] Deseja salvar em arquivo .env?")
save_env = input("Salvar em .env? (s/n): ").strip().lower()

if save_env == 's':
    env_file = ".env"

    # Ler .env existente
    env_content = ""
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            env_content = f.read()

    # Atualizar ou adicionar chave
    if "ANTHROPIC_API_KEY=" in env_content:
        env_content = "\n".join(
            line if not line.startswith("ANTHROPIC_API_KEY=")
            else f"ANTHROPIC_API_KEY={api_key}"
            for line in env_content.split("\n")
        )
    else:
        env_content += f"\nANTHROPIC_API_KEY={api_key}\n"

    with open(env_file, 'w') as f:
        f.write(env_content)

    print(f"[OK] Chave salva em {env_file}")
else:
    # Configurar no ambiente
    os.environ["ANTHROPIC_API_KEY"] = api_key
    print("[INFO] Chave configurada apenas para esta sessao")

# Testar conexao
print("\n[INFO] Testando conexao com Claude API...")
print("Isto pode levar alguns segundos...")

try:
    import httpx
    import json

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 150,
        "messages": [{
            "role": "user",
            "content": 'Responda com exatamente isto: "Query Enhancement Funcionando!"'
        }],
    }

    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")

    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, json=payload, headers=headers)

        print(f"\nStatus: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")

        if response.status_code != 200:
            try:
                error_data = response.json()
                print(f"Erro: {json.dumps(error_data, indent=2)}")
            except:
                print(f"Resposta: {response.text}")

            if response.status_code == 401:
                print("\n[ERROR] Nao autorizado! Chave invalida ou expirada")
            elif response.status_code == 400:
                print("\n[ERROR] Requisicao invalida - verifique o payload")
            else:
                print(f"\n[ERROR] Erro HTTP {response.status_code}")

            sys.exit(1)

        result = response.json()
        print(f"Resposta da API: {result['content'][0]['text']}")
        print("\n" + "=" * 70)
        print("[OK] CONFIGURACAO CONCLUIDA COM SUCESSO!")
        print("=" * 70)
        print("\nVoce pode agora usar o Query Enhancement!")
        print("\nPara testar a interface Flask:")
        print("  python interface_demo.py")
        print("\nAcesse: http://localhost:5000")
        print("Digite: 'Jogos digitais para formacao de criancas'")
        print("\nO resultado deve incluir keywords diferentes de:")
        print("  machine learning, neural networks, prediction, emissions")

except Exception as e:
    print(f"\n[ERROR] Erro ao conectar: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
