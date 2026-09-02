"""Every handler the bot topic invokes must get a usable ``parsed``.

Found 2026-09-02. ``dispatch/bot_topic.py`` built its ctx by hand with
``"parsed": None``, because there is no Telegram message to parse in
that topic. **Seven handlers in ``_HANDLERS`` open with
``parsed["raw_text"]`` before they check their own command word**:
cmd_gm, cmd_trackers, cmd_trackers_items, cmd_conditions_hp, cmd_clocks,
cmd_votes_timers, cmd_player.

So any bot-topic command that reached the chain raised
``TypeError: 'NoneType' object is not subscriptable``, and router.py's
``except Exception: print(...)`` turned that into **silence**. The GM
taps a command that is in the Telegram menu and nothing happens, which
is indistinguishable from the bot being down. bot_topic.py already
carries a comment about that exact failure mode from a 2026-08-14 bug.

Only `/markdone` actually got that far: a bot-topic command must pass
cmd_info and cmd_info_ext first, and it is the one read command handled
by the **last** entry in ``_HANDLERS``.

⭐ Found by driving all 46 commands in ``_READ_CMDS`` through the real
``handle_bot_topic_cmd``, not by reading the code. Fixing cmd_gm alone
just moved the identical crash to cmd_trackers, which is the whole
lesson: **the fix was owed at the source, once, not at seven call
sites.**

⚠️ The subscript also sat **above** ``if uid not in gm_ids``, so it
crashed for non-GMs too. That gate is now the first thing cmd_gm does;
the ordering is asserted in test_gm_commands_work_in_every_topic.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

_PRIMARY, _SECONDARY = "40585", "137075"

_CONFIG = {"group_id": -100, "gm_user_ids": [999], "bot_topic_id": 7,
           "topic_pairs": [
               {"name": "Kibwe", "code": "C06", "chat_topic_id": 21528,
                "pbp_topic_ids": [int(_PRIMARY), int(_SECONDARY)]}]}


def _state():
    return {"players": {}, "removed_players": {}, "characters": {},
            "away": {}}


def _bot_topic(monkeypatch, cmd, uid=999):
    """Drive the real bot-topic path, and REPORT which handlers ran.

    ⛔⛔ The reachability half is not decoration. My first version of
    these tests used ``/markdone Kibwe 1``, which ``resolve_campaign``
    could not parse at the time, so the command bounced off "Specify a
    campaign" and never reached a handler at all. Both tests passed, and
    the mutation restoring the crash **survived them**. A test that only
    asserts "nothing raised" cannot tell "the bug is fixed" apart from
    "the code never ran".
    """
    import telegram as tg
    from dispatch.bot_topic import handle_bot_topic_cmd
    from dispatch.router import _READ_CMDS, _HANDLERS
    from helpers import build_topic_maps
    sent, reached = [], []
    monkeypatch.setattr(tg, "send_message",
                        lambda g, t, b, **k: sent.append(b) or True)

    def wrap(h):
        def spy(ctx):
            reached.append((h.__module__, ctx.get("parsed", "<absent>")))
            return h(ctx)
        return spy

    msg = {"message_id": 1, "message_thread_id": 7,
           "chat": {"id": -100}, "date": 1756800000,
           "from": {"id": uid, "first_name": "Lewis"},
           "text": cmd}
    handle_bot_topic_cmd(msg, _CONFIG, _state(), build_topic_maps(_CONFIG),
                         -100, 7, _READ_CMDS, [wrap(h) for h in _HANDLERS])
    return sent, reached


class TestTheChainSurvivesTheBotTopic:
    def test_markdone_in_the_bot_topic_does_not_crash(self, monkeypatch):
        sent, reached = _bot_topic(monkeypatch, "/markdone Kibwe 1")
        assert reached, (
            "no handler was reached at all, so this test is not "
            "exercising the crash it exists for")
        assert sent, "the GM got no reply at all"

    def test_every_handler_reached_can_read_raw_text(self, monkeypatch):
        # ⭐ The actual contract, and the reason the fix is in bot_topic:
        # it holds for EVERY handler the chain invokes, not just the one
        # that happened to crash first.
        _, reached = _bot_topic(monkeypatch, "/markdone Kibwe 1")
        for module, parsed in reached:
            assert isinstance(parsed, dict), (
                f"{module} was handed parsed={parsed!r}")
            assert "raw_text" in parsed, f"{module} got no raw_text"

    def test_raw_text_matches_the_campaign_stripped_command(self, monkeypatch):
        # ⛔ Not just present, but RIGHT. Those handlers slice
        # parsed["raw_text"][N:] by command length, so handing them the
        # message's own text ("/markdone kibwe 1") would leave the
        # campaign name inside every argument they parse.
        _, reached = _bot_topic(monkeypatch, "/markdone Kibwe 1")
        assert reached[0][1]["raw_text"] == "/markdone 1"

    def test_a_non_gm_does_not_crash_it_either(self, monkeypatch):
        # ⚠️ The crash was not gated on authorisation.
        _, reached = _bot_topic(monkeypatch, "/markdone Kibwe 1", uid=12345)
        assert reached


class TestHeroPointClaimsFromTheBotTopic:
    """The one branch of handle_bot_topic_cmd nothing reached.

    ⚠️ Not scope creep: bot_topic.py is a changed file, and the standing
    rule is 100% on changed files. It was also the only branch that
    MUTATES state (`pending_hero_points`) without a test driving it from
    this entry point, which is the shape most worth closing: an untested
    write, not an untested message.
    """

    def _claim(self, monkeypatch, arg, pending=True):
        import telegram as tg
        from dispatch.bot_topic import handle_bot_topic_cmd
        from dispatch.router import _READ_CMDS, _HANDLERS
        from helpers import build_topic_maps
        sent = []
        monkeypatch.setattr(tg, "send_message",
                            lambda g, t, b, **k: sent.append(b) or True)
        state = _state()
        state["players"][f"{_PRIMARY}:999"] = {
            "user_id": "999", "first_name": "Lewis", "username": "Lewis",
            "campaign_name": "Kibwe", "pbp_topic_id": _PRIMARY,
            "last_post_time": "2026-09-01T00:00:00+00:00",
            "last_warned_week": 0}
        if pending:
            state["pending_hero_points"] = {"999": {"name": "Lewis"}}
        msg = {"message_id": 1, "message_thread_id": 7,
               "chat": {"id": -100}, "date": 1756800000,
               "from": {"id": 999, "first_name": "Lewis"},
               "text": f"/heropoint {arg}".strip()}
        handle_bot_topic_cmd(msg, _CONFIG, state, build_topic_maps(_CONFIG),
                             -100, 7, _READ_CMDS, _HANDLERS)
        return sent, state

    def test_naming_the_campaign_claims_the_point(self, monkeypatch):
        sent, state = self._claim(monkeypatch, "Kibwe")
        assert "999" not in state.get("pending_hero_points", {}), (
            "the Hero Point was not consumed, so it can be claimed twice")
        assert any("Kibwe" in m for m in sent)

    def test_naming_no_campaign_prompts_instead_of_claiming(self, monkeypatch):
        # can-fail counterpart: a bare /heropoint must NOT silently spend
        # the point on whichever campaign happens to sort first.
        sent, state = self._claim(monkeypatch, "")
        assert "999" in state.get("pending_hero_points", {}), (
            "a bare /heropoint consumed the point without being told where")
        assert sent

    def test_a_player_with_no_pending_point_is_told_so(self, monkeypatch):
        sent, _ = self._claim(monkeypatch, "Kibwe", pending=False)
        assert sent and "Hero Point" in sent[0]


class TestACampaignArgumentMayCarryTrailingArgs:
    """⛔ The defect that made the tests above hollow, now its own guard."""

    def _maps(self):
        from helpers import build_topic_maps
        return build_topic_maps(_CONFIG)

    def test_a_trailing_argument_still_resolves_the_campaign(self):
        from dispatch.campaign_lookup import resolve_campaign
        maps = self._maps()
        assert resolve_campaign("Kibwe 3", maps) == (_PRIMARY, "Kibwe")
        assert resolve_campaign("Kibwe", maps) == (_PRIMARY, "Kibwe")
        assert resolve_campaign("kib all", maps) == (_PRIMARY, "Kibwe")

    def test_an_argument_naming_no_campaign_resolves_to_nothing(self):
        # can-fail counterpart: the prefix walk must not make every
        # string match something. Answering the WRONG campaign is worse
        # than answering "specify a campaign", because `/markdone all`
        # would then clear a queue nobody named.
        from dispatch.campaign_lookup import resolve_campaign
        maps = self._maps()
        assert resolve_campaign("zzz 3", maps) == (None, None)
        assert resolve_campaign("", maps) == (None, None)

    def test_the_name_is_still_reachable_from_bot_topic(self):
        # ⛔ The body moved out on 2026-09-02; the NAME must not. Several
        # call sites and tests import it from dispatch.bot_topic.
        from dispatch.bot_topic import resolve_campaign as from_bot_topic
        from dispatch.campaign_lookup import resolve_campaign as from_lookup
        assert from_bot_topic is from_lookup
