# Codebase Refactor — Progress Log

Tracks the posting-abstraction refactor that started May 8, 2026.

## Goal

Eliminate the duplicated "send chunks → pin first → track IDs → delete-then-replace"
pattern that previously lived in three places:

- `scheduled/gm_queue_history.py` — rolling 3-batch history for the GM Queue topic.
- `scheduled/topic_queue_poster.py` — single-slot replace for per-campaign topic queues.
- `scheduled/topic_queue_state.py` — slot schema helpers used by `topic_queue_poster`.

The duplication caused (and re-caused) a class of bugs over multiple sessions:

- Failed deletes silently orphaning messages forever (no retry path).
- Schema drift between `msg_id` (legacy single int) and `msg_ids` (list).
- A "10-minute double-post guard" that broke the simple fingerprint check
  and made the bot re-post identical content every hour.
- Per-batch deletion logic scattered across both modules with subtly different
  failure-handling rules.

## Approach

A small `scripts/posting/` package contains the shared primitives, with each
scheduled module delegating to it while preserving its existing public API.
Blast radius stays small; call sites in `queue_reminder.py` and `checker.py`
don't need to change.

Constraints (from project conventions):

- **200-line rule.** Every new file under 200 lines.
- **Logging is permanent.** No diagnostic prints removed.
- **No warning suppression.** Fix the cause.
- **OOP-first extraction.** Each new module exposes a class or dataclass.

## Layers of `scripts/posting/`

| File | Lines | Role |
|------|-------|------|
| `__init__.py` | ~30 | Public re-exports |
| `message_batch.py` | ~80 | `MessageBatch` dataclass with `delete_all()` returning failed IDs |
| `sender.py` | ~55 | `post_batch()` — send chunks + pin first |
| `queue_history.py` | ~75 | `QueueHistory` — rolling N-batch window with retry-on-failure |
| `single_pin.py` | ~80 | `SinglePin` — replace-only slot for per-thread pins |

## What changed

### `scheduled/gm_queue_history.py`

Public surface (`migrate_legacy`, `append_and_evict`, `post_and_persist`,
`MAX_KEPT_BATCHES`) unchanged. Internals delegate to `posting.QueueHistory`
and `posting.post_batch`.

### `scheduled/topic_queue_poster.py`

Inline send/delete/pin logic replaced with `SinglePin` + `post_batch`.
Caught-up tracking preserved: each clear cycle's "✅ All caught up!"
message ID is stored in `slot["caught_up_msg_id"]`, and the next cycle
(post or clear) deletes it before posting its own — preventing the
historical "stack of caught-up notices" bug.

### `scheduled/topic_queue_state.py`

Reduced to a thin shim. Four functions now delegate to `SinglePin`
static methods. Behaviour is identical from outside, including
legacy-slot tolerance.

### `conftest.py` — new `tg_mock` fixture

A shared `MagicMock` patched into every module that imports `telegram as tg`
for queue-posting (orchestrator + posting package). Lets tests assert on
`tg_mock.delete_message.assert_called_once(…)` regardless of which module
made the call. Also adds `unpin_all_messages` to the mock surface.

### Test files

`test_topic_queue.py` and `test_topic_queue_b.py` adopted `tg_mock` instead
of per-module `patch(…)`. New tests for caught-up tracking on both the
post and clear paths. Four new `test_posting_*.py` files cover the new
package directly.

## Learnings

### L1 — Mock patches are coupled to implementation, not behaviour

`patch("module.tg")` patches *that module's* namespace reference. When
`delete_message` is called from a different module (because we extracted
the call into a helper), the patch doesn't reach it.

This is a code smell in the tests, not the production code. A `tg_mock`
fixture in `conftest.py` that patches every module's namespace at once
fixes the symptom; a longer-term cleanup would assert on `_sent_messages`
from the conftest mock instead of re-patching `tg` per test.

### L2 — Dataclass + side-effecting method is fine for this domain

`MessageBatch` is a dataclass that also has `delete_all(group_id)` calling
`tg.delete_message`. Strict CQS would split that. For a thin wrapper around
an HTTP call where "a batch knows how to remove itself" is the natural
mental model, the combined form reads better and saves a class.

The line we drew: dataclass methods may *call* `tg`, but they do not
*construct* batches. That responsibility belongs to `sender.post_batch`.

### L3 — Backwards-compatible state migration belongs at the boundary

`SinglePin.read_batch` tolerates both `{"msg_id": int}` and `{"msg_ids":
[int]}`. `write_batch` always emits the current shape and drops legacy
keys. Migration is implicit: the first successful write upgrades the slot.

Read-permissively, write-strictly. No one-shot migration scripts needed.

### L4 — A shared mock fixture beats per-module patching

When a refactor moves Telegram calls from one module to several, every
existing test that patched the old module's `tg` ref breaks. A `tg_mock`
fixture that patches all relevant module namespaces with one shared
`MagicMock` lets tests stay agnostic about which module makes the call.
Diffs to test files become small and mechanical: drop the `with patch(…)`
block, accept `tg_mock` as a fixture arg.

