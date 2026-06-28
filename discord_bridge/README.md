# Discord → Telegram voice bridge

Posts a message to a Telegram forum topic whenever someone **joins, leaves, or
switches** a Discord voice channel — the Tatsu-style behaviour Telegram's own
Bot API can't provide.

```
🔊 Alice joined the voice channel Public.
🔇 Bob has left the voice channel Public.
🔀 Carol switched voice channel: Public → AFK.
```

## Why this is a separate process (not the cron bot)

The rest of this project runs hourly on GitHub Actions cron. This bridge **can't**:
Discord only delivers voice presence over a persistent **gateway websocket**, so
it must stay connected to catch events the instant they happen. It reuses this
repo's `scripts/telegram.py` to post, but runs as its own always-on process.

## Setup

### 1. Create the Discord bot
1. <https://discord.com/developers/applications> → **New Application**.
2. **Bot** tab → **Reset Token** → copy it (this is `DISCORD_BOT_TOKEN`).
3. **Bot** tab → **Privileged Gateway Intents**: the bridge only needs the
   non-privileged **Server Voice States** intent, which is on by default. (If
   member display names ever come through blank, also enable **Server Members
   Intent** and set `intents.members = True` in `voice_bridge.py`.)
4. **OAuth2 → URL Generator**: scope `bot`, permission **View Channels**. Open
   the generated URL and invite the bot to your server.

### 2. Configure tokens
```
cp .env.example .env        # then edit .env
```
Fill in `DISCORD_BOT_TOKEN` and `TELEGRAM_BOT_TOKEN` (the **same** Telegram bot
this project already uses). Everything else has defaults — it posts to Telegram
topic **119703** in the group from `config.json`.

### 3. Install + run
```
pip install -r requirements.txt
python voice_bridge.py
```
On connect it prints `Voice bridge online as <bot> -> Telegram chat <id>, topic
119703`. Hop into a voice channel to test.

## Running it 24/7

The bot is only live while its process is. Pick a host:

### Windows (your PC)
- **Quick:** double-click `run.bat`.
- **Survives reboots:** Task Scheduler → Create Task → Trigger *At log on* →
  Action *Start a program* → `run.bat`. Or wrap it as a true service with
  [NSSM](https://nssm.cc/): `nssm install VoiceBridge python <path>\voice_bridge.py`.
- Caveat: events are missed while the PC is asleep/off (Discord gives a fresh
  snapshot on reconnect but no backfill).

### Raspberry Pi / Linux VM (true 24/7)
Use the included `voice-bridge.service` (edit paths + user first):
```
sudo cp voice-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now voice-bridge
journalctl -u voice-bridge -f
```
`Restart=always` brings it back after crashes/reboots.

## Configuration reference

| Env var | Default | Purpose |
|---|---|---|
| `DISCORD_BOT_TOKEN` | — | **Required.** Discord bot token. |
| `TELEGRAM_BOT_TOKEN` | — | **Required.** Telegram bot token. |
| `TG_VOICE_TOPIC_ID` | `119703` | Telegram forum topic to post into. |
| `TG_GROUP_ID` | `config.json` `group_id` | Telegram group id. |
| `DISCORD_GUILD_ID` | (all) | Restrict to one Discord server. |
| `INCLUDE_BOTS` | `false` | Also announce bot accounts. |

## Tests

`format_event` is unit-tested in `scripts/test_voice_bridge_format.py` (runs in
the normal `pytest` suite — no Discord connection or token needed).
