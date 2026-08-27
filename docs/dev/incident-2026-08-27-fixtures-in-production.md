# 2026-08-27: the test suite posted 43 imaginary messages to the group

Lewis, 07:06: *"There are some serious bugs with the GM queue, such as
Paul's messages that don't exist."*

```
📋 GM Queue #1495 — Unreplied: 66 | ✅ 7 today | 🏆 3521 all-time
━━ 📌 🦠 C06: Kibwe (4) ━━
01 [42] 🆕 0h. Alice: Hi! 🔗 https://t.me/Path_Wars/100/42
...
━━ ⭐️ C07: Hopeful End-Times (43) ━━
17 [42] 🆕 23h. Paul: Hello all! 🔗 https://t.me/Path_Wars/100/42
   ... 43 of them
```

Of 66 unreplied entries, **47 were test fixtures**. The real backlog was
19.

## What happened

`track_message` does two things for any non-command message: it records
an unreplied entry in the GM queue, and it appends to the campaign
transcript. Both writes went to the **real** `data/` tree during test
runs, because neither path was isolated.

The debris accumulated for months:

| artefact | contents |
|---|---|
| `data/state/queues/100.json` | a pid that has never existed, with a **1,796-entry** reply_log |
| `data/pbp_logs/Hopeful_End-Times/2026-08.md` | 48 fixture message blocks |
| `data/pbp_logs/Kibwe/2026-08.md` | 8 fixture message blocks |

It became visible on 2026-08-27 because nine new tests in
`test_new_player_join_is_recorded.py` each tracked a player message,
taking it from background noise to 43 entries in one post.

It reached the repository through **local test runs plus `git add
data/`**, not through CI. PR #64 committed `queues/100.json`.

## Two second-order effects nobody would have spotted

**The all-time counter was more than half fake.** `get_alltime_clears()`
reads every campaign's `reply_log`, and `queues/100.json` was a campaign
as far as it was concerned. `3521` was really `1725`.

**The bot republished a years-old spam link.** The fixture entries
carried `message_id 42` and `pid 100`, so `_build_link` correctly
composed `https://t.me/Path_Wars/100/42`. That resolves to a **real**
early message in the group, whose content is an Opera News link, and
Telegram rendered a preview card for it under the queue post.

> Fake data in an id field is not inert. Id spaces are dense and small
> ids always resolve, so a fabricated entry produces a valid link to an
> arbitrary real message.

## Why it took three attempts to fix

**Attempt 1 cleaned the queue files.** They are not the source.
`scan_transcripts` rebuilds the queue from `data/pbp_logs/` on every run,
so the entries returned the moment the bot ran again.

**Attempt 2 guarded the queue files.** Same mistake, one level up: the
guard was written against the artefact that had been looked at, and it
passed while the bug was still live.

**Attempt 3 asserted the invariant.** A test run must leave `data/`
byte-identical. That holds regardless of which module writes.

### The isolation looked correct and was not

A full-suite run reported `data/` unchanged. Running the offending file
**alone** re-added 10 blocks: something else in the suite happened to
patch `_LOGS_DIR` in an order that masked it.

⚠️ **An accidentally-passing isolation is worse than a missing one**,
because the measurement everybody runs reports clean.

### Proving the guard caused the bug

Mutating the isolation away to prove the guard fires made the probe
append to a real transcript for real. Restoring the source file does not
undo a write to `data/`.

> A probe that exercises a safety mechanism must be harmless when that
> mechanism is absent.

The probe now targets `__probe_not_a_campaign__`.

## Why no guard could have helped

Both of these were found by looking at what actually *runs* the tests:

- **The `test` job had no `pull_request` trigger.** Nothing ran the suite
  before a merge, so every guard gated nothing at review time.
- **The test step swallowed pytest's exit code.** The last command was
  the `if` that fires the alert, so a red suite exited `0`. The tests
  could not fail the build even on push.

⛔ And the trap while fixing it: the `run` job was gated on
`github.event_name != 'schedule' || ...`. A denylist. Adding a
`pull_request` trigger would have satisfied it on every PR, and that job
posts to Telegram, writes state and pushes commits.

> A condition phrased as "not X" opts in every trigger anyone adds later.

## What is in place now

| layer | catches | file |
|---|---|---|
| path isolation | the six known writers, deterministically | `scripts/_test_state_isolation.py` |
| per-writer probes | each known writer, by doing it and hashing `data/` | `test_tests_never_touch_real_data.py` |
| **CI: fail on dirty `data/`** | **any writer, including unenumerated ones** | `.github/workflows/pbp-reminder.yml` |
| content backstop | a transcript referencing a topic no campaign has | `test_tests_never_touch_real_data.py` |
| queue backstop | a fixture fingerprint in a live queue | `test_no_test_data_in_live_queues.py` |
| workflow guard | the CI conditions regressing | `test_workflow_cannot_post_from_a_pr.py` |

The third row is the one that answers "make sure it cannot happen
again". Every other row depends on somebody remembering to add a module
to a list.

Thirteen mutations were used to prove these, each asserted to have
applied before the run.

## Cleanup notes

`queues/100.json` was deleted after verifying pid 100 appears in no
config pair, seats no player and has no transcript.

`queues/1242.json` was **kept**: retired C11 Dark Pockets, but 282
replied keys and 158 reply-log entries are genuine history. It is named
in `RETIRED_PIDS` rather than removed.

Transcript cleaning used `@100` as the discriminator and counted real
message blocks before and after, refusing to write unless they matched.
The diff was 190 lines, pure deletion.

⚠️ The cleanup had to be re-applied at merge time. The bot appends to
these files continuously, so `main` moved while the PR was open and the
deletion conflicted. Resolved by taking `main`'s copy wholesale and
re-running the cleaner, never by hand-merging a live data file.

## Verified end state

```
Queue reminder: 22 unreplied (2 msg)      # production, post-fix
data/ and config.json untouched by the test run.   # CI gate
run: skipping   test: pass   run-queue: skipping   # on a pull request
```

PRs #65, #66, #67.
