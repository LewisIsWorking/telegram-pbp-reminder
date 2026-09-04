# tools/

Local scripts. Not imported by the bot, not run in CI. Each answers a
question that came up once and will come up again.

| Script | Question it answers |
|---|---|
| `schedule_delivery_report.py` | Is GitHub actually running the workflow as often as the cron asks? |
| `external_heartbeat.py` | Runs the bot from OUTSIDE GitHub when GitHub stops running it. Meant for the VPS crontab. |
| `audit_queue_deletes.py` | Which superseded queue posts were actually deleted, and which became orphans? |
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

> ⛔⛔ **CORRECTED 2026-09-02:** the in-repo watchdog CAN now restart the
> bot by itself. It was failing with HTTP 403 because its job held
> `actions: read`; GitHub exempts `workflow_dispatch` from the
> GITHUB_TOKEN recursion guard, so no PAT was ever needed. **This script
> is now a second line of defence, not the only one.** It still matters:
> it is the only thing that survives GitHub delivering no schedules at
> all, which is what the watchdog cannot do.

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

This script belongs on the VPS crontab. It dispatches the workflow only
when the bot's state has not been pushed in 45 minutes.

### What it costs the VPS, measured

Lewis asked, so it was measured rather than estimated:

| | |
|---|---|
| wall time per run | **392 ms** (best of 3, end to end) |
| of which network idle | ~450 ms of the first version; almost all the time |
| download per run | **200 bytes** |
| peak heap | ~1.5 MiB, nothing resident between runs |
| **per day at `*/15`** | **~38 s wall total, ~19 KiB down** |

⭐⭐ **The first version cost 1,500x more.** It asked the Actions API for
the run list:

```
GitHub Actions run list   306,759 bytes   1415 ms
raw ci_heartbeat.json         200 bytes    452 ms
```

⭐ And the cheap version is the *better* one. `data/ci_heartbeat.json` is
only written by a run that did the work **and pushed**, so a `skipped`
run cannot produce one. The expensive version needed an explicit
"skipped does not count as running" rule to survive the 2026-08-31
outage; this one gets that property for free, because a skipped run
leaves nothing to misread.

⚠️ The heartbeat fetch is **unauthenticated** (public repo), so the PAT
is only touched when a dispatch is actually needed.

⛔ A **30 minute dispatch cooldown** is enforced locally via a marker
file. If the bot runs but its *push* is broken the heartbeat never
refreshes, and without a floor this would fire every tick forever,
multiplying a broken run.

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

## `audit_queue_deletes.py`

```bash
py -3 tools/audit_queue_deletes.py             # problems only, since 2026-08-01
py -3 tools/audit_queue_deletes.py --all       # every superseded post
py -3 tools/audit_queue_deletes.py --since 2026-09-01
```

⛔ **Exists because I got this wrong by inferring it.** Hunting orphaned queue
posts on 2026-09-04, I measured the GAP between consecutive posts in a thread
and called anything over Telegram's 48h delete wall an orphan. That gave four,
and Lewis deleted four messages by hand on my word. Only three were real:
`m175902` had been deleted by the bot on the first attempt, and
`pin_audit_log.json` recorded exactly that the whole time.

The gap is a proxy. It supports *"a delete attempted at the END of this window
could not have succeeded"* and nothing more. It agreed with the direct evidence
three times in four, which is how a proxy earns trust it has not got.

This reads the direct record instead:

| file | what it contributes |
|---|---|
| `pin_audit_log.json` | every delete ATTEMPT, with `ok` / `refused` |
| `stuck_deletes.json` | ids the bot gave up on, for a human to clear |
| `sent_messages.json` | what was posted, when, to which thread |

Three verdicts, and the third is the one that matters most:

- **deleted**: an attempt succeeded.
- **ORPHAN**: attempts were made and all failed. History, not a broken build.
  Shows `(resolved <date>)` once a human has removed it.
- **DROPPED**: no delete was ever attempted. This is the only exit-1 case,
  because it means ids are being lost *before* Telegram is ever asked.

Measured 2026-09-04: **292 superseded, 289 deleted cleanly, 3 orphans (all
resolved), 0 dropped.** `scripts/test_orphans_are_counted_from_the_delete_log.py`
runs it against the real state files so it cannot rot into a fixture-only tool.
