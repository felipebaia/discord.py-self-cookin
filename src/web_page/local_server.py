"""
Servidor HTTP Local para receber mensagens do Discord Self-Bot
============================================================

Este servidor Flask recebe as mensagens capturadas pelo self-bot
e as exibe em tempo real através de uma interface web com múltiplas abas.
"""

from flask import Flask, request, jsonify, render_template_string
from flask_socketio import SocketIO, emit
from datetime import datetime
import logging
import json
import os

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'discord-monitor-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Armazena as últimas mensagens por canal
messages_history = {}  # {channel_id: [messages]}
all_messages_history = []  # Todas as mensagens em ordem cronológica
MAX_HISTORY = 1000  # Máximo de mensagens em memória por canal

# Configuração dos canais monitorados
monitored_channels = {}

def load_channel_config():
    """Carrega configuração dos canais do arquivo dc_keys.json"""
    dc_keys_path = "/home/baia/git/discord.py-self/.local_keys/dc_keys.json"
    
    if not os.path.exists(dc_keys_path):
        logger.warning(f"Arquivo de configuração não encontrado: {dc_keys_path}")
        return {}
    
    try:
        with open(dc_keys_path, "r", encoding="utf-8") as f:
            dc_keys = json.load(f)
        
        channels = {}
        # Processa todos os canais no arquivo dc_keys
        for key, value in dc_keys.items():
            if key.startswith("CHANNEL_") and isinstance(value, int):
                channel_number = key.replace("CHANNEL_", "")
                channels[str(value)] = {
                    "id": value,
                    "name": f"Canal {channel_number}",
                    "guild_name": "Discord",
                    "key": key
                }
        
        logger.info(f"Carregados {len(channels)} canais da configuração")
        return channels
        
    except Exception as e:
        logger.error(f"Erro ao carregar configuração de canais: {e}")
        return {}

# Carrega configuração dos canais
monitored_channels = load_channel_config()


# Template HTML para interface web
with open('src/web_page/html/template.html', 'r', encoding='utf-8') as f:
    HTML_TEMPLATE = f.read()

@app.route('/')
def index():
    """Página principal com dashboard"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/channels')
def get_channels():
    """Retorna informações dos canais configurados"""
    channels_list = list(monitored_channels.values())
    return jsonify({
        "channels": channels_list,
        "total": len(channels_list)
    })

@app.route('/discord-message', methods=['POST'])
def receive_discord_message():
    """
    Endpoint que recebe mensagens do self-bot
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Dados JSON inválidos"}), 400
        
        # Adiciona timestamp se não existir
        if 'timestamp' not in data:
            data['timestamp'] = datetime.utcnow().isoformat()
        
        # Obtém ID do canal da mensagem
        channel_id = str(data.get('channel_id', 'unknown'))
        
        # Adiciona ao histórico geral
        all_messages_history.append(data)
        if len(all_messages_history) > MAX_HISTORY:
            all_messages_history.pop(0)
        
        # Adiciona ao histórico específico do canal
        if channel_id not in messages_history:
            messages_history[channel_id] = []
        
        messages_history[channel_id].append(data)
        if len(messages_history[channel_id]) > MAX_HISTORY:
            messages_history[channel_id].pop(0)
        
        # Atualiza informações do canal se recebeu dados novos
        if channel_id != 'unknown' and channel_id not in monitored_channels:
            monitored_channels[channel_id] = {
                "id": int(channel_id) if channel_id.isdigit() else channel_id,
                "name": data.get('channel_name', f'Canal {channel_id}'),
                "guild_name": data.get('guild_name', 'Discord'),
                "key": f"CHANNEL_AUTO_{channel_id}"
            }
        
        # Log da mensagem recebida
        event_type = data.get('event_type', 'message')
        author = data.get('author', {}).get('username', 'Unknown')
        guild = data.get('guild_name', 'DM')
        channel = data.get('channel_name', 'Unknown')
        
        logger.info(f"📨 {event_type.upper()}: {author} em {guild}#{channel}")
        
        # Envia para clientes conectados via WebSocket
        socketio.emit('new_message', data)
        
        return jsonify({
            "status": "success",
            "message": "Mensagem recebida e processada",
            "timestamp": data['timestamp']
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao processar mensagem: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/history')
def get_history():
    """Retorna histórico de mensagens"""
    return jsonify({
        "messages": all_messages_history[-100:],  # Últimas 100 mensagens
        "total": len(all_messages_history)
    })

@app.route('/history/<channel_id>')
def get_channel_history(channel_id):
    """Retorna histórico de mensagens de um canal específico"""
    channel_messages = messages_history.get(channel_id, [])
    return jsonify({
        "messages": channel_messages[-100:],  # Últimas 100 mensagens do canal
        "total": len(channel_messages),
        "channel_id": channel_id
    })

@app.route('/status')
def get_status():
    """Status do servidor"""
    total_messages = len(all_messages_history)
    channels_with_messages = len([ch for ch in messages_history.keys() if messages_history[ch]])
    
    return jsonify({
        "status": "running",
        "messages_count": total_messages,
        "channels_monitored": len(monitored_channels),
        "channels_with_messages": channels_with_messages,
        "uptime": "Em execução",
        "timestamp": datetime.utcnow().isoformat()
    })

@socketio.on('connect')
def handle_connect():
    """Cliente conectou via WebSocket"""
    logger.info("🟢 Cliente conectado via WebSocket")
    emit('status', {'message': 'Conectado ao monitor Discord'})

@socketio.on('disconnect')
def handle_disconnect():
    """Cliente desconectou"""
    logger.info("🔴 Cliente desconectado")

def main():
    """Inicia o servidor Flask"""
    logger.info("🚀 Iniciando servidor HTTP local...")
    logger.info("📱 Dashboard disponível em: http://localhost:3000")
    logger.info("🔌 Endpoint para self-bot: http://localhost:3000/discord-message")
    logger.info("=" * 50)
    
    try:
        socketio.run(
            app,
            host='0.0.0.0',
            port=3000,
            debug=False,
            allow_unsafe_werkzeug=True
        )
    except Exception as e:
        logger.error(f"❌ Erro ao iniciar servidor: {e}")

if __name__ == "__main__":
    main()