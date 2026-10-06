"""A Telegram edit rewrites its transcript entry (transcript/edits.py).

Lewis, 2026-10-06: "I already edited the message on October 1st, did you not
catch that?" The bot ignored edits, so the transcript kept a lore post's
wrong year five days after Lewis fixed it in Telegram.
"""

import pytest

import transcript.logger as logger
from _test_checker_helpers import _make_config, _make_msg, _make_state, checker
from commands import queue_io
from transcript.edits import EDITED_MARK, replace_entry

_ENTRY = "**Path Wars** [GM] (2026-10-01 12:44:55) msg#{mid}@146645:\n{body}\n"


@pytest.fixture(autouse=True)
def _tmp_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(logger, "_LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path / "queues")
    logger._transcript_cache.clear()


class TestReplaceEntry:
    def test_replaces_a_multi_paragraph_body_and_keeps_its_neighbours(self):
        before = (_ENTRY.format(mid=1, body="First.") + "\n"
                  + _ENTRY.format(mid=2, body="The Eel Sea.\n\nIt is the year 2,000,000.")
                  + "\n### 📅 Friday, Oct 02\n\n"
                  + _ENTRY.format(mid=3, body="Later."))
        new = _ENTRY.format(mid=2, body="It is the year 112,026 AF.").rstrip("\n")
        after = replace_entry(before, 2, new)
        assert "2,000,000" not in after
        assert "It is the year 112,026 AF." in after
        assert "First." in after and "Later." in after
        assert "\n\n### 📅 Friday, Oct 02" in after

    def test_message_not_in_transcript_changes_nothing(self):
        assert replace_entry(_ENTRY.format(mid=1, body="x"), 99, "new") is None

    def test_does_not_match_a_longer_id_with_the_same_prefix(self):
        text = _ENTRY.format(mid=12, body="twelve")
        assert replace_entry(text, 1, "new") is None


def _edit(update_id, message_id, text, date_ts):
    update = _make_msg(update_id, 100, text, date_ts=date_ts)
    msg = update.pop("message")
    msg["message_id"] = message_id
    msg["edit_date"] = date_ts + 3600
    update["edited_message"] = msg
    return update


def test_an_edit_through_the_router_rewrites_the_transcript_only():
    config, state = _make_config(), _make_state()
    ts = 1_759_300_000
    first = _make_msg(1, 100, "It is the year 2,000,000.", date_ts=ts)
    first["message"]["message_id"] = 500
    checker.process_updates([first], config, state)
    counts = dict(state["message_counts"]["100"])
    queued = queue_io.load("100")["unreplied"]
    assert queued and queued[0]["preview"] == "It is the year 2,000,000."

    checker.process_updates([_edit(2, 500, "It is the year 112,026 AF.", ts)],
                            config, state)

    log = next((logger._LOGS_DIR / "TestCampaign").glob("*.md")).read_text(
        encoding="utf-8")
    assert "2,000,000" not in log
    assert "It is the year 112,026 AF.\n" + EDITED_MARK in log
    assert log.count("msg#500") == 1
    # ⭐ Not a new post: no extra count, no second queue entry.
    assert state["message_counts"]["100"] == counts
    queued = queue_io.load("100")["unreplied"]
    assert len(queued) == 1
    assert queued[0]["preview"] == "It is the year 112,026 AF."


def test_edits_are_requested_from_telegram():
    import inspect
    import telegram_utils
    assert '"edited_message"' in inspect.getsource(telegram_utils.fetch_updates)
