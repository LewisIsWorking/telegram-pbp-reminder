"""Weekly recruitment pick for the GM: the ONE campaign most in need.

Lewis, 2026-10-21: campaigns really want 6 players, but recruiting for every
campaign under 6 at once would mean constant recruiting. So: *"a weekly
recruitment for the most in need campaign"*.

Once every ``INTERVAL_DAYS`` the bot DMs the GM (the same delivery as the
"Reply to this next" focus DM, never a player topic) naming one campaign, how
far below 6 it is, the Open Slots figure to advertise, and where its Discord
ad lives in PathWarsWiki.

How the campaign is chosen
--------------------------
* **Active** means a record in state ``players`` (players.json) for the
  campaign's canonical pbp topic, GMs excluded. Removed players live in
  ``removed_players``, so they are already out.
* **Eligible** means fewer than ``TARGET`` (6) active players, and not marked
  as not recruiting: ``recruitment`` in ``disabled_features`` (C08, C10, C11,
  C99 today) or ``"weekly_recruit": false`` on the pair.
* **Furthest below 6 wins.** Ties go to the campaign picked longest ago
  (never picked counts as longest), then config order. "Fewest players" is
  not a separate tie-break: with one fixed target, equal shortfall already
  means equal players.

⚠️ This is NOT ``recruit_focus``. That one is the daily player-facing advert
in each campaign's chat topic, measured by ``/roster``'s 30-day rule and the
recruiting ladder. This one is a weekly instruction to the GM to go and post
the external Discord ad, measured against a fixed 6.

Registration: ``checker._run_checks`` ("Weekly recruitment"),
``schedule_intervals.INTERVAL_JOBS`` and ``state_schema.PARTITIONS``. Missing
the last one would discard both keys on every save and DM the GM hourly.
"""

from datetime import datetime, timezone

import helpers
import telegram as tg
from commands.roster_members import _TARGET

TARGET = _TARGET
INTERVAL_DAYS = 7
LAST_KEY = "last_weekly_recruit"
PICKS_KEY = "weekly_recruit_picks"

WIKI_TOPICS_URL = ("https://github.com/LewisIsWorking/PathWarsWiki/blob/"
                   "main/Writerside/topics/")
MULTI_AD = "Other-campaigns/Multi-discord-ad.md"


def _pid(pair: dict) -> str:
    return str(pair["pbp_topic_ids"][0])


def active_count(pair: dict, config: dict, state: dict) -> int:
    """Records in ``players`` for this campaign's canonical topic, GMs out."""
    pid = _pid(pair)
    gms = helpers.gm_ids_for_campaign(config, pid)
    return sum(1 for p in state.get("players", {}).values()
               if str(p.get("pbp_topic_id", "")) == pid
               and str(p.get("user_id", "")) not in gms)


def is_recruiting(pair: dict, config: dict) -> bool:
    """False for a campaign config marks as not recruiting."""
    if not pair.get("pbp_topic_ids") or pair.get("weekly_recruit") is False:
        return False
    return helpers.feature_enabled(config, _pid(pair), "recruitment")


def short_campaigns(config: dict, state: dict) -> list[tuple[dict, int]]:
    """Every recruiting campaign below ``TARGET``, as ``(pair, active)``."""
    out = []
    for pair in config.get("topic_pairs", []):
        if not is_recruiting(pair, config):
            continue
        count = active_count(pair, config, state)
        if count < TARGET:
            out.append((pair, count))
    return out


def _last_picked(pair: dict, state: dict) -> datetime | None:
    raw = (state.get(PICKS_KEY) or {}).get(_pid(pair))
    try:
        return datetime.fromisoformat(raw) if raw else None
    except (ValueError, TypeError):
        return None


def rank(config: dict, state: dict) -> list[tuple[dict, int]]:
    """Short campaigns, most in need first."""
    oldest = datetime.min.replace(tzinfo=timezone.utc)
    short = short_campaigns(config, state)
    order = {id(p): i for i, (p, _c) in enumerate(short)}
    return sorted(short, key=lambda pc: (
        pc[1], _last_picked(pc[0], state) or oldest, order[id(pc[0])]))


def open_slots(active: int) -> int:
    """Shortfall + 1: Lewis inflates open slots so drop-offs are survivable."""
    return max(TARGET - active, 0) + 1


def ad_line(pair: dict, config: dict) -> str:
    """Where this campaign's Discord ad lives, or how to record it."""
    base = config.get("wiki_topics_url") or WIKI_TOPICS_URL
    page = pair.get("discord_ad")
    if page:
        return f"📝 Discord ad: {base}{page}"
    code = pair.get("code") or pair.get("name", "this campaign")
    return (f"📝 No Discord ad page recorded for {code}. Start one in "
            f"PathWarsWiki Writerside/topics/ and set `discord_ad` in config.")


def _picked_text(pair: dict, state: dict, now: datetime) -> str:
    last = _last_picked(pair, state)
    if not last:
        return "🕰 Not picked for weekly recruitment before."
    days = int(helpers.days_since(now, last))
    return f"🕰 Last picked {last.date().isoformat()} ({days}d ago)."


def build_weekly_recruit(config: dict, state: dict,
                         now: datetime) -> tuple[str, dict | None]:
    """``(text, pair)`` for the neediest campaign, or ``("", None)``."""
    ranked = rank(config, state)
    if not ranked:
        return "", None
    pair, active = ranked[0]
    code = pair.get("code", "")
    label = f"{code} {pair.get('name', '')}".strip()
    short = TARGET - active
    lines = [
        f"📣 Weekly recruitment: {label}",
        f"👥 Active players: {active}/{TARGET} ({short} short)",
        f"🎯 Suggested Open Slots: {open_slots(active)}",
        ad_line(pair, config),
        f"🧩 Multi-campaign ad: "
        f"{config.get('wiki_topics_url') or WIKI_TOPICS_URL}{MULTI_AD}",
        "✏️ Refresh the ad's facts (open slots, level, schedule) and make "
        "it a bit better than last time.",
        _picked_text(pair, state, now),
    ]
    rest = [f"{p.get('code') or p.get('name', '?')} {c}/{TARGET}"
            for p, c in ranked[1:]]
    if rest:
        lines.append(f"Also below {TARGET}: " + ", ".join(rest))
    return "\n".join(lines), pair


def post_weekly_recruit(config: dict, state: dict, *,
                        now: datetime | None = None, **_kw) -> None:
    """Once every ``INTERVAL_DAYS``, DM the GM the neediest campaign."""
    now = now or datetime.now(timezone.utc)
    if not config.get("weekly_recruit_enabled", True):
        return
    if not helpers.interval_elapsed(state.get(LAST_KEY), INTERVAL_DAYS, now):
        return
    gm_uid = config.get("gm_user_id")
    if not gm_uid:
        return
    text, pair = build_weekly_recruit(config, state, now)
    if not pair:
        # Every campaign is at 6 or more. That is this week's answer, so
        # the week is spent; the stale-feature check reads this marker too.
        state[LAST_KEY] = now.isoformat()
        return
    # ⚠️ Stamp only on a confirmed send, or a failed DM is lost for a week.
    if tg.send_message(gm_uid, None, text):
        state[LAST_KEY] = now.isoformat()
        state.setdefault(PICKS_KEY, {})[_pid(pair)] = now.isoformat()
