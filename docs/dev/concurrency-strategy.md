## Concurrency strategy — design doc for ROADMAP P3/10

Status: **draft for review**. Implementation has not started.

Depends on: P3/9 (`statestore-design.md`) for the locking primitives.

---

### The problem

The bot's main entry point is `scripts/checker.py`, invoked by
`.github/workflows/pbp-reminder.yml` on three triggers:

* `cron: 0 * * * *` (hourly, automatic)
* `push: branches: [main]` (whenever a commit lands)
* `workflow_dispatch` (manual run)

The workflow has:

```yaml
concurrency:
  group: pbp-checker
  cancel-in-progress: false
```

That setting *queues* runs rather than letting them overlap. So in
the steady state, only one process touches state at a time. Good.

But the protection is at the CI level, not the code level. Two ways
it can fail:

**F1. Two processes outside CI.** A maintenance script and the bot
running on different machines (e.g. Lewis runs `purge_gm_queue_history.py`
locally while the hourly cron fires on GitHub) both read+write the
same state files. The CI concurrency group doesn't help — only one
side of the race is in CI.

**F2. The CI guarantee is weaker than it looks.** GitHub Actions
queues runs by start time, but:

* A `workflow_dispatch` triggered while a scheduled run is *still
  pushing its state-commit* enters the queue *after* the scheduled
  run technically "finished" — but before the push has propagated.
  The new run reads a stale `main`, computes diffs from it, and
  pushes a state commit that effectively rewinds the previous run's
  changes. Recovery requires `git pull --rebase`, which the
  `Commit data` step does *not* do.

* `paths-ignore: ['data/**']` means a state-only commit doesn't
  trigger a new push run, but it doesn't preclude a *different* push
  (a code change) from racing the scheduled run that's mid-write.

**F3. Within a single run, no protection.** The current code path
reads `live.json`, mutates the dict in memory, writes back. If a
future feature adds a sub-process or async I/O, the in-memory state
isn't protected from concurrent mutation. Today this is theoretical;
it stops being theoretical the moment we touch async.

---

### Failure modes observed (or near-observed)

Three real events worth recording:

1. **State auto-commit conflicts.** During the 200-line refactor, my
   pushes regularly raced the bot's hourly state auto-commits.
   Resolution was always `git pull --rebase` and re-push. Annoying,
   not dangerous — git's rebase semantics correctly identified the
   non-conflicting changes in each.

2. **The 2026-05-08 deletion incident.** Not strictly concurrency,
   but the same shape: a maintenance script ran without coordinating
   with the bot. The damage was message-deletion, not state corruption,
   but state corruption was equally available. The bot_sent_registry
   safeguard fixed *that* class of damage; the next class-of-damage
   needs a structural fix here.

3. **Gist backup divergence (theoretical).** `state.py:save()` writes
   files then writes gist. If two processes both finish their file
   writes (one wins via filesystem ordering, the other gets clobbered
   on the file write but still writes its stale data to gist), the
   gist now reflects neither current state. We have not seen this
   because the workflow concurrency group prevents simultaneous
   completion. We'd see it the moment that guarantee gets relaxed.

---

### Three options

**Option A — Lockfile per partition.**

Each partition file (`live.json`, `players.json`, `queues/{pid}.json`,
`bot_sent_ids.json`, etc.) gets a sibling `.lock` file. Acquire the
lock on read, hold across the write, release. Use `fcntl.flock` on
Linux, `msvcrt.locking` on Windows, or a portable cross-platform
library (`filelock` package).

```
data/state/live.json
data/state/live.json.lock        # OS-level advisory lock
```

* **Pros:** Conceptually simplest. Defends against F1 (different
  machines on shared FS) only if the FS supports `flock` semantics
  across mounts (NFS does, GitHub Actions checkout does, local disk
  does). Defends against F3 (in-process) trivially. Works regardless
  of whether the writer is in CI or not.

* **Cons:** Doesn't help F2 — git pushes are not lock-aware. A run
  that holds the lock locally is invisible to another machine that
  cloned the repo. So this option fixes within-machine races but not
  the actual incident shape (machine A pushes, machine B's clone is
  stale).

* **Effort:** Small. Slice 8 of `StateStore` adds the locking
  primitive. Each partition's read/write goes through it.

**Option B — Git-as-source-of-truth with optimistic concurrency.**

Treat the working-tree state files as a *cache* and the `main` branch
as the canonical state. Every save:

1. Pull-rebase to get the latest `main`.
2. Compute the diff against in-memory state.
3. Commit and push.
4. On rejected push (someone else won the race), pull-rebase, re-apply
   the diff, retry. Up to N retries before bailing.

* **Pros:** Solves F1 and F2 directly. Multiple machines, multiple
  CI runs, manual scripts — all cooperate via git's existing
  optimistic-concurrency model. No new lock files, no new failure
  modes. Git already handles "merge non-conflicting changes" cleanly.

* **Cons:** State writes now require network I/O on every save —
  ~2-5 seconds added to every bot run. CI has a single state commit
  at end-of-run anyway, so the *net* cost is small there, but
  ad-hoc scripts (`purge_gm_queue_history.py`, dev iteration) get
  visibly slower. Also, "pull-rebase, re-apply diff" is non-trivial
  for nested-dict changes — a clean diff/patch model on JSON
  (RFC 6902 patches?) would help.

* **Effort:** Medium. The pull-rebase is a one-liner; the re-apply
  logic isn't.

**Option C — Telegram pinned-message as canonical state.**