### L5 — Abstractions should not own fields they didn't create

`caught_up_msg_id` is `topic_queue_poster.py`'s concern, not `SinglePin`'s.
The temptation was to add it to `SinglePin.empty_slot()` and have
`SinglePin.clear()` preserve it, but that bleeds an unrelated concern
into the abstraction. The cleaner split: `SinglePin` only touches keys
it knows about (`msg_ids`, `fingerprint`, `last_posted_at`, plus the
legacy `msg_id`). Other slot keys persist naturally because no method
touches them.

A test in `test_posting_single_pin.py::TestClear::test_preserves_caught_up_msg_id`
locks this property in.

### L6 — MCP-flake recovery: keep file content reproducible from chat

When the local Windows-MCP server hung mid-write, the file dropped was
recoverable for free because (a) every file's content was already in chat
history, (b) `Filesystem:list_directory` revealed the missing file, and
(c) when `edit_file` can't create new files, push via the GitHub Contents
API works as a fallback. Prefer many small writes over one big one to
minimise the blast radius of a hang.

## What's next (out of scope here)

- 11 test files violate the 200-line rule. Most of them
  (`test_branch_gaps`, `test_close_gaps`, `test_final_*`, `test_remaining_*`,
  `test_zero_coverage`) have names suggesting they exist purely to seed
  coverage %. `test_checker.py` alone is **5,257 lines**. Worth a focused
  cleanup pass.
- Test code is **57% of all Python** in the repo (19,055 lines vs 14,190
  production). Some of that is healthy belt-and-braces, much of it is
  duplicated coverage seeding.
- The state layer is still a candidate for extraction (`live.json`,
  `queue.json`, `queues/{pid}.json`, partitions registered in `state.py`).
  Higher leverage but more invasive than this refactor.

---

# Phase 2 — `test_checker.py` split

Started May 9, 2026. The previous phase left `test_checker.py` at
**5,257 lines** as the largest 200-line-rule violator. This phase
extracts it into themed sibling files using a programmatic AST-based
split — no hand-edits per function, no risk of misplacing decorators.

## Approach

1. Parse `test_checker.py` with `ast.parse`.
2. Group functions by their `test_<command>_…` prefix.
3. Bundle related prefixes into themed buckets (combat = `test_combat_*`
   plus `test_hp_*`, `test_dc_*`, `test_roll_*`, etc.).
4. For each bucket bigger than ~160 body lines, split into `_a`/`_b`/...
   sibling files.
5. Move shared helpers (`_utc`, `_reset`, `_make_config`, `_make_state`,
   `_make_msg`, `_run_all`) plus the module-level `_LOGS_DIR` redirection
   setup into `_test_checker_helpers.py`. Each sub-file imports from it.
   Python's import-once-per-process semantics guarantee the tempdir setup
   runs exactly once regardless of which test file pytest collects first.

## Progress

### `475883c7` — Phase 2.1: format / milestone / check / process / build / transcript

- `_test_checker_helpers.py` — 114 lines, the new shared setup module
- 11 themed sub-files, all under 200 lines
- `test_checker.py`: 5,257 → 3,304 lines (37% reduction)
- All 301 tests preserved (verified by name diff)
- CI green

### `<this commit>` — Phase 2.2: combat / session / profile / roster

- 14 themed sub-files, all under 200 lines
- `test_checker.py`: 3,304 → ~1,425 lines (further 57% reduction)
- All 225 remaining tests preserved
- `test_checker.py` is still over the 200-line cap; the rest of its
  tests (parse, vote/pin, note, timer/loot, quest/clock, plus a long
  tail of one-test-per-prefix groups) will be extracted in phase 2.3.

## Learnings (phase 2)

### L7 — AST-based splits beat hand-editing for big files

`test_checker.py` had 307 top-level definitions and was completely flat
(no classes). Splitting it by hand would take hours and risk losing
decorators or interleaving test fixtures wrong. Doing it via
`ast.parse` + `node.lineno` + `node.end_lineno` is precise: each test
function (and its decorators, via `node.decorator_list[0].lineno`) is
extracted as a contiguous source range and pasted into a sub-file. The
only manual judgment is the *grouping*; everything else is mechanical.

### L8 — Two-pass split with line target works better than one-shot

First attempt with `target=175` body lines produced two files at 210
and 219 lines (just over the cap) because individual long tests pushed
buckets just past the limit. Second attempt with `target=160` (leaves
~40 lines of breathing room for the per-file header + decorators)
produced all files ≤200 lines. The right answer is to pick a target
that gives ~20% headroom over your real line cap.

### L9 — `if __name__ == "__main__"` blocks need explicit handling

The original file ended with `if __name__ == "__main__": sys.exit(_run_all())`
for standalone runs. AST splitting that only pulls function definitions
silently drops this. Fine for our case (we use pytest), but worth
checking if the tail block does anything load-bearing before discarding.

