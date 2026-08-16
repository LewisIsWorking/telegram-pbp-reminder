"""Name a message from its ID: who sent it, what it said, is it a problem?

Lewis, 2026-08-16: *"You should capture the message's contents and sender
so you know if it is an issue."*

The alerts up to now reported bare IDs. ``mid=169479`` cannot be triaged
by anyone. Worse, it flattens the one distinction the delete guard exists
to make:

  * a stale bot post nobody will miss, and
  * **the bot reaching for a player's message**

The second is the reason ``perform_guarded_delete`` exists at all, and
under the old alert format both arrived looking identical.

Three sources, most authoritative first:

1. ``posting.sent_log`` — what the bot recorded at send time. Definitive
   for bot messages, because it was written by the code that sent them.
2. The transcript archive under ``data/pbp_logs/`` — every player and GM
   message the bot has ever ingested, stored as
   ``**Name** [GM] (timestamp) msg#<id>@<thread>:`` followed by the text.
   Definitive for non-bot messages.
3. The per-campaign queue state — ``unreplied`` entries carry
   ``user_name`` and ``preview`` for anything currently awaiting a reply.

⭐ When all three miss, that is **not** a shrug. An ID nothing recognises
is more alarming than one we can name, because it means something asked
the bot to delete a message it has no record of ever seeing. The verdict
is ``unknown`` and callers are expected to treat it as the loud case.
"""

import json
import re
from pathlib import Path

from posting.sent_log import describe as _sent_describe

_REPO = Path(__file__).resolve().parent.parent.parent
_LOGS = _REPO / "data" / "pbp_logs"
_QUEUES = _REPO / "data" / "state" / "queues"

# **Ryo Yamakawa** (2026-08-15 07:51:12) msg#172171@40585:
_ENTRY = re.compile(
    r"^\*\*(?P<who>[^*]+)\*\*\s*(?P<gm>\[GM\])?\s*"
    r"\((?P<when>[^)]+)\)\s*msg#(?P<mid>\d+)@(?P<thread>\d+):\s*$")

# Verdicts. BOT is routine; PLAYER on a delete path is an incident;
# UNKNOWN is the one that should make somebody look.
BOT = "bot"
PLAYER = "player"
UNKNOWN = "unknown"


def _from_sent_log(message_id: int) -> dict | None:
    facts = _sent_describe(message_id)
    if not facts:
        return None
    return {"origin": BOT, "sender": "PathWarsNudgeBot",
            "when": facts.get("at"), "thread_id": facts.get("thread_id"),
            "preview": facts.get("preview") or "", "source": "sent_log"}


def _from_transcripts(message_id: int) -> dict | None:
    """Scan the archive for this ID. Newest files first — a message being
    asked about is far more likely to be recent, and stopping early keeps
    a rare alert from reading 3.5MB of markdown."""
    needle = f"msg#{message_id}@"
    if not _LOGS.exists():
        return None
    for path in sorted(_LOGS.rglob("*.md"), reverse=True):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if needle not in text:
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines):
            m = _ENTRY.match(line)
            if not m or m.group("mid") != str(message_id):
                continue
            body = []
            for follow in lines[i + 1:]:
                if not follow.strip() or _ENTRY.match(follow):
                    break
                body.append(follow.strip())
            return {"origin": PLAYER, "sender": m.group("who").strip(),
                    "is_gm": bool(m.group("gm")), "when": m.group("when"),
                    "thread_id": int(m.group("thread")),
                    "preview": " ".join(body)[:120],
                    "campaign": path.parent.name, "source": "transcript"}
    return None


def _from_queue_state(message_id: int) -> dict | None:
    if not _QUEUES.exists():
        return None
    for path in _QUEUES.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for entry in data.get("unreplied") or []:
            if entry.get("message_id") == message_id:
                return {"origin": PLAYER,
                        "sender": entry.get("user_name") or "?",
                        "when": entry.get("time"),
                        "thread_id": entry.get("thread_id"),
                        "preview": entry.get("preview") or "",
                        "campaign": path.stem, "source": "queue_state"}
    return None


def _from_registry(message_id: int) -> dict | None:
    """Weakest source, and still decisive on the question that matters.

    ``bot_sent_ids`` carries no text, but membership alone proves the bot
    sent it. Checked last so any richer source wins, and checked at all
    so that ``unknown`` keeps its meaning: without this, every message
    sent before ``sent_log`` existed would read as unrecognised and the
    genuinely alarming case would drown in a crowd of harmless ones.
    """
    from posting.bot_sent_registry import is_bot_sent
    if not is_bot_sent(message_id):
        return None
    return {"origin": BOT, "sender": "PathWarsNudgeBot", "when": None,
            "thread_id": None,
            "preview": "(sent before send-logging; no text recorded)",
            "source": "bot_sent_registry"}


def describe(message_id: int) -> dict:
    """Best available facts about a message. Always returns a dict.

    ``origin`` is the field to branch on: ``bot`` is routine, ``player``
    on a delete path is an incident, ``unknown`` means no local record
    exists at all and deserves the same attention as ``player``.
    """
    for lookup in (_from_sent_log, _from_transcripts, _from_queue_state,
                   _from_registry):
        facts = lookup(message_id)
        if facts:
            return facts
    return {"origin": UNKNOWN, "sender": None, "when": None,
            "thread_id": None, "preview": "", "source": None}


def one_line(message_id: int, facts: dict | None = None) -> str:
    """A single human-readable line for an alert or report."""
    facts = facts or describe(message_id)
    if facts["origin"] == UNKNOWN:
        return f"mid={message_id} — ⁉️ no local record of this message"
    who = facts.get("sender") or "?"
    if facts.get("is_gm"):
        who += " [GM]"
    where = facts.get("campaign") or facts.get("thread_id") or "?"
    preview = facts.get("preview") or "(no text)"
    return f"mid={message_id} — {who} in {where}: “{preview}”"
