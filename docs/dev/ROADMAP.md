# PathWarsNudgeBot Roadmap

Forward-looking plan after the 200-line refactor and the delete-safety
incident of 2026-05-08. Each item lists the *why*, the *plan*, the
*acceptance criteria*, and the *risk*. Numbers are priority order, not
time estimates.

When an item is done, it moves to the bottom of `REFACTOR_PROGRESS.md`
with the commit SHA(s) and learnings, and the entry here gets struck
through.

---

## P0 — Hygiene

### 1. Workspace cleanup: `.refactor-fix/`

The `.refactor-fix/` directory in the repo root holds session-only
artefacts from the phase-3-7 re-split work: 13 fetched-from-git
originals, the regenerated `out/` sub-files (now living in `scripts/`),
old progress-doc copies, and `fixed_splitter.py`.

The splitter has real value as a maintenance tool — it encodes 12+
learnings about section-marker styles, cross-section helpers, module-
level constants, and section preambles. Re-deriving it would be a
multi-hour exercise.

**Plan:**
1. Create `tools/` directory at repo root.
2. Move `.refactor-fix/fixed_splitter.py` to `tools/test_splitter.py`
   with a top-of-file comment pointing at this roadmap entry and at
   `docs/dev/REFACTOR_PROGRESS.md` for context.
3. Delete the rest of `.refactor-fix/` (originals, `out/`, the
   intermediate progress copies, `current_progress*.md`).
4. Add a brief entry to `docs/dev/REFACTOR_PROGRESS.md` recording where
   the splitter ended up.

**Done when:** `git status` is clean, `tools/test_splitter.py` exists,
`.refactor-fix/` is gone.

**Risk:** none — these are all session artefacts.

### 2. Memory update

Claude's memory should record three new facts:

* The 200-line refactor is complete (already noted, but reinforce).
* The bot has a hard delete safeguard via `posting.bot_sent_registry`
  + `posting.safe_delete`; `tg.delete_message` refuses any ID not in
  the registry.
* Future maintenance scripts that delete messages must route through
  `tg.delete_message` (no raw `requests.post` to `deleteMessage`). The
  rewritten `purge_gm_queue_history.py` is the reference template.

**Done when:** the user instructs the memory update, or this session
ends with the user reading the summary.

**Risk:** none — declarative.

---

## P1 — Safety hardening

### 0. `_post` soft-success semantics (2026-05-10)

**Status:** ✅ done.

Lewis reported on 2026-05-10 that old GM queue messages weren't being
deleted (state had 6 batches retained against `MAX_KEPT_BATCHES = 3`)
and topic queue prev-deletes were logging spurious failures even
when the messages were actually gone. Investigation found:

* All affected msg_ids were in `bot_sent_ids.json` — the safeguard
  was NOT refusing.
* `refusal_log.json` did not exist — confirms no safeguard
  refusals.
* CI logs showed `Topic queue prev-delete failed:
  thread=107171 undeleted=[150803, 150804]` with no Telegram
  error printed — indicating the response was suppressed.

Root cause: `telegram._post` returned `None` for both real failures
and suppressed-error responses (“message to delete not found”, etc.).
Both callers (`posting.safe_delete.perform_guarded_delete` and
`telegram.unpin_message`) checked `_post(...) is not None` and so
treated “already gone” as failure, leaving evicted batches stuck
in state.

Fix landed: `_post` now returns `True` for suppressed-error
responses, signalling soft success. Real failures still print and
return `None`. The safety argument: this is downstream of
`bot_sent_registry.is_bot_sent` — it does NOT change *which* IDs
get attempted, only how the result is interpreted. Catalogue of
recognised soft-success patterns is in
`scripts/telegram_post_notes.py`. White-box tests in
`scripts/test_telegram_03_suppress.py` lock the new behaviour and
guard against regression. 1631 tests passing.

