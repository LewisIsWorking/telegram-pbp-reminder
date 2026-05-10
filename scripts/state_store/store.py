"""StateStore class — slice 1: aux-file load/save with atomic writes.

The class lives here; the package ``__init__.py`` re-exports it.

Slice 1 scope (delivered):
  * Atomic writes (tmp + rename) on every ``save_aux``.
  * Single configurable root (default: ``<repo_root>/data/state``).
  * Test isolation via constructor parameter — no module-level
    monkeypatch dance.
  * Graceful handling of missing/corrupt aux files (returns the
    caller-supplied default rather than raising).

Slice 1 NON-scope (planned for later slices):
  * ``load_partition`` / ``save_partition`` — slice 3-4.
  * ``load_queue`` / ``save_queue`` — slice 5.
  * Migration registry — slice 7.
  * Per-partition locks for concurrency — slice 8 (P3/10).

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

from .locks import LockRegistry
from .partition_api import PartitionAPI
from .queue_api import QueueAPI


class StateStore(QueueAPI, PartitionAPI):
    """Owns load/save of every file in ``data/state/``.

    Constructor takes an optional ``state_dir`` override; tests pass
    ``tmp_path`` so production state files are never touched.
    Production callers use the default ``<repo_root>/data/state``.

    Method groups (each group lives in a sibling mixin file):
      * Aux files (this file): ``load_aux`` / ``save_aux`` /
        ``delete_aux`` / ``list_aux``.
      * Partitions (see ``partition_api.py``): ``partition_exists``
        / ``load_partition`` / ``save_partition``.
      * Queues (see ``queue_api.py``): ``queue_path`` /
        ``queue_exists`` / ``load_queue`` / ``save_queue`` /
        ``list_queues``.

    Slice 8 of P3/9: every save_* method acquires a per-resource
    lock from ``self._locks`` for the duration of its tmp+rename
    write. Two concurrent saves to the same resource serialise;
    saves to different resources proceed in parallel. The lock
    registry is instance-scoped so test isolation isn't broken.
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
        # Slice 8 of P3/9: per-resource locks acquired during save_*.
        # Lock keys are namespaced (``aux:{name}`` / ``partition:{name}``
        # / ``queue:{pid}``) so an aux file and a partition with the
        # same bare name don't share a lock.
        self._locks = LockRegistry()

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
        message but does not raise — callers always get a usable
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
        files committed to git. Slice 8 of P3/9 added the
        ``aux:{name}`` lock so concurrent saves to the same aux
        file serialise; concurrent saves to different aux files
        proceed in parallel.
        """
        path = self.aux_path(name)
        with self._locks.held(f"aux:{name}"):
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
