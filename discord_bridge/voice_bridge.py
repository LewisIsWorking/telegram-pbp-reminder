"""Discord -> Telegram voice-channel activity bridge.

Listens to Discord voice-state changes (join / leave / move between channels)
and posts a Tatsu-style message to a Telegram forum topic, reusing this repo's
``scripts/telegram.py`` helper as the posting layer.

This is a STANDALONE, always-on process. It is deliberately NOT part of the
hourly GitHub Actions cron: a Discord gateway connection must stay open to
receive voice events the instant they happen. See README.md for setup and
hosting (Windows Task Scheduler / NSSM, or a Pi / VM with systemd).

Why a Discord bot at all: Telegram's Bot API does not expose per-user voice
chat presence. Discord's gateway does (`on_voice_state_update`). So Discord is
the event *source* and the existing Telegram helper is the *sink*.

``discord`` is imported lazily inside ``main()`` so the pure helpers
(``format_event``, ``telegram_chat_id``) can be unit-tested without the
dependency installed.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# Reuse the existing Telegram helper from scripts/ (init + send_message).
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import telegram as tg  # noqa: E402  (path set above)


def _load_dotenv(path: Path) -> None:
    """Minimal KEY=VALUE .env loader so we need no extra dependency.

    Existing environment variables win (``setdefault``), so a real env var
    always overrides the file.
    """
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def telegram_chat_id() -> int:
    """Resolve the destination Telegram chat (group) id.

    ``TG_GROUP_ID`` env wins; otherwise fall back to ``config.json`` so the
    bridge posts to the same group the rest of the bot uses.
    """
    env = os.environ.get("TG_GROUP_ID")
    if env:
        return int(env)
    cfg = json.loads((REPO_ROOT / "config.json").read_text(encoding="utf-8"))
    return int(cfg["group_id"])


def format_event(name: str, before_channel, after_channel) -> str | None:
    """Return the message text for a voice-state transition, or None.

    None means "not a channel change" (e.g. a mute/deafen/stream toggle that
    fires the same event) — those are ignored so we only post real movements.
    """
    b = before_channel.name if before_channel else None
    a = after_channel.name if after_channel else None
    if before_channel is None and after_channel is not None:
        return f"🔊 {name} joined the voice channel {a}."
    if before_channel is not None and after_channel is None:
        return f"🔇 {name} has left the voice channel {b}."
    if (before_channel is not None and after_channel is not None
            and before_channel.id != after_channel.id):
        return f"🔀 {name} switched voice channel: {b} → {a}."
    return None


def main() -> None:  # pragma: no cover - requires live Discord gateway
    import discord  # lazy: keeps the module importable without the dep

    # Windows consoles default to cp1252, which can't encode the emoji/Unicode
    # in event lines (and Discord names) — printing one would raise
    # UnicodeEncodeError on every event. Force UTF-8 so logging never crashes
    # the handler. (The Telegram send is unaffected; it's a separate path.)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # already wrapped / not a TextIO
            pass

    _load_dotenv(Path(__file__).resolve().parent / ".env")
    discord_token = os.environ.get("DISCORD_BOT_TOKEN", "")
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    topic_id = int(os.environ.get("TG_VOICE_TOPIC_ID", "119703"))
    guild_filter = os.environ.get("DISCORD_GUILD_ID", "").strip()
    include_bots = os.environ.get("INCLUDE_BOTS", "false").lower() == "true"

    if not discord_token:
        sys.exit("DISCORD_BOT_TOKEN not set (copy .env.example to .env).")
    if not telegram_token:
        sys.exit("TELEGRAM_BOT_TOKEN not set (copy .env.example to .env).")

    tg.init(telegram_token)
    chat_id = telegram_chat_id()

    intents = discord.Intents.none()
    intents.guilds = True
    intents.voice_states = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f"Voice bridge online as {client.user} -> "
              f"Telegram chat {chat_id}, topic {topic_id}", flush=True)
        # List every server the bot is in, so you can copy the right id into
        # DISCORD_GUILD_ID. (TheGrandExplorers is in 2 servers — only one
        # should be bridged.)
        for g in client.guilds:
            bridged = (not guild_filter) or str(g.id) == guild_filter
            print(f"  guild: {g.name!r} id={g.id} "
                  f"-> {'BRIDGING' if bridged else 'ignored'}", flush=True)
        if len(client.guilds) > 1 and not guild_filter:
            print("  WARNING: bot is in multiple servers and DISCORD_GUILD_ID "
                  "is unset — voice events from ALL of them will be bridged. "
                  "Set DISCORD_GUILD_ID to restrict to one.", flush=True)

    @client.event
    async def on_voice_state_update(member, before, after):
        if guild_filter and str(member.guild.id) != guild_filter:
            return
        if member.bot and not include_bots:
            return
        text = format_event(member.display_name, before.channel, after.channel)
        if not text:
            return
        # tg.send_message is a blocking requests call — run it off the event
        # loop so it never stalls the gateway heartbeat.
        await asyncio.get_running_loop().run_in_executor(
            None, tg.send_message, chat_id, topic_id, text)
        print(text, flush=True)

    client.run(discord_token)


if __name__ == "__main__":  # pragma: no cover
    main()
