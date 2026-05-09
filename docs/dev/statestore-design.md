## StateStore — design doc for ROADMAP P3/9

Status: **draft for review**. Implementation has not started; this doc
exists so the design can be argued with before any code is written.

---

### Why a design doc

State today works correctly but is structurally fragile. The fragility
hasn't bitten yet, but it's the same shape as the bugs that produced
the 2026-05-08 deletion incident: an invariant that's enforced by
convention rather than by code, in a place where any new caller can
forget the convention. Before extending the bot further (especially
into the P3/10 race-condition work), the state layer needs to land on
a shape that's hard to misuse.

---

### Current state — survey

Three things in this codebase get called "state":

**1. The merged-dict state.** `scripts/state.py` exposes `load() ->
dict` and `save(state)`. Internally it splits the dict across five
files in `data/state/`:

| Partition file       | Holds                                                  |
| -------------------- | ------------------------------------------------------ |
| `live.json`          | bot offset, topics, alert/post timestamps, gm queue, … (38 keys) |
| `players.json`       | players, removed_players, history, boons, characters, away |
| `queue.json`         | queue_history, queue_archive, pending_potw_boons       |
| `activity.json`      | post_timestamps, message_counts, hourly/daily activity, polls |
| `trackers.json`      | clocks, conditions, hp_tracker, loot, npcs, quests, … (in-game cmd state) |

The `PARTITIONS` map in `state.py` is the schema. Every key that
should persist must appear there or it gets dropped on save.
`DEFAULT_STATE` is a parallel dict of empty initial values — adding a
new key means editing both.

**2. Per-campaign queue files.** `data/state/queues/{pid}.json` —
one file per campaign (10 partitions today, ranging 6 KB to 366 KB).
These hold `topic_queues` (pinned-message tracking per thread),
`unreplied`/`replied` lists, `topic_msg_id`, etc. They're touched by
`scripts/posting/topic_queue_poster.py`,
`scripts/commands/queue_io.py`, and a handful of others. **They're
not handled by `state.py` at all** — separate ad-hoc reads/writes
scattered across the posting flow.

**3. Auxiliary files.** `data/state/bot_sent_ids.json` (the registry
from the safeguard work), `data/state/refusal_log.json`,
`data/state/refusal_log_alerted.json`. Each owned by its own module
with its own `_STATE_PATH`. No central registration. The test
isolation hook in `scripts/_test_state_isolation.py` knows about all
of them by name and has to be updated when a new one's added.

---

### Pain points

The survey makes the issues concrete:

**P1. Dual-write asymmetry (`state.py`).** `save()` writes the
five partition files and then calls `gist_save`. If files succeed
and gist fails, file state and gist state diverge silently. The
`_loaded_ok` guard prevents *some* mismatches but doesn't help here.

**P2. No atomic writes.** `_save_to_files` calls
`path.write_text(...)`. A crash or kill mid-write leaves a
half-written JSON file that fails to parse next load, triggering the
gist fallback. This is how `live.json` corruption has happened in
the past. The bot_sent_registry already does atomic writes via
tmp+rename — that pattern needs to be everywhere.

**P3. Schema-by-convention.** `PARTITIONS` is the source of truth
for "which keys go where", but no test enforces that every key
written by production code is also listed there. Add a new key to
`live.json`-shaped state without updating `PARTITIONS` and the key
silently disappears on save. We've spotted this twice in code review;
nothing prevents it.

**P4. Two parallel state systems.** `state.py` (merged dict) vs
`queues/{pid}.json` (per-campaign files) have different APIs,
different write contracts, different invariants. New work has to
learn both. Most state-related bugs are near the seam.

**P5. No concurrent-access protection.** `_save_to_files` blindly
overwrites. If two processes (e.g. a workflow_dispatch run and a
scheduled run that just started) both call `save()`, the later
finisher wins; everything the earlier finisher wrote is lost. Today
this is mitigated by `concurrency: pbp-checker, cancel-in-progress:
false` queueing runs serially, but that's a CI-config invariant, not
a code one. P3/10 (race conditions) needs this fixed at the code
level too.

**P6. No write isolation in tests.** Solved for the registry and
refusal log via `_test_state_isolation.py`. *Not* solved for
`state.py` or `queues/{pid}.json` — tests that exercise production
read/write paths can in principle clobber `data/state/*.json`. We
haven't seen it, but we're one importlib-bypass away.

---

### Proposed design — `StateStore`

Single typed abstraction over every persisted state file. Lives in
`scripts/posting/state_store.py` (or `scripts/state_store/`,
multi-file if needed for the 200-line cap). All reads/writes route
through it.

```python
class StateStore:
    """Owns every file in data/state/. Atomic writes, partition-aware,
    test-isolatable, lock-friendly. Replaces state.py + the ad-hoc
    queues/ accesses."""

    # Reading
    def load_partition(self, name: str) -> dict: ...
    def load_queue(self, pid: str) -> dict: ...
    def load_aux(self, name: str) -> dict | list | None: ...

    # Writing — all atomic, all journaled
    def save_partition(self, name: str, data: dict) -> None: ...
    def save_queue(self, pid: str, data: dict) -> None: ...
    def save_aux(self, name: str, data) -> None: ...

    # Migrations — declarative, run at first read of a partition
    def register_migration(self, partition: str, version: int,
                           fn: Callable[[dict], dict]) -> None: ...

    # Test hook
    @classmethod
    def for_tests(cls, root: Path) -> "StateStore": ...
```

