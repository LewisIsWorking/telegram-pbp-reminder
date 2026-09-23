"""GM-facing notification families route out of the bot topic (2026-09-22).

Lewis asked for health, activity, pin and poll-admin messages to leave the
Path Wars bot topic (137393) for their own topics in Nudge Bot
Notifications. See helpers_pkg/routes.py.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    "scheduled/roster_nudge.py": "roster_overview",
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
        assert entry.get("chat_id") and (entry.get("thread_id") or entry.get("campaigns")), (
            f"route {name!r} needs a chat_id AND a thread_id (or per-campaign "
            f"topics): senders skip when the topic is empty")
        codes = {p.get("code") for p in CONFIG["topic_pairs"]}
        for code in (entry.get("campaigns") or {}):
            assert code in codes, f"route {name!r} names unknown campaign {code!r}"


def test_roster_summary_goes_to_each_campaigns_own_topic():
    """Lewis, 2026-09-23: one roster topic per campaign in Nudge Bot
    Notifications; C08 and C10 added the same day."""
    from helpers_pkg.routes import campaign_route
    notif = -1004303231713
    assert campaign_route(CONFIG, "roster_summary", "66154") == (notif, 1444)  # C00
    assert campaign_route(CONFIG, "roster_summary", "25059") == (notif, 1448)  # C01
    assert campaign_route(CONFIG, "roster_summary", "107171") == (notif, 1456)  # C09
    assert campaign_route(CONFIG, "roster_summary", "107151") == (notif, 1493)  # C08
    assert campaign_route(CONFIG, "roster_summary", "146645") == (notif, 1495)  # C10


def test_a_campaign_route_that_is_not_configured_moves_nothing():
    from helpers_pkg.routes import campaign_route
    cfg = {**BASE, "topic_pairs": [{"code": "C01", "pbp_topic_ids": [25059]}]}
    assert campaign_route(cfg, "roster_summary", "25059") is None


@patch("scheduled.reports.tg")
@patch("scheduled.reports.helpers")
def test_the_roster_summary_is_actually_sent_to_the_campaign_topic(helpers, tg):
    from scheduled.reports import post_roster_summary
    helpers.feature_enabled.return_value = True
    helpers.interval_elapsed.return_value = True
    helpers.players_by_campaign.return_value = {"25059": [{"user_id": "1", "username": "p"}]}
    helpers.player_full_name.return_value = "Player One"
    helpers.get_label.return_value = "C01"
    helpers.REQUIRED_PLAYERS = 6
    cfg = {**BASE, "topic_pairs": [{"code": "C01", "pbp_topic_ids": [25059]}],
           "notification_routes": {"roster_summary": {"chat_id": -7, "campaigns": {"C01": 71}}}}
    state = {"last_roster": {}, "message_counts": {"25059": {"1": 3}}}
    maps = MagicMock(to_chat={"25059": 21514}, to_name={"25059": "DF"})
    helpers.get_topic_timestamps.return_value = {"1": ["2026-09-22T10:00:00+00:00"]}
    helpers.gm_ids_for_campaign.return_value = []
    helpers.get_characters.return_value = {}
    with patch("commands.player_registry.get_or_assign_id", return_value=1):
        post_roster_summary(cfg, state, now=datetime(2026, 9, 23, tzinfo=timezone.utc), maps=maps)
    assert tg.send_message.call_args[0][:2] == (-7, 71)


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


def test_the_live_destinations_are_the_ones_lewis_named():
    """Lewis, 2026-09-23. Changing one of these should be deliberate."""
    routes = CONFIG["notification_routes"]
    assert (routes["pace_report"]["chat_id"], routes["pace_report"]["thread_id"]) \
        == (-1004303231713, 1430)        # t.me/NudgeBotNotifications/1430
    assert (routes["roster_overview"]["chat_id"], routes["roster_overview"]["thread_id"]) \
        == (CONFIG["group_id"], 119703)  # t.me/Path_Wars/119703


def test_pace_report_and_roster_overview_use_their_own_routes():
    reports = (SCRIPTS / "scheduled/reports.py").read_text(encoding="utf-8")
    pace = reports[reports.index("def post_pace_report"):]
    assert 'route(config, "pace_report")' in pace
    nudge = (SCRIPTS / "scheduled/roster_nudge.py").read_text(encoding="utf-8")
    assert 'route(config, "roster_overview")' in nudge


def test_player_inactivity_posts_in_the_campaign_chat_topic():
    """Warnings and removals go where the player and the table will see
    them (Lewis, 2026-09-23), never to a routed or bot topic."""
    body = (SCRIPTS / "scheduled/alerts.py").read_text(encoding="utf-8")
    fn = body[body.index('    """Warn inactive players at 1/2/3 weeks'):]
    sends = re.findall(r"tg\.send_message\(([^\n]*)", fn)
    assert len(sends) == 2, sends
    for args in sends:
        assert args.startswith("group_id_for_campaign(config, str(pbp_topic_id)), chat_topic_id,")
    assert "route(config" not in fn


def test_campaign_silence_alert_posts_in_the_campaign_chat_topic():
    """Lewis, 2026-09-23: "No new posts in Kibwe PBP" belongs in Kibwe chat."""
    body = (SCRIPTS / "scheduled/alerts.py").read_text(encoding="utf-8")
    fn = body[body.index("def check_and_alert"):body.index("_INACTIVITY_TEMPLATES")]
    sends = re.findall(r"tg\.send_message\(([^\n]*)", fn)
    assert sends == ["group_id_for_campaign(config, str(pid)), chat_topic_id, message):"], sends
    assert "route(config" not in body
