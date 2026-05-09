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

The 200-line refactor split many "coverage-seed" files (`test_branch_gaps`,
`test_remaining_*`, `test_final_*`, etc.) into themed sub-files. Many
of those tests duplicate behaviour-focused tests in proper feature
files (e.g. `test_remaining_gaps_04_commands_trackers.py` likely
overlaps with whatever test file owns `commands/cmd_trackers.py`).

**Plan:**
1. Build a quick map: for each coverage-seed sub-file, which production
   module(s) does it test? (Their docstrings already say this.)
2. For each production module, list every test file that exercises it.
3. Where two test files exercise the same module: review test names
   for behavioural overlap.
4. Where overlap is real: delete the coverage-seed test, keep the
   feature test.
5. Run pytest with `--cov` to confirm 100% coverage is preserved.

**Done when:** coverage is 100%, the suite passes, total test LoC has
dropped meaningfully (target: -25% test code).

**Risk:** medium — touching tests is touchy; a deleted "duplicate"
might cover an edge case the feature test misses. Coverage report is
the safety net.

### 7. Fix datetime deprecation warning

Pytest currently shows:

> `DeprecationWarning: Parsing dates involving a day of month without
> a year specified is ambiguous and fails to parse leap day. The
> default behavior will change in Python 3.15`

at `helpers_pkg/time_utils.py:116`.

**Plan:**
1. Look at `time_utils.py:116` — find the format string accepting
   day/month without year.
2. Decide the fix: explicit current year, fail-on-leap-day, or use
   `dateutil.parser` (already a likely transitive dep).
3. Update tests to cover the resolution behaviour at year boundaries.

**Done when:** zero DeprecationWarnings in pytest output.

**Risk:** low — narrow, well-bounded.

### 8. Test sub-file naming cleanup

A few regenerated sub-files have ugly auto-generated names from the
splitter, e.g. `test_dispatch_coverage_07_voting_code_not_in_any_pair_s_code___no_posts_but_no_crash.py`.
These came from section comments that the splitter slugified
verbatim.

**Plan:**
1. Walk each phase-3-7 sub-file; check the file name vs the actual
   sections it contains.
2. Rename to a shorter, production-module-based slug
   (`test_dispatch_coverage_07_poll_notify.py`).
3. Update any `git log --follow` references in `REFACTOR_PROGRESS.md`.

**Done when:** every sub-file name is ≤60 chars and identifies the
production module it covers.

**Risk:** none — pure rename.

---

## P3 — Architectural improvements

### 9. State layer extraction (`StateStore`)

State is currently scattered: `data/state/live.json`,
`data/state/queues/{pid}.json`, partition registrations in
`scripts/state.py`, ad-hoc reads/writes in many command modules.
Schema migrations are inline in callers (`_migrate_legacy` etc.).

A `StateStore` abstraction would centralise:
* Read/write contracts (atomic writes, lockfile per partition).
* Migration registry (declarative, run at first read).
* In-memory cache (avoid re-reading the same JSON twice per run).
* A typed interface per partition (instead of nested-dict dancing).

**Plan:** large enough to deserve its own design doc; not started
here.

**Done when:** every `with open(state_path) as f: json.load(f)` in
production code goes through `StateStore`, schemas are declared once,
migrations are declarative.

**Risk:** high — touches everything. Best done with the state-layer
work split into vertical slices (one partition at a time).

### 10. Race condition strategy

The workflow concurrency `pbp-checker` group + `cancel-in-progress:
false` means simultaneous runs queue rather than overlap. But a manual
trigger during an in-flight scheduled run still gives two processes
writing to the same state file in sequence; the second can lose data
if it read before the first finished writing.

**Plan:** also too big for inline. Options sketched:
* Lockfile per partition with timeout fallback.
* Git-as-source-of-truth with optimistic-concurrency rebases.
* Telegram-pinned-message as canonical state for the queue.

**Done when:** two workflow runs racing produce the same final state
as either one running alone.

**Risk:** high — distributed-systems territory.

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
