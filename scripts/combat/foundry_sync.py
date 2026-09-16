"""Foundry encounters, read from ComeOnOverUno, driving the bot's combat state.

Added 2026-09-16. ⛔ DECIDED WITH LEWIS: FOUNDRY DRIVES THE BOT. The GM's
Foundry (Tongs Browser) posts every turn to the ComeOnOverUno server, which
keeps a tracker message in the campaign's combat topic edited in place. An
edit notifies nobody, so the pings are the bot's job: this reads each
campaign's latest encounter, mirrors it into ``state["combat"][pid]``, and
pings the allies still to act when a phase starts. ``check_combat_turns``
then reminds them every ``combat_ping_hours`` as for a /combat fight.

⚠️ Allies act in any order (side phases), so "players" is every ally's
turn at once, and "enemies" starts once all of them have acted.

⚠️ A campaign missing from the server's answer is left alone. The server
keeps encounters in memory, so a restart empties the list until the GM's
Foundry sends the next turn; ending the fight on that would be wrong.
"""

import html
import os
from datetime import datetime

import requests

import helpers
import telegram as tg

DEFAULT_SERVER = "https://cooserver.duckdns.org"
KEY_HEADER = "X-PathWars-Bot-Key"
SOURCE = "foundry"


def fetch_encounters(get=requests.get, env=os.environ) -> list | None:
    """Every campaign's latest encounter, or None when there is no key or no answer."""
    key = env.get("PATHWARS_BOT_READ_KEY", "").strip()
    if not key:
        return None
    base = env.get("COO_SERVER_URL", DEFAULT_SERVER).rstrip("/")
    try:
        response = get(f"{base}/api/pathwars/encounters",
                       headers={KEY_HEADER: key}, timeout=20)
    except requests.RequestException as e:
        print(f"Foundry encounters: server unreachable ({type(e).__name__})")
        return None
    if response.status_code != 200:
        print(f"Foundry encounters: server answered {response.status_code}")
        return None
    body = response.json()
    return body if isinstance(body, list) else None


def _pair_for_code(config: dict, code: str) -> dict | None:
    return next((p for p in config.get("topic_pairs", []) if p.get("code") == code), None)


def reconcile(config: dict, state: dict, encounters: list, now: datetime) -> list[str]:
    """Mirror each encounter into the bot's combat state. Returns the pids whose phase just began."""
    started = []
    for stored in encounters:
        pair = _pair_for_code(config, str(stored.get("code", "")))
        snapshot = stored.get("snapshot") or {}
        if pair is None or not pair.get("pbp_topic_ids"):
            continue
        pid = str(pair["pbp_topic_ids"][0])
        if not helpers.feature_enabled(config, pid, "combat"):
            continue
        combat = state.setdefault("combat", {}).get(pid)
        encounter_id = snapshot.get("encounterId")
        if snapshot.get("ended"):
            if combat and combat.get("source") == SOURCE and combat.get("encounter_id") == encounter_id:
                combat["active"] = False
            continue
        allies = snapshot.get("allies") or []
        phase = "players" if stored.get("phase") == "allies" else "enemies"
        round_num = int(snapshot.get("round") or 0)
        same_phase = (combat is not None and combat.get("source") == SOURCE and combat.get("active")
                      and combat.get("encounter_id") == encounter_id
                      and combat.get("round") == round_num and combat.get("current_phase") == phase)
        if not same_phase:
            previous = combat if combat and combat.get("encounter_id") == encounter_id else {}
            combat = state["combat"][pid] = {
                "active": True, "source": SOURCE, "encounter_id": encounter_id,
                "campaign_name": pair.get("name", pid), "round": round_num,
                "current_phase": phase, "phase_started_at": now.isoformat(),
                "started_at": previous.get("started_at", now.isoformat()),
                "players_acted": {}, "last_ping_at": None, "all_players_notified": True,
            }
            started.append(pid)
        acted = combat["players_acted"]
        for ally in allies:
            uid = ally.get("telegramUserId")
            if uid and ally.get("acted") and uid not in acted:
                acted[uid] = now.isoformat()
        combat["waiting_user_ids"] = [
            a["telegramUserId"] for a in allies if a.get("telegramUserId") and not a.get("acted")
        ]
    return started


def mentions(state: dict, pid: str, user_ids: list[str]) -> list[str]:
    """HTML mentions by Telegram id, which notify a player with no username too."""
    names = {p["user_id"]: p.get("first_name", "player")
             for p in state.get("players", {}).values() if p.get("pbp_topic_id") == pid}
    return [f'<a href="tg://user?id={html.escape(uid)}">{html.escape(names.get(uid, "player"))}</a>'
            for uid in user_ids]


def ping_waiting(config: dict, state: dict, pid: str, now: datetime, heading: str) -> bool:
    """Name the allies still to act, in the campaign's combat topic. True when it was sent."""
    combat = state["combat"][pid]
    pair = next((p for p in config.get("topic_pairs", [])
                 if str(p["pbp_topic_ids"][0]) == pid), None)
    waiting = [uid for uid in combat.get("waiting_user_ids", [])
               if not helpers.is_away(state, pid, uid, now)]
    if not pair or not pair.get("combat_topic_id") or not waiting:
        return False
    text = f"⚔️ <b>{html.escape(heading)}</b>\nYour turn: " + ", ".join(mentions(state, pid, waiting))
    group_id = pair.get("group_id", config["group_id"])
    if tg.send_message(group_id, pair["combat_topic_id"], text, parse_mode="HTML"):
        combat["last_ping_at"] = now.isoformat()
        return True
    return False  # pragma: no cover


def sync_foundry_encounters(config: dict, state: dict, *, now: datetime, maps=None,
                            fetch=fetch_encounters) -> None:
    """The hourly job: read the server, mirror its encounters, ping each phase that began."""
    encounters = fetch()
    if encounters is None:
        return
    for pid in reconcile(config, state, encounters, now):
        combat = state["combat"][pid]
        if combat["current_phase"] == "players":
            ping_waiting(config, state, pid, now, f"Round {combat['round']}: Unacted Allies")
