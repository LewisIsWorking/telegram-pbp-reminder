"""A delete failure on someone else's message must not look routine.

COVERS  the severity split in ``refusal_alert._registry_section`` and the
        message description carried into both sections.
MISSES  whether the escalated case is real. That is
        ``posting.message_facts``'s job and is tested in
        ``test_message_facts.py``; here the facts are injected.
PROVEN  by ``test_a_refusal_on_a_bot_message_stays_calm``, which is the
        counterpart that fails if everything escalates.

Split from ``test_alert_names_the_right_cause.py`` on 2026-08-16 at 203
lines. That file owns *which cause* an alert reports; this one owns *how
loudly*. They came from the same request and are two questions.

Lewis: *"You should capture the message's contents and sender so you know
if it is an issue."* A bare ``mid=`` cannot answer that. Worse, it makes
the guard's most important finding — the bot reaching for a player's
message — indistinguishable from routine bookkeeping.
"""
from unittest.mock import patch

from posting.refusal_log import REASON_REGISTRY, REASON_UNDELETABLE
from refusal_alert import _format_alert


def _entry(mid, reason=None, ts="2026-08-16T12:52:36+00:00"):
    return {"timestamp": ts, "chat_id": -1001661053273,
            "message_id": mid, "reason": reason}


def _facts(origin, sender="somebody", preview="hello"):
    return {"origin": origin, "sender": sender, "preview": preview,
            "campaign": "Kibwe", "thread_id": 40585, "when": None,
            "source": "test"}


def test_a_refusal_on_a_player_message_escalates():
    """The single most important thing this alert can say.

    A registry refusal on a bot message is bookkeeping. On a player's
    message it is the guard stopping what it was built to stop, and the
    two must not look alike — which under the bare-mid format they did.
    """
    with patch("refusal_alert.describe",
               return_value=_facts("player", "Ryo Yamakawa", "Next. Next")):
        text = _format_alert([_entry(172171, REASON_REGISTRY)], "abc")
    assert "🚨" in text
    assert "NOT sent by the bot" in text
    assert "Ryo Yamakawa" in text, "name the sender; 'a player' is not triage"
    assert "Next. Next" in text


def test_a_refusal_on_a_bot_message_stays_calm():
    """The positive counterpart. Escalating everything is the same as
    escalating nothing, and this alert already cried wolf once today."""
    with patch("refusal_alert.describe", return_value=_facts("bot")):
        text = _format_alert([_entry(999, REASON_REGISTRY)], "abc")
    assert "🚨" not in text
    assert "all are bot messages" in text


def test_an_unknown_message_escalates_too():
    """An ID no local record recognises is stranger than either normal
    case, so it must not fall into the quiet branch by default."""
    with patch("refusal_alert.describe",
               return_value=_facts("unknown", None, "")):
        text = _format_alert([_entry(4242, REASON_REGISTRY)], "abc")
    assert "🚨" in text


def test_undeletable_entries_carry_their_text():
    """It is how Lewis decides whether a stranded post is worth the walk."""
    with patch("refusal_alert.describe",
               return_value=_facts("bot", preview="Unreplied: 2")):
        text = _format_alert([_entry(170029, REASON_UNDELETABLE)], "abc")
    assert "Unreplied: 2" in text
    assert "https://t.me/Path_Wars/170029" in text