Known remaining issue: an orphaned topic queue message from
2026-05-03 in thread 107171 is still visible in chat. The bot
lost track of its msg_id at some earlier point so neither the
safeguard nor this fix can reach it. Resolution requires either
manual deletion or Lewis supplying the msg_id so it can be added
to the registry and a one-shot delete invoked. **Do NOT auto-
discover candidate IDs** — that's exactly the path the 2026-05-08
incident took.

**2026-05-11 update:** the same class of bug bit again, producing
duplicate GM queue #360 and a duplicate per-topic-queue post. Root
cause was the workflow's checkout pinning to GITHUB_SHA, defeating
the concurrency group's serialisation guarantee — documented in
L21 and mitigated by the same-day workflow fix. The 2026-05-03
orphan was almost certainly produced by this same mechanism. The
fix prevents future occurrences; previously-orphaned messages
(2026-05-03 and 2026-05-11) remain Lewis's manual cleanup task.
**Claude must never perform orphan cleanup** — hard rule, recorded
in Claude's persistent memory.

### 3. Audit codebase for bypass paths

The safeguard works because every delete in the codebase routes through
`tg.delete_message`. If any module directly POSTs to Telegram's
`deleteMessage` endpoint via `requests`, it bypasses the guard.

**Plan:**
1. Grep for `deleteMessage` (case-insensitive) across the entire repo.
2. Grep for `requests.post.*api.telegram.org` to catch any direct
   API construction.
3. For each hit, confirm it routes through `tg.delete_message` or move
   it onto that path.
4. Add a `test_no_direct_delete_bypass.py` that asserts the only
   places `deleteMessage` appears are: `posting/safe_delete.py`,
   `telegram.py` (in a comment), and the maintenance script. Any new
   bypass added later fails the test.

**Done when:** the bypass test passes, and a deliberate audit found no
direct callers.

**Risk:** low — adding a regression test, no behaviour change.

### 4. Document the safeguard

Currently the safeguard is documented inline in the source files but
nowhere users (or future contributors) would look first.

