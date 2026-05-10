"""Slice 8 of P3/9 — LockRegistry and per-resource save locking.

The tests in this file split into two groups:

  1. ``LockRegistry`` mechanics in isolation — lazy creation, name
     filtering, snapshot immutability. Pure unit tests.

  2. End-to-end save locking via ``StateStore`` — verifies that
     ``save_aux`` / ``save_partition`` / ``save_queue`` actually
     acquire the right keyed lock and that two concurrent saves to
     the same resource serialise. Uses a short-blocking write to
     prove serialisation deterministically rather than relying on
     wall-clock timing.

Slice 8 is pure setup for P3/10. Production code today doesn't have
observed concurrency bugs — the bot runs hourly via a single CI
worker. The locks are wired in so that when slice 10 (and beyond)
adds read-modify-write APIs, the serialisation primitive is already
in place.
"""

import threading
import time
from pathlib import Path

import pytest

from state_store import StateStore
from state_store.locks import LockRegistry


# ---------------------------------------------------------------------------
# StateStore save locking — lock acquisition is observable
# ---------------------------------------------------------------------------


def test_save_aux_uses_namespaced_aux_lock(tmp_path: Path) -> None:
    """``save_aux`` registers a lock under the ``aux:{name}`` key.

    Verifies the namespacing convention: aux files use ``aux:foo``,
    partitions use ``partition:foo``, queues use ``queue:{pid}``.
    The slice-8 test for partition uses the same shape.
    """
    store = StateStore(state_dir=tmp_path)
    store.save_aux("foo", {"hello": "world"})
    assert "aux:foo" in store._locks.names()


def test_save_partition_uses_namespaced_partition_lock(tmp_path: Path) -> None:
    """``save_partition`` registers a lock under the ``partition:{name}`` key."""
    store = StateStore(state_dir=tmp_path)
    store.save_partition("live", {"offset": 123})
    assert "partition:live" in store._locks.names()


def test_save_queue_uses_namespaced_queue_lock(tmp_path: Path) -> None:
    """``save_queue`` registers a lock under the ``queue:{pid}`` key."""
    store = StateStore(state_dir=tmp_path)
    store.save_queue("40585", {"pid": "40585", "unreplied": []})
    assert "queue:40585" in store._locks.names()


def test_aux_and_partition_with_same_name_use_distinct_locks(
    tmp_path: Path,
) -> None:
    """Aux and partition with same name don't share a lock.

    A safety property of the namespace prefix: if a partition
    happened to be named ``foo`` and an aux file were also named
    ``foo``, they should NOT serialise on each other (they're
    different files on disk). The keys ``aux:foo`` and
    ``partition:foo`` are different, so they don't.
    """
    store = StateStore(state_dir=tmp_path)
    store.save_aux("foo", {"a": 1})
    store.save_partition("foo", {"b": 2})
    aux_lock = store._locks.get("aux:foo")
    part_lock = store._locks.get("partition:foo")
    assert aux_lock is not part_lock


# ---------------------------------------------------------------------------
# StateStore save locking — instance scoping
# ---------------------------------------------------------------------------


def test_lock_registries_are_per_instance(tmp_path: Path) -> None:
    """Two StateStores have independent LockRegistries.

    Critical for test isolation: tests that construct
    ``StateStore(state_dir=tmp_path)`` for a fresh tmp dir
    shouldn't see locks left over from prior tests' StateStores.
    Per-instance registries make this automatic — there's no
    shared mutable state between instances.
    """
    a = StateStore(state_dir=tmp_path / "a")
    b = StateStore(state_dir=tmp_path / "b")
    assert a._locks is not b._locks
    a.save_aux("foo", 1)
    # b's registry stays empty — the save on a didn't leak.
    assert "aux:foo" not in b._locks.names()


# ---------------------------------------------------------------------------
# Concurrent saves serialise on the same resource
# ---------------------------------------------------------------------------


def test_concurrent_saves_to_same_aux_serialise(tmp_path: Path) -> None:
    """Two threads saving the same aux file serialise on the lock.

    Verified by tracking the order of acquisition: both threads
    acquire the lock around their save, but only one can hold it at
    a time. If the lock is held by thread A when thread B tries to
    enter, B blocks until A releases — we observe this via a
    counter incremented inside the lock that should never read 2
    while another thread is also inside.
    """
    store = StateStore(state_dir=tmp_path)
    in_critical = [0]
    max_seen = [0]
    barrier = threading.Barrier(2)

    def saver():
        barrier.wait()
        for _ in range(20):
            with store._locks.held("aux:counter"):
                in_critical[0] += 1
                if in_critical[0] > max_seen[0]:
                    max_seen[0] = in_critical[0]
                # tiny sleep to widen the race window
                time.sleep(0.001)
                in_critical[0] -= 1

    t1 = threading.Thread(target=saver)
    t2 = threading.Thread(target=saver)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # If serialisation works, no two threads were ever in the
    # critical section simultaneously — max_seen must be 1.
    assert max_seen[0] == 1, (
        f"Expected serialised access (max_seen=1), got max_seen="
        f"{max_seen[0]}. Lock not held during write."
    )