### `<phase 2.3>` — parse / vote+pin / note / timer+loot / quest+clock / activity / chat / misc

Final extraction phase. The remaining 99 tests in `test_checker.py`
move to 10 themed sibling files. After this commit `test_checker.py`
holds only the 13-line module-level header.

New files (all <200 lines):
  test_checker_parse.py        23 tests  parse, validate, sanitize, feature, cleanup
  test_checker_vote_pin.py      9 tests  vote, endvote, showvote, pin, pins, delpin
  test_checker_note.py          8 tests  note, notes, delnote
  test_checker_timer_loot.py   11 tests  timer, expire, loot
  test_checker_quest_clock.py  13 tests  quest, quests, clog, clock
  test_checker_activity.py      7 tests  activity, streak
  test_checker_chat_a.py       10 tests  conversation, post, gm
  test_checker_chat_b.py        4 tests  write, word, append
  test_checker_misc_a.py       12 tests  pace, handle, pick, calc, overview, summary, get
  test_checker_misc_b.py        2 tests  next, character

`test_checker.py`: 1,425 → 13 lines.

## End state

- 35 themed sibling files, all under the 200-line cap
- `_test_checker_helpers.py` (114 lines) provides imports, helpers, and
  the `_LOGS_DIR` redirection setup, imported by every sub-file
- All **301 tests** preserved through every phase (verified by name diff
  on each commit)
- The 5,257-line monolith is fully decomposed into 35 files
  averaging ~140 lines each — easier to find tests, faster pytest
  collection, and 200-line-rule compliant for the first time

## Learnings (phase 2 cumulative)

### L10 — Greedy bin-packing with rebalance pass

A naive "fill until target, then start new bin" pass leaves the last
bin small (e.g. one test of 23 lines as a separate file). A second
rebalance pass that merges any tail bin under 50 lines into the
previous bin (when the merged result fits within `cap + small_margin`)
eliminates the wastefully-tiny files without exceeding the line limit.
Two passes, both O(n), good enough for this kind of split.

### L11 — Module-level setup runs once even with N importers

`_test_checker_helpers.py` does `checker._LOGS_DIR = Path(_test_log_dir)`
at module top level. Python imports each module exactly once per
process; pytest discovers many sub-files but each one's
`from _test_checker_helpers import …` resolves to the same already-
imported module. The tempdir is created once and every sub-file's
tests share it. No fixture needed, no setup duplication, no test
ordering risk. The shared module IS the fixture.

## Next opportunities (out of scope for the test_checker.py split)

- 14 other test files still violate the 200-line rule (`test_branch_gaps`,
  `test_close_gaps`, `test_final_*`, `test_remaining_*`, `test_zero_coverage`,
  etc.) — names suggest coverage-seeding rather than feature tests.
  Worth a focused review pass to see how much can be deleted as
  duplicate of the now-themed feature tests.
- The state layer remains a candidate for extraction (live.json,
  queue.json, queues/{pid}.json, partitions registered in state.py).
  Higher leverage than test cleanup but more invasive.

---

# Phase 3 — `test_branch_gaps.py` split

`test_branch_gaps.py` was 1,477 lines — second-largest 200-line-rule
violator after `test_checker.py`. Header read: *"Targeted tests for
every remaining coverage gap. Organised by file, hitting each
uncovered branch."* — explicitly a coverage-driven file rather than
a behavioural one. The 100% coverage rule means we can't delete it,
but the 200-line rule means it can't stay monolithic either.

## Approach

Same AST-based machinery as phase 2, with one twist: this file
already has section comments (`# ─── module/file.py: branch ───`)
that group tests by the production module they exercise. Those
comments make ideal split boundaries, so the splitter walks
`# ───`-prefixed lines and groups adjacent sections into bins of
≤140 body lines.

One section ("Various single-line branches") is 492 lines on its
own — bigger than the cap. The splitter detects oversized sections
and falls back to internal AST-based test-by-test packing for those.

## Result

- 13 numbered themed sub-files (`test_branch_gaps_01_dispatch_cmd_gm.py`
  through `test_branch_gaps_13_dispatch_poll_notify.py`), all <200 lines
- `test_branch_gaps.py` reduced from 1,477 to 11 lines (just a stub
  preserving the module name in case any tooling references it)
- All 107 tests preserved (verified by name diff)
- The 31 section headers from the original file are quoted in each
  sub-file's docstring as a manifest of which production branches
  it covers

## Learning (phase 3)

### L12 — Existing comment structure is the cheapest split signal

`test_checker.py` had no section comments — the splitter had to infer
groups from `test_<command>_*` name prefixes. `test_branch_gaps.py`
was easier because the developer had already written
`# ─── module/file.py: branch ───` header lines. Treating those as
authoritative bin boundaries (and only falling back to AST splitting
when a single section overflows the cap) produces files whose
contents map 1:1 to a production module — much easier to find than
prefix-based grouping.

