"""GM silences come off a player's 4-week clock (2026-11-23).

C05 Grand Explorers: the players last posted on 2026-10-21, the GM's next
post was owed and came on 2026-11-10, and the sweep removed all four
players between 11-10 and 11-18 for a silence that was the GM's.
"""

import inspect
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from scheduled.gm_silence import counted_days, record_gm_post  # noqa: E402

_NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
_PID = "51357"
_GM = "999"


def _ago(days: float) -> str:
    return (_NOW - timedelta(days=days)).isoformat()


def _config():
    return {"group_id": -100, "bot_topic_id": 1, "gm_user_ids": [int(_GM)],
            "topic_pairs": [{"name": "Grand Explorers", "code": "C05",
                             "chat_topic_id": 52, "pbp_topic_ids": [int(_PID)]}]}


def _state(days_quiet=28.5):
    seat = {"user_id": "7", "first_name": "Ryo", "username": "RyoYamakawa",
            "campaign_name": "Grand Explorers", "pbp_topic_id": _PID,
            "last_post_time": _ago(days_quiet), "last_warned_week": 3}
    return {"players": {f"{_PID}:RyoYamakawa": seat}, "removed_players": {},
            "topics": {}, "last_alerts": {}, "post_timestamps": {}}


def _gm_posts(state, *days_ago):
    """Feed GM posts through record_gm_post in order, as tracking.py does."""
    for d in sorted(days_ago, reverse=True):
        record_gm_post(_config(), state, _PID, _ago(d))
        state["post_timestamps"].setdefault(_PID, {}).setdefault(_GM, []).append(_ago(d))


def _sweep(monkeypatch, state):
    import telegram as tg
    from scheduled.alerts import check_player_activity
    sent = []
    monkeypatch.setattr(tg, "send_message", lambda g, t, b, **k: sent.append(b) or True)
    monkeypatch.setattr(tg, "send_message_id", lambda g, t, b, **k: sent.append(b) or 1)
    check_player_activity(_config(), state, now=_NOW)
    return sent


def test_without_a_gm_silence_the_quiet_player_is_still_swept(monkeypatch):
    # ⭐ Can-fail counterpart first: the GM posts every day, so all 28.5 days count.
    state = _state()
    _gm_posts(state, *range(1, 29))
    sent = _sweep(monkeypatch, state)
    assert f"{_PID}:RyoYamakawa" not in state["players"]
    assert "28 days" in sent[0], "the message gives real days, not counted ones"


def test_c05_players_waiting_on_a_silent_gm_are_kept(monkeypatch):
    # GM replies just after the player (28.4 days ago), then nothing until 8 days ago.
    state = _state()
    _gm_posts(state, 28.4, 8, 7, 6, 5, 4, 3, 2, 1)
    _sweep(monkeypatch, state)
    assert f"{_PID}:RyoYamakawa" in state["players"]
    assert round(counted_days(_config(), state, _PID, datetime.fromisoformat(_ago(28.5)), _NOW)) == 8


def test_a_silence_still_running_is_off_the_clock(monkeypatch):
    state = _state(days_quiet=40)
    _gm_posts(state, 39, 38, 37, 25)  # the GM has said nothing for 25 days
    _sweep(monkeypatch, state)
    assert f"{_PID}:RyoYamakawa" in state["players"]


def test_a_silence_older_than_post_timestamps_still_counts(monkeypatch):
    # post_timestamps are pruned at 15 days; the gm_silences record is what remembers.
    state = _state()
    _gm_posts(state, 28.4, 8)
    state["post_timestamps"][_PID][_GM] = [_ago(8)]
    _sweep(monkeypatch, state)
    assert f"{_PID}:RyoYamakawa" in state["players"]


def test_short_gaps_do_not_count():
    state = _state()
    _gm_posts(state, *[d / 2 for d in range(2, 60, 5)])  # a post every 2.5 days
    assert state["gm_silences"][_PID]["gaps"] == []
    since = datetime.fromisoformat(_ago(29))
    assert round(counted_days(_config(), state, _PID, since, _NOW)) == 29


def test_only_the_overlap_with_the_players_silence_comes_off():
    state = _state()
    _gm_posts(state, 50, 30, 1)  # silences 50 to 30 and 30 to 1
    since = datetime.fromisoformat(_ago(40))
    assert round(counted_days(_config(), state, _PID, since, _NOW)) == 1


def test_old_silences_are_pruned():
    state = _state()
    _gm_posts(state, 200, 150, 10)
    gaps = state["gm_silences"][_PID]["gaps"]
    assert [round((_NOW - datetime.fromisoformat(e)).days) for _, e in gaps] == [10]


def test_tracking_records_gm_posts_before_appending_the_timestamp():
    from dispatch import tracking
    src = inspect.getsource(tracking.track_message)
    assert "record_gm_post" in src
    assert src.index("record_gm_post(") < src.index('state["post_timestamps"]')


def test_the_state_key_is_declared_so_it_is_saved():
    from state_schema import PARTITIONS
    assert any("gm_silences" in keys for keys in PARTITIONS.values())


def test_a_gm_posting_every_four_days_does_not_stop_the_sweep(monkeypatch):
    # ⛔ At the first threshold (3 days) this kept every quiet player forever.
    state = _state(days_quiet=30)
    _gm_posts(state, *range(1, 33, 4))
    _sweep(monkeypatch, state)
    assert f"{_PID}:RyoYamakawa" not in state["players"]
