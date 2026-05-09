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
