"""An orphan is proven by the delete log, never inferred from a gap.

⛔ Written 2026-09-04 against a mistake I made and shipped into two
files. Hunting orphaned queue posts, I measured the GAP between
consecutive posts in a thread and called anything over Telegram's 48h
delete wall an orphan. That gave four, and Lewis deleted four messages by
hand on my word.

Only three were real. ``m175902`` (thread 52083) had been deleted by the
bot on the first attempt, and ``pin_audit_log.json`` recorded exactly
that, the whole time, while I reasoned about calendars.

The gap is a proxy. It supports "a delete attempted at the END of this
window could not have succeeded" and nothing more: not whether a delete
was attempted, not whether one succeeded earlier. It agreed with the
direct evidence three times in four, which is how a proxy earns trust it
has not got.

These tests pin the distinction the tool now makes, using the real
2026-08-30 window as the fixture.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from audit_queue_deletes import classify, delete_attempts, superseded

_WINDOW = "2026-08-30T07:05:00+00:00"
_LATER = "2026-09-01T16:34:00+00:00"


def _sent(*ids_at_thread):
    return {mid: {"at": at, "thread_id": th, "preview": "📋 Unreplied: 2"}
            for mid, at, th in ids_at_thread}


def _audit(*rows):
    return [{"action": "delete", "message_id": int(mid), "ok": ok}
            for mid, ok in rows]


class TestTheRealWindow:
    """The four candidates from 2026-08-30, three of which were orphans."""

    def _rows(self, audit, stuck=None):
        sent = _sent(("175998", _WINDOW, 51357), ("176610", _LATER, 51357),
                     ("175902", _WINDOW, 52083), ("176402", _LATER, 52083))
        return {r["msg_id"]: r for r in classify(
            superseded(sent, "Unreplied", "2026-08-01"),
            delete_attempts(audit), stuck or {})}

    def test_a_failed_delete_is_an_orphan(self):
        rows = self._rows(_audit(*[("175998", False)] * 4),
                          {"175998": {"hopeless": True}})
        assert rows["175998"]["verdict"] == "ORPHAN"

    def test_a_SUCCEEDED_delete_is_not_an_orphan_however_old_the_gap(self):
        """⭐⭐ THE CORRECTION. m175902's gap to the next post was 53.2h,
        well past the 48h wall, and it was deleted cleanly anyway. Gap
        arithmetic said orphan; the log said deleted; the log was right."""
        rows = self._rows(_audit(("175902", True)))
        assert rows["175902"]["deleted"] is True
        assert rows["175902"]["verdict"] == "deleted"

    def test_the_two_are_told_apart_in_one_pass(self):
        """Both in the same window, same 48h-plus gap, opposite verdicts.
        Nothing about the calendar separates them."""
        rows = self._rows(_audit(("175902", True),
                                 *[("175998", False)] * 4),
                          {"175998": {"hopeless": True}})
        assert rows["175902"]["verdict"] == "deleted"
        assert rows["175998"]["verdict"] == "ORPHAN"


class TestTheDangerousCase:
    def test_a_post_with_NO_attempt_is_reported_separately(self):
        """⛔ The one finding that would mean the bookkeeping itself is
        losing ids, rather than losing a race with Telegram. It must not
        be filed under the same heading as a refused delete."""
        rows = classify(
            superseded(_sent(("1", _WINDOW, 51357), ("2", _LATER, 51357)),
                       "Unreplied", "2026-08-01"),
            delete_attempts([]), {})
        assert rows[0]["verdict"].startswith("DROPPED")

    def test_the_live_post_is_never_counted(self):
        """The newest post per thread was not supposed to be deleted."""
        rows = superseded(_sent(("1", _WINDOW, 51357), ("2", _LATER, 51357)),
                          "Unreplied", "2026-08-01")
        assert [r["msg_id"] for r in rows] == ["1"]

    def test_a_hand_resolved_orphan_stops_reading_as_outstanding(self):
        """⭐ Lewis deleted the three by hand. They stay in the file as
        history, but must not nag as open work for the rest of time."""
        rows = classify(
            superseded(_sent(("175998", _WINDOW, 51357),
                             ("176610", _LATER, 51357)),
                       "Unreplied", "2026-08-01"),
            delete_attempts(_audit(*[("175998", False)] * 4)),
            {"175998": {"hopeless": True,
                        "resolved_at": "2026-09-04T22:50:00+00:00"}})
        assert rows[0]["resolved"] is True
        assert rows[0]["verdict"] == "ORPHAN (resolved 2026-09-04)"


class TestAgainstTheRealState:
    """⚠️ Runs the tool over the repository's actual state files. A tool
    that only ever meets fixtures can pass forever while its real input
    has changed shape underneath it."""

    def _live(self):
        import audit_queue_deletes as tool
        return classify(
            superseded(tool._load("sent_messages.json", {}),
                       "Unreplied", "2026-08-01"),
            delete_attempts(tool._load("pin_audit_log.json", [])),
            tool._load("stuck_deletes.json", {}))

    def test_the_scan_finds_a_real_population(self):
        """⛔ Guards against the scan silently matching nothing, which
        would report a clean bill of health forever."""
        assert len(self._live()) > 100

    def test_nothing_was_dropped_without_an_attempt(self):
        """⭐ The invariant that says the bookkeeping still works. 292
        superseded posts since 2026-08-01, 0 dropped, measured
        2026-09-04. If this ever fails, ids are being lost before
        Telegram is ever asked."""
        dropped = [r for r in self._live()
                   if r["verdict"].startswith("DROPPED")]
        assert dropped == [], (
            f"{len(dropped)} queue posts were superseded with no delete "
            f"ever attempted: {[r['msg_id'] for r in dropped][:5]}")

    def test_no_orphan_is_left_outstanding(self):
        """The three from 2026-08-30 are resolved; a NEW one appearing
        here is a real regression of the 46h edit-in-place fix."""
        open_ones = [r for r in self._live()
                     if r["verdict"] == "ORPHAN"
                     or r["verdict"] == "ORPHAN (unfiled)"]
        assert open_ones == [], (
            f"unresolved orphans: {[r['msg_id'] for r in open_ones]}")
