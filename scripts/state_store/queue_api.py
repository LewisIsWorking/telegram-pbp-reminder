"""Queue partition API \u2014 per-campaign queue files.

Mixin extracted from ``state_store/store.py`` to keep that file under
the 200-line cap while still grouping all queue-related methods in
one place. ``StateStore`` inherits from this class so callers can
treat the queue API as just another method group.

Slice 5 of P3/9. Adds:
  * ``queue_path(pid)`` \u2014 the on-disk path for ``queues/{pid}.json``
  * ``queue_exists(pid)`` \u2014 True iff that file is present
  * ``load_queue(pid)`` \u2014 parsed dict or None on missing/corrupt
  * ``save_queue(pid, data)`` \u2014 atomic write via tmp+rename
  * ``list_queues()`` \u2014 PIDs for every queue file under ``queues/``

Why a separate API rather than re-using ``load_aux``/``save_aux``:
the on-disk layout is different (subdirectory ``queues/`` rather
than the state_dir root), and slice 7 will add migration support
to queues only (not aux files). Keeping them as separate method
groups now means the slice-7 hook lands cleanly without
restructuring callers.
"""

import json
from pathlib import Path


class QueueAPI:
    """Mixin providing per-campaign queue file methods.

    Expects ``self._state_dir`` to be set by the host class
    (``StateStore``). Tests can construct a ``StateStore`` with a
    ``state_dir`` override and exercise the queue methods on the
    same instance \u2014 isolation flows through naturally.
    """

    _state_dir: Path  # provided by StateStore.__init__

    def queue_path(self, pid: str) -> Path:
        """Return the on-disk path for ``queues/{pid}.json``.

        Exposed publicly so callers that need to walk the queue file
        for diagnostics or migration purposes can do so without
        hard-coding the layout. Slice 7 will replace direct path
        usage at most call sites.
        """
        return self._state_dir / "queues" / f"{pid}.json"

    def queue_exists(self, pid: str) -> bool:
        """Return True iff the queue file for ``pid`` is present."""
        return self.queue_path(pid).exists()

    def load_queue(self, pid: str) -> dict | None:
        """Load a per-campaign queue file by ``pid``.

        Returns the parsed dict on success, or None if the file is
        missing or unparseable. The legacy contract that ``queue_io``
        had pre-slice-5 was to return an empty default structure on
        missing/corrupt; that policy now lives at the ``queue_io``
        call site so this layer can stay schema-agnostic. Corrupt
        files print a diagnostic but do not raise.
        """
        path = self.queue_path(pid)
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[state_store] Corrupt queue file {path} ({e}); "
                  f"returning None")
            return None

    def save_queue(self, pid: str, data: dict) -> None:
        """Save a per-campaign queue file atomically.

        Uses tmp+rename so a crash mid-write cannot leave a partially
        written ``queues/{pid}.json`` that the next process startup
        would mis-parse. Creates the ``queues/`` subdirectory if
        missing. Same semantics as ``save_aux`` and
        ``save_partition`` \u2014 indented JSON for human-readable git
        diffs, ``default=str`` so callers don't have to convert
        datetime values manually.
        """
        path = self.queue_path(pid)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        tmp.replace(path)

    def list_queues(self) -> list[str]:
        """Return PIDs (bare stems) for every queue file under
        ``queues/``.

        Used by ``commands.queue_io.all_pids`` post-slice-5 and by
        the slice-6 schema-completeness test. Returns an empty list
        if the ``queues/`` subdirectory doesn't exist (fresh
        checkout, no campaigns yet).
        """
        queues_dir = self._state_dir / "queues"
        if not queues_dir.exists():
            return []
        return sorted(p.stem for p in queues_dir.glob("*.json"))
