"""Read the whole backlog before concluding anything from it.

2026-09-01. Lewis reported three things in one message, all with one
cause:

* the daily "campaign that needs players most" post never arrived;
* the GM queue looked wrong;
* the bot posted **"All caught up. Time for players to post!"** into C07
  while two player messages sat unanswered.

⛔⛔ `getUpdates` returns at most 100 updates per call, and the checker
called it **once** per run. After the 15 hour outage there were several
hundred queued. The 16:33 run logged:

```
Received 100 new updates
```

drained the oldest hundred (still 2026-08-31), advanced the offset, and
ran every scheduled check against that partial view. From inside that
run C07 genuinely had nothing unreplied, because Anthony's 11:20 and
Terra's 11:28 messages had not been read yet.

⭐ **The caught-up notice was not wrong. It was answered from half a
page.** So the fix is not "fetch more" alone: paging handles the common
case, and **refusing to run the checks while the backlog is non-empty**
is what stops the bot announcing a conclusion it has not finished
reading the evidence for.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from dispatch.drain import MAX_PAGES, drain
from telegram_utils import PAGE_LIMIT


def _pages(*sizes):
    """A fetch() that returns pages of the given sizes, then nothing."""
    remaining = list(sizes)
    seen = []

    def fetch(offset):
        seen.append(offset)
        return [{"update_id": offset + i} for i in range(remaining.pop(0))] \
            if remaining else []
    return fetch, seen


def _process(updates):
    """Stand-in for process_updates: returns the next offset."""
    return updates[-1]["update_id"] + 1


class TestItReadsEveryPage:
    def test_a_short_first_page_stops_immediately(self):
        fetch, seen = _pages(3)
        offset, total, complete = drain(0, fetch, _process)
        assert (total, complete) == (3, True)
        assert len(seen) == 1, "a short page means Telegram has no more"

    def test_a_full_page_is_followed_by_another_fetch(self):
        # ⭐⭐ The bug. One full page used to be the end of the read.
        fetch, seen = _pages(PAGE_LIMIT, 7)
        offset, total, complete = drain(0, fetch, _process)
        assert total == PAGE_LIMIT + 7
        assert complete and len(seen) == 2

    def test_a_long_backlog_is_drained_across_many_pages(self):
        fetch, _ = _pages(*([PAGE_LIMIT] * 5), 12)
        _, total, complete = drain(0, fetch, _process)
        assert total == PAGE_LIMIT * 5 + 12 and complete

    def test_an_empty_first_page_reads_as_complete(self):
        fetch, seen = _pages()
        offset, total, complete = drain(42, fetch, _process)
        assert (offset, total, complete) == (42, 0, True)

    def test_the_offset_advances_across_pages(self):
        fetch, seen = _pages(PAGE_LIMIT, 5)
        offset, _, _ = drain(0, fetch, _process)
        assert seen[1] == PAGE_LIMIT, "second fetch must use the new offset"
        assert offset == PAGE_LIMIT + 5


class TestAPartialReadIsReportedAsPartial:
    """⭐ The half that actually stops the bad post."""

    def test_hitting_the_page_cap_reports_incomplete(self):
        fetch, _ = _pages(*([PAGE_LIMIT] * (MAX_PAGES + 3)))
        _, total, complete = drain(0, fetch, _process)
        assert not complete, (
            "still a full page after MAX_PAGES, so the caller must not "
            "conclude anything from what it read")
        assert total == PAGE_LIMIT * MAX_PAGES

    def test_it_stops_rather_than_looping_forever(self):
        fetch, seen = _pages(*([PAGE_LIMIT] * 1000))
        drain(0, fetch, _process)
        assert len(seen) == MAX_PAGES

    def test_a_backlog_that_ends_exactly_at_the_cap_is_complete(self):
        # can-fail counterpart: the cap must not report "incomplete" for
        # a backlog it genuinely finished.
        fetch, _ = _pages(*([PAGE_LIMIT] * (MAX_PAGES - 1)), 4)
        _, _, complete = drain(0, fetch, _process)
        assert complete


class TestTheCheckerHonoursIt:
    """⛔ Proven is not reachable. The drain is worthless if the checker
    still runs its posting checks on an incomplete read."""

    def test_the_checker_gates_the_checks_on_completeness(self):
        import inspect
        import checker
        source = inspect.getsource(checker.main)
        # ⚠️ Assert the GATING, not the presence of both names. My first
        # version checked `"drain_into" in source and "_run_checks" in
        # source`, which stays true when the `if` is deleted, and a
        # mutation that unguarded the checks survived.
        assert "if drain_into(" in source, (
            "_run_checks is no longer gated on drain_into's verdict; a "
            "partial read would post again")

    def test_drain_into_returns_false_and_says_so_on_a_partial_read(self, capsys):
        from dispatch.drain import drain_into
        fetch, _ = _pages(*([PAGE_LIMIT] * (MAX_PAGES + 1)))
        state = {"offset": 0}
        assert drain_into(state, fetch, _process) is False
        out = capsys.readouterr().out
        assert "STILL NOT EMPTY" in out and "Skipping scheduled checks" in out
        assert state["offset"] > 0, "the drain must still bank its progress"

    def test_drain_into_returns_true_when_finished(self, capsys):
        from dispatch.drain import drain_into
        fetch, _ = _pages(4)
        assert drain_into({"offset": 0}, fetch, _process) is True
        assert "drained" in capsys.readouterr().out

    def test_the_page_limit_is_not_duplicated(self):
        # ⛔ A literal 100 in drain.py could drift from the one the
        # request actually sends, and then a full page would read as
        # short. That is the same duplicated-literal shape that skipped
        # every scheduled run earlier the same day.
        import inspect
        from dispatch import drain as drain_mod
        source = inspect.getsource(drain_mod)
        assert "from telegram_utils import PAGE_LIMIT" in source
        assert "100" not in source.split('"""')[-1], (
            "drain.py hardcodes a page size instead of importing it")

    def test_the_request_actually_sends_PAGE_LIMIT(self, monkeypatch):
        # ⛔ The other end of the same reference, and it survived a
        # mutation until this existed. drain.py importing the constant
        # proves nothing if fetch_updates sends a different number: a
        # page of 50 would then always look "short" and the drain would
        # stop on a full backlog, which is the original bug restored.
        import telegram_utils
        seen = {}

        class _Resp:
            status_code = 200

            @staticmethod
            def json():
                return {"ok": True, "result": []}

        def fake_get(url, params=None, timeout=None):
            seen.update(params or {})
            return _Resp()

        monkeypatch.setattr(telegram_utils.requests, "get", fake_get)
        telegram_utils.fetch_updates("http://x", 0)
        assert seen.get("limit") == PAGE_LIMIT, (
            f"getUpdates asks for {seen.get('limit')} but drain.py reasons "
            f"about {PAGE_LIMIT}")
