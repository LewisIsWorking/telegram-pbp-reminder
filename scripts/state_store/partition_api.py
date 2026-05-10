"""Partition API — main state-shape JSON files.

Mixin extracted from ``state_store/store.py`` to keep that file
under the 200-line cap while still grouping all partition-related
methods in one place. ``StateStore`` inherits from this class so
callers can treat the partition API as just another method group.

Partition files are the five JSON files written by ``state.py``:
``live`` / ``players`` / ``queue`` / ``activity`` / ``trackers``.
On disk they have the same shape as aux files — just bigger, with
multi-key dicts. Slice 3 of P3/9 added the read side; slice 4 made
writes atomic; slice 8 (this file's reason for existing as a
mixin) adds per-partition locking so concurrent writes can't
corrupt each other's tmp+rename.

Why a separate API rather than re-using ``load_aux``/``save_aux``:
the two have similar implementations today, but later slices add
partition-only concerns (migration registry in slice 7, schema
validation in slice 6+) that aux files don't need. Keeping the
namespaces separate also gives the lock registry distinct keys
(``partition:live`` vs ``aux:live``) — a safety property that
becomes meaningful if an aux file and a partition ever share a
name.
"""

import json
from pathlib import Path


class PartitionAPI:
    """Mixin providing main-state-partition load/save methods.

    Expects ``self._state_dir`` (Path) and ``self._locks``
    (LockRegistry) to be set by the host class — both are
    initialised by ``StateStore.__init__``. The aux_path/load_aux
    methods are also provided by the host class; partition_exists
    and load_partition delegate to them since the read side has no
    partition-specific concerns yet.
    """

    # Set by StateStore.__init__ — declared here so type-checkers
    # don't flag the attribute access in mixin methods.
    _state_dir: Path

    def partition_exists(self, name: str) -> bool:
        """Return True iff the partition file is present on disk."""
        return (self._state_dir / f"{name}.json").exists()

    def load_partition(self, name: str) -> dict | None:
        """Load a partition file by name.

        Returns the parsed dict on success, or None if the file is
        missing or unparseable. Callers (e.g. ``state.py``) get to
        decide whether "missing" means "defaults" or "fall back to
        gist". Corrupt files are logged but don't raise — the
        contract matches ``load_aux``.
        """
        path = self._state_dir / f"{name}.json"
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[state_store] Corrupt partition file {path} "
                  f"({e}); returning None")
            return None

    def save_partition(self, name: str, data: dict) -> None:
        """Save a partition file atomically, holding the partition lock.

        Slice 4 of P3/9 made the write atomic (tmp + rename); slice 8
        adds per-partition locking via ``self._locks.held(f"partition:
        {name}")``. Two concurrent calls to save_partition for the
        same name will serialise; calls for different names run in
        parallel. The lock is released as soon as the rename
        completes — readers that have already opened the path before
        the rename see the old bytes, readers that open after see the
        new bytes; partial-byte reads are impossible.

        Why this no longer delegates to save_aux: doing so would
        acquire BOTH the ``partition:{name}`` lock and the
        ``aux:{name}`` lock (different keys, no deadlock — but
        wasteful). Inlining the atomic write here uses one lock per
        save, matching the queue and aux paths.
        """
        path = self._state_dir / f"{name}.json"
        with self._locks.held(f"partition:{name}"):
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            tmp.replace(path)