Worth checking other coverage-seed files (`test_close_gaps`,
`test_final_*`, `test_remaining_*`, `test_zero_coverage`) for the
same pattern before designing splitters for them.

---

# Phase 4 — three more coverage-seed files

`test_final_push.py` (790), `test_remaining_gaps.py` (738), and
`test_aaa_isolated.py` (679) all used the same `# ── module ──`
section header pattern as `test_branch_gaps.py`. The phase 3 splitter
applied directly with one tweak: the regex needed to be lenient about
the number of dashes (`# [─━]+` instead of `# [─━]{3,}`) — those files
use `# ── ` (two dashes) where `test_branch_gaps.py` used `# ─── `
(three).

  test_final_push:    790 -> 11 lines + 6 sub-files (57 tests)
  test_remaining_gaps:738 -> 11 lines + 6 sub-files (50 tests)
  test_aaa_isolated:  679 -> 11 lines + 6 sub-files (51 tests)

158 tests preserved. Committed as `5342a1f1`.

# Phase 5 — two more

`test_remaining_100.py` (650) and `test_final_100.py` (538) — same
splitter, same pattern.

  test_remaining_100: 650 -> 11 lines + 5 sub-files (51 tests)
  test_final_100:     538 -> 11 lines + 4 sub-files (40 tests)

91 tests preserved. Committed as `3edf62c7`.

# End-of-session totals

Started this session at 22 files >200 lines.

After phases 1-5:
  - 5 production files in posting/ package (new abstraction)
  - 35 sub-files of test_checker.py decomposition
  - 13 sub-files of test_branch_gaps.py
  - 6 + 6 + 6 sub-files of phase 4 files
  - 5 + 4 sub-files of phase 5 files
  - 11 stub files preserving original module names

Files >200 lines remaining: 12 (down from 22).

Of those 12 remaining violators:
  - 5 are coverage-seed files without section headers (need an
    AST-based splitter that groups by tested-module imports)
  - 7 are regular test files for production behaviour (test_helpers,
    test_roster, test_telegram, etc.) — could split by feature

The non-section-header coverage files (test_final_coverage,
test_close_gaps, test_zero_coverage, test_final_gaps,
test_commands_coverage, test_scheduled_coverage,
test_utility_coverage, test_dispatch_coverage, test_push_to_100)
will need a different splitter that detects production-module imports
and groups tests by which module they exercise. Quick sketch:
  1. AST-walk every test function
  2. For each test, find the FIRST production-package import (via
     `import production.x` or `from production.x import y`)
  3. Group tests by that import path; bin into ≤140-line chunks
This pattern works because the coverage-seed convention is one test
per branch, and each test's first import is the file whose branch it
covers.

# Cumulative learnings

Across phases 1-5, the 200-line refactor produced 12 new principles
worth keeping (L1-L12 in the sections above). The pattern that saved
the most time was: detect existing structure (section comments, name
prefixes, file imports) and let it drive the split, rather than
imposing a new structure on top.

---

# 🎉 COMPLETE — 200-line rule satisfied across the entire repo
After phases 1-9 across two sessions:

- **0 files >200 lines** (down from 22 at the start)
- **310 Python files** (up from 165 — a +145 sub-files net new from splits)
- **35,949 lines total** (was 33,245; +2,704 from new doc/header overhead
  in sub-files, no test code lost)
- All test counts preserved through every phase (verified by name diff
  on every commit)

# Phase 6-9 splits (this session)

  test_final_coverage:    762 -> 7 sub-files (65 tests)
  test_zero_coverage:     567 -> 5 sub-files (52 tests)
  test_commands_coverage: 447 -> 5 sub-files (44 tests)
  test_scheduled_coverage:443 -> 4 sub-files (45 tests)
  test_utility_coverage:  431 -> 5 sub-files (46 tests)
  test_dispatch_coverage: 628 -> 5 sub-files (49 tests)
  test_push_to_100:       374 -> 4 sub-files (41 tests)
  test_close_gaps:        512 -> 3 sub-files (44 tests)
  test_final_gaps:        452 -> 3 sub-files (37 tests)
  test_helpers:           385 -> 4 sub-files (37 tests)
  test_import_history:    334 -> 3 sub-files (18 tests)
  test_roster:            329 -> 5 sub-files (24 tests)
  test_new_features:      274 -> 2 sub-files (16 tests)
  test_telegram:          262 -> 2 sub-files (39 tests)
  test_potw_streaks:      254 -> 3 sub-files (33 tests)

# Splitter taxonomy — three patterns, one toolchain

The full refactor used three distinct splitter strategies, all built on
the same AST-walking + line-range extraction core:

### Strategy A — Section-marker splitting (phases 3-7)
For files with explicit `# ── module/file.py: branch ──` or `# ═══`
section comments. Treat each marker line as a bin boundary; pack
adjacent sections greedily until the bin hits the line target. For
sections larger than the target, fall back to internal AST-test
packing.

