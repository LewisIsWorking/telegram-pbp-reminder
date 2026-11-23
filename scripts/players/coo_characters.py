"""Every campaign's character names, from the COO server.

Added 2026-11-23. ``characters`` in players.json is filled only by a GM's
``/setchar``, and nobody had used it: it was empty for every campaign, so
the weekly reports and ``/summary`` named no characters. COO knows them
from each campaign's Foundry party sheet (its owner is the player's linked
COO account, or a Foundry user named after their Telegram handle).

⚠️ Read from ``/api/pathwars/characters`` with the bot's read key, ONCE per
run, on first use (as ``coo_link.linked_ids``). No key or no answer means no names
from COO: ``get_characters`` then has the config and ``/setchar`` names
only, exactly as before. A GM's ``/setchar`` still wins over COO.

Shape: ``{"<first pbp topic id>": {"<telegram id>": "Character"}}``.
"""

import os

import requests

from combat.foundry_sync import DEFAULT_SERVER, KEY_HEADER

_names: dict = {}


def fetch_characters(get=requests.get, env=os.environ) -> dict | None:
    """COO's character names by campaign, or None when unknown."""
    key = env.get("PATHWARS_BOT_READ_KEY", "").strip()
    if not key:
        return None
    base = env.get("COO_SERVER_URL", DEFAULT_SERVER).rstrip("/")
    try:
        response = get(f"{base}/api/pathwars/characters",
                       headers={KEY_HEADER: key}, timeout=20)
    except requests.RequestException as e:
        print(f"COO character names: server unreachable ({type(e).__name__})")
        return None
    if response.status_code != 200:
        print(f"COO character names: server answered {response.status_code}")
        return None
    try:
        body = response.json()
    except ValueError:
        print("COO character names: the answer was not JSON")
        return None
    if not isinstance(body, dict):
        return None
    return {str(pid): {str(uid): name for uid, name in chars.items()
                       if isinstance(name, str) and name.strip()}
            for pid, chars in body.items() if isinstance(chars, dict)}


def load(fetch=fetch_characters) -> None:
    """Read the names for this run. Once: a second call keeps the first."""
    if "by_pid" not in _names:
        _names["by_pid"] = fetch() or {}
        total = sum(len(c) for c in _names["by_pid"].values())
        if total:
            print(f"COO character names: {total} across {len(_names['by_pid'])} campaign(s)")


def for_campaign(pid: str, fetch=fetch_characters) -> dict:
    """``{telegram id: name}`` for this campaign's first pbp topic, or {}."""
    load(fetch)
    return dict(_names["by_pid"].get(str(pid), {}))


def reset() -> None:
    _names.clear()
