from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
import io

import aiohttp

import sys
sys.path.append("/home/baia/git/discord.py-self-cookin/")
import discord

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent.parent
CONFIG_PATH = ROOT_DIR / ".local_keys" / "dc_keys.json"
STATE_PATH = BASE_DIR / "selfbot_relay_state.json"

LOG_PATH = BASE_DIR / "selfbot_relay.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class RelayConfig:
    token: str
    source_channel_id: int
    target_channel_id: int
    webhook_url: str

    @classmethod
    def load_from_json(cls, path: Path) -> "RelayConfig":
        if not path.exists():
            raise FileNotFoundError(f"Arquivo de configuração ausente: {path}")

        with path.open("r", encoding="utf-8") as fp:
            raw_config = json.load(fp)

        try:
            return cls(
                token=raw_config["TOKEN_DC"],
                source_channel_id=int(raw_config["SOURCE_CHANNEL_ID_1"]),
                target_channel_id=int(raw_config["TARGET_CHANNEL_ID_1"]),
                webhook_url=str(raw_config["WEBHOOK"])
            )
        except KeyError as exc:
            raise KeyError(f"Chave obrigatória não encontrada no JSON: {exc}") from exc


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load_last_message_id(self) -> Optional[int]:
        if not self.path.exists():
            return None

        try:
            with self.path.open("r", encoding="utf-8") as fp:
                data = json.load(fp)
            return int(data.get("last_message_id")) if data.get("last_message_id") else None
        except (json.JSONDecodeError, ValueError):
            logger.warning("Estado inválido encontrado, iniciando sem histórico")
            return None

    def save_last_message_id(self, message_id: int) -> None:
        temp_path = self.path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as fp:
            json.dump({"last_message_id": message_id}, fp)
        temp_path.replace(self.path)


class ChannelRelay(discord.Client):
    def __init__(self, config: RelayConfig, state_store: StateStore, poll_interval: int = 20) -> None:
        intents_kwargs: dict[str, Any] = {}
        intents_cls = getattr(discord, "Intents", None)
        if intents_cls is not None:
            intents = intents_cls.default()
            for attr in ("guilds", "guild_messages", "message_content"):
                if hasattr(intents, attr):
                    setattr(intents, attr, True)
            intents_kwargs["intents"] = intents

        super().__init__(self_bot=True, **intents_kwargs)

        self.config = config
        self.state_store = state_store
        self.poll_interval = poll_interval

        self._polling_task: Optional[asyncio.Task[None]] = None
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._webhook: Optional[discord.Webhook] = None

        self._source_channel: Optional[discord.TextChannel] = None
        self._last_message_id: Optional[int] = self.state_store.load_last_message_id()

    async def setup_hook(self) -> None:
        self._http_session = aiohttp.ClientSession()
        self._webhook = discord.Webhook.from_url(self.config.webhook_url, session=self._http_session)
        self._polling_task = asyncio.create_task(self._poll_loop())
        logger.info("Webhook inicializado e rotina agendada")

    async def close(self) -> None:
        if self._polling_task:
            self._polling_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._polling_task

        if self._http_session:
            await self._http_session.close()

        await super().close()

    async def on_ready(self) -> None:
        logger.info(
            "Self-bot conectado: %s (ID: %s)",
            getattr(self.user, "name", "desconhecido"),
            getattr(self.user, "id", "N/A")
        )

    async def _ensure_source_channel(self) -> discord.TextChannel:
        if self._source_channel and self._source_channel.guild:
            return self._source_channel

        channel = self.get_channel(self.config.source_channel_id)
        if channel is None:
            channel = await self.fetch_channel(self.config.source_channel_id)

        if not isinstance(channel, discord.TextChannel):
            raise TypeError("Canal de origem não é um TextChannel")

        self._source_channel = channel
        logger.info(
            "Canal de origem pronto: #%s (%s)",
            getattr(channel, "name", str(channel.id)),
            channel.id,
        )
        return channel

    async def _poll_loop(self) -> None:
        await self.wait_until_ready()
        logger.info("Rotina de polling iniciada; intervalo: %ss", self.poll_interval)

        await self._prime_last_message_id()

        while not self.is_closed():
            try:
                await self._collect_and_forward()
            except Exception as exc:
                logger.exception("Erro durante o polling: %s", exc)
            await asyncio.sleep(self.poll_interval)

    async def _prime_last_message_id(self) -> None:
        if self._last_message_id is not None:
            return

        channel = await self._ensure_source_channel()
        async for message in channel.history(limit=1):
            self._last_message_id = message.id
            self.state_store.save_last_message_id(message.id)
            logger.info("Iniciado a partir da mensagem %s para evitar duplicações iniciais", message.id)
            break

    async def _collect_and_forward(self) -> None:
        channel = await self._ensure_source_channel()

        history_kwargs = {
            "limit": 100,
            "oldest_first": True,
        }
        if self._last_message_id:
            history_kwargs["after"] = discord.Object(id=self._last_message_id)

        new_messages = [message async for message in channel.history(**history_kwargs)]

        if not new_messages:
            logger.debug("Nenhuma mensagem nova encontrada")
            return

        for message in new_messages:
            await self._forward_message(message)
            self._last_message_id = message.id
            self.state_store.save_last_message_id(message.id)

        logger.info("%s mensagens replicadas do canal %s", len(new_messages), channel.id)

    async def _forward_message(self, message: discord.Message) -> None:
        if message.author.id == getattr(self.user, "id", None):
            return

        if not self._webhook:
            raise RuntimeError("Webhook não inicializado")

        files: list[discord.File] = []
        for attachment in message.attachments:
            try:
                payload = await attachment.read()
                buffer = io.BytesIO(payload)
                buffer.seek(0)
                files.append(discord.File(buffer, filename=attachment.filename))
            except Exception as exc:
                logger.exception("Falha ao preparar anexo %s: %s", attachment.filename, exc)

        embeds = [discord.Embed.from_dict(embed.to_dict()) for embed in message.embeds]

        send_kwargs = {
            "username": message.author.display_name,
            "avatar_url": getattr(message.author.display_avatar, "url", None),
            "allowed_mentions": discord.AllowedMentions.none(),
            "wait": True,
        }

        if message.content:
            send_kwargs["content"] = message.content

        if embeds:
            send_kwargs["embeds"] = embeds

        if files:
            send_kwargs["files"] = files

        try:
            await self._webhook.send(**send_kwargs)
        except Exception as exc:
            logger.exception("Erro ao enviar mensagem para o webhook: %s", exc)
        finally:
            for file in files:
                file.close()


def main() -> None:
    try:
        config = RelayConfig.load_from_json(CONFIG_PATH)
    except Exception as exc:
        logger.error("Não foi possível carregar a configuração: %s", exc)
        return

    if not config.token:
        logger.error("Token inválido ou vazio; abortando")
        return

    state_store = StateStore(STATE_PATH)
    relay = ChannelRelay(config, state_store)

    try:
        relay.run(config.token)
    except discord.LoginFailure:
        logger.error("Falha na autenticação. Verifique o token fornecido.")
    except KeyboardInterrupt:
        logger.info("Interrupção solicitada pelo usuário.")
    except Exception as exc:
        logger.exception("Erro fatal na execução do relay: %s", exc)
    finally:
        logger.info("Relay encerrado")


if __name__ == "__main__":
    main()