The bot already pins per-thread queue messages. Extend the pattern:
the bot also pins a JSON-serialised state blob in the bot topic.
Every run reads the pinned blob (Telegram is a single source of
truth across all machines), mutates, edits the pinned message.
Files in `data/state/` become a local cache.

* **Pros:** Telegram's API is ordered (it serialises edits to the
  same message). Two machines can't both successfully edit a pinned
  message simultaneously without one seeing a stale-pin error.
  Solves F1 and F2 by punting the consistency problem to a system
  that already solved it.

* **Cons:** Telegram message size cap is 4096 chars; current
  combined state is ~20 KB JSON. Would need either compression
  (gzip + base64 ≈ 4× expansion, no) or sharding (one pinned message
  per partition, ~5 pins, each <4 KB after stripping whitespace —
  feasible but ugly). Also: the bot becomes dependent on Telegram
  for read availability, which inverts the current model where state
  is repo-local.

* **Effort:** Large. This is a real architecture change.

---

### Recommendation

**[STATUS — 2026-05-10]** Slice 8 of P3/9 shipped with `threading.
Lock` rather than `filelock`. The recommendation below is what was
originally proposed; the section that follows it ("What slice 8
actually landed") is what's actually in production. Both are kept
so the deviation is visible to future maintainers.

Original recommendation: **Option A for the immediate fix; Option B
as a follow-up if F2 actually bites.**

The reasoning:

* F3 (in-process) needs Option A regardless — locking primitives in
  `StateStore` are good for their own sake (concurrent saves within
  one run, or across threads if we ever go async).
* F1 (different machines, shared FS) is rare in practice. Lewis's
  laptop and CI don't share a FS. The only "two machines" scenario
  is two GitHub Actions runners — and the `concurrency: pbp-checker`
  group prevents that today.
* F2 (CI guarantee weakness) is the real risk, but it's also the
  rarest. The bot writes state ~3 KB/run. The window for racing
  state commits is the few seconds between `_save_to_files` finish
  and `git push` returning. Fixed by Option B (`pull --rebase`
  before push), but Option B's overall cost is high.
* The deletion incident shape was *not* a race — it was a single
  process doing the wrong thing. The safeguard already fixed that
  class.

So: ship Option A as part of `StateStore` slice 8. Treat F2 as a
known limitation, document it explicitly, and only escalate to
Option B if it bites. Don't touch Option C unless we encounter a
problem that genuinely needs it.

---

### What slice 8 actually landed (2026-05-10)

**TL;DR:** in-process `threading.Lock` per resource, NOT filesystem
`filelock`. Covers F3 fully; does not cover F1. The pragmatic
position: F1 doesn't apply to this deployment (single CI runner,
no shared FS), so the simpler primitive is sufficient for actual
risk reduction today.

**What's in production:**

* `state_store/locks.py` provides `LockRegistry`, an instance-
  scoped registry of `threading.Lock` objects with lazy creation
  and a `held()` context manager.
* Every `save_*` method on `StateStore` acquires its keyed lock
  (`aux:{name}` / `partition:{name}` / `queue:{pid}`) for the
  duration of its tmp+rename write. Disjoint resources don't
  serialise on each other.
* Per-instance registry means tests using `StateStore(state_dir=
  tmp_path)` don't cross-serialise.
* 10 tests in `test_state_store_locks_01_registry.py` and
  `test_state_store_locks_02_savelock.py` cover registry mechanics
  + end-to-end save serialisation (verified with threading +
  counter-based critical-section check).

**What it covers:**

* F3 (in-process concurrency) — fully. If/when threading or async
  arrives, the serialisation primitive is in place.
* Foundation for slice 10 (read-modify-write API) — the locks are
  the right shape for a future RMW context manager.

**What it does NOT cover:**

* F1 (different machines, shared FS) — in-process locks are
  invisible across processes. Would need `filelock` or `fcntl.flock`
  to address. Deferred because F1 doesn't apply to this deployment
  (GitHub Actions VMs are isolated, no shared FS scenario).
* F2 (CI commit-window race) — neither in-process nor file locks
  help. Option B (`pull --rebase` before push) would; still treated
  as a known limitation per the original recommendation.
* Read-modify-write atomicity — a reader holding stale data can
  still overwrite a concurrent writer's update. Deferred to slice
  10 (P3/10).

**Path forward if F1 ever applies:**

1. Add `filelock` package to `requirements.txt` (~30 sec install,
   pure Python, no native deps).
2. Wrap each `with self._locks.held(...)` in a parallel `with
   FileLock(path.with_suffix('.json.lock'))`. Defence in depth —
   the existing in-process lock stays for F3 protection in the
   same process, the file lock adds cross-process protection.
3. Add `*.lock` to `.gitignore`.
4. Add `test_concurrent_writes.py` that spawns two subprocesses
   both calling `save_partition` and asserts the final state is
   one of the two inputs (not a corrupt mix).

Effort estimate: ~45-60 min if needed.

---

### Decision needed

1. **Confirm Option A as the target.** Or argue for B/C if I'm
   wrong about F1/F2 frequency.
2. **`filelock` dependency.** Adds one package to `pip install`.
   Acceptable, or do we want a pure-stdlib `fcntl`/`msvcrt`
   wrapper (~30 lines, more code to maintain)?
3. **Implementation timing.** Land in `StateStore` slice 8 (after
   the read/write paths are unified) or as a separate effort
   alongside? I lean slice 8 — keeps the locking and the I/O in
   one place, in one PR, easier to review.
