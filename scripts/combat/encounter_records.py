"""Each Foundry encounter saved as a record, for the wiki to publish.

Added 2026-09-17. The wiki's own workflow already pulls this public repo
to publish the PBP transcripts; it reads ``data/encounters/`` the same way
and renders each record as an encounter page. So no credential that can
write to the wiki exists anywhere, and the bot commits the records with
the rest of ``data/`` as it always has.

⭐ A record is written on first sight (the stub) and rewritten while the
fight runs, so the page fills in round by round and is complete when
Foundry ends the encounter.

⚠️ The server keeps its hit log in memory. After a server restart it
reports the same encounter with a later ``startedAt`` and only the hits
since; those are appended to what this record already holds rather than
replacing it.

⛔ Public facts only, exactly as the server returns them: names as
players see them, bands and causes as posted to the combat topic.
"""

import json
from pathlib import Path

RECORDS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "encounters"


def _player(state: dict, pid: str, user_id: str | None) -> str | None:
    if not user_id:
        return None
    for p in state.get("players", {}).values():
        if p.get("user_id") == user_id and p.get("pbp_topic_id") == pid:
            return f"@{p['username']}" if p.get("username") else p.get("first_name")
    return None


def build_record(stored: dict, pair: dict, state: dict, previous: dict | None) -> dict:
    """The record for one encounter, merged with what was saved before."""
    snapshot = stored.get("snapshot") or {}
    pid = str(pair["pbp_topic_ids"][0])
    server_started = stored.get("startedAt")
    server_hits = [{"round": h.get("round"), "text": h.get("text")} for h in stored.get("hits") or []]
    started, earlier = server_started, []
    if previous:
        before = previous.get("started_at")
        started = min(before, server_started) if before and server_started else (before or server_started)
        # 🔁 The server restarted since: everything saved so far came from earlier sessions.
        restarted = (previous.get("server_started_at") or "") < (server_started or "")
        earlier = previous.get("hits", []) if restarted else previous.get("earlier_hits", [])
    allies = [{"name": a.get("name"), "player": _player(state, pid, a.get("telegramUserId")),
               "initiative": a.get("initiative"), "side": "ally"} for a in snapshot.get("allies") or []]
    enemies = [{"name": e.get("name"), "initiative": e.get("initiative"), "side": "enemy"}
               for e in snapshot.get("enemies") or []]
    order = sorted((c for c in allies + enemies if isinstance(c.get("initiative"), (int, float))),
                   key=lambda c: -c["initiative"])
    ended = bool(snapshot.get("ended"))
    return {
        "code": stored.get("code"), "campaign": pair.get("name"),
        "encounter_id": snapshot.get("encounterId"),
        "name": snapshot.get("name") or snapshot.get("location") or "Encounter",
        "location": snapshot.get("location"),
        "started_at": started, "server_started_at": server_started,
        "ended": ended, "ended_at": stored.get("updatedAt") if ended else None,
        "rounds": snapshot.get("round"),
        "initiative": order,
        "allies": [{"name": a["name"], "player": a["player"]} for a in allies],
        "enemies": [e["name"] for e in enemies],
        "earlier_hits": earlier,
        "hits": earlier + server_hits,
    }


def _safe(value) -> str:
    return "".join(ch for ch in str(value or "") if ch.isalnum()) or "unknown"


def record_path(root: Path, stored: dict) -> Path:
    """``<code>/<YYYY-MM-DD>-<encounter id>.json``. A record already saved for the id wins over a new date."""
    folder = root / _safe(stored.get("code"))
    encounter = _safe((stored.get("snapshot") or {}).get("encounterId"))
    found = sorted(folder.glob(f"*-{encounter}.json")) if folder.exists() else []
    day = str(stored.get("startedAt") or "")[:10] or "undated"
    return found[0] if found else folder / f"{day}-{encounter}.json"


def save_records(config: dict, state: dict, encounters: list, root: Path | None = None) -> int:
    """Write each encounter's record when it changed. Returns how many were written."""
    root = root or RECORDS_DIR
    pairs = {p.get("code"): p for p in config.get("topic_pairs", []) if p.get("pbp_topic_ids")}
    written = 0
    for stored in encounters:
        pair = pairs.get(stored.get("code"))
        snapshot = stored.get("snapshot") or {}
        if pair is None or not snapshot.get("encounterId"):
            continue
        # ⚠️ Found by id: a server restart moves the start date, the id never moves.
        path = record_path(root, stored)
        previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        text = json.dumps(build_record(stored, pair, state, previous), indent=2, ensure_ascii=False) + "\n"
        if previous is None or path.read_text(encoding="utf-8") != text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            written += 1
    return written
