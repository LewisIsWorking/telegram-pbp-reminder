"""Telling a player whose Telegram is not linked to COO how to link it.

Added 2026-10-08. A player with no linked COO account has no Foundry login,
so Tongs never sees them and never makes their character sheet. KP asked
for a sheet in C00 and nothing could have made one.

Decided with Lewis, 2026-10-08: nudge on the player's FIRST post (once),
and again WHENEVER they ask for a sheet, a character or Foundry.

⚠️ The linked ids come from the COO server (``/api/pathwars/linked``) with
the bot's read key, once per run. No key or no answer means nobody is
nudged: telling a linked player to link would be worse than silence.

⭐ The nudge is posted by @ComeOnOverBot through COO (Lewis, 2026-10-08),
and by this bot only when COO cannot.

⚠️ A repeat ask is answered at most once per ``ASK_COOLDOWN``, so a
player chatting about their sheet gets one reply, not one per message.
"""

import os
import re
from datetime import datetime, timedelta

import requests

import telegram as tg
from combat.foundry_sync import DEFAULT_SERVER, KEY_HEADER

STATE_KEY = "coo_link_nudges"
LINK_URL = "https://comeonover.netlify.app/PathWars"
ASK_COOLDOWN = timedelta(hours=6)
ASKS = re.compile(r"\b(sheets?|characters?|foundry)\b", re.IGNORECASE)

_linked: dict = {}


def fetch_linked(get=requests.get, env=os.environ) -> set[str] | None:
    """The Telegram ids with a linked COO account, or None when unknown."""
    key = env.get("PATHWARS_BOT_READ_KEY", "").strip()
    if not key:
        return None
    base = env.get("COO_SERVER_URL", DEFAULT_SERVER).rstrip("/")
    try:
        response = get(f"{base}/api/pathwars/linked",
                       headers={KEY_HEADER: key}, timeout=20)
    except requests.RequestException as e:
        print(f"COO linked ids: server unreachable ({type(e).__name__})")
        return None
    if response.status_code != 200:
        print(f"COO linked ids: server answered {response.status_code}")
        return None
    body = response.json()
    return {str(i) for i in body} if isinstance(body, list) else None


def linked_ids(fetch=fetch_linked) -> set[str] | None:
    """``fetch_linked`` once per run; ``reset`` forgets it."""
    if "ids" not in _linked:
        _linked["ids"] = fetch()
    return _linked["ids"]


def reset() -> None:
    _linked.clear()


def nudge_text(parsed: dict) -> str:
    uname = parsed.get("username", "")
    who = f"@{uname}" if uname else parsed.get("user_name", "there")
    return (f"\U0001f44b {who}, your Telegram isn't linked to ComeOnOver yet, "
            "so Foundry has no login or character sheet for you.\n\n"
            f"1. Open {LINK_URL} and sign in (or sign up).\n"
            "2. Link your Telegram there.\n"
            "3. Press Play on your campaign. Your sheet is made when you join.")


def post_as_comeonoverbot(parsed: dict, thread, post=requests.post,
                          env=os.environ) -> bool:
    """Ask COO to post the nudge as @ComeOnOverBot (Lewis, 2026-10-08).

    False on anything but a 200, and the caller then posts it itself: no
    key, COO down, no ComeOnOverBot token (503) or Telegram refusing (502).
    """
    key = env.get("PATHWARS_BOT_READ_KEY", "").strip()
    if not key:
        return False
    base = env.get("COO_SERVER_URL", DEFAULT_SERVER).rstrip("/")
    body = {"name": parsed.get("user_name", ""),
            "username": parsed.get("username") or None, "threadId": thread}
    try:
        response = post(f"{base}/api/pathwars/link-nudge", json=body,
                        headers={KEY_HEADER: key}, timeout=20)
    except requests.RequestException as e:
        print(f"COO link nudge: server unreachable ({type(e).__name__})")
        return False
    if response.status_code != 200:
        print(f"COO link nudge: server answered {response.status_code}")
    return response.status_code == 200


def _due(parsed: dict, last: str | None) -> bool:
    if last is None:
        return True
    if not ASKS.search(parsed.get("raw_text") or ""):
        return False
    now = datetime.fromisoformat(parsed["msg_time_iso"])
    return now - datetime.fromisoformat(last) >= ASK_COOLDOWN


def nudge_if_unlinked(parsed: dict, state: dict, config: dict, maps,
                      linked=linked_ids) -> bool:
    """Tell an unlinked player how to link, when due. True when sent."""
    if (parsed.get("text") or "").startswith("/"):
        return False
    ids = linked()
    user_id = str(parsed["user_id"])
    if ids is None or user_id in ids:
        return False
    nudges = state.setdefault(STATE_KEY, {})
    if not _due(parsed, nudges.get(user_id)):
        return False
    thread = maps.to_chat.get(parsed["pid"]) or parsed.get("thread_id")
    if not (post_as_comeonoverbot(parsed, thread)
            or tg.send_message(config["group_id"], thread, nudge_text(parsed))):
        return False
    nudges[user_id] = parsed["msg_time_iso"]
    return True
