"""`cmd_gm.handle` must not depend on what its caller happens to pass.

2026-09-02, found while double-checking the merge fix, and the one I
nearly shipped a false claim about.

`/setpermanent` compared the **raw** pid against a player record's
`pbp_topic_id`, and records are keyed on a campaign's **first** pbp
topic. I wrote that up as *"17 topics affected across every campaign"*,
having listed every secondary and chat topic in the live config.

⛔⛔ **That number was wrong, and only tracing the caller showed it.**
Both callers already canonicalise:

- `parsing/message.py:50` → `pid = maps.to_canonical[thread_id_str]`,
  and line 46 rejects any thread that is not a pbp topic at all, so the
  chat topics in my list could never reach a handler in the first place.
- `dispatch/bot_topic.py` resolves via `maps.name_to_pid` / `to_name`,
  both canonical-keyed.

So the reachable blast radius was **zero topics**. The fix stays, moved
to a single call at the top of `handle()`, because four branches
canonicalised by hand and seven did not, and I had written `/setproxy`
the day before by copying the shape of one that did not. These tests
pin it so a future caller passing a raw thread id cannot silently break
`/setpermanent`.

⭐ **Counting things in the config is not measuring the code.** A number
that large should have made me ask which of those topics can actually
deliver a message here.

⚠️ Tracing that caller turned up a real crash next door, in the same
`handle()`. It has moved out with its own tests to
`test_bot_topic_supplies_a_parsed_message.py`. The `uid not in gm_ids`
ordering it exposed is asserted at the bottom of THIS file, because
that ordering is cmd_gm's property rather than the bot topic's.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from dispatch.cmd_gm import _canonical_pid

# C06 Kibwe: primary PBP, secondary COMBAT thread, and the chat topic.
_PRIMARY, _SECONDARY, _CHAT = "40585", "137075", "21528"

_CONFIG = {"group_id": -100, "gm_user_ids": [999], "topic_pairs": [
    {"name": "Kibwe", "code": "C06", "chat_topic_id": int(_CHAT),
     "pbp_topic_ids": [int(_PRIMARY), int(_SECONDARY)]}]}


def _state(**extra):
    seat = {"user_id": "u1", "first_name": "Horia", "username": "Nemesiux",
            "campaign_name": "Kibwe", "pbp_topic_id": _PRIMARY,
            "last_post_time": "2026-09-01T00:00:00+00:00",
            "last_warned_week": 0}
    seat.update(extra)
    return {"players": {f"{_PRIMARY}:u1": seat}, "removed_players": {},
            "characters": {}, "away": {}}


def _run(monkeypatch, text, pid, state, campaign_name="Kibwe"):
    import telegram as tg
    from dispatch import cmd_gm
    sent = []
    monkeypatch.setattr(tg, "send_message",
                        lambda g, t, b, **k: sent.append(b) or True)
    cmd_gm.handle({"text": text, "parsed": {"raw_text": text},
                   "cmd_word": text.split()[0],
                   "user_id": 999, "gm_ids": {999}, "pid": pid,
                   "group_id": -100, "thread_id": int(pid), "state": state,
                   "config": _CONFIG, "campaign_name": campaign_name,
                   "now_iso": "2026-09-02T12:00:00+00:00"})
    return sent


class TestCanonicalisation:
    def test_a_secondary_topic_maps_to_the_primary(self):
        assert _canonical_pid(_SECONDARY, _CONFIG) == _PRIMARY

    def test_the_chat_topic_maps_to_the_primary(self):
        assert _canonical_pid(_CHAT, _CONFIG) == _PRIMARY

    def test_the_primary_maps_to_itself(self):
        assert _canonical_pid(_PRIMARY, _CONFIG) == _PRIMARY

    def test_an_unknown_topic_is_returned_unchanged(self):
        # can-fail counterpart: it must not silently rewrite a pid that
        # belongs to no campaign into some arbitrary campaign's.
        assert _canonical_pid("999999", _CONFIG) == "999999"


@pytest.mark.parametrize("pid,where", [(_PRIMARY, "the primary PBP topic"),
                                       (_SECONDARY, "a secondary thread"),
                                       (_CHAT, "the campaign chat topic")])
class TestSetPermanentWorksAnywhere:
    def test_it_finds_the_player(self, monkeypatch, pid, where):
        state = _state()
        sent = _run(monkeypatch, "/setpermanent @Nemesiux", pid, state)
        assert state["players"][f"{_PRIMARY}:u1"].get("permanent") is True, (
            f"/setpermanent failed in {where}; it must not depend on the "
            f"caller having canonicalised the pid for it")
        assert sent and "not found" not in sent[0]

    def test_unset_works_there_too(self, monkeypatch, pid, where):
        state = _state(permanent=True)
        _run(monkeypatch, "/unsetpermanent @Nemesiux", pid, state)
        assert "permanent" not in state["players"][f"{_PRIMARY}:u1"]

    def test_the_reply_names_the_campaign_the_pid_resolved_to(
            self, monkeypatch, pid, where):
        # ⛔ The pid and the name are TWO values, and only the pid was
        # asserted, so canonicalising the pid while keeping the caller's
        # campaign_name survived the mutation harness. A GM would be told
        # the change landed in whatever campaign the caller named, which
        # is the one thing they cannot verify from the reply.
        state = _state()
        sent = _run(monkeypatch, "/setpermanent @Nemesiux", pid, state,
                    campaign_name="Some Other Campaign")
        assert sent and "Kibwe" in sent[0], (
            f"reply in {where} named the caller's campaign, not the one "
            f"the pid actually resolved to: {sent}")


@pytest.mark.parametrize("pid", [_PRIMARY, _SECONDARY, _CHAT])
class TestSetProxyWorksAnywhere:
    def test_it_finds_the_player(self, monkeypatch, pid):
        # ⚠️ I wrote /setproxy the day before by copying the shape of
        # the broken /setpermanent, and inherited the same defect.
        state = _state()
        state["players"][f"{_PRIMARY}:u2"] = {
            "user_id": "u2", "first_name": "Anthony", "username": "MrNegetZ",
            "campaign_name": "Kibwe", "pbp_topic_id": _PRIMARY,
            "last_post_time": "2026-09-02T00:00:00+00:00",
            "last_warned_week": 0}
        _run(monkeypatch, "/setproxy @Nemesiux @MrNegetZ", pid, state)
        assert state["players"][f"{_PRIMARY}:u1"].get("played_by") == "MrNegetZ"

    def test_clearproxy_works_there_too(self, monkeypatch, pid):
        state = _state(played_by="MrNegetZ")
        _run(monkeypatch, "/clearproxy @Nemesiux", pid, state)
        assert "played_by" not in state["players"][f"{_PRIMARY}:u1"]


class TestRawTextIsStillTheRawText:
    def test_scene_keeps_the_case_the_gm_typed(self, monkeypatch):
        # ⛔ `text` is lowercased; only `parsed["raw_text"]` carries case.
        # A "defensive" `raw_text = ctx.get("text")` fallback would pass
        # every other test in this file and quietly title-case nothing,
        # writing "the docks at midnight" into the transcript.
        state = _state()
        _run(monkeypatch, "/scene The Docks at Midnight", _PRIMARY, state)
        assert state["current_scenes"][_PRIMARY] == "The Docks at Midnight"


class TestTheAuthGateComesFirst:
    def test_a_non_gm_is_refused(self, monkeypatch):
        import telegram as tg
        from dispatch import cmd_gm
        monkeypatch.setattr(tg, "send_message", lambda *a, **k: True)
        state = _state()
        handled = cmd_gm.handle({"text": "/setpermanent @Nemesiux",
                                 "parsed": {"raw_text": "/setpermanent @Nemesiux"},
                                 "cmd_word": "/setpermanent",
                                 "user_id": 12345, "gm_ids": {999},
                                 "pid": _PRIMARY, "group_id": -100,
                                 "thread_id": 1, "state": state,
                                 "config": _CONFIG, "campaign_name": "Kibwe",
                                 "now_iso": "2026-09-02T12:00:00+00:00"})
        assert handled is False
        assert "permanent" not in state["players"][f"{_PRIMARY}:u1"]

    def test_it_needs_nothing_but_the_two_auth_keys(self, monkeypatch):
        # ⭐ The ordering, asserted as a property rather than by reading
        # line numbers: a ctx holding ONLY user_id and gm_ids must be
        # enough to refuse. Any lookup that creeps back above the gate
        # turns this into a KeyError.
        from dispatch import cmd_gm
        assert cmd_gm.handle({"user_id": 12345, "gm_ids": {999}}) is False