Used for: `test_branch_gaps`, `test_final_push`, `test_remaining_gaps`,
`test_aaa_isolated`, `test_remaining_100`, `test_final_100`,
`test_final_coverage`, `test_zero_coverage`, `test_commands_coverage`,
`test_scheduled_coverage`, `test_utility_coverage`,
`test_dispatch_coverage`, `test_push_to_100`, `test_roster`,
`test_potw_streaks`.

### Strategy B — Import-based splitting (phase 8)
For files with no section markers but where every test opens with
`from <production.module> import <name>`. Walk each test's body, find
the first import whose top-level package is a production package, and
group tests by that module path.

Used for: `test_close_gaps`, `test_final_gaps`, `test_helpers`,
`test_import_history`, `test_new_features`, `test_telegram`.

### Strategy C — Prefix-based splitting (phase 2)
For files whose tests follow a `test_<command>_*` naming convention.
Group by command prefix, then bundle related commands into themed
buckets.

Used for: `test_checker.py` (35 sub-files).

A "multi-strategy" splitter (`_generic_splitter.py`) ships in this
repo's staging area for any future test-file growth that re-violates
the 200-line cap.

# Cumulative learnings

L1. Mock patches are coupled to implementation, not behaviour.
L2. Dataclass + side-effecting method is fine for thin HTTP wrappers.
L3. Backwards-compatible state migration belongs at the read boundary.
L4. A shared mock fixture beats per-module patching across refactors.
L5. Abstractions should not own fields they didn't create.
L6. MCP-flake recovery: keep file content reproducible from chat.
L7. AST-based splits beat hand-editing for big files.
L8. Two-pass split with line target + rebalance pass beats one-shot.
L9. `if __name__ == "__main__"` blocks need explicit handling.
L10. Greedy bin-packing with rebalance pass for clean tail bins.
L11. Module-level setup runs once even with N importers.
L12. Existing comment structure is the cheapest split signal.
L13. Section-marker style varies (`#─`, `#━`, `#═`) — pattern-match
     all box-drawing characters, not just one.
L14. When no section markers exist, the first production-module import
     in each test body is reliable as a grouping key.

# What's next (truly out of scope now)

The 200-line refactor is complete. Future work that came up during
this effort but isn't yet done:

- **Test consolidation pass.** Many of the coverage-seed sub-files
  test the same production paths as the proper feature tests. A
  follow-up pass could review each `test_*_NN_<topic>.py` file
  against its corresponding `test_<feature>.py` and delete
  duplicates.
- **State layer extraction.** `live.json`, `queue.json`,
  `queues/{pid}.json`, `partitions` registered in `state.py` could be
  encapsulated behind a `StateStore` abstraction. High leverage for
  future schema changes; invasive.
- **Race condition strategy.** The workflow concurrency `pbp-checker`
  group + `cancel-in-progress: false` queues runs but a true
  simultaneous start could still race on git-state writes. Real fix:
  design idempotent posts or use Telegram pinned-message as source of
  truth.

---

# Post-incident addendum (2026-05-09)

Two more commits landed after the original phase-1-9 sequence:

* `9281af8` `fix: re-split phase 3-7 files preserving helpers, preambles, constants`
  Re-ran the splitter on the 13 phase-3-7 originals after Lewis noticed
  75 NameErrors locally. Three classes of bug were preserving:
  module-level helpers, section preambles for AST-split sections, and
  cross-section helpers/constants. `test_splitter.py` (now in
  `tools/`) encodes all three fixes; see its docstring for the
  defect log.

* `9dc40a5` `feat(safety): bot refuses to delete messages it didn't send`
  Triggered by the 2026-05-08 purge-script incident where 224 message
  IDs were swept blindly, deleting ~200 player and GM messages along
  with the intended bot pins. The safeguard adds a registry of every
  ID the bot has sent (`posting/bot_sent_registry.py`) and a
  guarded delete path (`posting/safe_delete.py`) that `telegram.
  delete_message` now delegates to. No bypass, no force flag. See
  `docs/dev/ROADMAP.md` P1/4 for the docs follow-up.

The `tools/test_splitter.py` file is the canonical splitter for
future test-file cleanup. Run from `tools/` after `git show
<pre-split-sha>:scripts/<file>.py > _<file>_full.py`.

---

## P3/9 StateStore migration ‒ complete (2026-05-10)

8-slice refactor consolidating every data/state/ file under one
class with atomic writes, schema-completeness checking, central
migration registry, and per-resource locking. Single session.

### Slices delivered

| Slice | Description | Commit | Key file |
|-------|-------------|--------|----------|
| 1 | StateStore shell + bot_sent_ids migration | (earlier) | scripts/state_store/store.py |
| 2 | refusal_log migration | (earlier) | scripts/posting/refusal_log.py |
| 3 | Partition reads (load_partition) | (earlier) | scripts/state_store/store.py |
| 4 | Partition writes atomic (save_partition tmp+rename) | `95692a2` | scripts/state_store/store.py |
| 5 | Queue partitions (per-campaign queues/{pid}.json) | `d7d3bde` | scripts/state_store/queue_api.py |
| 6 | Schema-completeness regression test | `0deb102` | scripts/state_store/schema.py + test_state_schema.py |
| 7 | Migration registry | `20f6a17` | scripts/state_store/migration_registry.py |
| 8 | Per-resource locking primitives | `3bd1ca8` | scripts/state_store/locks.py + partition_api.py |