**Plan:**
1. Add a section to `docs/dev/` called `delete-safety.md` covering:
   * The 2026-05-08 incident as the cautionary tale.
   * The registry's invariants ("once recorded, always referenced;
     never removed").
   * The contract for new senders ("call `record_sent` after every
     successful send that returns a message_id").
   * The contract for new deleters ("only call `tg.delete_message`;
     never `requests.post` to `deleteMessage` directly").
   * The escape hatch: `posting.bot_sent_registry.record_sent(mid)` to
     manually add a known bot ID before deleting it.
2. Link from `docs/troubleshooting.md` and `docs/dev/REFACTOR_PROGRESS.md`.

**Done when:** the file exists, the links resolve, and a reader could
extend the bot without re-introducing the bug.

**Risk:** none.

### 5. Registry refusal monitoring

If `tg.delete_message` refuses a delete in production, that's either
(a) a bug — the bot tried to delete its own message but the ID isn't
in the registry, or (b) an attempted incident — something tried to
delete a non-bot message.

Either way, the operator should know.

**Plan:**
1. Have `safe_delete.perform_guarded_delete` record refusals to a
   simple counter or log file (e.g. `data/state/refusal_log.json`
   with `{timestamp, chat_id, message_id}` entries).
2. Extend `scripts/ci_alert.py` (already used for test failures) to
   check the refusal log size after each bot run and post a Telegram
   alert if it grew.
3. Optional: a `/refusals` GM command that prints recent refusals.

**Done when:** a refusal is observable from outside the CI logs.

**Risk:** low — additive logging.

---

## P2 — Tech debt from the refactor

### 6. Test consolidation pass

**Status:** plan written, awaiting decision on scope/threshold/order.

Full plan: **`docs/dev/test-consolidation-plan.md`**.

Short version: ~89 coverage-seed sub-files (`test_branch_gaps_*`,
`test_remaining_*`, `test_final_*`, etc.) likely duplicate behaviour-
focused tests in feature files. Process module-by-module, in risk
order (helpers first, `checker.py` last). Use **branch coverage** as
the safety net, not line coverage. Target -25% test code while
keeping coverage at baseline. ~25 hours, multi-session.

**Risk:** medium — deleting a test that *looks* like a duplicate but
covers an edge case the feature test misses is silent. Branch
coverage + per-module commits are the mitigation.

### 7. Fix datetime deprecation warning ✅

**Status:** done in commits `a0588c1` / `46f4c4f`. The fix lives at
`helpers_pkg/time_utils.py:113-131`: year-having formats are
tried first; year-less formats synthesise the current year via
`f"{date_str} {now.year}"` BEFORE strptime, with a past-date check
that bumps to next year (so "until January 1" said in November
resolves to *next* January).

**Verified 2026-05-10:** `pytest -W error::DeprecationWarning`
passes cleanly across all 1664 tests. No production strptime
calls anywhere else in the codebase use year-less formats.

**Risk:** low — narrow, well-bounded.

### 8. Test sub-file naming cleanup ✅

**Status:** done in commit `a4ac15d`. Every test sub-file under
`scripts/test_*.py` is now ≤60 chars and identifies the production
module it covers.

**Verified 2026-05-10:** scan of `scripts/test_*.py` finds zero
files exceeding the 60-char limit.

**Risk:** none — pure rename.

---

## P3 — Architectural improvements

### 9. State layer extraction (`StateStore`)

**Status:** slice 1 landed. Slices 2-8 pending; questions 1, 2, and
5 from the design doc are now answered (see slice 1 commit message)
or deferred until they actually apply.

Full design: **`docs/dev/statestore-design.md`**.

Short version: state is fragmented across `state.py` (5 partitions in
`live`/`players`/`queue`/`activity`/`trackers`), `queues/{pid}.json`
(separate ad-hoc system), and three auxiliary files
(`bot_sent_ids`, `refusal_log`, `refusal_log_alerted`). Each system
has different write contracts, no schema enforcement test, and no
atomic writes (except the registry, which got it for free during
P1/5). Proposed: a single `StateStore` class owning every file in
`data/state/`, with atomic writes, partition-aware
load/save, declarative migrations, single test-isolation point, and
locking primitives ready for P3/10. Eight vertical slices, each
independently shippable.

**Slice progress:**
* ✅ Slice 1 — `state_store/` package shell, aux file API
  (`load_aux`/`save_aux`/`delete_aux`/`list_aux`), `bot_sent_ids`
  migrated. 17 new tests; 1623 total passing.
* ✅ Slice 2 — `refusal_log` migrated to use `StateStore`. Both
  `refusal_log` (entries) and `refusal_log_alerted` (marker) now
  flow through `_store.load_aux`/`save_aux`. Test isolation hook
  in `_test_state_isolation.py` simplified to a single shared
  `_TEST_STORE` for both modules.
* ✅ Slice 3 — partitions read path. `StateStore.partition_exists` /
  `load_partition` added. `state.py:_load_from_files` now
  delegates per-partition reads to StateStore. Corrupt-file policy
  preserved (returns None → gist fallback) but tightened: previously
  a corrupt partition file was wrapped in a try/except that returned
  None, now it's an explicit per-partition check that distinguishes
  "file missing" (continue, e.g. trackers.json on fresh checkout)
  from "file exists but parse failed" (return None, don't merge
  half-loaded state). 5 new partition tests; 1636 total passing.
* ✅ Slice 4 — partitions write path. `StateStore.save_partition`
  added (delegates to `save_aux` for tmp+rename atomic write).
  `state.py:_save_to_files` migrated. The previous implementation
  did `path.write_text(json.dumps(...))` per partition with a
  docstring claiming atomicity — it wasn't. Now every partition
  write goes through tmp+rename so a crash mid-write cannot leave
  a half-written `live.json`. `import json` dropped from `state.py`
  (no longer used). Test file split into `test_state_store.py`
  (aux API, slices 1+2) and `test_state_store_partitions.py`
  (partition API, slices 3+4) to stay under the 200-line cap. 5
  new save tests; 1641 total passing.
* ✅ Slice 5 — queue partitions. `QueueAPI` mixin in
  `state_store/queue_api.py` (`queue_path` / `queue_exists` /
  `load_queue` / `save_queue` / `list_queues`); `StateStore`
  inherits via `class StateStore(QueueAPI):`. `commands/queue_io.py`
  migrated: production writes now atomic (tmp+rename via
  StateStore), and a `_QUEUES_DIR` test-compat hook preserves the
  existing fixture pattern across ~24 test files so the slice
  doesn't force a touch on every test that ever exercised the old
  layout. 1641 total passing.
* ✅ Slice 6 — schema-completeness regression test.
  `state_store/schema.py` declares the canonical inventory of
  expected state files (5 PARTITIONS, 3 AUX_FILES, 1 WRITE_ONCE).
  `test_state_schema.py` asserts: (a) every file under
  `data/state/` matches a schema entry, (b) schema PARTITIONS
  mirrors `state.PARTITIONS` keys, (c) every PARTITIONS/AUX_FILES
  entry has the corresponding StateStore method, (d) WRITE_ONCE
  entries (e.g. `manifest.json` from the 2026-04 migration) have
  no dedicated loader, (e) queue files match the digits-only pid
  shape. 1648 total passing.
* ✅ Slice 7 — migration registry. `state_store/migration_registry.py`
  centralises every state migration in one discoverable place.
  Production call sites still invoke each migration directly
  (pure refactor, no behaviour change); the registry exists for
  discovery and so the regression test can assert known
  migrations remain wired up. Two production migrations now
  registered: `live/last_queue_pin_id_to_gm_queue_history` and
  `queue/topic_msg_id_to_topic_queues`. `test_migration_registry.py`
  asserts (a) every known migration is registered, (b) no
  unexpected migrations have appeared, (c) every registration has
  callable fn + non-empty description, (d) registration is
  idempotent on (target, name), (e) `for_target` filtering works,
  (f) `all_migrations` returns an immutable tuple. 1654 total
  passing.
* ✅ Slice 8 — locking primitives (P3/10 prerequisite).
  `state_store/locks.py` provides `LockRegistry`, a thread-safe
  registry of named `threading.Lock` objects with lazy creation.
  Every `save_*` method now acquires a per-resource lock for the
  duration of its tmp+rename write: `aux:{name}` for save_aux,
  `partition:{name}` for save_partition, `queue:{pid}` for
  save_queue. Concurrent saves to the same resource serialise;
  saves to different resources run in parallel. Lock registry is
  instance-scoped (per StateStore), so test isolation isn't
  broken. Partition methods extracted to a new
  `state_store/partition_api.py` mixin (mirroring the slice-5
  QueueAPI pattern) to keep store.py under the 200-line cap; the
  partition save no longer delegates through save_aux, removing
  the dual-lock acquisition that delegation would have caused.
  10 new tests across `test_state_store_locks_01_registry.py`
  (LockRegistry mechanics) and `test_state_store_locks_02_savelock.py`
  (end-to-end save locking, concurrent serialisation). 1664 total
  passing.

  What this slice does NOT yet provide: read-modify-write
  atomicity. A reader holding stale data can still overwrite a
  concurrent writer's update — last-write-wins. P3/10 will add
  the read-modify-write API on top of these primitives.

**Risk:** high — touches every state read/write in production. Slice
plan keeps each slice small and independently testable.

### 10. Race condition strategy

**Status:** strategy doc written; slice 8 of P3/9 shipped
in-process `threading.Lock` (not `filelock`). The pragmatic
position: F1 (different machines, shared FS) doesn't apply to this
deployment, so the simpler primitive is sufficient for actual risk
reduction today. F3 (in-process concurrency) is covered fully.

Full strategy: **`docs/dev/concurrency-strategy.md`** — see the
"What slice 8 actually landed" section for what's in production
and the "Path forward if F1 ever applies" section for the file-
lock upgrade path (~45-60 min effort, deferred).

Short version: the workflow concurrency group queues runs serially,
but the protection is at the CI level, not the code level. Three
failure modes (different machines on shared FS / weak CI guarantee
during the state-commit window / future in-process concurrency).
Three options weighed: (A) lockfile per partition, (B) git-as-source-
of-truth with optimistic concurrency, (C) Telegram pinned message as
canonical state. Recommendation: ship Option A in P3/9 slice 8;
treat F2 (CI window) as a known limitation; document; only escalate
if F2 actually bites.

**Risk:** medium given the recommendation; high if we picked B or C.

**2026-05-11 update — F2 bit.** The duplicate-#360 incident was a
textbook F2 manifestation: two pushes 32s apart triggered back-to-
back runs, the second checked out its trigger SHA (which predated
the first run's state commit), read stale state, and posted the
same queue a second time. The earlier orphan in thread 107171
from 2026-05-03 was almost certainly the same root cause. Both are
documented in L21.

Mitigation shipped (also 2026-05-11): two-line workflow fix
— `ref: main` on the run-job's checkout, plus retry-with-rebase
on the state push. After concurrency-group serialisation, Run B
now checks out main HEAD (including any state commits from Run A)
rather than the stale trigger SHA. The fingerprint check then
trips and Run B skips the duplicate. State pushes that race no
longer silently drop — the loop retries with `git pull --rebase`
or fails the job loudly. F2 is **no longer a known-tolerable
limitation**; it's a fixed bug.

The broader read-modify-write story (P3/10) is still future work
on its own merits, but F2 specifically is closed.

---

## Done (moved to REFACTOR_PROGRESS.md)

* 200-line refactor (phases 1-9)
* Phase 3-7 re-split fix-up (helpers, preambles, constants)
* Delete safeguard (`bot_sent_registry`, `safe_delete`,
  `tg.delete_message` guard)
* P0/1 — Workspace cleanup: `tools/test_splitter.py` (commit
  `967d4a5`)
* P0/2 — Memory update (memory entries #11, #12, #13)
* P1/3 — Bypass audit + regression test
  `scripts/test_no_direct_delete_bypass.py` (commit `c5fd4b5`).
  Audit found no production bypass; the test now locks that in.
* P1/4 — `docs/dev/delete-safety.md` written; cross-linked from
  `docs/troubleshooting.md`.
* P1/5 — Refusal logging (`posting/refusal_log.py`) + Telegram
  alert (`refusal_alert.py`) + workflow step + 16 tests + global
  test isolation (`_test_state_isolation.py`) plugging the
  `data/state/bot_sent_ids.json` pollution leak (commit `76252c9`).
* P2/7 — `datetime.strptime` deprecation fixed in
  `helpers_pkg/time_utils.py` `parse_away_duration`. Year-less
  formats now synthesize the current year before parsing,
  eliminating the Python 3.15 DeprecationWarning. Full suite went
  from 5 warnings to 0.
* P2/8 — Sub-file naming cleanup. Seven test files with auto-
  generated 60+ char names (slugified verbatim from section
  comments) renamed to short production-module slugs:
  `test_scheduled_coverage_04_boons_display.py`,
  `test_dispatch_coverage_07_checker_voting.py`,
  `test_utility_coverage_03_migrate_gist.py`,
  `test_zero_coverage_05_commands_health.py`,
  `test_zero_coverage_02_commands_queue_stats.py`,
  `test_branch_gaps_12_queue_reminder_silent_a.py`,
  `test_branch_gaps_13_queue_reminder_silent_b.py`. All renames
  done via `git mv` so blame/log history follows. 1606 tests
  still pass.
