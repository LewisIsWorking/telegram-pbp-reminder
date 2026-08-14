"""No command in the Telegram menu may silently do nothing (2026-08-14).

The bug this prevents
---------------------
Lewis tapped ``/rosterplayers`` from the command menu and nothing
happened. Not an error, not a usage message — nothing, which from the
outside is indistinguishable from the bot being down.

``/rosterplayers`` was registered in three of the five places a command
needs to exist:

===================================== ==========================
place                                 had it?
===================================== ==========================
``set_commands.py`` (the menu)        yes — so it was tappable
``dispatch/cmd_info.py`` (handler)    yes
``router._READ_CMDS``                 **no**
``bot_topic.no_campaign``             **no**
``help_text``                         no (nor does /roster)
===================================== ==========================

Missing from the last two meant the bot topic fell through to
``return  # Non-read commands not allowed`` and did nothing, while in a
campaign topic it worked but replied into the in-character pbp thread
instead of the chat topic. Its sibling ``/roster`` was registered
everywhere and behaved correctly, which is what made it look like one
broken command rather than a missing registration.

Why a registration cross-check was not enough
---------------------------------------------
The obvious guard — "every menu command appears in ``_READ_CMDS``" — is
wrong, because write commands legitimately are not read commands. Any
rule stated over the *registries* has to encode which category each
command belongs to, and that mapping is the thing that was wrong in the
first place.

So this asserts the **outcome** instead: send it and see whether the bot
says anything at all. Non-silence is the contract. A read command that
answers passes; a write command that explains where it works passes;
only a command that swallows the message fails. That holds no matter how
the registries are reorganised.

Unrecognised commands must stay silent — other bots share this group,
and answering ``/somethingelse@OtherBot`` would interrupt every one.
"""

import copy
import io
import os
import sys
from contextlib import redirect_stdout

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from set_commands import EVERYONE_COMMANDS, GM_COMMANDS  # noqa: E402

_BOT_TOPIC = 137393
_GROUP = -100
_GM = 1698524397

_CFG = {
    "group_id": _GROUP, "bot_topic_id": _BOT_TOPIC,
    "gm_queue_topic_id": 146780, "gm_user_id": _GM,
    "poll_post_hour": 7, "diagnostic_hour": 8,
    "topic_pairs": [{
        "name": "Doomsday Funtime", "code": "C01", "chat_topic_id": 21514,
        "pbp_topic_ids": [25059], "gm_user_ids": [_GM],
    }],
}


def _menu_commands() -> list[str]:
    return ["/" + name for name, _desc in EVERYONE_COMMANDS + GM_COMMANDS]


def _say(text: str, monkeypatch) -> list[str]:
    """Send ``text`` from the bot topic; return what the bot said back.

    Patches ``telegram.send_message`` on the module object rather than
    per-importer. Every dispatch module does ``import telegram as tg``
    and calls ``tg.send_message``, so one patch covers all of them —
    a hand-listed set of patch targets is how an earlier fixture came to
    assert against a mock the code never touched.

    ``deepcopy``, not ``dict()``. ``DEFAULT_STATE``'s values are mutable
    and a shallow copy aliases every one of them, so a command writing
    ``state["thread_message_counts"][25059]`` mutates the module global
    and every later test in the session inherits it. That is what the
    first draft did: it failed ``test_state_io`` with an int key where a
    round-tripped str key was expected, in a file this one never touches.
    """
    import telegram as tg
    sent: list[str] = []
    monkeypatch.setattr(tg, "send_message",
                        lambda gid, tid, body, **kw: sent.append(body) or True)
    monkeypatch.setattr(tg, "send_message_id", lambda *a, **k: 1)

    import helpers
    from dispatch import router
    from dispatch.bot_topic import handle_bot_topic_cmd
    from state import DEFAULT_STATE

    msg = {"message_id": 1, "date": 1786000000, "chat": {"id": _GROUP},
           "message_thread_id": _BOT_TOPIC,
           "from": {"id": _GM, "first_name": "Lewis", "is_bot": False},
           "text": text}
    with redirect_stdout(io.StringIO()):
        handle_bot_topic_cmd(msg, _CFG, copy.deepcopy(DEFAULT_STATE),
                             helpers.build_topic_maps(dict(_CFG)),
                             _GROUP, _BOT_TOPIC,
                             router._READ_CMDS, router._HANDLERS)
    return sent


