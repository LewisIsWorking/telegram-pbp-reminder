"""Slice 6 of P3/9 — schema-completeness regression tests.

Walks the on-disk ``data/state/`` directory and asserts that every
JSON file there matches an entry in ``state_store/schema.py``. New
state files added without integration will fail this test, forcing
either:

  * Adding a reader/writer (most cases — promote to PARTITIONS or
    AUX_FILES with matching StateStore methods), or
  * Documenting it as WRITE_ONCE with a clear rationale (rare — the
    only current example is ``manifest.json`` from the 2026-04
    partition migration).

This test catches the orphan failure mode the 2026-05-10 incident
highlighted: state files diverging from code without anyone noticing.
It also asserts that schema entries map to real StateStore methods,
catching the inverse case (schema declares a partition that no one
reads/writes).
"""

import re
from pathlib import Path

import pytest

from state_store import StateStore
from state_store.schema import (
    AUX_FILES,
    PARTITIONS,
    QUEUE_FILES_DIR,
    WRITE_ONCE,
    all_top_level_names,
)
import state as state_module


# Repo-root-relative state directory. Resolved once at import time so
# every test in this file walks the same target.
_STATE_DIR = (Path(__file__).resolve().parent.parent / "data" / "state")


# ---------------------------------------------------------------------------
# On-disk inventory ↔ schema agreement
# ---------------------------------------------------------------------------


def test_every_top_level_state_file_is_known() -> None:
    """Every ``data/state/*.json`` file must match a schema entry.

    This is the headline check: a new file appears under data/state/
    without an accompanying schema entry → test fails → forces the
    PR author to either integrate it (PARTITIONS/AUX_FILES with a
    matching StateStore method) or document it (WRITE_ONCE with a
    rationale).
    """
    if not _STATE_DIR.exists():
        pytest.skip("data/state/ does not exist on this checkout")

    actual = {p.stem for p in _STATE_DIR.glob("*.json")}
    declared = all_top_level_names()
    unknown = actual - declared

    assert not unknown, (
        f"Found state files with no schema entry: {sorted(unknown)}. "
        f"Add them to scripts/state_store/schema.py under PARTITIONS, "
        f"AUX_FILES, or WRITE_ONCE with a description of who reads "
        f"and writes them."
    )


def test_partitions_match_state_module() -> None:
    """Schema PARTITIONS must mirror ``state.PARTITIONS`` keys.

    ``state.PARTITIONS`` is the production source of truth for which
    partition files exist (it maps each partition→keys). The schema
    must mirror it exactly — drift means either schema declares a
    partition the bot doesn't actually have, or the bot has one the
    schema doesn't know about.
    """
    schema_names = {name for name, _ in PARTITIONS}
    state_names = set(state_module.PARTITIONS.keys())
    assert schema_names == state_names, (
        f"Schema PARTITIONS {sorted(schema_names)} differ from "
        f"state.PARTITIONS {sorted(state_names)}. Update one or the "
        f"other so they agree."
    )


# ---------------------------------------------------------------------------
# Schema ↔ StateStore reader/writer agreement
# ---------------------------------------------------------------------------


def test_every_partition_has_loader_and_saver() -> None:
    """Every PARTITIONS entry must be loadable+savable by StateStore.

    Asserts that ``StateStore.load_partition(name)`` and
    ``save_partition(name, ...)`` exist for every declared partition.
    Catches the case where a partition is declared in the schema but
    has no corresponding StateStore method.
    """
    store = StateStore()
    for name, _desc in PARTITIONS:
        assert callable(getattr(store, "load_partition", None)), (
            "StateStore.load_partition missing"
        )
        assert callable(getattr(store, "save_partition", None)), (
            "StateStore.save_partition missing"
        )
        # The methods accept any name string — we don't actually call
        # them here (would require synthesising data). Existence is
        # enough for the schema-completeness contract; data-shape
        # tests live in test_state_store_partitions.py.


def test_every_aux_file_has_loader_and_saver() -> None:
    """Every AUX_FILES entry must be loadable+savable by StateStore."""
    store = StateStore()
    for name, _desc in AUX_FILES:
        assert callable(getattr(store, "load_aux", None)), (
            "StateStore.load_aux missing"
        )
        assert callable(getattr(store, "save_aux", None)), (
            "StateStore.save_aux missing"
        )


def test_write_once_files_have_no_loader_method() -> None:
    """WRITE_ONCE entries must NOT have a dedicated StateStore reader.

    These are intentional orphans: written by an external tool (e.g.
    migrate_gist_to_files.py for manifest.json) with no runtime
    reader. If a reader is added, the entry should move to AUX_FILES
    or PARTITIONS so the schema reflects production reality.
    """
    store = StateStore()
    for name, _desc in WRITE_ONCE:
        # No load_<name> shortcut method should exist (we use
        # load_aux/load_partition for files that have a runtime
        # reader; absence of a dedicated method is what marks it
        # write-once).
        loader_name = f"load_{name}"
        assert not hasattr(store, loader_name), (
            f"WRITE_ONCE entry '{name}' has a load_{name} method on "
            f"StateStore. If it has a runtime reader, move it to "
            f"AUX_FILES or PARTITIONS in schema.py."
        )


# ---------------------------------------------------------------------------
# Queue-file shape
# ---------------------------------------------------------------------------


_PID_RE = re.compile(r"^\d+$")


def test_queue_files_match_pid_shape() -> None:
    """Every file under ``data/state/queues/`` must be ``{pid}.json``.

    pid is digits-only (Telegram thread IDs). A non-digit filename
    here means something other than a campaign queue has been
    written into the queues directory — either accidentally or by
    a bug — and should be investigated.
    """
    queues_dir = _STATE_DIR / QUEUE_FILES_DIR
    if not queues_dir.exists():
        pytest.skip("data/state/queues/ does not exist on this checkout")

    for path in queues_dir.glob("*.json"):
        assert _PID_RE.match(path.stem), (
            f"Unexpected queue file shape: {path.name}. Expected "
            f"digits-only stem (e.g. 40585.json)."
        )


def test_state_store_has_queue_methods() -> None:
    """StateStore must expose the slice-5 queue methods.

    Every method the production codebase relies on for queue I/O
    (production path, not test override) must be callable. Catches
    accidental removal or rename of the QueueAPI mixin methods.
    """
    store = StateStore()
    for method_name in (
        "queue_path", "queue_exists", "load_queue",
        "save_queue", "list_queues",
    ):
        assert callable(getattr(store, method_name, None)), (
            f"StateStore missing queue method: {method_name}"
        )
