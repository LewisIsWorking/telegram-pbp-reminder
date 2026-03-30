"""
Backward-compat aliases so test_checker.py can reference checker.xxx
for functions that now live in submodules.
"""

# fmt: off
__all__ = [
    "_format_boon_result", "process_boon_callback", "choose_boon_by_text",
    "build_boons", "build_boons_all", "_build_whosturn", "_format_elapsed",
    "_build_combatlog", "_handle_combat_message", "_handle_round_command",
    "_handle_combat_start", "_handle_next_command", "_handle_endcombat",
    "_handle_enemies_command", "_parse_message", "_build_status",
    "_build_overview", "_build_campaign_report", "_roster_user_stats",
    "_roster_block", "_build_mystats", "_build_myhistory", "_sparkline",
    "_build_notes", "_build_quests", "_build_pins", "_build_lootlist",
    "_build_npcs", "_build_conditions", "_build_vote", "_build_timer",
    "_build_hp_tracker", "_build_clocks", "_build_summary", "_build_party",
    "_build_gm_dashboard", "_build_activity", "_build_profile",
    "_build_catchup", "_build_recap", "_append_to_transcript",
    "_write_scene_marker", "_sanitize_dirname", "_LOGS_DIR",
    "_transcript_cache", "_finalize_previous_month", "_format_log_entry",
    "_format_transcript_content", "_TIPS", "_gather_potw_candidates",
    "_next_anniversary", "_format_leaderboard", "_gather_leaderboard_stats",
    "_build_weekly_digest", "_HELP_TEXT", "_handle_kick", "_handle_addplayer",
    "_calc_streak", "_health_icon",
]
# fmt: on

import helpers

from boons.handler import (
    _format_boon_result, process_boon_callback,
    choose_boon_by_text,
)
from boons.display import build_boons, build_boons_all
from combat.display import (
    build_whosturn as _build_whosturn,
    format_elapsed as _format_elapsed,
    build_combatlog as _build_combatlog,
)
from combat.tracker import (
    handle_combat_message as _handle_combat_message,
    handle_round_command as _handle_round_command,
)
from combat.commands import (
    handle_combat_start as _handle_combat_start,
    handle_next_command as _handle_next_command,
    handle_endcombat as _handle_endcombat,
    handle_enemies_command as _handle_enemies_command,
)
from parsing.message import parse_message as _parse_message
from commands.status import (
    build_status as _build_status, build_overview as _build_overview,
)
from commands.campaign import (
    build_campaign_report as _build_campaign_report,
    roster_user_stats as _roster_user_stats,
    roster_block as _roster_block,
)
from commands.player import (
    build_mystats as _build_mystats,
    build_myhistory as _build_myhistory,
    _sparkline,
)
from commands.trackers import (
    build_notes as _build_notes, build_quests as _build_quests,
    build_pins as _build_pins, build_lootlist as _build_lootlist,
    build_npcs as _build_npcs, build_conditions as _build_conditions,
)
from commands.mechanics import (
    build_vote as _build_vote, build_timer as _build_timer,
    build_hp_tracker as _build_hp_tracker, build_clocks as _build_clocks,
)
from commands.summary import (
    build_summary as _build_summary, build_party as _build_party,
)
from commands.dashboard import (
    build_gm_dashboard as _build_gm_dashboard,
    build_activity as _build_activity,
)
from commands.profile import build_profile as _build_profile
from commands.catchup import build_catchup as _build_catchup
from commands.recap import build_recap as _build_recap
from transcript.logger import (
    append_to_transcript as _append_to_transcript,
    write_scene_marker as _write_scene_marker,
    sanitize_dirname as _sanitize_dirname,
    _LOGS_DIR, _transcript_cache,
)
from transcript.finalize import finalize_previous_month as _finalize_previous_month
from transcript.formatting import (
    format_log_entry as _format_log_entry,
    format_transcript_content as _format_transcript_content,
)
from scheduled.tips_data import _TIPS
from scheduled.potw import _gather_potw_candidates
from scheduled.milestones import _next_anniversary
from scheduled.leaderboard import _format_leaderboard
from scheduled.leaderboard_data import _gather_leaderboard_stats
from scheduled.digest import _build_weekly_digest
from dispatch.help_text import _HELP_TEXT
from players.management import (
    handle_kick as _handle_kick, handle_addplayer as _handle_addplayer,
)

_calc_streak = helpers.calc_streak
_health_icon = helpers.health_icon
