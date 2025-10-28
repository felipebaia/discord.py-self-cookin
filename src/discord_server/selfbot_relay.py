from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

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
class RelayTarget:
    webhook_url: str
    caller_name: str
    avatar_url: str


@dataclass
class RelayConfig:
    token: str
    channel_targets: dict[int, list[RelayTarget]]

    @classmethod
    def load_from_json(cls, path: Path) -> "RelayConfig":
        if not path.exists():
            raise FileNotFoundError(f"Arquivo de configuração ausente: {path}")

        with path.open("r", encoding="utf-8") as fp:
            raw_config = json.load(fp)

        try:
            token = raw_config["TOKEN_DC"]
        except KeyError as exc:
            raise KeyError("TOKEN_DC não encontrado no arquivo de configuração") from exc

        channel_targets: dict[int, list[RelayTarget]] = {}
        index = 1
        while True:
            source_key = f"SOURCE_CHANNEL_ID_{index}"
            webhook_key = f"WEBHOOK_{index}"
            caller_key = f"CALLER_NAME_{index}"
            pfp_key = f"PFP_{index}"

            source_present = source_key in raw_config
            webhook_present = webhook_key in raw_config
            caller_present = caller_key in raw_config
            pfp_present = pfp_key in raw_config

            if not source_present and not webhook_present and not caller_present and not pfp_present:
                break

            if not source_present or not webhook_present or not caller_present or not pfp_present:
                raise KeyError(
                    f"Par de configuração incompleto: {source_key} / {webhook_key} / {caller_key} / {pfp_key}"
                )

            channel_id = int(raw_config[source_key])
            webhook_url = str(raw_config[webhook_key])
            caller_name = str(raw_config[caller_key]).strip()
            avatar_url = str(raw_config[pfp_key]).strip()

            if not webhook_url:
                raise ValueError(f"Webhook vazio para {webhook_key}")
            if not caller_name:
                raise ValueError(f"Caller name vazio para {caller_key}")
            if not avatar_url:
                raise ValueError(f"Avatar URL vazio para {pfp_key}")

            channel_targets.setdefault(channel_id, []).append(
                RelayTarget(webhook_url, caller_name, avatar_url)
            )
            index += 1

        if not channel_targets:
            raise ValueError("Nenhum canal foi configurado para replicação")

        return cls(token=token, channel_targets=channel_targets)


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._state: dict[int, int] = self._load_state()

    def _load_state(self) -> dict[int, int]:
        if not self.path.exists():
            return {}

        try:
            with self.path.open("r", encoding="utf-8") as fp:
                data = json.load(fp)
        except (json.JSONDecodeError, OSError):
            logger.warning("Estado inválido encontrado, iniciando sem histórico")
            return {}

        if isinstance(data, dict):
            # Formato novo preferencial
            channels = data.get("channels")
            if isinstance(channels, dict):
                result: dict[int, int] = {}
                for key, value in channels.items():
                    try:
                        channel_id = int(key)
                        message_id = int(value)
                    except (TypeError, ValueError):
                        continue
                    result[channel_id] = message_id
                return result

            # Compatibilidade com formato antigo (valor único)
            raw_single = data.get("last_message_id")
            try:
                single_value = int(raw_single) if raw_single is not None else None
            except (TypeError, ValueError):
                single_value = None
            if single_value:
                logger.info("Convertendo estado antigo para o formato multi-canal")
                return {-1: single_value}

        return {}

    def load_last_message_id(self, channel_id: int) -> Optional[int]:
        return self._state.get(channel_id)

    def save_last_message_id(self, channel_id: int, message_id: int) -> None:
        self._state[channel_id] = message_id
        self._persist()

    def _persist(self) -> None:
        temp_path = self.path.with_suffix(".tmp")
        payload = {"channels": {str(cid): mid for cid, mid in self._state.items() if cid >= 0}}
        with temp_path.open("w", encoding="utf-8") as fp:
            json.dump(payload, fp)
        temp_path.replace(self.path)


