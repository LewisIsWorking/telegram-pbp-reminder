# PBP Reminder Bot

A free, serverless bot for **play-by-post tabletop RPG groups on Telegram**.
Runs hourly via GitHub Actions, tracks activity across campaigns, and posts
summaries, nudges and awards directly into your group topics.

No hosting, no server, no cost. Just a GitHub repo, a Telegram bot, and a config file.

---

## Features

| Feature                    | Frequency                         | Where it posts             |
|----------------------------|-----------------------------------|----------------------------|
| **Inactivity alerts**      | Every N hours of silence          | Campaign chat topics       |
| **Player warnings**        | At 1, 2, 3 weeks inactive         | Campaign chat topics       |
| **Auto-removal**           | At 4 weeks inactive               | Campaign chat topics       |
| **Party roster**           | Every 3 days                      | Campaign chat topics       |
| **Player of the Week**     | Weekly (with boon choice)         | Campaign chat topics       |
| **Pace report**            | Weekly                            | Campaign chat topics       |
| **Campaign leaderboard**   | Every 3 days                      | Bot topic                  |
| **Weekly digest**          | Weekly                            | Bot topic                  |
| **Combat turn pinger**     | During combat                     | Campaign PBP topics        |
| **Smart alerts**           | On pace drop or silence           | Campaign chat topics       |
| **Recruitment notices**    | Every 2 weeks (if under capacity) | Campaign chat topics       |
| **Campaign anniversaries** | Yearly                            | Campaign chat topics       |
| **Streak milestones**      | On 7/14/30/60/90 day streaks      | Campaign chat topics       |
| **Message milestones**     | Every 500/5000 messages           | Campaign/bot topic         |
| **Daily tips**             | Daily                             | Bot topic                  |
| **PBP transcripts**        | Every message (auto-archived)     | `data/pbp_logs/`           |
| **Weekly archive**         | Weekly                            | `data/weekly_archive.json` |
| **Dashboard**              | On every archive update           | [GitHub Pages](https://lewisisworking.github.io/telegram-pbp-reminder/) |
| **AoN search**             | On demand (`/search`)             | Any topic                  |
| **GM reply queue**         | On change + daily 9am             | Bot topic                  |
| **Queue nudge**            | When entry crosses 48h            | Bot topic                  |
| **Reaction tracking**      | Automatic                         | On demand (`/reactions`)   |
| **Player availability**    | On demand (`/available`)          | Campaign PBP topics        |
| **Cross-campaign timeline**| On demand (`/timeline`)           | Any topic                  |
| **Player registry**        | Automatic (on first post)         | On demand (`/registry`)    |
| **Weekly campaign table**  | Weekly                            | Bot topic                  |
| **Campaign health**        | On demand (`/health`)             | Any topic                  |
| **Session counter**        | Auto-increment on GM post day     | On demand (`/session`)     |
| **Player waiting queue**   | On demand (`/waiting`)            | Any topic                  |
| **Queue stats**            | On demand (`/queuestats`)         | Any topic                  |
| **Session poll**           | Weekly (Mon-Fri, native Telegram) | Campaign chat topic        |
| **Comeback alerts**        | On player return after 5d+        | Bot topic                  |
| **State backup**           | Daily                             | `data/state_backup.json`   |

All intervals are configurable. All features run automatically once set up.

---

## How it works

```
GitHub Actions (hourly cron)
    │
    ▼
checker.py (orchestrator)
    │
    ├── dispatch/       Process Telegram updates, route commands
    ├── commands/       Build responses for /status, /campaign, etc.
    ├── scheduled/      Run 20+ cron tasks (alerts, rosters, POTW, etc.)
    ├── combat/         Combat turn tracking
    ├── boons/          Player of the Week boon system
    ├── transcript/     PBP transcript archiving
    ├── helpers_pkg/    Shared utilities (config, formatting, dice, campaigns)
    │
    ├── telegram.py     Telegram Bot API (fetch updates, send messages, polls)
    └── state.py        State persistence (files primary, Gist backup)
```

`data/state/` holds the live state as four versioned JSON files:
`live.json`, `players.json`, `queue.json`, `activity.json`.
The GitHub Gist is written on every run as an emergency backup.

96 production files, 436 tests, 40 player commands, 75 admin commands.
Every file held to a strict 200-line maximum.

---

## Documentation

| Doc | Contents |
|-----|----------|
| [Setup Guide](docs/setup.md) | Create bot, find topic IDs, configure, deploy |
| [Commands](docs/commands.md) | All player and GM commands |
| [Configuration](docs/configuration.md) | config.json reference |
| [Data Storage](docs/data-storage.md) | Where data lives, backup strategy |
| [Architecture](docs/architecture.md) | File structure, multi-topic campaigns |
| [Examples](docs/examples.md) | Sample bot output |
| [Importing History](docs/importing-history.md) | Backfill from Telegram exports |
| [Troubleshooting](docs/troubleshooting.md) | Common issues and fixes |
| [CHANGELOG.md](CHANGELOG.md) | Full version history |

---

## Quick start

1. Create a Telegram bot via [@BotFather](https://t.me/BotFather) with group privacy **disabled**.
2. Add the bot to your supergroup (forum topics enabled).
3. Fork this repo, add secrets (`TELEGRAM_BOT_TOKEN`, `GIST_TOKEN`, `GIST_ID`).
4. Edit `config.json` with your group ID and topic IDs.
5. Push — the bot starts running on the next hourly cron.

See [Setup Guide](docs/setup.md) for detailed instructions.

---

## Versioning

[Semantic Versioning](https://semver.org/). Current version in `VERSION`.
All changes in `CHANGELOG.md`, auto-posted to Telegram on push.

---

## Cost

**Free.** GitHub Actions free tier gives 2,000 minutes/month.
The bot uses ~1 minute per run × 24 runs/day = ~720 minutes/month.
