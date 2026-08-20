"""A command in the menu that nothing handles must fail the build.

A Telegram command has to be registered in FOUR independent places, and
missing any one of them fails silently in a different way:

  set_commands.py        BotFather menu. Missing: nobody discovers it.
  dispatch/router.py     _READ_CMDS. Missing: from the bot topic it falls
                         through to "non-read commands not allowed" and
                         does nothing at all.
  dispatch/bot_topic.py  no_campaign set. Missing: a cross-campaign
                         command demands a campaign it cannot use, or
                         answers into the in-character thread.
  a handler              Missing: the menu makes it tappable and tapping
                         it does nothing.

⛔ **Every one of those failures is silent.** The command appears in the
menu, the user taps it, and nothing happens. There is no error, no log
line, and no test failure. It happened on 2026-08-14 to three of the four
roster commands, which sat in BotFather and in a handler while being in
neither of the two dispatch sets. The comment recording that is still in
router.py.

This test is the guard that was missing. It reads the registries as data
rather than trusting anyone to remember all four.

⚠️ It deliberately does NOT try to prove the handler produces the right
output. It proves REACHABILITY, which is the property that was silently
absent. See ``a-guard-nothing-invokes``: proven and reachable are
different questions.
"""

import re
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent

# Commands deliberately handled outside the read-command path: they are
# writes, polls, or callbacks with their own dispatch. Listed explicitly
# so that adding a command never lands here by accident.
NOT_READ_COMMANDS = {"/pause", "/resume", "/scene", "/event", "/setchar"}


def _menu_commands() -> set:
    """Commands advertised to Telegram, from set_commands.py."""
    text = (SCRIPTS / "set_commands.py").read_text(encoding="utf-8")
    return {f"/{m}" for m in re.findall(r'^\s*\("([a-z]+)",\s*"', text,
                                        re.MULTILINE)}


def _router_read_commands() -> set:
    text = (SCRIPTS / "dispatch" / "router.py").read_text(encoding="utf-8")
    block = text.split("_READ_CMDS = frozenset({", 1)[1].split("})", 1)[0]
    return set(re.findall(r'"(/[a-z]+)"', _strip_comments(block)))


def _bot_topic_global_commands() -> set:
    text = (SCRIPTS / "dispatch" / "bot_topic.py").read_text(encoding="utf-8")
    block = text.split("no_campaign = {", 1)[1].split("}", 1)[0]
    return set(re.findall(r'"(/[a-z]+)"', _strip_comments(block)))


def _strip_comments(block: str) -> str:
    """⚠️ A commented-out command is not a registered one.

    Without this, the long explanatory comments in these files would count
    as registrations and the guard would pass for the wrong reason.
    See ``a-comment-is-not-a-caller``.
    """
    return "\n".join(line.split("#", 1)[0] for line in block.splitlines())


def _without_registry_blocks(body: str) -> str:
    """Drop the two permission sets, so they cannot count as handlers.

    ⚠️ Without this the general guard is vacuous: every command is listed
    in ``_READ_CMDS``, so "does any dispatch file mention it" would be
    true for all of them and the test would pass no matter what.
    """
    for opener, closer in (("_READ_CMDS = frozenset({", "})"),
                           ("no_campaign = {", "}")):
        if opener in body:
            head, rest = body.split(opener, 1)
            body = head + rest.split(closer, 1)[1]
    return body


def _handled_commands() -> set:
    """Every command some dispatch module actually acts on.

    Covers both idioms in this codebase: ``cmd == "/x"`` (and the ``in``
    tuple/set forms) and ``text.startswith("/x")``. Missing the second one
    reported 55 working commands as orphans on the first attempt, which is
    how I learned the parser was wrong rather than the code.
    """
    found = set()
    # Handlers are not all under dispatch/: combat commands live in
    # combat/tracker.py and /markdone in commands/markdone.py. Scanning
    # only dispatch/ reported those five as orphans.
    paths = [p for folder in ("dispatch", "combat", "commands")
             for p in (SCRIPTS / folder).glob("*.py")]
    for path in paths:
        body = _without_registry_blocks(
            _strip_comments(path.read_text(encoding="utf-8")))
        # Both == and !=: commands/markdone.py opens with the guard clause
        # `if cmd != "/markdone": return`, which is every bit a handler.
        found |= set(re.findall(r'[=!]=\s*"(/[a-z]+)"', body))
        found |= set(re.findall(r'startswith\(\s*"(/[a-z]+)"', body))
        for group in re.findall(r'\bin\s+[({]([^)}]*)[)}]', body):
            found |= set(re.findall(r'"(/[a-z]+)"', group))
    return found


RECRUIT = {"/recruitads", "/recruityield", "/recruitposted", "/recruitjoined"}


class TestTheRegistriesAgree:
    def test_the_parsers_find_something(self):
        # ⭐ Without this, a regex that silently matched nothing would make
        # every test below pass against empty sets. The guard would be
        # perfectly green and checking nothing at all.
        assert len(_menu_commands()) > 20
        assert len(_router_read_commands()) > 20
        assert len(_bot_topic_global_commands()) > 5
        assert len(_handled_commands()) > 20

    @pytest.mark.parametrize("cmd", sorted(RECRUIT))
    def test_recruitment_commands_reached_every_registry(self, cmd):
        # The commands added 2026-08-20, pinned individually so a failure
        # names the one that was missed.
        assert cmd in _menu_commands(), f"{cmd} missing from set_commands.py"
        assert cmd in _router_read_commands(), f"{cmd} missing from _READ_CMDS"
        assert cmd in _bot_topic_global_commands(), f"{cmd} missing from no_campaign"
        assert cmd in _handled_commands(), f"{cmd} has no handler"

    def test_every_menu_command_has_a_handler_or_is_declared_a_write(self):
        # ⭐⭐ The general guard. Any future command that reaches BotFather
        # without a handler fails here instead of doing nothing forever.
        orphans = sorted(_menu_commands() - _handled_commands()
                         - NOT_READ_COMMANDS)
        assert not orphans, (
            f"advertised in the menu but no dispatch module handles them: "
            f"{orphans}")


class TestStripComments:
    def test_a_commented_out_command_does_not_count(self):
        assert "/ghost" not in _strip_comments('  # "/ghost",\n  "/real",')

    def test_a_real_one_survives(self):
        assert "/real" in _strip_comments('  # "/ghost",\n  "/real",')