### Adjacent fixes shipped same session

- `89bfbb5`/`2807893` — `_post` soft-success semantics. Telegram returning "message to delete not found" / "MESSAGE_ID_INVALID" / similar was being treated as a real failure by `safe_delete.perform_guarded_delete` and `unpin_message`, blocking eviction state from advancing. Fix routed those responses to `return True` while real failures still `return None`. Verified working in production: queue #343 deleted when #344 posted (Lewis's 14:41 confirmation).
- `5f9e70e` — `MAX_KEPT_BATCHES = 1` in `scripts/scheduled/gm_queue_history.py` (was 3). UX preference; matches per-topic queue UX (single pinned message per thread). Verified live in chat.
- `83a321a` — `config.json` C04 campaign display name typo: "Magni Watch" → "Magni Guard".

### Tests

1664 passing (was 1641 pre-session — net +23). 0 warnings. Every
file under the 200-line cap.

### Learnings (P3/9)

#### L13 — Soft-success ≠ safety relaxation

The `_post` fix changed how Telegram's "already deleted" responses
are interpreted, but it sits **downstream** of
`posting.bot_sent_registry.is_bot_sent`. The registry remains the
gatekeeper for which message IDs are even attempted. The fix changes
how the *result* is interpreted, not which IDs are touched. The
2026-05-08 incident's "don't delete non-bot messages" invariant is
fully preserved.

Documented in `docs/dev/delete-safety.md` so future maintainers
don't read the soft-success change as a softening of the safeguard.

#### L14 — Cap-1 is multi-message-queue safe

When a queue overflows Telegram's 4096-char limit it sends as
multiple chunks; `MessageBatch.msg_ids` is the list of every chunk.
Eviction routes through `MessageBatch.delete_all` which iterates
the list. So cap=1 evicting a 3-chunk batch produces 3
`delete_message` calls, all safeguard-gated. The cap is in batches,
not individual messages.

#### L15 — Strategy doc drift documented, not retro-fixed

