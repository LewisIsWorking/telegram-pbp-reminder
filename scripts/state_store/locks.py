"""Per-resource locks for StateStore.

Slice 8 of P3/9. Provides ``LockRegistry`` — a thread-safe registry
of named locks that StateStore acquires during save operations.
Sets up the locking primitives that P3/10 (actual concurrency
hardening) will use; the bot itself doesn't have observed
concurrency bugs today, so this slice is pure setup with the lock
plumbed into save_* methods but no caller relying on the
serialisation guarantee yet.

Design notes:

* **Per-resource granularity, not one big lock.** Saves to
  ``live.json`` shouldn't block saves to ``queue.json`` or to a
  per-campaign ``queues/{pid}.json``. Each resource (partition
  name, aux name, queue pid) keys its own lock so disjoint writes
  proceed in parallel.

* **Threading, not asyncio.** The bot is synchronous (requests-
  based). ``threading.Lock`` is the right primitive. If async
  support arrives, a parallel AsyncLockRegistry can sit beside
  this one without restructuring callers.

* **Instance-scoped, not module-level.** Tests construct
  ``StateStore(state_dir=tmp_path)`` for isolation. If locks lived
  at module scope, two tests using the same partition name would
  serialise on the same lock instance even though they're talking
  to different on-disk state. Per-instance keeps each StateStore
  independent.

* **What this DOES guarantee.** Two concurrent calls to
  ``save_*`` on the same resource will serialise — the second
  blocks until the first's tmp+rename completes. Different
  resources run in parallel. Lock acquisition is FIFO-ish (Python
  threading.Lock isn't strictly FIFO but is fair enough for
  bot use).

* **What this does NOT yet guarantee.** Read-modify-write
  atomicity. A reader holding stale data can still overwrite a
  concurrent writer's update — last-write-wins. Slice 10 will add
  the read-modify-write API; for now save-side locking just
  prevents byte-level corruption from two writers fighting over
  ``tmp.replace()``.
"""

import threading
from contextlib import contextmanager
from typing import Iterator


class LockRegistry:
    """Thread-safe registry of named locks.

    Locks are created lazily on first request and cached. Subsequent
    requests with the same name return the same Lock instance, so
    callers across threads see consistent serialisation. The
    registry itself is guarded by a meta-lock so concurrent first-
    access calls can't race to create the same name twice.
    """

    def __init__(self) -> None:
        self._locks: dict[str, threading.Lock] = {}
        self._meta = threading.Lock()

    def get(self, name: str) -> threading.Lock:
        """Return (creating if needed) the lock for ``name``.

        First call for a given name creates a fresh ``threading.Lock``
        and stores it. Subsequent calls return the same instance.
        Two callers requesting different names get different Lock
        objects, so disjoint resources don't serialise on each
        other.
        """
        with self._meta:
            if name not in self._locks:
                self._locks[name] = threading.Lock()
            return self._locks[name]

    @contextmanager
    def held(self, name: str) -> Iterator[None]:
        """Context manager: hold the lock for ``name`` for the block.

        Convenience wrapper so callers can write
        ``with registry.held("partition:live"): ...`` instead of
        ``lock = registry.get(...); lock.acquire(); try: ... finally:
        lock.release()``. The pattern matches how ``save_*`` methods
        in StateStore wrap their tmp+rename writes.
        """
        lock = self.get(name)
        with lock:
            yield

    def names(self) -> tuple[str, ...]:
        """Return a snapshot of every lock name currently registered.

        Used by the slice-8 regression tests to introspect which
        resources have been locked. Production code should not
        depend on this — it's debug/test surface only.
        """
        with self._meta:
            return tuple(self._locks.keys())
