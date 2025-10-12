#!/usr/bin/env python3
"""
Script de teste para o sistema de abas múltiplas
===============================================

Este script simula mensagens de diferentes canais para testar
a funcionalidade de abas múltiplas no dashboard.
"""
import sys
sys.path.append("/home/baia/git/discord.py-self-cookin/")
import requests
import json
import time
from datetime import datetime

# Configuração
SERVER_URL = "http://localhost:3000"
ENDPOINT = f"{SERVER_URL}/discord-message"

# Dados de teste simulando diferentes canais
test_messages = [
    {
        "event_type": "message",
        "message_id": 1234567890,
        "channel_id": 1424209207049191427,  # CHANNEL_1 do dc_keys.json
        "channel_name": "canal-teste-1",
        "guild_id": 987654321,
        "guild_name": "Servidor de Teste",
        "author": {
            "id": 111111111,
            "username": "usuario_teste1",
            "display_name": "Usuário Teste 1",
            "bot": False
        },
        "content": "Esta é uma mensagem de teste do Canal 1!",
        "attachments": [],
        "embeds": 0,
        "mentions": [],
        "channel_mentions": [],
        "role_mentions": []
    },
    {
        "event_type": "message", 
        "message_id": 1234567891,
        "channel_id": 1424210037194231942,  # CHANNEL_2 do dc_keys.json
        "channel_name": "canal-teste-2",
        "guild_id": 987654321,
        "guild_name": "Servidor de Teste",
        "author": {
            "id": 222222222,
            "username": "usuario_teste2", 
            "display_name": "Usuário Teste 2",
            "bot": False
        },
        "content": "Esta é uma mensagem de teste do Canal 2!",
        "attachments": [],
        "embeds": 0,
        "mentions": [],
        "channel_mentions": [],
        "role_mentions": []
    },
    {
        "event_type": "message_edit",
        "message_id": 1234567892,
        "channel_id": 1424209207049191427,  # CHANNEL_1 
        "channel_name": "canal-teste-1",
        "guild_id": 987654321,
        "guild_name": "Servidor de Teste",
        "author": {
            "id": 111111111,
            "username": "usuario_teste1",
            "display_name": "Usuário Teste 1", 
            "bot": False
        },
        "before_content": "Mensagem original",
        "after_content": "Mensagem editada no Canal 1",
        "attachments": [],
        "embeds": 0,
        "mentions": [],
        "channel_mentions": [],
        "role_mentions": []
    }
]

def send_test_message(message_data):
    """Envia uma mensagem de teste para o servidor"""
    try:
        # Adiciona timestamp
        message_data["timestamp"] = datetime.utcnow().isoformat()
        
        response = requests.post(
            ENDPOINT,
            json=message_data,
            headers={'Content-Type': 'application/json'},
            timeout=5
        )
        
        if response.status_code == 200:
            print(f"✅ Mensagem enviada com sucesso para canal {message_data['channel_id']}")
            print(f"   Conteúdo: {message_data.get('content', message_data.get('after_content', 'N/A'))[:50]}...")
        else:
            print(f"❌ Erro ao enviar mensagem: {response.status_code}")
            print(f"   Resposta: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro de conexão: {e}")

def test_server_endpoints():
    """Testa os endpoints do servidor"""
    print("🔍 Testando endpoints do servidor...")
    
    try:
        # Teste do endpoint de canais
        response = requests.get(f"{SERVER_URL}/channels", timeout=5)
        if response.status_code == 200:
            channels = response.json()
            print(f"✅ Endpoint /channels funcionando: {len(channels['channels'])} canais configurados")
        else:
            print(f"❌ Erro no endpoint /channels: {response.status_code}")
        
        # Teste do endpoint de status
        response = requests.get(f"{SERVER_URL}/status", timeout=5)
        if response.status_code == 200:
            status = response.json()
            print(f"✅ Endpoint /status funcionando: {status['messages_count']} mensagens")
        else:
            print(f"❌ Erro no endpoint /status: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro de conexão com servidor: {e}")
        print("   Certifique-se de que o servidor está rodando em http://localhost:3000")

def main():
    """Função principal de teste"""
    print("🚀 Iniciando testes do sistema de abas múltiplas")
    print("=" * 50)
    
    # Testa endpoints
    test_server_endpoints()
    print()
    
    # Envia mensagens de teste
    print("📨 Enviando mensagens de teste...")
    for i, message in enumerate(test_messages):
        print(f"\n[{i+1}/{len(test_messages)}] Enviando mensagem...")
        send_test_message(message)
        time.sleep(1)  # Pausa entre mensagens
    
    print("\n" + "=" * 50)
    print("✅ Testes concluídos!")
    print("🌐 Abra http://localhost:3000 para ver as abas funcionando")
    print("💡 Você deve ver uma aba 'Todos os Canais' e abas específicas para cada canal")

if __name__ == "__main__":
    main()