`concurrency-strategy.md` originally specified Option A as
`filelock`-based. Slice 8 shipped `threading.Lock`. The
deviation was made visible in the strategy doc (\"What slice 8
actually landed\" section) rather than retroactively implementing
`filelock` for failure modes that don't apply to this deployment
(F1 = different machines, shared FS — irrelevant on isolated CI VMs).

Rule: when implementation diverges from a design doc, update the
design doc to reflect reality + rationale. Don't bend code to match
a doc whose assumptions no longer hold.

#### L16 — Schema-completeness needs a registry, not a directory walk

Slice 6's first instinct was \"walk `data/state/` and assert every
file has a known reader by inspection.\" That couples the test to
production state and is flaky (CI commits change the dir contents).
Better shape: a declarative registry (`state_store/schema.py`)
that documents every expected file, then the test asserts the
on-disk dir is a subset of the registry. The registry becomes the
single source of truth; the test enforces agreement.

Side benefit: `manifest.json` from the 2026-04 migration is now
explicitly documented as `WRITE_ONCE` rather than a confusing
orphan with no reader.

#### L17 — Mixin extraction is the right reflex when a class hits the line cap

`store.py` hit 200 lines exactly during slice 7. Slice 8 needed
+12 lines (lock init + save_partition lock wrap). Two extraction
patterns considered:
1. Move partition methods to a sibling file as a mixin (chose this).
2. Compress the existing class docstring (rejected — lossy).

The mixin pattern (already used for QueueAPI in slice 5) keeps the
class diagram clean: `StateStore(QueueAPI, PartitionAPI)` makes
the method-group composition self-documenting. Each mixin sits in
its own file with its own scope-specific docstring. The 200-line
rule isn't a code-smell signal here; it's a forcing function for
better module decomposition.

#### L18 — PowerShell text manipulation has gotchas, prefer Python on Windows

During slice 6/7 file fixups, `[System.IO.File]::ReadAllText` on
several paths returned 0-byte content while `Get-Content -Raw` on
the same path read fine. The discrepancy wasted ~10 min of debug
time. Workaround: write a small Python script and invoke via
`python -X utf8 -c '...'` for any non-trivial string surgery on
Windows files. Python's `Path.read_text(encoding=\"utf-8\")`
behaves identically to `Get-Content -Raw` and avoids the .NET
quirk.

(Possibly relates to file locking by the IDE; not investigated
further. The Python escape hatch is reliable enough that it's not
worth deeper diagnosis.)

#### L19 — `read_only` lock test patterns

The slice-8 concurrent-save test uses a counter-based critical-
section check rather than wall-clock timing:

`python
in_critical = [0]
max_seen = [0]

def saver():
    for _ in range(20):
        with store._locks.held("aux:counter"):
            in_critical[0] += 1
            max_seen[0] = max(max_seen[0], in_critical[0])
            time.sleep(0.001)  # widen race window
            in_critical[0] -= 1
`

If serialisation works, `max_seen` is always 1 (only one thread
in the critical section at a time). If the lock is broken,
`max_seen` will be 2. Deterministic, no timing flakiness, no
`threading.Event` choreography needed.

#### L20 — Ask before "fixing" intentional design (the permanent-roster lesson)

On 2026-05-10 evening, Lewis asked whether the campaign roster
numbers were right — "it feels less active than that." The
`_active_players` function in `scripts/commands/roster.py` counts
permanent players regardless of when they last posted (no recency
check). Claude jumped straight to "this is the over-counting bug,
let me fix it" and drafted a remediation plan.

Lewis pushed back: **permanent players are SUPPOSED to be counted.**
The `permanent` flag (set via `/setpermanent`) marks someone as a
full member of the campaign regardless of activity — long-term
players, GMs-as-players who post sporadically, anyone who wants to
stay enrolled across dormant stretches. The same flag also
suppresses the week-3 auto-removal ping; together they implement
"this person is a member full stop; don't measure them, don't kick
them." The bypass in `_active_players` is the roster-count side of
that same contract.

Claude's mistake wasn't writing wrong code (no code change was
made) — it was the *framing*. "I found the over-counting bug"
biases the user toward agreement; "this counts permanent players
bypassing the recency check — is that intentional?" leaves room
for the right answer. Lewis caught it before any damage. Two
follow-up actions taken:

1. Documented the design intent verbosely in `_active_players`'s
   docstring + inline comment so the next Claude session (or any
   other reader) sees the rationale before considering changes.
2. Recorded the lesson here.

**Rule of thumb for future sessions:** when a piece of code looks
like a bug but its existence is plausibly load-bearing, ask before
proposing the fix. Surprising code in a working system is more
often intentional than not. The cost of asking is one extra
round-trip; the cost of "fixing" something that was intentional is
broken behaviour the user has to chase down later. Especially for
code that interacts with user-visible commands (`/setpermanent` in
this case) where the contract is established and the bypass
implements that contract.

#### L21 — Concurrency groups don't help if checkout pins to GITHUB_SHA

On 2026-05-11 evening Lewis spotted the GM queue posting #360 twice
at 19:57 UTC, and shortly after that the per-topic queue doing the
same thing. The diagnosis took a couple of false starts before the
actual root cause emerged from the parent chain of state commits.

The workflow has a `concurrency: pbp-checker, cancel-in-progress:
false` clause, which correctly serialises workflow runs in this
group. That's not the problem. The problem is the checkout step:

```yaml
- uses: actions/checkout@v6
```

With no `ref:` specified, `actions/checkout@v6` defaults to the
**triggering SHA** (`GITHUB_SHA`), NOT main HEAD. So even though
Run B was queued behind Run A and waited for Run A to finish,
when Run B finally started it checked out the SHA that triggered
it — a SHA that predates Run A's state push.

The sequence:

1. Lewis pushed two commits 32s apart at 19:56:47 and 19:57:25.
2. Run A (triggered by the first push) ran, posted #360 with
   msg_id X, updated state to count=360 + pin=X, committed,
   tried to push.
3. **Run A's push failed non-fast-forward** because origin/main
   had already moved to Lewis's second push (19:57:25). The
   workflow's `git push || echo "Nothing to push"` swallowed the
   error silently. Run A's state update + bot_sent_registry entry
   for msg X were both lost.
4. Run B (queued behind Run A by the concurrency group) started
   after Run A finished. Checkout pinned to Run B's trigger SHA,
   which doesn't include any state commits. Run B read the same
   stale state Run A had read (count=359, pin=152615).
5. Run B posted #360 again with msg_id 152643, evicted the long-
   gone 152615 (soft-success thanks to the recent `_post` change),
   committed, pushed — succeeded this time because no other run
   was racing.

Result: two `#360` messages visible in Telegram; one orphaned
(msg X) with no entry in `gm_queue_history` and no entry in
`bot_sent_registry` — it can never be auto-evicted, can't even be
deleted via `tg.delete_message` because the registry safeguard
would refuse it. The per-topic queue had the same shape of bug
for the same reason; both code paths use the same
read-state → side-effect → write-state → push pattern, both were
broken by the same root cause.

**The fix (applied in this commit) has two parts, both in the
workflow:**

1. **`ref: main`** on the run-job's `actions/checkout`. After the
   concurrency-group wait, this picks up whatever's at main HEAD
   (including any state push from the previous run in the group),
   not the pinned trigger SHA. Run B's fingerprint check then
   trips and Run B skips the duplicate post.
2. **Retry-with-rebase on `git push`.** Replaced
   `git push || echo "Nothing to push"` with a 5-attempt loop
   that does `git pull --rebase origin main` between failures.
   If all 5 attempts fail the job fails loudly instead of
   silently losing state.

**Why this matters beyond the GM queue:** Lewis correctly flagged
that this isn't a GM-queue-specific issue. Every code path that
follows the "read state → do something with side effects → write
state → push" pattern was vulnerable to the same race. The fix
is at the workflow layer because the root cause is at the workflow
layer; fixing it once covers per-topic queues, recruitment alerts,
weekly campaign tables, anything else that mutates state and has
an external side effect.

**What didn't work in the diagnosis:** initial hypothesis was
"two runs ran in parallel" — disproved by the workflow's
concurrency clause. Second hypothesis was "the bot's `[skip ci]`
commit messages somehow re-triggered" — disproved by checking
`paths-ignore`. Third (correct) was found by reading the parent
chain of state commits: `git log --format='%h %p %ad %s'` between
the relevant SHAs showed only ONE state commit between the two
pushes, proving Run A's state push was lost. The lesson here is
that **the git history is the source of truth for what actually
happened** when reasoning about CI races — not run-log output,
not the bot's print statements.

The orphan from this incident (msg X in the bot topic, between
msg_ids 152615 and 152643, posted by PathWarsNudge but not in
any batch and not in bot_sent_registry) is Lewis's to clean up
manually. Anthropic-side rule: Claude must never delete orphans
or perform any chat-cleanup action on Lewis's behalf. The bot's
safeguards exist precisely to prevent automated cleanup that
bypasses tracked state; respecting them is the whole point.

#### L22 — Removing a user-facing command is wider than the handler

On 2026-05-11 Lewis asked to retire the `/chooseboon` command and
the inline buttons on the POTW announcement, moving boon selection
entirely to the website. The naive scope of that work is "delete
the handler"; the actual scope was nine production files and two
test files, because `/chooseboon` had grown tendrils into every
layer of the dispatch and parsing pipeline. Cataloguing them was
the most important step of the change:

1. **Generation** — `scripts/scheduled/potw.py` constructed the
   POTW message with both inline buttons and a `/chooseboon` text
   reference. Both had to go from the message body and the
   button-construction array had to be removed. The send call
   changed from `send_message_with_buttons` to `send_message_id`.
2. **Three text-command handlers** — `dispatch/cmd_player.py`,
   `dispatch/bot_topic.py`, and `dispatch/router.py` each had
   their own `/chooseboon` branch (one per dispatch context).
   Forgetting any one would leave a stealth code path that still
   processed the command.
3. **Callback handler** — `dispatch/router.py`'s callback_query
   block dispatched `boon:` callbacks to `process_boon_callback`.
   Removing only the text-command branch would leave the inline
   buttons working from chat history.
4. **Reminder messages** — `boons/reminders.py` had three
   escalating reminder messages (24h / 3d / 6d) that all told
   players to use `/chooseboon`. Updating only the POTW message
   would have left the reminders contradicting the new flow.
5. **Help text** — `dispatch/help_text.py` listed `/chooseboon`
   in the help blob shown by `/help` and `/commands`.
6. **Command registration** — `set_commands.py` registered
   `/chooseboon` with Telegram so it appeared in the bot's
   slash-command suggestion list.
7. **Parser special-case** — `parsing/message.py` had a
   `/chooseboon`-specific bypass that allowed the command from
   the main group chat (no thread_id) by setting a sentinel pid.
   The sentinel logic propagated through later checks.
8. **Imports** — `dispatch/cmd_player.py` and `dispatch/router.py`
   each imported the now-unused helper (`choose_boon_by_text` and
   `process_boon_callback` respectively). Leaving the imports in
   place wouldn't break anything but would make the eventual
   cleanup harder.
9. **Tests** — two tests (`test_chooseboon_executes` and
   `test_process_updates_boon_callback`) failed loudly once the
   handlers were gone, which actually served as a checksum: the
   test names confirmed I'd reached the right code paths.

What NOT to do (deliberately left in place): the internal helper
functions `choose_boon_by_text` and `process_boon_callback` in
`boons/handler.py` remain, along with their exports from
`boons/__init__.py` and tests in several `test_*.py` files. They
are now dead code in production but their tests continue to pass.
Removing them would balloon scope into a multi-file test cleanup
for functions that may be reintroduced later (e.g. if the website
has downtime and a chat-side fallback becomes useful). Future
work can excise the dead branches once the website flow has
proven stable for a few weeks.

**The lesson:** when removing a user-facing command, search for
every touch point before opening the editor. The handler is
rarely the whole story — commands tend to accumulate help-text
lines, registration entries, reminder mentions, parser special-
cases, and multi-dispatch branches. A focused early
`grep -rn '/command'` across `scripts/` plus a second pass on
`grep -rn 'helper_func'` for the underlying implementation
identifies the full surface before any code change. Skipping
that catalogue produces ghost code paths that still kick in
for users who hit them, which is the worst kind of deprecation
bug — silent retention of behaviour the changelog claims is gone.