Properties this gives us:

* **Atomic writes everywhere.** `save_*` always does
  `tmp.write + rename`. Partial writes are impossible.
* **Schema centralised.** `PARTITIONS` moves into `StateStore` as
  `_PARTITION_KEYS`. A test asserts every key written by production
  appears in some partition — solves P3.
* **Single test isolation point.** `for_tests(tmp_path)` replaces
  the conftest hook and the per-test `monkeypatch.setattr` rituals
  for registry/refusal-log. One pattern instead of three.
* **Migration registry.** Schema bumps stop being inline
  `_migrate_legacy` calls scattered across loaders. Each migration
  declares `(partition, from_version, to_version, fn)` once.
* **Lock-friendly.** `save_*` takes the partition lock for the
  duration of the write. P3/10 implementation gets this for free.
* **Auxiliary file colocation.** `bot_sent_ids.json`,
  `refusal_log.json`, `refusal_log_alerted.json` become
  `load_aux("bot_sent_ids")` — same atomic, same test isolation,
  same locking as everything else.

---

### Migration plan — vertical slices

Implementing the full design as one PR is hostile. Slice it instead.
Each slice is independently shippable, doesn't break tests, and
gives us a usable subset.

**Slice 1 — `StateStore` shell + `bot_sent_ids` migration.**
Stand up the class with `load_aux`/`save_aux` only. Migrate
`posting/bot_sent_registry.py` to use it. Tiny scope; proves the
shape works; replaces one of three ad-hoc state files.

**Slice 2 — refusal log migration.** Same pattern, second module.
After this, all auxiliary files are unified.

**Slice 3 — partitions read path.** Add `load_partition`. Have
`state.py:load()` delegate to it for reads. `state.py:save()` still
uses the old write path. Risk: zero — read-only change.

**Slice 4 — partitions write path with atomic writes.** Implement
`save_partition` with tmp+rename. Have `state.py:save()` delegate.
Now every partition write is atomic.

**Slice 5 — queue partitions.** Add `load_queue`/`save_queue`,
migrate `topic_queue_poster.py` and friends. After this, P4 is
gone — one state system, one API.

**Slice 6 — schema-completeness test.** Walk production code with
AST, find every `state[<literal>] =` and assert the key appears in
`_PARTITION_KEYS`. Lock in P3.

**Slice 7 — migration registry.** Move existing `_migrate_legacy`
calls into the registry. Pure refactor, no behaviour change.

**Slice 8 — locking primitives.** Per-partition `Lock` objects
held across save. Sets up P3/10 implementation.

Slices 1–3 can all land in one session each. Slices 4–8 are larger
and probably need two sessions each.

---

### Open questions for review

1. **`state.py` deprecation path.** Keep it as a thin facade over
   `StateStore` indefinitely (existing call sites stable, no
   coordinated rewrite needed)? Or rip it out on slice 4 and update
   every caller? I lean facade — the call sites are the documentation
   of intent. Removing them costs more than it saves.

2. **`queues/{pid}.json` schema.** The current shape is what
   `topic_queue_poster.py` happens to write. Lock the schema (declare
   it explicitly in `StateStore`) or keep it free-form? I lean
   declared — it's how P3 gets enforced.

3. **Migration semantics.** Run migrations at every load (cheap, but
   re-runs validation every hour) or persist a `_schema_version` per
   partition and only run on bump? I lean version field — it's worth
   the 5 lines.

4. **Gist backup contract.** `state.py` writes to gist on every save.
   Is that "always" desirable, or only on `live`/`players`/`queue`
   (the partitions worth backing up — `activity` is rebuildable from
   chat history, `trackers` is mostly cosmetic)? I lean partition-
   filtered — saves API quota and reduces gist file size.

5. **Where to put it.** `scripts/posting/state_store.py`?
   `scripts/state_store/` package? `scripts/persistence/`? The new
   home shouldn't be inside `posting/` because aux files like the
   registry conceptually aren't posting-related — but `posting/`
   already owns `bot_sent_registry`, so colocating is at least
   consistent with existing layout. Open.

---

### What this doc does NOT design

* **Schema validation.** Treated as a v2 concern. Today's "raw dict
  matching `PARTITIONS`" is good enough for slice 1; structured
  schemas (Pydantic models or dataclasses per partition) can come
  later if there's appetite.

* **Cross-partition transactions.** A real database would let you
  update `live` and `players` atomically. We don't. I think we don't
  need to — the existing flows update one partition at a time. If
  that turns out to be wrong, slice 9 adds a `WriteBatch` context
  manager.

* **Concurrency strategy.** That's P3/10 (`docs/dev/concurrency-
  strategy.md`). This doc only ensures the locking primitives needed
  by P3/10 have a place to live.

---

### Decision needed

Before slice 1, I need answers to questions 1, 2, and 5. Questions 3
and 4 can be defaulted (version field, partition-filtered gist) and
revisited if the defaults turn out wrong.
