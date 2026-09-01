# tools/

Local scripts. Not imported by the bot, not run in CI. Each answers a
question that came up once and will come up again.

| Script | Question it answers |
|---|---|
| `schedule_delivery_report.py` | Is GitHub actually running the workflow as often as the cron asks? |
| `external_heartbeat.py` | Runs the bot from OUTSIDE GitHub when GitHub stops running it. Meant for the VPS crontab. |
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

## `external_heartbeat.py`

⛔⛔ **The watchdog inside GitHub cannot save the bot from GitHub's own
scheduler, because it is scheduled too.** `.github/workflows/watchdog.yml`
recovers a *broken workflow*. It cannot recover a *scheduler that has
stopped delivering*, because then it does not run either.

Measured 2026-09-01, **after** moving the crons off the contended
`:00`/`:30` minutes, which was supposed to fix delivery:

```
2026-08-30   18 / 48   38%
2026-08-31    3 / 48    6%     <-- the 15h outage
2026-09-01    8 / 48   17%
worst gap 27.8h
```

The bot asks for 48 runs a day and gets between 3 and 18. That is not
jitter, and no code inside the repository fixes it.

⚠️ It matters more here than for most bots: a tracked message ID is a
**perishable asset with a hard 48h expiry**, so any outage longer than
12h strands messages permanently. **Uptime is a correctness requirement,
and it is currently outsourced to something that does not provide it.**

This script belongs on the VPS crontab. It reads the run history and
dispatches the workflow only when nothing has **actually run** in 45
minutes. ⛔ `skipped` deliberately does not count as running: on
2026-08-31 every run was skipped and the bot was dead.

```bash
install -m 600 /dev/null ~/.pathwars-dispatch-token   # PAT, never committed
echo 'ghp_xxx' > ~/.pathwars-dispatch-token

*/15 * * * * GITHUB_TOKEN=$(cat ~/.pathwars-dispatch-token) \
    /usr/bin/python3 /opt/pathwars/external_heartbeat.py >> /var/log/pathwars-heartbeat.log 2>&1
```

Decision logic tested in `scripts/test_the_external_heartbeat_decides_well.py`.

---

Written 2026-08-31, when GitHub delivered 4 scheduled runs in a day
against 48 requested and the only symptom was the bot pausing its own
posting.
