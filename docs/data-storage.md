## Data storage

| Data | Location | Persistence |
|------|----------|-------------|
| Live state — operational | `data/state/live.json` | Written every run, git-committed |
| Live state — players | `data/state/players.json` | Written every run, git-committed |
| Live state — GM queue | `data/state/queue.json` | Written every run, git-committed |
| Per-campaign queues | `data/state/queues/{pid}.json` | Written on each reply/markdone, git-committed |
| Live state — activity | `data/state/activity.json` | Written every run, git-committed |
| Live state — trackers | `data/state/trackers.json` | Written every run, git-committed |
| Emergency backup | GitHub Gist `pbp_state.json` | Written every run (read-only fallback) |
| Legacy state backup | `data/state_backup.json` | Daily snapshot (superseded by state files) |
| PBP transcripts | `data/pbp_logs/` | Per-campaign monthly markdown files |
| Weekly archive | `data/weekly_archive.json` | Leaderboard history |
| Message ID lookup | `data/message_ids.json` | Backfilled message links |

### Load order

1. **Files** — `data/state/*.json` (all four core partitions must exist)
2. **Gist** — fallback if any file is missing (e.g. first run after a fresh checkout)
3. **Defaults** — empty state if neither source is available

The bot refuses to save if no source loaded successfully, preventing an
empty-state write from wiping data.

### Multi-group operation

Campaigns in separate Telegram groups (e.g. C11 Dark Pockets) carry a
`group_id` override in their `config.json` topic pair. The bot operates
across all groups simultaneously in each hourly run. `send_message` and
`send_poll` accept any `chat_id`, so no extra authentication is needed —
just ensure the bot is a member of each group.

### State partition layout

| File | Keys | Typical size |
|---|---|---|
| `live.json` | offset, timestamps, combat, session poll | ~8 KB |
| `players.json` | players, registry, characters, boons, MVP wins | ~17 KB |
| `queue.json` | queue_history, queue_archive, pending_potw_boons | ~5 KB |
| `queues/{pid}.json` | unreplied, replied (no cap), reply_log per campaign | ~2–10 KB each |
| `activity.json` | post_timestamps, message_counts, word counts | ~35 KB |
| `trackers.json` | clocks, conditions, HP, loot, NPCs, pins, quests, votes | ~1 KB |

Every file is committed to the repo by the workflow on each run,
giving a complete git history of all state changes.


### Per-campaign queue files — topic pin state

Each `data/state/queues/{pid}.json` now carries two additional fields
alongside `unreplied`, `replied`, and `reply_log`:

| Field | Type | Description |
|---|---|---|
| `topic_msg_id` | `int \| null` | `message_id` of the currently pinned per-topic queue message. `null` when no pin exists. |
| `topic_fingerprint` | `string` | Change-detection string (`"t1\|t2\|…"` or `"empty"`). The hourly poster skips reposting if this matches the current entries. |

These fields are managed exclusively by `scheduled/topic_queue_poster.py`
and require no manual migration — they default to absent/null on first run.

## Versioning

The bot uses [Semantic Versioning](https://semver.org/). The current version is in `VERSION`.
All changes are documented in `CHANGELOG.md`.

When a new version is pushed, the changelog is automatically posted to the
[Foundry & GitHub](https://t.me/Path_Wars/71537) Telegram topic via the
`changelog-notify.yml` workflow.

Version bumps:
- **MAJOR** (x.0.0): Breaking config changes or workflow restructuring.
- **MINOR** (0.x.0): New commands, new features, new bot behaviours.
- **PATCH** (0.0.x): Bug fixes, test additions, refactors, documentation.

---

