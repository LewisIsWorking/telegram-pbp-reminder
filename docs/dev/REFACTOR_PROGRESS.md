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
