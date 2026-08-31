# tools/

Local scripts. Not imported by the bot, not run in CI. Each answers a
question that came up once and will come up again.

| Script | Question it answers |
|---|---|
| `schedule_delivery_report.py` | Is GitHub actually running the workflow as often as the cron asks? |
| `_splitter_pack.py`, `_splitter_helpers.py`, `test_splitter.py` | Message splitting for long Telegram posts. |

## `schedule_delivery_report.py`

```bash
py -3 tools/schedule_delivery_report.py            # last 14 days
py -3 tools/schedule_delivery_report.py --days 30
```

Counts commits of `data/ci_heartbeat.json`, which only land inside a
successful run, so the git log of that one file is the record of runs
that happened.

⭐ **This exists to be independent of the Actions API**, which has been
caught serving a cached page of runs three days old (2026-08-19) and
nearly unlocked the posting gate with it. Git history cannot be served
stale. The daily diagnostic reports the same figure from the API; when
the two agree, the reading is trustworthy.

⛔ It measures `origin/main`, not `HEAD`, and fetches first. State commits
land on the remote, so a local checkout is behind the moment anything
runs, and a stale branch reads exactly like a dead pipeline. The ref is
printed in the output for that reason.

Written 2026-08-31, when GitHub delivered 4 scheduled runs in a day
against 48 requested and the only symptom was the bot pausing its own
posting.
