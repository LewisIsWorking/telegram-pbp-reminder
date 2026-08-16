"""An alert must name the cause it actually observed.

COVERS  ``refusal_alert._format_alert`` grouping, both section
        renderers, the legacy-entry fallback, and that
        ``stuck_deletes`` tags its give-ups as undeletable.
MISSES  whether the wording is *useful*. A human reads that; a test
        can only check the claim is true.
PROVEN  by ``test_the_guard_can_fail``.

────────────────────────────────────────────────────────────────────────

2026-08-16, in production. The alert Lewis received:

    ⚠️ Delete refusals: 11 message(s) refused since last alert
    Each entry below is a delete that tg.delete_message refused because
    the message_id was not in the bot-sent registry.

**All eleven IDs were in the registry.** They were give-ups from
``stuck_deletes`` — messages Telegram will not remove because they are
over 48h old — routed through ``record_refusal`` because it was the
existing alert channel. The transport was reusable. The explanation was
not, and it pointed at a bug that did not exist while hiding a chore
that did: eleven messages needing manual deletion.

⭐ The two classes need **opposite** responses. ``registry`` means the
code is wrong and someone must debug it. ``undeletable`` means the code
is right and someone must tap delete. An alert that cannot tell them
apart is worse than none, because it spends the reader's attention in
the wrong place.
"""
from unittest.mock import patch

import pytest

import refusal_alert
from posting.refusal_log import REASON_REGISTRY, REASON_UNDELETABLE
from refusal_alert import _format_alert


def _entry(mid, reason=None, ts="2026-08-16T12:52:36+00:00"):
    e = {"timestamp": ts, "chat_id": -1001661053273, "message_id": mid}
    if reason:
        e["reason"] = reason
    return e


def _facts(origin, sender="somebody", preview="hello"):
    return {"origin": origin, "sender": sender, "preview": preview,
            "campaign": "Kibwe", "thread_id": 40585, "when": None,
            "source": "test"}


# ── The bug ──────────────────────────────────────────────────────────────────

def test_give_ups_are_not_called_registry_refusals():
    """The exact regression. This wording went out for 11 messages."""
    text = _format_alert([_entry(170060, REASON_UNDELETABLE)], "abc123")
    assert "not in the bot-sent registry" not in text
    assert "does not list" not in text


def test_give_ups_say_a_human_must_act():
    """The reader's next action must be in the message."""
    text = _format_alert([_entry(170060, REASON_UNDELETABLE)], "abc123")
    assert "ONLY A HUMAN" in text
    assert "https://t.me/Path_Wars/170060" in text, (
        "an undeletable entry is a chore; give the link that completes it")
    assert "not a code fault" in text


def test_registry_refusals_still_say_investigate():
    """The positive counterpart. Softening both classes into one polite
    non-statement would pass every assertion above."""
    with patch("refusal_alert.describe", return_value=_facts("bot")):
        text = _format_alert([_entry(999, REASON_REGISTRY)], "abc123")
    assert "docs/dev/delete-safety.md" in text
    assert "ONLY A HUMAN" not in text


# ── Grouping ─────────────────────────────────────────────────────────────────

def test_mixed_causes_are_reported_separately():
    """A batch containing both must not collapse to one explanation."""
    text = _format_alert(
        [_entry(999, REASON_REGISTRY), _entry(170060, REASON_UNDELETABLE)],
        "abc123")
    assert "Registry refusals: 1" in text
    assert "Undeletable: 1" in text
    assert "Delete failures: 2" in text


def test_legacy_entries_without_a_reason_read_as_registry():
    """Every entry written before 2026-08-16 was a registry refusal, so
    the fallback must say so rather than dropping them silently."""
    text = _format_alert([_entry(999)], "abc123")
    assert "Registry refusals: 1" in text
    assert "mid=999" in text


def test_an_unknown_reason_still_reports_the_message():
    """A future reason with no renderer must not vanish from the alert.
    Falling back is acceptable; silence is not."""
    text = _format_alert([_entry(555, "some-future-reason")], "abc123")
    assert "555" in text


def test_long_lists_are_truncated_but_say_so():
    entries = [_entry(1000 + i, REASON_UNDELETABLE) for i in range(30)]
    text = _format_alert(entries, "abc123")
    assert "Undeletable: 30" in text
    assert "and 5 more" in text
    assert "audit_orphans.py" in text


# ── The producer tags correctly ──────────────────────────────────────────────

def test_stuck_deletes_tags_its_give_ups(tmp_path, monkeypatch):
    """The renderer is only right if the writer supplies the reason."""
    from posting import stuck_deletes
    from state_store import StateStore
    monkeypatch.setattr(stuck_deletes, "_store",
                        StateStore(state_dir=tmp_path))
    stuck_deletes.reset_for_test()
    with patch("posting.stuck_deletes.record_refusal") as rec:
        for _ in range(stuck_deletes.MAX_ATTEMPTS):
            stuck_deletes.note_failed_delete(-1001, 170060)
    assert rec.call_args.kwargs["reason"] == REASON_UNDELETABLE


def test_registry_refusal_keeps_the_default_reason(tmp_path, monkeypatch):
    """safe_delete's own refusal path must stay tagged as registry."""
    from posting import safe_delete
    monkeypatch.setattr(safe_delete, "is_bot_sent", lambda mid: False)
    with patch.object(safe_delete, "record_action"), \
            patch.object(safe_delete, "record_refusal") as rec:
        safe_delete.perform_guarded_delete(-1001, 12345, lambda *a, **k: None)
    # Called positionally with no reason -> default applies.
    assert "reason" not in rec.call_args.kwargs


# ── PROVE the guard can fail ─────────────────────────────────────────────────

def test_the_guard_can_fail(monkeypatch):
    """Restore the single-cause renderer and confirm the tests go red.

    Before the fix every entry rendered with the registry wording
    regardless of reason. Pointing both sections at the registry
    renderer reproduces that exactly.
    """
    monkeypatch.setitem(refusal_alert._SECTIONS, REASON_UNDELETABLE,
                        refusal_alert._registry_section)
    with patch("refusal_alert.describe", return_value=_facts("bot")):
        text = _format_alert([_entry(170060, REASON_UNDELETABLE)], "abc123")
    assert "does not list" in text, (
        "With the single-cause renderer restored the give-up must be "
        "mislabelled. If this fails, _format_alert no longer dispatches "
        "on reason and the tests above prove nothing.")
    assert "https://t.me/Path_Wars/170060" not in text
