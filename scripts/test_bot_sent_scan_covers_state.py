"""Every message-ID state field must be known to the bot-sent scan (2026-08-11).

The bug this prevents
---------------------
I added ``state["schedule_post_msg_id"]`` for the self-replacing schedule
post and did not add it to ``posting/bot_sent_state_scan.py`` — despite
that module's docstring stating the contract explicitly:

    When new fields are added to ``live.json`` ... that store a bot-sent
    message ID, that field should be picked up here so the registry's
    backfill stays accurate.

Consequence: every GitHub Actions run is a fresh checkout, so
``bot_sent_ids.json`` does not survive and the registry rebuilds from
``backfill_from_state``. An ID the scan does not know about is absent
from the registry, so ``perform_guarded_delete`` **refuses** it — doing
exactly what it should — and the previous post is never deleted. The
schedule post stopped replacing itself and accumulated one message every
30 minutes.

The failure is quiet in the worst way: the guard behaved correctly, the
delete was refused for a good reason, and the only visible symptom was
duplicate posts in Telegram hours later.

This guard closes the loop mechanically: any state key ending in
``_msg_id`` (or ``_message_id``) that production code writes must appear
in the scan module. Adding a new one without registering it fails here
rather than in Lewis's topic.
"""

import ast
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

_ROOT = Path(os.path.dirname(__file__))
_SCAN = _ROOT / "posting" / "bot_sent_state_scan.py"

# Keys that look like message ids but are not bot-sent ids the bot deletes.
# Each needs a reason; an unexplained entry here is how this guard would rot.
_NOT_BOT_SENT = {
    # Player/GM message ids recorded for queue tracking — the bot must never
    # delete these, so they must NOT be in the registry.
    "message_id", "reply_to_message_id", "last_message_id",
}


def _state_msg_id_keys() -> set[str]:
    """Every ``state[...]`` / ``slot[...]`` key that looks like a message id.

    Scans production source for string literals ending in ``_msg_id`` or
    ``_message_id`` used as a subscript key.
    """
    found: set[str] = set()
    pattern = re.compile(r'\[\s*["\'](\w*?(?:_msg_id|_message_id))["\']\s*\]')
    for path in _ROOT.rglob("*.py"):
        if path.name.startswith("test_") or path.name == "conftest.py":
            continue
        if "__pycache__" in path.parts:
            continue
        try:
            src = path.read_text(encoding="utf-8")
        except OSError:  # pragma: no cover - unreadable file
            continue
        found.update(pattern.findall(src))
    return found - _NOT_BOT_SENT


class TestScanCoversEveryMessageIdField:
    def test_finds_some_keys_at_all(self):
        """If the regex breaks, the guard silently passes forever."""
        keys = _state_msg_id_keys()
        assert len(keys) >= 2, (
            f"only found {keys} — the source scan has probably broken, which "
            f"would make this guard vacuous")

    def test_schedule_post_msg_id_is_registered(self):
        """The specific field whose omission caused the 2026-08-11 bug."""
        assert "schedule_post_msg_id" in _SCAN.read_text(encoding="utf-8")

    def test_every_discovered_key_is_in_the_scan(self):
        scan_src = _SCAN.read_text(encoding="utf-8")
        missing = sorted(k for k in _state_msg_id_keys() if k not in scan_src)
        assert not missing, (
            f"these message-id state fields are not known to "
            f"posting/bot_sent_state_scan.py: {missing}. The bot cannot "
            f"delete a message whose ID is not in the registry, so a "
            f"self-replacing post using one of these will duplicate instead "
            f"of replacing. Add it to extract_ids_from_live or "
            f"extract_ids_from_queue.")


class TestRegistryRoundTrip:
    """The positive direction — an ID in state must survive a rebuild.

    Coverage of the key name is not enough; what matters is that a fresh
    registry (as every Actions run gets) can actually authorise the delete.
    """

    def test_schedule_id_survives_a_registry_rebuild(self):
        from posting.bot_sent_state_scan import extract_ids_from_live
        assert 4242 in extract_ids_from_live({"schedule_post_msg_id": 4242})

    def test_absent_field_yields_nothing(self):
        from posting.bot_sent_state_scan import extract_ids_from_live
        assert extract_ids_from_live({}) == []

    def test_null_field_is_not_recorded(self):
        """A cleared slot must not put None into the registry."""
        from posting.bot_sent_state_scan import extract_ids_from_live
        assert extract_ids_from_live({"schedule_post_msg_id": None}) == []
