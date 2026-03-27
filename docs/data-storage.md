## Data storage

| Data | Location | Persistence |
|------|----------|-------------|
| Bot state (players, counts, queue, registry, poll results, MVP wins) | GitHub Gist | Real-time, single source of truth |
| State backup | `data/state_backup.json` | Daily snapshot committed to repo |
| PBP transcripts | `data/pbp_logs/` | Per-campaign monthly markdown files |
| Weekly archive | `data/weekly_archive.json` | Leaderboard history |
| Message ID lookup | `data/message_ids.json` | Backfilled message links |
| Poll results archive | Gist `poll_results` key | Per-week voting data with UIDs |

The daily state backup ensures all data is recoverable from the repo's git history
even if the gist is corrupted or deleted.

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