class TestDiscovery:
    """If the menu import breaks, this guard silently covers nothing."""

    def test_the_menu_is_populated(self):
        menu = _menu_commands()
        assert len(menu) > 50, (
            f"only {len(menu)} menu commands found — set_commands has "
            f"probably moved, which would make this guard vacuous")

    def test_the_reported_command_is_in_the_menu(self):
        """It being tappable is why silence was a bug and not a typo."""
        assert "/rosterplayers" in _menu_commands()


@pytest.mark.parametrize("cmd", _menu_commands())
def test_advertised_command_is_never_silent(cmd, monkeypatch):
    """Every command in the Telegram menu must answer something."""
    assert _say(cmd, monkeypatch), (
        f"{cmd} is in the Telegram command menu, so it can be tapped, but "
        f"produces no reply at all from the bot topic. Silence is "
        f"indistinguishable from the bot being down.\n"
        f"Either register it (router._READ_CMDS and/or "
        f"bot_topic.no_campaign) so it works, or let it reach the "
        f"_MENU_COMMANDS branch in bot_topic so it says where it does.")


class TestUnknownCommandsStayQuiet:
    """The fix must not turn the bot into an answer-everything bot."""

    def test_another_bots_command_is_ignored(self, monkeypatch):
        assert _say("/deploy@SomeOtherBot now", monkeypatch) == []

    def test_an_unrecognised_command_is_ignored(self, monkeypatch):
        assert _say("/notacommandwehave", monkeypatch) == []

    def test_plain_text_is_ignored(self, monkeypatch):
        assert _say("just talking", monkeypatch) == []


class TestTheRosterFamily:
    """The reported command and its siblings, named so a refactor keeps them."""

    @pytest.mark.parametrize("cmd", ["/roster", "/rostercampaigns",
                                     "/rosterplayers", "/rosterall"])
    def test_answers_from_the_bot_topic(self, cmd, monkeypatch):
        replies = _say(cmd, monkeypatch)
        assert replies, f"{cmd} said nothing"
        assert "needs to know which campaign" not in replies[0], (
            f"{cmd} is cross-campaign and takes no pid — it must answer "
            f"here, not be deflected to a campaign topic")

    @pytest.mark.parametrize("cmd", ["/rostercampaigns", "/rosterplayers",
                                     "/rosterall"])
    def test_survives_the_botname_suffix(self, cmd, monkeypatch):
        """Telegram appends @BotName when a command is tapped in a group."""
        assert _say(f"{cmd}@PathWarsNudgeBot", monkeypatch)

    @pytest.mark.parametrize("cmd", ["/roster", "/rostercampaigns",
                                     "/rosterplayers", "/rosterall"])
    def test_replies_to_the_chat_topic_not_the_pbp_thread(self, cmd,
                                                          monkeypatch):
        """Read commands must not post into the in-character thread."""
        import telegram as tg
        import helpers
        from dispatch import router
        from state import DEFAULT_STATE
        topics: list[int] = []
        monkeypatch.setattr(tg, "send_message",
                            lambda gid, tid, body, **kw: topics.append(tid) or True)
        monkeypatch.setattr(tg, "send_message_id", lambda *a, **k: 1)
        helpers.build_topic_maps(dict(_CFG))
        upd = [{"update_id": 1, "message": {
            "message_id": 9, "date": 1786000000, "chat": {"id": _GROUP},
            "message_thread_id": 25059,
            "from": {"id": _GM, "first_name": "Lewis", "is_bot": False},
            "text": cmd}}]
        with redirect_stdout(io.StringIO()):
            router.process_updates(upd, _CFG, copy.deepcopy(DEFAULT_STATE))
        assert topics and topics[0] == 21514, (
            f"{cmd} replied to {topics or 'nothing'}; 21514 is the chat "
            f"topic, 25059 is the in-character pbp thread")
