"""The test suite must never write a real GM queue file.

2026-08-27. The GM queue posted this to the group:

    17 [42] 🆕 23h. Paul: Hello all! 🔗 .../100/42
    18 [42] 🆕 23h. Paul: Hello all! 🔗 .../100/42
    ... 43 of them

Paul never sent any of it. They are fixtures from
``test_new_player_join_is_recorded.py``, and the Alice/"Hi!" entries
under C06 are older fixtures from
``test_final_100_02_dispatch_tracking.py``.

## How

Any test calling ``track_message`` with a non-GM user records an
unreplied entry, because that is exactly what the GM queue is for. Those
writes went to the **real** ``data/state/queues/``. The suite had built
``queues/100.json``, a pid that has never existed in any config, with a
**1,796-entry reply_log**, accumulated over months. CI committed it on
every run.

⚠️ ``queue_io``'s own docstring said its tests "all run in tmp_path
context via ``_test_state_isolation``". They never did. It was not on
that module's list, which was written for modules persisting through
``StateStore`` while ``queue_io`` reached the disk another way. **A
comment asserting isolation is not isolation.**

## What this file checks

Three separate ways the leak could return, because the fix is one line
in one file and nothing else was stopping it:

1. the redirect is actually in place during a test run
2. no queue file exists for a pid no config knows about
3. no live queue entry carries a fixture's fingerprint

Number 3 is the backstop: a future leak into a *real* pid's file would
pass 1 and 2 and still be visible to players.
"""

import json
import os

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_QUEUES = os.path.join(_ROOT, "data", "state", "queues")

# C11 Dark Pockets, retired from config in #22. Its file holds 282
# replied keys and 158 real reply-log entries: genuine history for a
# campaign that existed, not debris. Deleting it would destroy an audit
# trail, so it is named here rather than cleaned up.
RETIRED_PIDS = {"1242"}

# Names and text that only ever appear in fixtures. Real players are not
# called Alice or Bob, and nobody has ever posted the string "Hi!" as a
# whole message that reached the queue.
FIXTURE_NAMES = {"Alice", "Bob", "Paul"}
FIXTURE_PREVIEWS = {"Hi!", "hi", "yo", "Hello all!", "Rolling initiative"}


def _configured_pids() -> set:
    with open(os.path.join(_ROOT, "config.json"), encoding="utf-8") as handle:
        config = json.load(handle)
    return {str(t) for pair in config.get("topic_pairs", [])
            for t in pair.get("pbp_topic_ids", [])}


def _queue_files() -> list:
    if not os.path.isdir(_QUEUES):
        return []
    return sorted(f for f in os.listdir(_QUEUES) if f.endswith(".json"))


def _entries(name: str) -> list:
    with open(os.path.join(_QUEUES, name), encoding="utf-8") as handle:
        return json.load(handle).get("unreplied", [])


class TestTheRedirectIsInPlace:
    def test_queue_io_does_not_point_at_the_repo(self):
        # ⭐⭐ The fix itself. One line in _test_state_isolation.py, and
        # nothing else in the suite would notice if it were removed.
        #
        # ⚠️ The attribute is ``_state_dir``, private. The first version
        # of this test read ``state_dir`` with a getattr default, got
        # "", and its own guard-clause hid that it was checking nothing.
        # A default on a getattr is how an assertion stops asserting.
        from commands import queue_io
        where = str(queue_io._store._state_dir)
        assert os.path.realpath(_ROOT) not in os.path.realpath(where), (
            f"queue_io writes to {where}, which is inside the repo. Every "
            f"test that tracks a player message will land in a real GM "
            f"queue and be posted to the group.")

    def test_the_override_hook_is_not_left_pointing_at_the_repo(self):
        # ``_QUEUES_DIR`` takes precedence over ``_store`` entirely, so a
        # test leaving it set defeats the isolation no matter what the
        # store says. It must be None or somewhere outside the repo.
        from commands import queue_io
        if queue_io._QUEUES_DIR is None:
            return
        where = os.path.realpath(str(queue_io._QUEUES_DIR))
        assert os.path.realpath(_ROOT) not in where, (
            f"_QUEUES_DIR is left set to {where}")

    def test_writing_a_queue_here_does_not_touch_the_repo(self):
        # ⭐ Proven by doing it, not by reading a path. Records an entry
        # exactly the way track_message does and checks the real
        # directory is untouched.
        from commands import queue_io
        before = {f: os.path.getmtime(os.path.join(_QUEUES, f))
                  for f in _queue_files()}
        queue = queue_io.load("999999")
        queue["unreplied"].append({"message_id": 1, "user_name": "Probe",
                                   "preview": "probe", "time": "x"})
        queue_io.save("999999", queue)
        assert not os.path.exists(os.path.join(_QUEUES, "999999.json"))
        after = {f: os.path.getmtime(os.path.join(_QUEUES, f))
                 for f in _queue_files()}
        assert before == after, "a queue write touched the real directory"


class TestTheLiveQueuesAreClean:
    def test_there_are_queue_files_at_all(self):
        # ⭐ Without this, deleting the directory would make everything
        # below pass against nothing.
        assert _queue_files(), "no queue files found; the scan is broken"

    def test_no_queue_file_for_an_unknown_campaign(self):
        known = _configured_pids() | RETIRED_PIDS
        orphans = [f for f in _queue_files() if f[:-5] not in known]
        assert not orphans, (
            f"queue files for pids no config knows: {orphans}. "
            f"queues/100.json was exactly this, built entirely by the "
            f"test suite and posted to the group.")

    @pytest.mark.parametrize("name", _queue_files())
    def test_no_live_entry_looks_like_a_fixture(self, name):
        # ⭐⭐ The backstop. A future leak into a REAL campaign's file
        # would pass both checks above and still reach players, so this
        # matches on the content rather than the filename.
        suspects = [e for e in _entries(name)
                    if e.get("user_name") in FIXTURE_NAMES
                    or e.get("preview") in FIXTURE_PREVIEWS]
        assert not suspects, (
            f"{name} holds {len(suspects)} entries that look like test "
            f"fixtures, e.g. {suspects[0]}. These get posted to the group "
            f"as real players waiting on a reply.")
