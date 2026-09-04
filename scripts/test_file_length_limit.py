"""No .py file over 200 lines (2026-08-15).

Lewis's global rule across every repo: 200 lines is a hard limit, and the
fix is to **extract**, never to trim comments or docstrings to squeeze
under it.

The backlog below is a **ratchet, not an exemption.** Each entry carries
its current length, and the guard fails if a listed file grows *or* if it
drops below 200 and is not removed from the list. A frozen ceiling would
permit regrowth back to the worst-ever length, which is the failure mode
in ``a-ratchet-that-never-tightens``.

When you clear one, delete its line. The guard will tell you to.

Why these seven are still here
------------------------------
Seven of the original thirteen were cleared on 2026-08-15 by extraction:
``state_schema``, ``roster_members``, ``bot_topic_dice``,
``potw_candidates``, ``session_poll_roster``, ``topic_queue_write``.

``telegram.py`` resisted every split attempt and is the interesting one.
Every function in it needs ``_post``, so any extracted module must import
back — a cycle. Moving ``_post`` out instead breaks
``test_telegram_01_misc``, which asserts on ``telegram.TELEGRAM_API``
directly after ``init()``. And a function-local import to dodge the cycle
resolves to the **mock** telegram module that ``conftest`` installs into
``sys.modules``, not the real one. It needs a deliberate transport-layer
refactor, not a slice.

The five test files and ``conftest`` are ordinary splits that simply were
not finished in the session that started them.
"""

import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(__file__))

_ROOT = pathlib.Path(os.path.dirname(__file__))
_LIMIT = 200

# path -> line count when last measured. Must only ever shrink.
_BACKLOG = {
    "test_branch_gaps_11_scheduled_queue_silence.py": 256,
    "test_potw_monday_schedule.py": 251,
    "test_topic_queue.py": 225,
    "test_branch_gaps_05_scheduled_session_poll.py": 213,
    "telegram.py": 207,
    "test_branch_gaps_12_queue_reminder_silent_a.py": 201,
}


def _lengths() -> dict[str, int]:
    out = {}
    for p in _ROOT.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        rel = p.relative_to(_ROOT).as_posix()
        out[rel] = len(p.read_text(encoding="utf-8", errors="replace")
                       .splitlines())
    return out


class TestDiscovery:
    def test_finds_the_whole_tree(self):
        """If the scan breaks, this guard silently passes forever."""
        found = _lengths()
        assert len(found) > 300, (
            f"only found {len(found)} python files — the scan has probably "
            f"broken, which would make this guard vacuous")

    def test_the_backlog_entries_all_exist(self):
        found = _lengths()
        missing = sorted(f for f in _BACKLOG if f not in found)
        assert not missing, (
            f"these are listed in _BACKLOG but no longer exist: {missing}. "
            f"Delete their lines.")


class TestNoNewOffenders:
    def test_no_unlisted_file_exceeds_the_limit(self):
        over = {f: n for f, n in _lengths().items()
                if n > _LIMIT and f not in _BACKLOG}
        assert not over, (
            f"these files exceed the {_LIMIT}-line limit and are not in the "
            f"backlog: {over}.\n"
            f"**Extract, do not trim.** Pull a coherent responsibility into "
            f"its own module and import it back — removing comments or "
            f"docstrings to get under the line is not a fix.")


class TestTheBacklogOnlyShrinks:
    def test_no_listed_file_has_grown(self):
        found = _lengths()
        grown = {f: (n, found[f]) for f, n in _BACKLOG.items()
                 if f in found and found[f] > n}
        assert not grown, (
            f"backlog files grew (was, now): {grown}.\n"
            f"A ratchet that never tightens is just a high-water mark. "
            f"These are allowed to exist, not to get worse.")

    def test_cleared_files_are_removed_from_the_backlog(self):
        found = _lengths()
        cleared = {f: found[f] for f, _n in _BACKLOG.items()
                   if f in found and found[f] <= _LIMIT}
        assert not cleared, (
            f"these are now under {_LIMIT} lines and must be removed from "
            f"_BACKLOG: {cleared}. Leaving them listed would let them grow "
            f"back to their old length unnoticed.")

    def test_the_backlog_is_shrinking_overall(self):
        """Named so the count is visible in the test output."""
        assert len(_BACKLOG) <= 7, (
            f"the backlog has {len(_BACKLOG)} entries; it stood at 7 on "
            f"2026-08-15 and 13 before that. It does not grow.")
