"""The sweep, the nudges, and the two commands that set it up.

Companion to ``test_played_by_is_a_redirection``, which pins the
resolution rule. This one pins what the resolution is FOR: Horia was at
week 4 with ``last_warned_week`` 3 on 2026-09-01, which is the exact
state that gets a seat removed on the next hourly run.

Split at the 200-line limit.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

_NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
_PID = "40585"
_CHAT = 21528
_GROUP = -100


def _ago(days: float) -> str:
    return (_NOW - timedelta(days=days)).isoformat()


def _seat(name, username, days, **extra):
    seat = {"user_id": username, "first_name": name, "username": username,
            "campaign_name": "Kibwe", "pbp_topic_id": _PID,
            "last_post_time": _ago(days), "last_warned_week": 0}
    seat.update(extra)
    return seat


def _config():
    return {"group_id": _GROUP, "bot_topic_id": 137393, "gm_user_ids": [999],
            "topic_pairs": [{"name": "Kibwe", "code": "C06",
                             "chat_topic_id": _CHAT,
                             "pbp_topic_ids": [int(_PID)]}]}


def _state(*seats):
    return {"players": {f"{_PID}:{s['username']}": s for s in seats},
            "removed_players": {}, "topics": {}, "last_alerts": {}}


def _run(monkeypatch, config, state):
    import telegram as tg
    from scheduled.alerts import check_player_activity
    sent = []
    monkeypatch.setattr(tg, "send_message",
                        lambda g, t, b, **k: sent.append(b) or True)
    monkeypatch.setattr(tg, "send_message_id",
                        lambda g, t, b, **k: sent.append(b) or 1)
    check_player_activity(config, state, now=_NOW)
    return sent


class TestHoriaIsNotSwept:
    """The measured 2026-09-01 state, which was one run from removal."""

    def _horia_at_week_four(self, **kw):
        return _seat("Horia", "Nemesiux", 28.84, last_warned_week=3, **kw)

    def test_the_unproxied_seat_is_removed(self, monkeypatch):
        # ⭐ The can-fail counterpart, deliberately first: it is the
        # evidence the fixture reproduces the real 2026-09-01 state. If
        # this ever stops removing him, every test below it is vacuous.
        state = _state(self._horia_at_week_four(),
                       _seat("Anthony", "MrNegetZ", 1.55))
        _run(monkeypatch, _config(), state)
        assert f"{_PID}:Nemesiux" not in state["players"], (
            "fixture no longer reproduces the 2026-09-01 removal; the "
            "tests below prove nothing without it")

    def test_the_proxied_seat_survives(self, monkeypatch):
        # ⭐⭐ The fix. Anthony posted 1.55 days ago and rolls for Lorn.
        state = _state(self._horia_at_week_four(played_by="MrNegetZ"),
                       _seat("Anthony", "MrNegetZ", 1.55))
        _run(monkeypatch, _config(), state)
        assert f"{_PID}:Nemesiux" in state["players"]

    def test_he_is_removed_again_once_the_proxy_goes_quiet(self, monkeypatch):
        # ⛔ Redirection, not exemption. Anthony silent 40 days: both go.
        state = _state(self._horia_at_week_four(played_by="MrNegetZ"),
                       _seat("Anthony", "MrNegetZ", 40))
        _run(monkeypatch, _config(), state)
        assert f"{_PID}:Nemesiux" not in state["players"]
        assert f"{_PID}:MrNegetZ" not in state["players"]

    def test_a_broken_proxy_does_not_save_him(self, monkeypatch):
        state = _state(self._horia_at_week_four(played_by="NotHere"),
                       _seat("Anthony", "MrNegetZ", 1.55))
        _run(monkeypatch, _config(), state)
        assert f"{_PID}:Nemesiux" not in state["players"]


class TestTheAbsentPlayerIsNotNagged:
    """⛔ THE PROXY MUST BE QUIET TOO, or this tests nothing.

    My first version put the proxy at 1.55 days. That resolves the
    proxied seat to week 0, so no warning was due for either of them and
    the test passed without the suppression ever running. A mutation
    that deleted ``is_proxied(player)`` from the condition survived, and
    that is exactly what a mutation harness is for.

    Here the proxy is 8 days quiet, so BOTH seats are at week 1 and a
    warning is genuinely due. Only the suppression stops it.
    """

    def test_an_unproxied_seat_at_one_week_is_warned(self, monkeypatch):
        # can-fail counterpart FIRST: proves a warning really is due at
        # this fixture, so the silence below means something.
        state = _state(_seat("Horia", "Nemesiux", 8),
                       _seat("Anthony", "MrNegetZ", 8))
        sent = _run(monkeypatch, _config(), state)
        assert any("hasn't posted" in m for m in sent), sent

    def test_a_proxied_seat_gets_no_weekly_warning(self, monkeypatch):
        # The nudge asks the player why they have not posted. For a
        # character somebody else rolls for, the recipient is not the
        # person who could act on it. Anthony is warned for HIS seat;
        # Horia is not warned for one Anthony is playing.
        state = _state(_seat("Horia", "Nemesiux", 8, played_by="MrNegetZ"),
                       _seat("Anthony", "MrNegetZ", 8))
        sent = _run(monkeypatch, _config(), state)
        assert not any("Horia" in m or "Nemesiux" in m for m in sent), sent
        assert any("Anthony" in m or "MrNegetZ" in m for m in sent), (
            "the proxy must still be warned about their own seat")


class TestTheCommands:
    def _run_cmd(self, monkeypatch, text, state):
        import telegram as tg
        from dispatch.cmd_proxy import handle_proxy
        sent = []
        monkeypatch.setattr(tg, "send_message",
                            lambda g, t, b, **k: sent.append(b) or True)
        handled = handle_proxy(text, text, _PID, "Kibwe", state, _GROUP, _CHAT)
        return handled, sent

    def test_setproxy_sets_the_field(self, monkeypatch):
        state = _state(_seat("Horia", "Nemesiux", 28.84),
                       _seat("Anthony", "MrNegetZ", 1.55))
        handled, sent = self._run_cmd(
            monkeypatch, "/setproxy @Nemesiux @MrNegetZ", state)
        assert handled
        assert state["players"][f"{_PID}:Nemesiux"]["played_by"] == "MrNegetZ"
        assert "MrNegetZ" in sent[0]

    def test_clearproxy_removes_it(self, monkeypatch):
        state = _state(_seat("Horia", "Nemesiux", 28.84, played_by="MrNegetZ"))
        self._run_cmd(monkeypatch, "/clearproxy @Nemesiux", state)
        assert "played_by" not in state["players"][f"{_PID}:Nemesiux"]

    def test_an_unknown_proxy_is_accepted_but_warned_about(self, monkeypatch):
        # ⚠️ Not an error: they may join later. But the GM must not walk
        # away believing the seat is covered when it is not.
        state = _state(_seat("Horia", "Nemesiux", 28.84))
        _, sent = self._run_cmd(
            monkeypatch, "/setproxy @Nemesiux @Ghost", state)
        assert state["players"][f"{_PID}:Nemesiux"]["played_by"] == "Ghost"
        assert "not on Kibwe's roster" in sent[0]

    def test_self_proxy_is_refused(self, monkeypatch):
        # ⛔ It would resolve to the seat's own time while displaying
        # "[played by @them]", a no-op that looks like protection.
        state = _state(_seat("Horia", "Nemesiux", 28.84))
        _, sent = self._run_cmd(
            monkeypatch, "/setproxy @Nemesiux @Nemesiux", state)
        assert "cannot be their own proxy" in sent[0]
        assert "played_by" not in state["players"][f"{_PID}:Nemesiux"]

    def test_an_unknown_player_is_reported(self, monkeypatch):
        state = _state(_seat("Anthony", "MrNegetZ", 1.55))
        _, sent = self._run_cmd(
            monkeypatch, "/setproxy @Nobody @MrNegetZ", state)
        assert "not found" in sent[0]

    def test_wrong_argument_count_shows_usage(self, monkeypatch):
        state = _state(_seat("Horia", "Nemesiux", 1))
        _, sent = self._run_cmd(monkeypatch, "/setproxy @Nemesiux", state)
        assert "Usage:" in sent[0]

    def test_the_command_is_reachable_from_the_gm_dispatcher(self):
        # ⛔ Proven is not reachable. Without this, cmd_proxy could be
        # perfect and never wired to a slash command anybody can type.
        import inspect
        from dispatch import cmd_gm
        source = inspect.getsource(cmd_gm)
        assert "/setproxy" in source and "handle_proxy" in source

    def test_both_commands_are_in_the_help(self):
        from dispatch.help_text import _HELP_TEXT
        assert "/setproxy" in _HELP_TEXT and "/clearproxy" in _HELP_TEXT
