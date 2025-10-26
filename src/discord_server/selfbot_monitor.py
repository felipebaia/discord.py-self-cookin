import os

import sys
sys.path.append("/home/baia/git/discord.py-self-cookin/")
import discord
import aiohttp
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional
import os

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('selfbot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DiscordMonitor(discord.Client):
    """
    Cliente Discord que monitora mensagens e as envia para localhost
    """
    
    def __init__(self, localhost_url: str = "http://localhost:3000", target_channels: Optional[list] = None):
        # Inicializa como self-bot
        super().__init__(self_bot=True)
        
        self.localhost_url = localhost_url
        self.target_channels = target_channels or []  # Lista de IDs de canais para monitorar
        self.session = None
        
    async def setup_hook(self):
        """Configuração inicial quando o bot conecta"""
        self.session = aiohttp.ClientSession()
        logger.info("Session HTTP criada")
        
    async def close(self):
        """Limpa recursos ao fechar"""
        if self.session:
            await self.session.close()
        await super().close()
        
    async def on_ready(self):
        """Evento disparado quando o bot está pronto"""
        logger.info(f'🟢 Self-bot conectado como: {self.user.name} (ID: {self.user.id})')
        logger.info(f'📡 Monitorando canais: {self.target_channels or "TODOS"}')
        logger.info(f'🌐 Enviando dados para: {self.localhost_url}')
        logger.info('=' * 50)
        
    async def on_message(self, message: discord.Message):
        """
        Evento disparado a cada mensagem recebida
        """
        # Ignora mensagens do próprio self-bot
        if message.author.id == self.user.id:
            return
            
        # Se canais específicos foram configurados, filtra apenas eles
        if self.target_channels and message.channel.id not in self.target_channels:
            return
            
        # Prepara dados da mensagem
        message_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "message_id": message.id,
            "channel_id": message.channel.id,
            "channel_name": getattr(message.channel, 'name', 'DM'),
            "guild_id": message.guild.id if message.guild else None,
            "guild_name": message.guild.name if message.guild else "Direct Message",
            "author": {
                "id": message.author.id,
                "username": message.author.name,
                "display_name": message.author.display_name,
                "bot": message.author.bot
            },
            "content": message.content,
            "attachments": [
                {
                    "filename": att.filename,
                    "url": att.url,
                    "size": att.size
                } for att in message.attachments
            ],
            "embeds": len(message.embeds),
            "mentions": [user.id for user in message.mentions],
            "channel_mentions": [channel.id for channel in message.channel_mentions],
            "role_mentions": [role.id for role in message.role_mentions]
        }
        
        # Log da mensagem capturada
        logger.info(f"📨 Nova mensagem capturada:")
        logger.info(f"   Guild: {message_data['guild_name']}")
        logger.info(f"   Canal: #{message_data['channel_name']}")
        logger.info(f"   Autor: {message_data['author']['username']}")
        logger.info(f"   Conteúdo: {message_data['content'][:100]}...")
        
        # Envia para localhost
        await self.send_to_localhost(message_data)
        
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Monitora edições de mensagens"""
        if before.author.id == self.user.id:
            return
            
        if self.target_channels and after.channel.id not in self.target_channels:
            return
            
        edit_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "message_edit",
            "message_id": after.id,
            "channel_id": after.channel.id,
            "channel_name": getattr(after.channel, 'name', 'DM'),
            "guild_name": after.guild.name if after.guild else "Direct Message",
            "author": {
                "id": after.author.id,
                "username": after.author.name,
                "display_name": after.author.display_name
            },
            "before_content": before.content,
            "after_content": after.content
        }
        
        logger.info(f"✏️  Mensagem editada em #{edit_data['channel_name']}")
        await self.send_to_localhost(edit_data)
        
    async def on_message_delete(self, message: discord.Message):
        """Monitora deleções de mensagens"""
        if message.author.id == self.user.id:
            return
            
        if self.target_channels and message.channel.id not in self.target_channels:
            return
            
        delete_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "message_delete",
            "message_id": message.id,
            "channel_id": message.channel.id,
            "channel_name": getattr(message.channel, 'name', 'DM'),
            "guild_name": message.guild.name if message.guild else "Direct Message",
            "author": {
                "id": message.author.id,
                "username": message.author.name,
                "display_name": message.author.display_name
            },
            "deleted_content": message.content
        }
        
        logger.info(f"🗑️  Mensagem deletada em #{delete_data['channel_name']}")
        await self.send_to_localhost(delete_data)
        
    async def send_to_localhost(self, data: dict):
        """
        Envia dados capturados para o servidor localhost
        """
        try:
            if not self.session:
                logger.error("❌ Session HTTP não inicializada")
                return
                
            async with self.session.post(
                f"{self.localhost_url}/discord-message",
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    logger.info(f"✅ Dados enviados para localhost (Status: {response.status})")
                else:
                    logger.warning(f"⚠️  Localhost respondeu com status: {response.status}")
                    
        except aiohttp.ClientError as e:
            logger.error(f"❌ Erro ao conectar com localhost: {e}")
        except asyncio.TimeoutError:
            logger.error("❌ Timeout ao enviar para localhost")
        except Exception as e:
            logger.error(f"❌ Erro inesperado: {e}")

def main():
    """
    Função principal para iniciar o self-bot
    """
    # Carrega variáveis do arquivo JSON

    DC_KEYS_PATH = ".local_keys/dc_keys.json"
    if not os.path.exists(DC_KEYS_PATH):
        logger.error(f"❌ Arquivo de chaves não encontrado: {DC_KEYS_PATH}")
        return

    with open(DC_KEYS_PATH, "r", encoding="utf-8") as f:
        dc_keys = json.load(f)

    TOKEN_DC = dc_keys["TOKEN_DC"]
    CHANNEL_1 = dc_keys["SOURCE_CHANNEL_ID_1"]
    CHANNEL_2 = dc_keys["SOURCE_CHANNEL_ID_2"]

    # CONFIGURAÇÕES - EDITE AQUI
    TOKEN = f"{TOKEN_DC}"  # ⚠️ NUNCA COMPARTILHE SEU TOKEN
    LOCALHOST_URL = "http://localhost:3000"  # URL do seu servidor local
    
    # IDs dos canais que você quer monitorar (deixe vazio para monitorar todos)
    # Para obter ID do canal: Modo desenvolvedor > Botão direito no canal > Copiar ID
    TARGET_CHANNELS = [
        CHANNEL_1,  # Exemplo de ID de canal
        CHANNEL_2,  # Adicione quantos quiser
    ]
    
    # Validações
    if TOKEN == "SEU_TOKEN_DE_USUARIO_AQUI":
        logger.error("❌ Por favor, configure seu token de usuário na variável TOKEN")
        return
        
    if not TOKEN:
        logger.error("❌ Token não pode estar vazio")
        return
    
    # Cria e inicia o monitor
    logger.info("🚀 Iniciando Discord Self-Bot Monitor...")
    logger.info("⚠️  AVISO: Self-bots violam os ToS do Discord!")
    
    monitor = DiscordMonitor(
        localhost_url=LOCALHOST_URL,
        target_channels=TARGET_CHANNELS
    )
    
    try:
        monitor.run(TOKEN)
    except discord.LoginFailure:
        logger.error("❌ Falha na autenticação. Verifique seu token.")
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
    finally:
        logger.info("🔴 Self-bot finalizado")

if __name__ == "__main__":
    main()