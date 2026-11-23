"""The one-off put-back of C05's four seats swept while waiting on the GM (2026-11-23)."""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from players.unsweep import DONE_KEY, RESTORE, backfill_gm_silences, restore_gm_wait_sweeps  # noqa: E402
from helpers import build_topic_maps  # noqa: E402

_NOW = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)
_RYO, _LAE, _BUF, _ANT = RESTORE


def _config():
    return {"group_id": -100, "bot_topic_id": 1, "gm_user_ids": [999],
            "topic_pairs": [{"name": "Grand Explorers", "code": "C05", "chat_topic_id": 52,
                             "pbp_topic_ids": [51357, 145040]},
                            {"name": "Magni Guard", "code": "C04", "chat_topic_id": 75,
                             "pbp_topic_ids": [76799]}]}


def _gone(when, **extra):
    return {"removed_at": when, "first_name": "P", "username": "p",
            "campaign_name": "Grand Explorers", **extra}


def _state():
    return {"players": {}, "post_timestamps": {}, "player_history": [], "removed_players": {
        _RYO: _gone("2026-11-10T05:37:05+00:00", username="RyoYamakawa"),
        _LAE: _gone("2026-11-11T06:12:03+00:00", username="StorybookRhizome"),
        _BUF: _gone("2026-11-12T06:43:23+00:00", username="buffetraider"),
        _ANT: _gone("2026-11-18T12:43:17+00:00", username="MrNegetZ"),
        "76799:8969117742": _gone("2026-10-21T18:43:27+00:00", username="RexVolf")}}


def _logs(tmp_path, *gm_times, thread="51357"):
    d = tmp_path / "Grand_Explorers"
    d.mkdir(exist_ok=True)
    lines = [f"**Path Wars** [GM] ({t}) msg#{i}@{thread}:\nText\n" for i, t in enumerate(gm_times)]
    lines.append("**Ryo Yamakawa** (2026-10-21 12:00:00) msg#9@51357:\nNot the GM\n")
    (d / "2026-10.md").write_text("\n".join(lines), encoding="utf-8")
    return tmp_path


_C05_GM = ("2026-10-01 10:00:00", "2026-10-13 06:00:00", "2026-10-21 12:52:41", "2026-11-10 05:16:51")


def _run(monkeypatch, state, logs):
    import telegram as tg
    sent = []
    monkeypatch.setattr(tg, "send_message", lambda g, t, b, **k: sent.append((t, b)) or True)
    return restore_gm_wait_sweeps(_config(), state, now=_NOW, logs_dir=logs), sent


def test_the_four_c05_seats_come_back_with_one_note(monkeypatch, tmp_path):
    state = _state()
    restored, sent = _run(monkeypatch, state, _logs(tmp_path, *_C05_GM))
    assert sorted(restored) == sorted(RESTORE)
    assert all(k in state["players"] and k not in state["removed_players"] for k in RESTORE)
    assert len(sent) == 1 and sent[0][0] == 52
    assert "@RyoYamakawa" in sent[0][1] and "@MrNegetZ" in sent[0][1]
    assert state["players"][_RYO]["last_post_time"].startswith("2026-10-13")


def test_a_seat_off_the_list_stays_gone_even_if_the_rule_would_clear_it(monkeypatch, tmp_path):
    state = _state()
    _run(monkeypatch, state, _logs(tmp_path, *_C05_GM))
    assert "76799:8969117742" in state["removed_players"], "Volf left; silence cannot tell"


def test_without_a_gm_silence_nobody_comes_back(monkeypatch, tmp_path):
    # ⭐ Can-fail counterpart: the GM posted every two days, so the sweep was right.
    days = [(_NOW - timedelta(days=d)).strftime("%Y-%m-%d %H:%M:%S") for d in range(80, 0, -2)]
    state = _state()
    restored, sent = _run(monkeypatch, state, _logs(tmp_path, *days))
    assert restored == [] and sent == []
    assert state[DONE_KEY]


def test_a_kicked_seat_is_never_put_back(monkeypatch, tmp_path):
    state = _state()
    state["removed_players"][_RYO]["kicked"] = True
    restored, _ = _run(monkeypatch, state, _logs(tmp_path, *_C05_GM))
    assert _RYO not in restored and _RYO in state["removed_players"]


def test_it_runs_once(monkeypatch, tmp_path):
    state = _state()
    _run(monkeypatch, state, _logs(tmp_path, *_C05_GM))
    state["removed_players"][_RYO] = state["players"].pop(_RYO) | {"removed_at": "2026-11-22T00:00:00+00:00"}
    restored, sent = _run(monkeypatch, state, _logs(tmp_path, *_C05_GM))
    assert restored == [] and sent == []


def test_backfill_maps_a_second_thread_to_the_campaign_and_skips_players(tmp_path):
    state = {}
    backfill_gm_silences(state, build_topic_maps(_config()),
                         _logs(tmp_path, "2026-10-21 12:52:41", "2026-11-10 05:16:51", thread="145040"), _NOW)
    assert state["gm_silences"]["51357"] == {
        "last": "2026-11-10T05:16:51+00:00",
        "gaps": [["2026-10-21T12:52:41+00:00", "2026-11-10T05:16:51+00:00"]]}


def test_it_runs_before_the_sweep():
    import inspect
    import checker
    src = inspect.getsource(checker._run_checks)
    assert src.index("restore_gm_wait_sweeps") < src.index("check_player_activity")
