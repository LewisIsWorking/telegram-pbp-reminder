"""GM-only poll commands: /sessionplayed and /swimmingdone (2026-08-10).

⚠️ These had **zero tests**. ``dispatch/gm_poll_cmds.py`` was 78%
``# pragma: no cover`` — 63 excluded lines covering the entire bodies of
both commands, *including the GM authorisation check*::

    gm_ids = set(str(g) for g in config.get("gm_user_ids", []))  # pragma: no cover
    if user_id not in gm_ids:                                    # pragma: no cover
        tg.send_message(group_id, bot_topic, "❌ GMs only.")      # pragma: no cover

So an auth bypass on these commands was invisible to both the test suite
and the coverage number. Both commands mutate shared state that silences
poll pings for the rest of the week (``session_happened = True``), which
is worth protecting: a non-GM able to set it could quietly switch off
everyone's reminders.

The auth test is written first and deliberately asserts on **both**
halves — that the refusal is sent *and* that the state was not mutated.
Asserting only the message would pass even if the command carried on and
wrote the state anyway.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

_GM = "111"
_PLAYER = "222"
_CFG = {"gm_user_ids": [111]}          # ints in config, str at runtime
_GID, _TOPIC = -100, 5


def _state(code="C11", week_iso="sun2026-04-05", happened=False):
    """State with one active poll. 2026-04-05 is ISO week 14."""
    return {"session_poll": {code: {"week_iso": week_iso,
                                    "session_happened": happened}}}


def _swim_state(week_iso="sun2026-04-05", happened=False):
    return {"swimming_poll": {"week_iso": week_iso,
                              "session_happened": happened}}


def _texts(tg_mock):
    return " ".join(str(c.args[2]) for c in tg_mock.send_message.call_args_list)


class TestWeekNumParsing:
    def test_parses_a_sunday_key(self):
        from dispatch.gm_poll_cmds import poll_week_num
        assert poll_week_num("sun2026-04-05") == 14

    def test_parses_a_saturday_key(self):
        from dispatch.gm_poll_cmds import poll_week_num
        assert poll_week_num("sat2026-04-05") == 14

    def test_bad_input_is_zero_not_a_crash(self):
        from dispatch.gm_poll_cmds import poll_week_num
        assert poll_week_num("nonsense") == 0

    def test_none_is_zero(self):
        from dispatch.gm_poll_cmds import poll_week_num
        assert poll_week_num(None) == 0


class TestSessionPlayedAuth:
    """🔒 The check that had no test at all."""

    def test_non_gm_is_refused_and_changes_nothing(self, tg_mock):
        from dispatch.gm_poll_cmds import handle_sessionplayed
        state = _state()
        handled = handle_sessionplayed("C11 14", _PLAYER, "Mallory",
                                       _CFG, state, _GID, _TOPIC)
        assert handled is True
        assert "GMs only" in _texts(tg_mock)
        # Both halves. Asserting only the message would still pass if the
        # command fell through and wrote the state anyway.
        assert state["session_poll"]["C11"]["session_happened"] is False

    def test_gm_is_allowed(self, tg_mock):
        """Counterweight — proves the refusal test can fail."""
        from dispatch.gm_poll_cmds import handle_sessionplayed
        state = _state()
        handle_sessionplayed("C11 14", _GM, "Lewis",
                             _CFG, state, _GID, _TOPIC)
        assert state["session_poll"]["C11"]["session_happened"] is True
        assert "GMs only" not in _texts(tg_mock)

    def test_gm_ids_compare_as_strings(self, tg_mock):
        """config holds ints, Telegram gives str — the cast must hold."""
        from dispatch.gm_poll_cmds import handle_sessionplayed
        state = _state()
        handle_sessionplayed("C11 14", "111", "Lewis",
                             {"gm_user_ids": [111]}, state, _GID, _TOPIC)
        assert state["session_poll"]["C11"]["session_happened"] is True

    def test_empty_gm_list_refuses_everyone(self, tg_mock):
        from dispatch.gm_poll_cmds import handle_sessionplayed
        state = _state()
        handle_sessionplayed("C11 14", _GM, "Lewis",
                             {}, state, _GID, _TOPIC)
        assert "GMs only" in _texts(tg_mock)
        assert state["session_poll"]["C11"]["session_happened"] is False


class TestSessionPlayedValidation:
    def test_missing_args_shows_usage(self, tg_mock):
        from dispatch.gm_poll_cmds import handle_sessionplayed
        state = _state()
        handle_sessionplayed("C11", _GM, "Lewis", _CFG, state, _GID, _TOPIC)
        assert "Usage:" in _texts(tg_mock)
        assert state["session_poll"]["C11"]["session_happened"] is False

    def test_non_numeric_week_is_rejected(self, tg_mock):
        from dispatch.gm_poll_cmds import handle_sessionplayed
        state = _state()
        handle_sessionplayed("C11 fourteen", _GM, "Lewis",
                             _CFG, state, _GID, _TOPIC)
        assert "must be a number" in _texts(tg_mock)
        assert state["session_poll"]["C11"]["session_happened"] is False

    def test_unknown_code_lists_the_known_ones(self, tg_mock):
        from dispatch.gm_poll_cmds import handle_sessionplayed
        state = _state()
        handle_sessionplayed("C99 14", _GM, "Lewis",
                             _CFG, state, _GID, _TOPIC)
        text = _texts(tg_mock)
        assert "No active poll" in text
        assert "C11" in text, "the error must name what IS available"

    def test_code_is_case_insensitive(self, tg_mock):
        from dispatch.gm_poll_cmds import handle_sessionplayed
        state = _state()
        handle_sessionplayed("c11 14", _GM, "Lewis",
                             _CFG, state, _GID, _TOPIC)
        assert state["session_poll"]["C11"]["session_happened"] is True

    def test_wrong_week_is_refused(self, tg_mock):
        """Guards against silencing a week that is not the active one."""
        from dispatch.gm_poll_cmds import handle_sessionplayed
        state = _state()
        handle_sessionplayed("C11 13", _GM, "Lewis",
                             _CFG, state, _GID, _TOPIC)
        assert "not 13" in _texts(tg_mock)
        assert state["session_poll"]["C11"]["session_happened"] is False


class TestSwimmingDoneAuth:
    def test_non_gm_is_refused_and_changes_nothing(self, tg_mock):
        from dispatch.gm_poll_cmds import handle_swimmingdone
        state = _swim_state()
        handled = handle_swimmingdone("14", _PLAYER, "Mallory",
                                      _CFG, state, _GID, _TOPIC)
        assert handled is True
        assert "GMs only" in _texts(tg_mock)
        assert state["swimming_poll"]["session_happened"] is False

    def test_gm_is_allowed(self, tg_mock):
        from dispatch.gm_poll_cmds import handle_swimmingdone
        state = _swim_state()
        handle_swimmingdone("14", _GM, "Lewis", _CFG, state, _GID, _TOPIC)
        assert state["swimming_poll"]["session_happened"] is True


class TestSwimmingDoneValidation:
    def test_non_numeric_week_shows_usage(self, tg_mock):
        from dispatch.gm_poll_cmds import handle_swimmingdone
        state = _swim_state()
        handle_swimmingdone("soon", _GM, "Lewis", _CFG, state, _GID, _TOPIC)
        assert "Usage:" in _texts(tg_mock)
        assert state["swimming_poll"]["session_happened"] is False

    def test_no_active_poll_is_reported(self, tg_mock):
        from dispatch.gm_poll_cmds import handle_swimmingdone
        state = {"swimming_poll": {}}
        handle_swimmingdone("14", _GM, "Lewis", _CFG, state, _GID, _TOPIC)
        assert "No active swimming poll" in _texts(tg_mock)

    def test_missing_swimming_poll_key_is_reported(self, tg_mock):
        from dispatch.gm_poll_cmds import handle_swimmingdone
        state = {}
        handle_swimmingdone("14", _GM, "Lewis", _CFG, state, _GID, _TOPIC)
        assert "No active swimming poll" in _texts(tg_mock)

    def test_wrong_week_is_refused(self, tg_mock):
        from dispatch.gm_poll_cmds import handle_swimmingdone
        state = _swim_state()
        handle_swimmingdone("13", _GM, "Lewis", _CFG, state, _GID, _TOPIC)
        assert "not 13" in _texts(tg_mock)
        assert state["swimming_poll"]["session_happened"] is False
