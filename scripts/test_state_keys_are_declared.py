"""Every persisted state key must be declared in PARTITIONS (2026-08-11).

The bug this prevents
---------------------
``state.py`` documents its own trap in a single line near the top:

    # Keys not listed here (e.g. _config_cache) are transient and not persisted.

``_save_to_files`` writes ``{k: state[k] for k in keys if k in state}`` per
partition, so **a key absent from PARTITIONS is silently discarded on every
save.** Nothing errors. Nothing warns. The value is simply gone next run.

I added four such keys without registering them:

===================== ===============================================
key                   consequence of being dropped
===================== ===============================================
potw_week             POTW re-awarded on every 30-min tick all Monday
last_potw_roundup     roundup reposted on every tick all Monday
last_potw_countdown   standings reposted on every tick all Thursday
schedule_post_msg_id  schedule post could never find its predecessor
                      to delete, so it duplicated indefinitely
===================== ===============================================

Only the last one was visible, because it posted in a topic Lewis reads.
The other three were waiting for the right weekday.

Why the existing guard missed it
--------------------------------
``test_state_schema.py::test_every_top_level_state_file_is_known`` guards
*files* — a new ``data/state/*.json`` without a schema entry. An undeclared
**key** inside an existing partition was never in scope. It also
``pytest.skip``s when ``data/state/`` is absent, so it can self-disable.

This guard is key-level and cannot skip.
"""

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from state import PARTITIONS  # noqa: E402

_ROOT = Path(os.path.dirname(__file__))

# Keys deliberately NOT persisted. Each needs a reason — an unexplained
# entry here is how this guard would rot into a rubber stamp.
_TRANSIENT = {
    "_config_cache",      # rebuilt per run from config.json; state.py says so
}


def _persisted_state_keys() -> set[str]:
    """Keys **written** to the ``state`` dict by production code.

    Writes only — ``state["x"] = ...`` and ``state.setdefault("x", ...)``.
    A key that is merely *read* needs no partition entry: the legacy
    migration path reads ``gm_queue`` / ``gm_queue_replied`` /
    ``gm_reply_log`` / ``paused`` / ``current_scene`` from old snapshots
    and writes their successors elsewhere, so demanding they persist
    would be wrong. Writing is what creates the expectation of survival,
    and writing is what ``_save_to_files`` silently discards.
    """
    pattern = re.compile(
        r'\bstate\[\s*["\'](\w+)["\']\s*\]\s*=|'
        r'\bstate\.setdefault\(\s*["\'](\w+)["\']')
    found: set[str] = set()
    for path in _ROOT.rglob("*.py"):
        if path.name.startswith("test_") or path.name == "conftest.py":
            continue
        if "__pycache__" in path.parts or path.name == "state.py":
            continue
        try:
            src = path.read_text(encoding="utf-8")
        except OSError:  # pragma: no cover - unreadable file
            continue
        for a, b in pattern.findall(src):
            found.add(a or b)
    return found - _TRANSIENT


class TestDiscovery:
    def test_finds_a_realistic_number_of_keys(self):
        """If the regex breaks, this guard silently passes forever."""
        keys = _persisted_state_keys()
        assert len(keys) > 20, (
            f"only found {len(keys)} state keys — the source scan has "
            f"probably broken, which would make this guard vacuous")

    def test_finds_the_keys_that_caused_the_bug(self):
        keys = _persisted_state_keys()
        for k in ("potw_week", "schedule_post_msg_id"):
            assert k in keys, f"{k} not discovered by the scan"


class TestEveryKeyIsDeclared:
    def test_no_undeclared_state_keys(self):
        declared = {k for keys in PARTITIONS.values() for k in keys}
        missing = sorted(_persisted_state_keys() - declared)
        assert not missing, (
            f"these state keys are written but not declared in "
            f"state.PARTITIONS, so _save_to_files DISCARDS them on every "
            f"save: {missing}.\n"
            f"Add each to the right partition, or to _TRANSIENT in this "
            f"file with a reason if it genuinely should not persist.\n"
            f"An idempotency key that does not persist means its job "
            f"re-fires on every 30-minute tick.")


class TestTheFourRegressions:
    """Named explicitly so a future refactor cannot quietly drop them."""

    def test_potw_week_persists(self):
        declared = {k for keys in PARTITIONS.values() for k in keys}
        assert "potw_week" in declared, "POTW would re-award every tick"

    def test_roundup_marker_persists(self):
        declared = {k for keys in PARTITIONS.values() for k in keys}
        assert "last_potw_roundup" in declared

    def test_countdown_marker_persists(self):
        declared = {k for keys in PARTITIONS.values() for k in keys}
        assert "last_potw_countdown" in declared

    def test_schedule_post_id_persists(self):
        declared = {k for keys in PARTITIONS.values() for k in keys}
        assert "schedule_post_msg_id" in declared, (
            "without this the schedule post cannot delete its predecessor")


class TestSaveLoadRoundTrip:
    """The property that actually matters: does a write survive a reload?

    Declaring the key is necessary but not sufficient — this exercises
    the real partition filter in ``_save_to_files``.
    """

    def test_all_four_survive_a_save_load_cycle(self, tmp_path, monkeypatch):
        import state as state_mod
        monkeypatch.setattr(state_mod, "_state_dir", lambda: tmp_path)
        monkeypatch.setattr(state_mod, "_loaded_ok", True)
        monkeypatch.setattr(state_mod, "gist_save",
                            lambda *a, **k: None)

        written = dict(state_mod.DEFAULT_STATE)
        written.update({
            "potw_week": {"40585": "2026-W33"},
            "last_potw_roundup": "2026-W33",
            "last_potw_countdown": "2026-W33",
            "schedule_post_msg_id": 4242,
        })
        state_mod._save_to_files(written)

        reloaded = state_mod._load_from_files()
        assert reloaded is not None, "partitions did not write"
        assert reloaded["potw_week"] == {"40585": "2026-W33"}
        assert reloaded["last_potw_roundup"] == "2026-W33"
        assert reloaded["last_potw_countdown"] == "2026-W33"
        assert reloaded["schedule_post_msg_id"] == 4242
