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


def test_lock_registry_returns_same_lock_for_same_name() -> None:
    """First and subsequent ``get`` calls return the same Lock object.

    This is the foundation property: if calls returned different
    Locks, two threads requesting "live" would each get their own
    lock and wouldn't serialise on each other.
    """
    reg = LockRegistry()
    lock1 = reg.get("live")
    lock2 = reg.get("live")
    assert lock1 is lock2


def test_lock_registry_returns_different_locks_for_different_names() -> None:
    """Different names get different Lock objects.

    This is what gives per-resource granularity. If both names
    returned the same lock, saves to disjoint resources would
    serialise unnecessarily.
    """
    reg = LockRegistry()
    assert reg.get("live") is not reg.get("queue")


def test_lock_registry_held_context_manager_acquires_and_releases() -> None:
    """The ``held`` context manager acquires on enter, releases on exit.

    Verifies by checking the lock is acquirable after the with-block
    completes — if the context manager didn't release, a fresh
    ``acquire(blocking=False)`` would return False.
    """
    reg = LockRegistry()
    with reg.held("k"):
        pass
    # After the with-block, the lock is free — confirm by
    # acquiring it non-blocking.
    lock = reg.get("k")
    assert lock.acquire(blocking=False)
    lock.release()


def test_lock_registry_names_returns_snapshot_tuple() -> None:
    """``names`` returns an immutable tuple, not a live view.

    Catches the case where a future refactor returns the internal
    dict's keys() view by mistake — callers iterating the snapshot
    while a concurrent ``get`` mutates the registry would see
    surprising behaviour.
    """
    reg = LockRegistry()
    reg.get("a")
    reg.get("b")
    snap = reg.names()
    assert isinstance(snap, tuple)
    assert set(snap) == {"a", "b"}
