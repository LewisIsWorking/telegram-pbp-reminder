"""GM-facing notification families route out of the bot topic (2026-09-22).

Lewis asked for health, activity, pin and poll-admin messages to leave the
Path Wars bot topic (137393) for their own topics in Nudge Bot
Notifications. See helpers_pkg/routes.py.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from helpers_pkg.routes import ROUTES, route

SCRIPTS = Path(__file__).resolve().parent
CONFIG = json.loads((SCRIPTS.parent / "config.json").read_text(encoding="utf-8"))
BASE = {"group_id": -100, "bot_topic_id": 999}

# Which family each moved sender posts as. The vote tally in poll_notify
# is player-facing and deliberately stays in the bot topic.
SENDERS = {
    "ci_alert.py": "bot_health",
    "refusal_alert.py": "bot_health",
    "preflight/alerting.py": "bot_health",
    "scheduled/diagnostic.py": "bot_health",
    "scheduled/alerts.py": "activity",
    "scheduled/roster_nudge.py": "activity",
    "scheduled/maintenance.py": "activity",
    "scheduled/smart_alerts.py": "activity",
    "scheduled/reports.py": "activity",
    "scheduled/campaign_table.py": "activity",
    "scheduled/pin_report.py": "pins",
    "dispatch/poll_notify.py": "poll_admin",
    "dispatch/poll_router.py": "poll_admin",
}


def test_unconfigured_route_falls_back_to_the_bot_topic():
    """A missing route must move nothing, not silence anything."""
    for name in ROUTES:
        assert route(BASE, name) == (-100, 999)


def test_configured_route_names_its_own_chat_and_topic():
    cfg = {**BASE, "notification_routes": {"pins": {"chat_id": -5, "thread_id": 42}}}
    assert route(cfg, "pins") == (-5, 42)
    assert route(cfg, "activity") == (-100, 999)


def test_an_unknown_route_name_is_an_error_not_a_silent_fallback():
    with pytest.raises(KeyError):
        route(BASE, "pin")


def test_config_routes_are_known_and_complete():
    """A typo in config.json would otherwise quietly fall back."""
    routes = CONFIG.get("notification_routes") or {}
    for name, entry in routes.items():
        assert name in ROUTES, f"unknown route {name!r} in config.json"
        assert entry.get("chat_id") and entry.get("thread_id"), (
            f"route {name!r} needs a chat_id AND a thread_id: senders skip "
            f"when the topic is empty")


@pytest.mark.parametrize("rel,name", sorted(SENDERS.items()))
def test_each_moved_sender_uses_its_route(rel, name):
    body = (SCRIPTS / rel).read_text(encoding="utf-8")
    assert f'route(config, "{name}")' in body
    assert not re.search(r'bot_topic\s*=\s*config\.get\("bot_topic_id"\)', body) \
        or rel == "dispatch/poll_notify.py"


def test_the_vote_tally_stays_with_players():
    """poll_notify has three sends; only the two unknown-voter alerts moved."""
    body = (SCRIPTS / "dispatch/poll_notify.py").read_text(encoding="utf-8")
    assert body.count('route(config, "poll_admin")') == 2
    assert body.count('config.get("bot_topic_id")') == 1


def test_pin_digest_actually_posts_to_the_routed_topic(monkeypatch):
    from scheduled import pin_report as pr
    tg = MagicMock()
    tg.send_message.return_value = True
    monkeypatch.setattr(pr, "tg", tg)
    monkeypatch.setattr(pr.pin_audit, "entries_since", lambda ts: [])
    cfg = {**BASE, "diagnostic_hour": 8,
           "notification_routes": {"pins": {"chat_id": -7, "thread_id": 70}}}
    pr.run_daily_pin_digest(cfg, {}, now=datetime(2026, 7, 15, 8, tzinfo=timezone.utc))
    assert tg.send_message.call_args[0][:2] == (-7, 70)
