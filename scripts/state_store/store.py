"""StateStore class \u2014 slice 1: aux-file load/save with atomic writes.

The class lives here; the package ``__init__.py`` re-exports it.

Slice 1 scope (delivered):
  * Atomic writes (tmp + rename) on every ``save_aux``.
  * Single configurable root (default: ``<repo_root>/data/state``).
  * Test isolation via constructor parameter \u2014 no module-level
    monkeypatch dance.
  * Graceful handling of missing/corrupt aux files (returns the
    caller-supplied default rather than raising).

Slice 1 NON-scope (planned for later slices):
  * ``load_partition`` / ``save_partition`` \u2014 slice 3-4.
  * ``load_queue`` / ``save_queue`` \u2014 slice 5.
  * Migration registry \u2014 slice 7.
  * Per-partition locks for concurrency \u2014 slice 8 (P3/10).

Usage::

    from state_store import StateStore

    store = StateStore()                       # production: data/state/
    store.save_aux(\"bot_sent_ids\", [1, 2, 3])
    ids = store.load_aux(\"bot_sent_ids\", default=[])

    test_store = StateStore(state_dir=tmp_path)  # tests: tmp dir
"""

import json
from pathlib import Path
from typing import Any


class StateStore:
    """Owns load/save of every file in ``data/state/``.

    The constructor takes an optional ``state_dir`` override; tests
    pass a ``tmp_path`` here so production state files are never
    touched. Production callers use the default, which resolves to
    ``<repo_root>/data/state``.
    """

    DEFAULT_STATE_DIR = (
        Path(__file__).resolve().parent.parent.parent
        / "data" / "state"
    )

    def __init__(self, state_dir: Path | None = None) -> None:
        self._state_dir = (
            Path(state_dir) if state_dir is not None
            else self.DEFAULT_STATE_DIR
        )

    @property
    def state_dir(self) -> Path:
        """The root directory this store reads/writes from.

        Exposed publicly so callers that need to walk siblings of an
        aux file (e.g. ``bot_sent_registry`` backfilling from
        ``live.json`` in the same directory) can do so without
        hard-coding paths. Slices 3-5 will replace those direct walks
        with ``load_partition`` / ``load_queue`` calls.
        """
        return self._state_dir

    def aux_path(self, name: str) -> Path:
        """Return the on-disk path for an auxiliary file by name.

        ``name`` is the bare stem (e.g. ``bot_sent_ids``); the
        ``.json`` extension is added here. Exposed publicly so a
        small number of legacy callers can still reference the
        path during the slice 1-2 migration window.
        """
        return self._state_dir / f"{name}.json"

    def load_aux(self, name: str, default: Any = None) -> Any:
        """Load an auxiliary JSON file by name.

        Returns the parsed JSON, or ``default`` if the file is
        missing or unparseable. A corrupt file produces a stderr
        message but does not raise \u2014 callers always get a usable
        value. This matches the contract that ``bot_sent_registry``
        and ``refusal_log`` already had with their direct-file I/O,
        so the migration is behaviour-preserving.
        """
        path = self.aux_path(name)
        if not path.exists():
            return default
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[state_store] Corrupt aux file {path} ({e}); "
                  f"returning default")
            return default

    def save_aux(self, name: str, data: Any) -> None:
        """Save data to an auxiliary JSON file atomically.

        Uses tmp + rename so a crash mid-write cannot leave a
        partially-written file. Creates the state directory if
        missing. Indents output for human-readability of state
        files committed to git.
        """
        path = self.aux_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        tmp.replace(path)

    def delete_aux(self, name: str) -> bool:
        """Delete an auxiliary JSON file.

        Returns True if the file existed and was removed; False if
        no file with that name was present. Exposed for tests and
        for cleanup hooks; production code typically just lets aux
        files persist across runs.
        """
        path = self.aux_path(name)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_aux(self) -> list[str]:
        """Return the bare stems of every ``.json`` file in the
        state directory (NOT recursing into ``queues/``).

        Useful for diagnostics and for the slice-6 schema-
        completeness test that walks every aux file and asserts
        someone reads it.
        """
        if not self._state_dir.exists():
            return []
        return sorted(p.stem for p in self._state_dir.glob("*.json"))

    # ------------------------------------------------------------------
    # Partition API (slice 3-4 of P3/9).
    #
    # Partition files are the five JSON files written by ``state.py``:
    # ``live`` / ``players`` / ``queue`` / ``activity`` / ``trackers``.
    # On disk they have the same shape as aux files — just bigger,
    # with multi-key dicts. Slice 3 adds the read side; slice 4 will
    # add ``save_partition`` with atomic-write semantics matching
    # ``save_aux`` so all partition writes become crash-safe.
    #
    # Why a separate API rather than re-using ``load_aux``: the two
    # have the same implementation today, but later slices add
    # partition-only concerns (migration registry in slice 7, schema
    # validation in slice 6+) that aux files don't need.
    # ------------------------------------------------------------------

    def partition_exists(self, name: str) -> bool:
        """Return True iff the partition file is present on disk."""
        return self.aux_path(name).exists()

    def load_partition(self, name: str) -> dict | None:
        """Load a partition file by name.

        Returns the parsed dict on success, or None if the file is
        missing or unparseable. Callers (e.g. ``state.py``) get to
        decide whether "missing" means "defaults" or "fall back to
        gist". Corrupt files are logged via the same path as
        ``load_aux`` (stderr message, no raise).
        """
        if not self.partition_exists(name):
            return None
        return self.load_aux(name, default=None)

    def save_partition(self, name: str, data: dict) -> None:
        """Save a partition file atomically.

        Slice 4 of P3/9: same atomic write semantics as ``save_aux``
        (tmp + rename), now applied to the five main partition files
        (``live`` / ``players`` / ``queue`` / ``activity`` /
        ``trackers``). Pre-slice-4 ``state.py:_save_to_files`` did
        ``path.write_text(json.dumps(...))`` per partition, so a
        crash between the open-write and the os flush could leave a
        half-written ``live.json`` that the next process startup
        couldn't parse. Routing through ``save_aux`` fixes this:
        the partial write happens to a ``.tmp`` sibling and the
        rename only goes through once the bytes are durable.

        Currently delegates to ``save_aux`` since they share the
        on-disk shape and write semantics. Slice 7 will add a
        migration-registry hook here that doesn't apply to aux files.
        """
        self.save_aux(name, data)
