"""A report must name the message, not just its ID.

COVERS  ``posting.message_facts`` — all four sources, their precedence,
        and the one_line renderer.
MISSES  whether the transcript archive is complete. If the bot never
        ingested a message it cannot describe it, and that is exactly
        what the ``unknown`` verdict is for.
PROVEN  by ``test_the_lookup_can_fail``.

────────────────────────────────────────────────────────────────────────

Lewis, 2026-08-16: *"You should capture the message's contents and sender
so you know if it is an issue."*

A bare ``mid=169479`` cannot be triaged, and worse, it flattens the one
distinction the delete guard exists to draw:

  * a stale bot post nobody will miss, and
  * **the bot reaching for a player's message**

The second is the reason ``perform_guarded_delete`` was written. Under
the old alert format both arrived looking identical, so the alert was
structurally unable to report its own most important finding.

⭐ ``unknown`` is the loud verdict, not the quiet one. An ID that no
local record recognises means something asked the bot to delete a message
it has never seen — which is stranger than either normal case.
"""
from unittest.mock import patch

import pytest

from posting import message_facts as mf
from posting.message_facts import BOT, PLAYER, UNKNOWN, describe, one_line

TRANSCRIPT = """# Kibwe — 2026-08

**Ryo Yamakawa** (2026-08-15 07:51:12) msg#172171@40585:
"Next. Next we stop those psychos and protect our city."

**Path Wars** [GM] (2026-08-01 06:34:08) msg#169589@137075:
Are you moved...?
"""


@pytest.fixture
def archive(tmp_path, monkeypatch):
    camp = tmp_path / "Kibwe"
    camp.mkdir()
    (camp / "2026-08.md").write_text(TRANSCRIPT, encoding="utf-8")
    monkeypatch.setattr(mf, "_LOGS", tmp_path)
    monkeypatch.setattr(mf, "_QUEUES", tmp_path / "nope")
    monkeypatch.setattr(mf, "_sent_describe", lambda mid: None)
    monkeypatch.setattr("posting.bot_sent_registry.is_bot_sent",
                        lambda mid: False)
    return tmp_path


# ── Naming a player message ──────────────────────────────────────────────────

def test_a_player_message_is_named_and_quoted(archive):
    facts = describe(172171)
    assert facts["origin"] == PLAYER
    assert facts["sender"] == "Ryo Yamakawa"
    assert "stop those psychos" in facts["preview"]
    assert facts["campaign"] == "Kibwe"
    assert facts["thread_id"] == 40585


def test_the_gm_tag_is_preserved(archive):
    facts = describe(169589)
    assert facts["is_gm"] is True
    assert facts["sender"] == "Path Wars"


def test_one_line_is_readable(archive):
    line = one_line(172171)
    assert "Ryo Yamakawa" in line and "Kibwe" in line
    assert "stop those psychos" in line


# ── The verdict that matters ─────────────────────────────────────────────────

def test_an_unrecognised_id_is_loud_not_quiet(archive):
    """The point of the unknown verdict. Something asked the bot to
    delete a message no local record has ever seen."""
    facts = describe(999999999)
    assert facts["origin"] == UNKNOWN
    assert "no local record" in one_line(999999999)


def test_a_registry_id_with_no_text_is_still_known_to_be_ours(tmp_path,
                                                              monkeypatch):
    """Weakest source, decisive question.

    Without it, every message sent before sent_log existed would read as
    unrecognised — and 'unknown' would stop meaning anything, because the
    genuinely alarming case would drown in harmless ones.
    """
    monkeypatch.setattr(mf, "_LOGS", tmp_path / "none")
    monkeypatch.setattr(mf, "_QUEUES", tmp_path / "none")
    monkeypatch.setattr(mf, "_sent_describe", lambda mid: None)
    monkeypatch.setattr("posting.bot_sent_registry.is_bot_sent",
                        lambda mid: True)
    facts = describe(170029)
    assert facts["origin"] == BOT
    assert facts["source"] == "bot_sent_registry"


# ── Precedence ───────────────────────────────────────────────────────────────

def test_the_send_log_wins_over_everything(archive, monkeypatch):
    """The bot's own record of what it sent is definitive for bot
    messages, and must not be overridden by a coincidental match."""
    monkeypatch.setattr(mf, "_sent_describe", lambda mid: {
        "at": "2026-08-15T07:00:00+00:00", "thread_id": 40585,
        "kind": "message", "preview": "Unreplied: 2"})
    facts = describe(172171)
    assert facts["origin"] == BOT
    assert facts["preview"] == "Unreplied: 2"


def test_queue_state_names_a_message_the_archive_missed(tmp_path,
                                                        monkeypatch):
    """Third source. The transcript archive rolls monthly and a very
    recent message may not be in it yet."""
    import json
    q = tmp_path / "queues"
    q.mkdir()
    (q / "40585.json").write_text(json.dumps({"unreplied": [
        {"message_id": 555, "user_name": "Anthony", "time": "2026-08-16",
         "preview": "Daichi tightens the rope", "thread_id": 40585}]}),
        encoding="utf-8")
    monkeypatch.setattr(mf, "_LOGS", tmp_path / "none")
    monkeypatch.setattr(mf, "_QUEUES", q)
    monkeypatch.setattr(mf, "_sent_describe", lambda mid: None)
    facts = describe(555)
    assert facts["origin"] == PLAYER
    assert facts["sender"] == "Anthony"
    assert "tightens the rope" in facts["preview"]


# ── Robustness ───────────────────────────────────────────────────────────────

def test_a_missing_archive_does_not_raise(tmp_path, monkeypatch):
    monkeypatch.setattr(mf, "_LOGS", tmp_path / "absent")
    monkeypatch.setattr(mf, "_QUEUES", tmp_path / "absent")
    monkeypatch.setattr(mf, "_sent_describe", lambda mid: None)
    monkeypatch.setattr("posting.bot_sent_registry.is_bot_sent",
                        lambda mid: False)
    assert describe(1)["origin"] == UNKNOWN


def test_an_id_that_is_a_prefix_of_another_does_not_match(archive):
    """msg#17217 must not match msg#172171. An off-by-one here would
    attribute one player's words to another, which is worse than saying
    nothing at all."""
    assert describe(17217)["origin"] == UNKNOWN


# ── PROVE the lookup can fail ────────────────────────────────────────────────

def test_the_lookup_can_fail(archive, monkeypatch):
    """Point the archive at nothing and confirm a known ID goes unknown.

    If this passes while the archive is empty, describe() is reading
    something other than what the tests above think it is.
    """
    monkeypatch.setattr(mf, "_LOGS", archive / "does-not-exist")
    assert describe(172171)["origin"] == UNKNOWN, (
        "With no archive the player message must be unrecognised. If it "
        "is still named, the tests above are not exercising the "
        "transcript path.")
