"""The state schema: which keys exist, and which partition file holds each.

Extracted from ``state.py`` on 2026-08-15, which had reached 225 lines.
Pure data, no I/O — ``state.py`` stays the load/save coordinator and this
file answers "what is state made of".

⚠️ **A key absent from PARTITIONS is silently discarded on every save.**
``_save_to_files`` writes ``{k: state[k] for k in keys if k in state}`` per
partition, so an unlisted key never errors, never warns, and is simply gone
next run. That cost two days of duplicate schedule posts in 4.54.x and is
now guarded by ``test_state_keys_are_declared``.
"""

# ── Partition map ─────────────────────────────────────────────────────────────
# Keys not listed here (e.g. _config_cache) are transient and not persisted.

PARTITIONS: dict[str, list[str]] = {
    "live": [
        "offset", "topics", "last_alerts", "last_roster", "last_potw",
        "last_pace", "last_anniversary", "combat", "last_leaderboard",
        "last_roster_nudge", "last_roster_snapshot", "gm_escalation",
        "last_recruitment_check", "last_archived_week", "celebrated_streaks",
        "celebrated_milestones", "last_weekly_digest", "last_daily_tip",
        "used_tip_indices", "last_pace_drop_check", "dying_alerts_sent",
        "last_campaign_table", "session_poll", "last_state_backup",
        "last_queue_daily", "last_queue_fingerprint", "queue_nudged",
        "paused_campaigns", "current_scenes", "poll_unknown_voters",
        "last_week_welcome", "last_queue_daily_slots", "swimming_poll",
        "queue_scan_floor", "last_diagnostic", "last_queue_pin_id",
        "queue_post_count", "gm_queue_history",
        # Added 2026-08-11. These four were written by new features but
        # never listed here, so _save_to_files silently dropped them every
        # run (see the note at the top of this file: keys not listed are
        # transient). Three are idempotency guards, so losing them meant
        # the job re-fired on every 30-minute tick:
        #   potw_week           POTW would re-award all Monday
        #   last_potw_roundup   roundup would repost all Monday
        #   last_potw_countdown standings would repost all Thursday
        #   schedule_post_msg_id  schedule post could never delete its
        #                         predecessor, so it duplicated forever
        "potw_week", "last_potw_roundup", "last_potw_countdown",
        "schedule_post_msg_id",
        # Added 2026-08-17 with the move to the Nudge Bot Notifications
        # group. Records WHICH CHAT the current schedule post is in, so
        # the run that moves it deletes the old copy from the old chat
        # instead of aiming that id at the new one. Losing this key would
        # strand a schedule post in the GM queue topic permanently: past
        # 48h Telegram will not let the bot delete it at all.
        "schedule_post_chat_id",
        # Pre-existing losses found by the same audit, same mechanism.
        # last_pin_digest is the identical once-per-day shape: pin_report
        # does `if state.get("last_pin_digest") == today: return`, so
        # dropping it meant the daily digest reposted on every tick.
        "last_pin_digest", "last_pin_alert_ts", "poll_identified_voters",
        # Added 2026-08-15 for the recruit focus post. Both are required:
        # the msg_id so it can delete its predecessor, the timestamp so the
        # 24h gate survives a run. Omitting either reproduces the schedule
        # post bug exactly.
        "recruit_focus_msg_id", "last_recruit_focus",
    ],
    "players": [
        "players", "removed_players", "player_registry", "player_history",
        "player_boons", "mvp_wins", "characters", "away",
        # /available — player-entered data that was being discarded.
        "availability",
    ],
    "queue": [
        "queue_history", "queue_archive", "pending_potw_boons",
        "pending_hero_points",
    ],
    "activity": [
        "post_timestamps", "message_counts", "activity_hours",
        "activity_days", "word_counts", "session_counts", "session_last_day",
        "poll_history", "poll_results", "potw_history",
        "thread_message_counts",
    ],
    "trackers": [
        "clocks", "conditions", "hp_tracker", "loot", "npcs",
        "pins", "quests", "reactions", "timers", "votes",
        "campaign_notes",
        # /timeline — GM-entered entries that were being discarded.
        "timeline_events",
    ],
}

DEFAULT_STATE: dict = {
    "offset": 0, "topics": {}, "last_alerts": {}, "players": {},
    "removed_players": {}, "player_history": [], "message_counts": {}, "last_roster": {},
    "post_timestamps": {}, "last_potw": {}, "last_pace": {},
    "last_anniversary": {}, "combat": {}, "pending_potw_boons": {},
    "pending_hero_points": {},
    "last_leaderboard": None, "last_recruitment_check": {}, "last_roster_nudge": None, "last_roster_snapshot": None, "gm_escalation": {},
    # Trackers (written by in-game commands)
    "characters": {}, "away": {}, "paused_campaigns": {},
    "clocks": {}, "conditions": {}, "hp_tracker": {}, "loot": {},
    "npcs": {}, "pins": {}, "quests": {}, "reactions": {},
    "timers": {}, "votes": {}, "campaign_notes": {}, "current_scenes": {},
    "poll_history": {}, "poll_results": {}, "poll_unknown_voters": {},
    "potw_history": [], "last_week_welcome": None,
    "thread_message_counts": {},
    "last_queue_daily_slots": [], "swimming_poll": {},
    "queue_scan_floor": None, "last_diagnostic": None,
    "last_queue_pin_id": None, "queue_post_count": 0,
    "gm_queue_history": [],
    "potw_week": {}, "last_potw_roundup": None,
    "last_potw_countdown": None, "schedule_post_msg_id": None,
    "schedule_post_chat_id": None,
    "last_pin_digest": None, "last_pin_alert_ts": "",
    "poll_identified_voters": {}, "availability": {}, "timeline_events": {},
    "recruit_focus_msg_id": None, "last_recruit_focus": None,
}