class ChannelRelay(discord.Client):
    def __init__(self, config: RelayConfig, state_store: StateStore, poll_interval: int = 720) -> None:
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
        self._channel_targets = config.channel_targets

        self._source_channels: dict[int, discord.TextChannel] = {}
        self._last_message_ids: dict[int, Optional[int]] = {
            channel_id: self.state_store.load_last_message_id(channel_id)
            for channel_id in self._channel_targets
        }

    async def setup_hook(self) -> None:
        self._http_session = aiohttp.ClientSession()
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

    async def _ensure_source_channel(self, channel_id: int) -> discord.TextChannel:
        channel = self._source_channels.get(channel_id)
        if channel and channel.guild:
            return channel

        channel = self.get_channel(channel_id)
        if channel is None:
            channel = await self.fetch_channel(channel_id)

        if not isinstance(channel, discord.TextChannel):
            raise TypeError("Canal de origem não é um TextChannel")

        self._source_channels[channel_id] = channel
        logger.info(
            "Canal de origem pronto: #%s (%s)",
            getattr(channel, "name", str(channel.id)),
            channel.id,
        )
        return channel

    async def _poll_loop(self) -> None:
        await self.wait_until_ready()
        logger.info("Rotina de polling iniciada; intervalo: %ss", self.poll_interval)

        await self._prime_last_message_ids()

        while not self.is_closed():
            for channel_id, targets in self._channel_targets.items():
                try:
                    await self._collect_and_forward(channel_id, targets)
                except Exception as exc:
                    logger.exception("Erro durante o polling do canal %s: %s", channel_id, exc)
            await asyncio.sleep(self.poll_interval)

    async def _prime_last_message_ids(self) -> None:
        for channel_id, last_id in list(self._last_message_ids.items()):
            if last_id is not None:
                continue

            channel = await self._ensure_source_channel(channel_id)
            async for message in channel.history(limit=1):
                self._last_message_ids[channel_id] = message.id
                self.state_store.save_last_message_id(channel_id, message.id)
                logger.info(
                    "Iniciado canal %s a partir da mensagem %s para evitar duplicações iniciais",
                    channel_id,
                    message.id,
                )
                break

    async def _collect_and_forward(self, channel_id: int, targets: list[RelayTarget]) -> None:
        channel = await self._ensure_source_channel(channel_id)

        history_kwargs = {
            "limit": 100,
            "oldest_first": True,
        }
        last_message_id = self._last_message_ids.get(channel_id)
        if last_message_id:
            history_kwargs["after"] = discord.Object(id=last_message_id)

        new_messages = [message async for message in channel.history(**history_kwargs)]

        if not new_messages:
            logger.debug("Nenhuma mensagem nova encontrada para o canal %s", channel_id)
            return

        for message in new_messages:
            await self._forward_message(message, targets)
            self._last_message_ids[channel_id] = message.id
            self.state_store.save_last_message_id(channel_id, message.id)

        logger.info(
            "%s mensagens replicadas do canal %s para %s webhook(s)",
            len(new_messages),
            channel_id,
            len(targets),
        )

    @staticmethod
    def _should_forward_attachment(attachment: discord.Attachment) -> bool:
        content_type = (attachment.content_type or "").lower()
        if content_type.startswith("image/gif"):
            return False
        if content_type.startswith("image/"):
            return True

        filename = attachment.filename.lower()
        if filename.endswith(".gif"):
            return False

        image_suffixes = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")
        return filename.endswith(image_suffixes)

    async def _forward_message(self, message: discord.Message, targets: list[RelayTarget]) -> None:
        if message.author.id == getattr(self.user, "id", None):
            return

        if not self._http_session:
            raise RuntimeError("Sessão HTTP não inicializada")

        files: list[tuple[str, bytes, Optional[str]]] = []
        for attachment in message.attachments:
            if not self._should_forward_attachment(attachment):
                logger.debug("Ignorando anexo %s (não é imagem suportada)", attachment.filename)
                continue

            try:
                file_bytes = await attachment.read()
                files.append((attachment.filename, file_bytes, attachment.content_type))
            except Exception as exc:
                logger.exception("Falha ao preparar anexo %s: %s", attachment.filename, exc)

        embeds = [discord.Embed.from_dict(embed.to_dict()) for embed in message.embeds]

        payload: dict[str, Any] = {
            "allowed_mentions": {"parse": []},
        }

        if message.content:
            payload["content"] = message.content

        if embeds:
            payload["embeds"] = [embed.to_dict() for embed in embeds]

        if files:
            payload["attachments"] = [
                {"id": index, "filename": filename}
                for index, (filename, _, _) in enumerate(files)
            ]

        for target in targets:
            try:
                await self._dispatch_via_webhook(
                    target.webhook_url,
                    target.caller_name,
                    target.avatar_url,
                    payload,
                    files,
                )
            except Exception as exc:
                logger.exception("Erro ao enviar mensagem para o webhook %s: %s", target.webhook_url, exc)

    async def _dispatch_via_webhook(
        self,
        webhook_url: str,
        caller_name: str,
        avatar_url: str,
        payload: dict[str, Any],
        files: list[tuple[str, bytes, Optional[str]]],
    ) -> None:
        if not self._http_session:
            raise RuntimeError("Sessão HTTP não inicializada")

        timeout = aiohttp.ClientTimeout(total=30)

        final_payload = dict(payload)
        final_payload["username"] = caller_name
        final_payload["avatar_url"] = avatar_url

        if files:
            form = aiohttp.FormData()
            form.add_field("payload_json", json.dumps(final_payload), content_type="application/json")

            for index, (filename, data_bytes, content_type) in enumerate(files):
                form.add_field(
                    name=f"files[{index}]",
                    value=data_bytes,
                    filename=filename,
                    content_type=content_type or "application/octet-stream",
                )

            async with self._http_session.post(
                webhook_url,
                data=form,
                timeout=timeout,
            ) as response:
                if response.status >= 400:
                    body = await response.text()
                    raise RuntimeError(f"Webhook retornou {response.status}: {body}")
        else:
            async with self._http_session.post(
                webhook_url,
                json=final_payload,
                timeout=timeout,
            ) as response:
                if response.status >= 400:
                    body = await response.text()
                    raise RuntimeError(f"Webhook retornou {response.status}: {body}")


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
