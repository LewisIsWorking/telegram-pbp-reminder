"""Drop queue entries whose Telegram message the player has deleted.

Telegram never tells a bot that a message was deleted, so a player who
deletes an RP post leaves it in the GM queue (and in the 🎯 focus
message) until the GM runs ``/markdone <link>`` by hand. Example
2026-10-07: https://t.me/Path_Wars/137075/183543 (Kibwe, C06).

Before the queue is listed, each entry is probed with
``posting.message_probe.message_exists``. Only Telegram's explicit
"message to react not found" drops an entry; a network error, a 429 or
any other answer keeps it. Never silently drop a real unreplied post.

A dropped entry is cleared through ``markdone._clear_entries``, the same
path ``/markdone`` takes, so ``replied``, ``unreplied`` and the audit
trail stay consistent.

Bounded API use:
  * a message confirmed to exist is not asked about again for
    ``RECHECK_HOURS`` (cached per campaign as ``probed`` in its queue
    file, pruned to the entries still waiting);
  * at most ``MAX_PROBES`` probes per run, oldest entries first, since
    the oldest is the one the focus message points at;
  * no probing at all without a configured bot token, which also keeps
    the test suite off the network.
"""

from datetime import datetime, timedelta, timezone

import helpers
import telegram as tg
from helpers_pkg.groups import campaign_link_target
from posting.message_probe import message_exists

RECHECK_HOURS = 6
MAX_PROBES = 25


def _chat_ids(config: dict) -> dict[str, int]:
    """pid -> the Telegram chat the campaign's messages live in."""
    return {pid: campaign_link_target(config, pair)[0]
            for pid, _c, _n, pair in helpers.iter_campaigns(config)}


def _fresh(stamp: str | None, now: datetime) -> bool:
    """True when an 'exists' answer from ``stamp`` is still trusted."""
    try:
        seen = datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return False
    return now - seen < timedelta(hours=RECHECK_HOURS)


def drop_deleted(config: dict, state: dict, scanned: dict,
                 now: datetime | None = None, *, probe=None) -> dict:
    """Remove deleted messages from ``scanned`` (in place) and return it.

    ``probe(chat_id, message_id) -> bool | None`` defaults to the live
    Telegram probe; tests pass a fake.
    """
    if not scanned:
        return scanned
    if probe is None:
        api = getattr(tg, "TELEGRAM_API", "")
        if not api:
            return scanned
        probe = lambda chat, mid: message_exists(api, chat, mid)  # noqa: E731
    now = now or datetime.now(timezone.utc)
    from commands.queue_io import load, save
    from commands.markdone import _clear_entries

    chats = _chat_ids(config)
    budget = MAX_PROBES
    for pid in sorted(scanned, key=lambda p: min(
            (e.get("time", "9999") for e in scanned[p]["entries"]),
            default="9999")):
        chat = chats.get(pid)
        entries = scanned[pid]["entries"]
        if chat is None or not entries:
            continue
        cq = load(pid)
        old = cq.get("probed", {})
        live = {str(e.get("message_id")) for e in entries if e.get("message_id")}
        probed = {m: t for m, t in old.items() if m in live}
        gone = []
        for e in sorted(entries, key=lambda x: x.get("time", "9999")):
            mid = e.get("message_id")
            if not mid or _fresh(probed.get(str(mid)), now) or budget <= 0:
                continue
            budget -= 1
            verdict = probe(chat, mid)
            if verdict is False:
                gone.append(e)
                probed.pop(str(mid), None)
            elif verdict is True:
                probed[str(mid)] = now.isoformat()
        if probed != old:
            cq["probed"] = probed
            save(pid, cq)
        if gone:
            _clear_entries(gone, pid, state, now)
            for e in gone:
                print(f"✅ Cleared message {e.get('message_id')} from "
                      f"{scanned[pid].get('campaign', pid)} queue "
                      f"(deleted by {e.get('name', '?')}).")
            scanned[pid]["entries"] = [e for e in entries if e not in gone]
    for pid in [p for p, d in scanned.items() if not d["entries"]]:
        del scanned[pid]
    return scanned
