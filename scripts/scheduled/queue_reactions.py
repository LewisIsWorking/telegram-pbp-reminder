"""👀 on unreplied player posts, ✍ once the GM has replied (2026-11-23).

The pinned "📋 Unreplied: N" list shows the queue in one place; these
reactions show it on the posts themselves. The unreplied set is exactly
the one the pin uses (``scan_transcripts`` after ``drop_deleted``, passed
in by ``queue_reminder``), so the two can never disagree.

⭐ A bot has ONE reaction per message, so setting ✍ replaces 👀. A post
that leaves the queue without a reply (deleted, aged out) has its 👀
removed instead.

⚠️ Only changes call the API. ``state[STATE_KEY]`` records what the bot
has set on each message, and at most ``MAX_CALLS`` calls go out per run,
oldest posts first, so the first backfill (dozens of posts) spreads over
several runs instead of hitting Telegram's rate limit. A call that fails
is retried on later runs, then given up after ``MAX_FAILS``.

Off switch: ``"queue_reactions_enabled": false`` in config.json.
"""

import time
from datetime import datetime, timedelta

import telegram as tg
from commands.queue_io import replied_set
from helpers_pkg.campaigns import get_pair
from helpers_pkg.groups import campaign_link_target

STATE_KEY = "queue_reactions"
EYES = "\U0001F440"
WRITING = "\u270D"
MAX_CALLS = 20
MAX_FAILS = 3
KEEP_DAYS = 30
PAUSE_SECONDS = 0.5


def _react(chat_id: int, message_id: int, emoji: str) -> bool:
    """Set (or with "" clear) the bot's reaction. True on success."""
    reaction = [{"type": "emoji", "emoji": emoji}] if emoji else []
    result = tg._post("setMessageReaction",
                      {"chat_id": chat_id, "message_id": message_id,
                       "reaction": reaction},
                      label=f"reaction {emoji or 'clear'} on {message_id}")
    return bool(result)


def _chat_for(config: dict, pid: str) -> int:
    pair = get_pair(config, pid) or {}
    return campaign_link_target(config, pair)[0]


def _wanted(config: dict, tracked: dict, scanned: dict,
            replied=replied_set) -> dict:
    """{key: (chat, mid, pid, emoji)} for every message whose reaction we own."""
    want = {}
    for pid, data in scanned.items():
        chat = _chat_for(config, pid)
        for entry in data.get("entries", []):
            mid = str(entry.get("message_id") or "")
            if mid.isdigit():
                want[f"{chat}:{mid}"] = (chat, int(mid), pid, EYES)
    cache: dict[str, set] = {}
    for key, rec in tracked.items():
        if key in want or rec.get("emoji") != EYES:
            continue
        pid = rec.get("pid", "")
        chat, mid = key.rsplit(":", 1)
        if pid not in cache:
            cache[pid] = replied(pid)
        emoji = WRITING if f"msg:{mid}" in cache[pid] else ""
        want[key] = (int(chat), int(mid), pid, emoji)
    return want


def sync_queue_reactions(config: dict, state: dict, scanned: dict,
                         now: datetime, *, react=None, replied=replied_set,
                         pause: float = PAUSE_SECONDS) -> int:
    """Bring the bot's reactions in line with the queue. Returns API calls made."""
    if not config.get("queue_reactions_enabled", True):
        return 0
    react = react or _react
    tracked = state.setdefault(STATE_KEY, {})
    calls = done = 0
    want = _wanted(config, tracked, scanned, replied)
    for key, (chat, mid, pid, emoji) in sorted(want.items(), key=lambda kv: kv[1][1]):
        rec = tracked.get(key, {})
        if rec.get("emoji") == emoji and key in tracked:
            continue
        if rec.get("want") == emoji and rec.get("fails", 0) >= MAX_FAILS:
            continue
        if calls >= MAX_CALLS:
            break
        if calls and pause:
            time.sleep(pause)
        calls += 1
        if react(chat, mid, emoji):
            done += 1
            if emoji:
                tracked[key] = {"emoji": emoji, "pid": pid, "at": now.isoformat()}
            else:
                tracked.pop(key, None)
        else:
            tracked[key] = {**rec, "pid": pid, "want": emoji,
                            "fails": rec.get("fails", 0) + 1}
    _prune(tracked, set(want), now)
    if calls:
        print(f"Queue reactions: {done}/{calls} set")
    return calls


def _prune(tracked: dict, wanted: set, now: datetime) -> None:
    """Forget ✍ records after KEEP_DAYS, and failures once the post leaves the queue.

    ⚠️ A given-up record is kept while its post is still queued, or the
    next run would forget the failures and retry it all over again.
    """
    cutoff = now - timedelta(days=KEEP_DAYS)
    for key, rec in list(tracked.items()):
        at = rec.get("at")
        finished = rec.get("emoji") == WRITING and at and datetime.fromisoformat(at) < cutoff
        failed_only = "want" in rec and not at and key not in wanted
        if finished or failed_only:
            tracked.pop(key, None)
