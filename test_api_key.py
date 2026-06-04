#!/usr/bin/env python
"""
Script para testar a configuracao da Query Enhancement com Claude API
"""

import os
import sys

print("=" * 60)
print("Configuracao do Query Enhancement")
print("=" * 60)

api_key = os.getenv("ANTHROPIC_API_KEY", "")

if not api_key:
    print("\n[ERROR] ANTHROPIC_API_KEY nao configurada!")
    print("\nPara usar o Query Enhancement, voce precisa:")
    print("\n1. Ir para: https://console.anthropic.com/")
    print("2. Criar conta ou fazer login")
    print("3. Clicar em 'API Keys'")
    print("4. Criar uma nova chave")
    print("5. Copiar a chave")
    print("\n6. Configurar a variavel de ambiente:")
    print("\n   Windows (PowerShell):")
    print("   $env:ANTHROPIC_API_KEY = 'sk-ant-...'")
    print("\n   Windows (CMD):")
    print("   set ANTHROPIC_API_KEY=sk-ant-...")
    print("\n   Linux/Mac:")
    print("   export ANTHROPIC_API_KEY='sk-ant-...'")
    print("\n7. Ou editar .env:")
    print("   ANTHROPIC_API_KEY=sk-ant-...")
    sys.exit(1)

elif api_key.startswith("sk-ant-test"):
    print("\n[ERROR] API Key e uma chave de teste (invalida)!")
    print("Configure uma API Key real de https://console.anthropic.com/")
    sys.exit(1)

elif not api_key.startswith("sk-ant-"):
    print("\n[WARNING] API Key nao parece valida!")
    print("Chaves validas comecam com 'sk-ant-'")
    print(f"Sua chave comeca com: {api_key[:20]}...")
    sys.exit(1)

print("\n[OK] ANTHROPIC_API_KEY configurada!")
print(f"Chave: {api_key[:20]}...{api_key[-5:]}")

# Testa a chamada para Claude
print("\n[INFO] Testando conexao com Claude API...")

try:
    import httpx

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 100,
        "messages": [{"role": "user", "content": "Responda com 'OK'"}],
    }

    with httpx.Client(timeout=10.0) as client:
        response = client.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            print(f"[ERROR] Status {response.status_code}")
            try:
                error_data = response.json()
                print(f"Detalhes do erro: {error_data}")
            except:
                print(f"Resposta: {response.text}")

            if response.status_code == 401:
                print("\n[ERROR] Chave API invalida ou expirada!")
                print("Gere uma nova chave em: https://console.anthropic.com/")
            elif response.status_code == 400:
                print("\n[ERROR] Requisicao invalida!")
                print("Verifique o payload enviado")

            sys.exit(1)

        result = response.json()
        print("[OK] Conexao com Claude API funcionando!")
        print(f"Resposta: {result['content'][0]['text']}")

except Exception as e:
    print(f"[ERROR] Erro ao conectar com Claude API: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("Configuracao OK! Voce pode usar o Query Enhancement")
print("=" * 60)
