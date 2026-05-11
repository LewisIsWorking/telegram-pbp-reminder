"""Read-only info commands. Build a report and send it, no state mutation."""

import helpers
import telegram as tg
from commands.trackers import (
    build_notes, build_quests, build_pins, build_lootlist, build_npcs,
    build_conditions,
)
from commands.mechanics import build_clocks, build_hp_tracker, build_vote, build_timer
from commands.summary import build_party, build_summary
from commands.dashboard import build_gm_dashboard, build_activity
from commands.profile import build_profile
from commands.catchup import build_catchup
from commands.recap import build_recap
from commands.status import build_status, build_overview
from commands.player import build_mystats, build_myhistory
from commands.campaign import build_campaign_report
from commands.queue import build_queue
from combat.display import build_whosturn, build_combatlog

_HELP_TEXT = ""

def init(help_text: str) -> None:
    """Initialise module with help text."""
    global _HELP_TEXT
    _HELP_TEXT = help_text

def handle(ctx: dict) -> bool:
    """Handle read-only info commands. Returns True if handled."""
    cmd = ctx["cmd_word"]
    text = ctx["text"]
    pid = ctx["pid"]
    uid = ctx["user_id"]
    name = ctx["campaign_name"]
    state = ctx["state"]
    config = ctx["config"]
    gm_ids = ctx["gm_ids"]
    gid = ctx["group_id"]
    reply = ctx["reply_topic"]

    if text in ("/help", "/pbphelp"):
        tg.send_message(gid, reply, _HELP_TEXT)
        return True

    if text == "/status":
        tg.send_message(gid, reply, build_status(pid, name, state, gm_ids, config))
        return True

    if text == "/overview":
        tg.send_message(gid, reply, build_overview(config, state))
        return True

    if text == "/campaign":
        tg.send_message(gid, reply, build_campaign_report(pid, config, state, gm_ids))
        return True

    if text in ("/mystats", "/me"):
        tg.send_message(gid, reply, build_mystats(pid, uid, name, state, gm_ids, config))
        return True

    if text == "/whosturn":
        tg.send_message(gid, reply, build_whosturn(pid, name, state))
        return True

    if text == "/combatlog":
        tg.send_message(gid, reply, build_combatlog(pid, name, state))
        return True

    if text == "/party":
        tg.send_message(gid, reply, build_party(pid, name, config, state))
        return True

    if text == "/myhistory":
        tg.send_message(gid, reply, build_myhistory(pid, uid, name, state, gm_ids))
        return True

    if text == "/catchup":
        tg.send_message(gid, reply, build_catchup(pid, uid, name, state, gm_ids, config))
        return True

    if text == "/notes":
        tg.send_message(gid, reply, build_notes(pid, name, state))
        return True

    if text == "/quests":
        tg.send_message(gid, reply, build_quests(pid, name, state))
        return True

    if text == "/pins":
        tg.send_message(gid, reply, build_pins(pid, name, state))
        return True

    if text == "/lootlist":
        tg.send_message(gid, reply, build_lootlist(pid, name, state))
        return True

    if text == "/npcs":
        tg.send_message(gid, reply, build_npcs(pid, name, state))
        return True

    if text == "/conditions":
        tg.send_message(gid, reply, build_conditions(pid, name, state, config))  # pragma: no cover
        return True  # pragma: no cover

    if text == "/hp" and text.strip() == "/hp":
        tg.send_message(gid, reply, build_hp_tracker(pid, name, state))
        return True

    if text == "/clocks":
        tg.send_message(gid, reply, build_clocks(pid, name, state))
        return True

    if text == "/showvote":
        tg.send_message(gid, reply, build_vote(pid, name, state))
        return True

    if text == "/showtimer":
        tg.send_message(gid, reply, build_timer(pid, name, state))
        return True

    if text == "/summary":
        tg.send_message(gid, reply, build_summary(pid, name, state, config))
        return True

    if text == "/gm" and uid in gm_ids:
        tg.send_message(gid, reply, build_gm_dashboard(config, state))
        return True

    if text == "/queue" and uid in gm_ids:
        tg.send_message(gid, reply, build_queue(config, state))
        return True

    if cmd == "/activity":
        tg.send_message(gid, reply, build_activity(pid, name, state, gm_ids))
        return True

    if cmd == "/profile":
        parts = text.split(None, 1)
        target = parts[1].strip().lstrip("@") if len(parts) > 1 else ""
        if not target:
            tg.send_message(gid, reply,
                            "Usage: /profile @username or /profile PlayerName")
        else:
            tg.send_message(gid, reply, build_profile(target, config, state))
        return True

    if cmd == "/recap":
        parts = text.split()
        n = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
        tg.send_message(gid, reply, build_recap(pid, name, config, n))
        return True


    if text == "/boons":
        from boons.display import build_boons
        tg.send_message(gid, reply, build_boons(pid, uid, name, state))
        return True

    if text == "/boonsall":
        from boons.display import build_boons_all
        tg.send_message(gid, reply, build_boons_all(uid, state))
        return True

    if cmd == "/roster":
        from commands.roster import build_roster
        arg = text[7:].strip()  # everything after '/roster'
        tg.send_message(gid, reply, build_roster(arg, config, state))
        return True

    if cmd == "/rostercampaigns":
        # Shape 1: per-campaign full breakdown for every campaign.
        # Same shape as /roster <code> repeated for each campaign,
        # emitted as one combined message.
        from commands.roster_views import build_roster_campaigns
        tg.send_message(gid, reply, build_roster_campaigns(config, state))
        return True

    if cmd == "/rosterplayers":
        # Shape 2: cross-campaign player table grouped by user_id,
        # with at-risk markers (→ last_warned_week 2 or 3) and a
        # recent join/leave footer from state['player_history'].
        from commands.roster_players import build_roster_players
        tg.send_message(gid, reply, build_roster_players(config, state))
        return True

    if cmd == "/rosterall":
        # Shape 3: per-campaign blocks (from Shape 1) plus the
        # at-risk / recent-joiners footer (subset of Shape 2).
        # Most comprehensive output; may approach Telegram's 4096
        # char limit on busy weeks.
        from commands.roster_views import build_roster_all
        tg.send_message(gid, reply, build_roster_all(config, state))
        return True

    return False
