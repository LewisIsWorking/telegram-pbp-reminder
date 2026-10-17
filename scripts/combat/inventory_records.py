"""Each campaign's daily Foundry inventory snapshot, saved for the wiki to publish.

Added 2026-10-17 (Lewis: "track party inventory and character inventory on a daily basis so if a player
accidentally (or cheats) more gold or items, then it's checkable when items were added" ... "I'd like the
inventories saved to PathWarsWiki").

ComeOnOverUno reads every closed world's characters and parties during Foundry's 06:00 update and keeps the
latest snapshot. This reads it with the same key as the encounters and writes
``data/inventories/<code>/<YYYY-MM-DD>.json``; the wiki's sync turns those into one page per campaign with every
change by day. As with the encounters, no credential that can write to the wiki exists anywhere.

⭐ One file per campaign per day, named by the day the server TOOK the snapshot, so the hourly run rewrites
nothing once the day's file exists, and a day the server missed is simply absent rather than a copy of the last.
⚠️ A world shared by two campaigns (C00 and C01) is listed once per code by the server; each gets its own file.
"""

import json
import os
from pathlib import Path

import requests

from combat.foundry_sync import DEFAULT_SERVER, KEY_HEADER

RECORDS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "inventories"


def fetch_inventories(get=requests.get, env=os.environ) -> list | None:
    """Every campaign's latest snapshot, or None when there is no key or no answer."""
    key = env.get("PATHWARS_BOT_READ_KEY", "").strip()
    if not key:
        return None
    base = env.get("COO_SERVER_URL", DEFAULT_SERVER).rstrip("/")
    try:
        response = get(f"{base}/api/pathwars/inventories", headers={KEY_HEADER: key}, timeout=20)
    except requests.RequestException as e:
        print(f"Foundry inventories: server unreachable ({type(e).__name__})")
        return None
    if response.status_code != 200:
        print(f"Foundry inventories: server answered {response.status_code}")
        return None
    body = response.json()
    return body if isinstance(body, list) else None


def _safe(value) -> str:
    return "".join(ch for ch in str(value or "") if ch.isalnum() or ch == "-")


def build_record(stored: dict, campaign: str | None) -> dict:
    """The saved shape the wiki reads: code, campaign, date, and each actor's items and currency."""
    actors = []
    for actor in stored.get("actors") or []:
        if not actor.get("name"):
            continue
        actors.append({
            "id": actor.get("id"), "name": actor["name"],
            "kind": "party" if actor.get("kind") == "party" else "character",
            "owners": list(actor.get("owners") or []),
            "currency": {k: v for k, v in (actor.get("currency") or {}).items() if isinstance(v, (int, float))},
            "items": [{"name": i.get("name"), "type": i.get("type"), "quantity": i.get("quantity", 1)}
                      for i in actor.get("items") or [] if i.get("name")],
        })
    return {"code": stored.get("code"), "campaign": campaign, "world": stored.get("world"),
            "date": str(stored.get("date") or "")[:10], "taken_at": stored.get("takenAt"), "actors": actors}


def save_records(config: dict, inventories: list, root: Path | None = None) -> int:
    """Write each campaign's snapshot when that day's file is new or changed. Returns how many were written."""
    root = root or RECORDS_DIR
    names = {p.get("code"): p.get("name") for p in config.get("topic_pairs", [])}
    written = 0
    for stored in inventories:
        code, date = _safe(stored.get("code")), _safe(str(stored.get("date") or "")[:10])
        if not code or len(date) != 10:
            continue
        path = root / code / f"{date}.json"
        text = json.dumps(build_record(stored, names.get(stored.get("code"))), indent=2, ensure_ascii=False) + "\n"
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            written += 1
    return written


def sync_foundry_inventories(config: dict, state: dict, *, now=None, maps=None, fetch=fetch_inventories,
                             root: Path | None = None) -> None:
    """The hourly job: save whatever snapshot the server holds. Nothing to say when it holds none."""
    inventories = fetch()
    if inventories:
        written = save_records(config, inventories, root)
        if written:
            print(f"Foundry inventories: {written} snapshot(s) saved")
