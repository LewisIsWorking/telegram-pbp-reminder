"""Answering "how do I dual class?" with the wiki's guide.

Added 2026-11-26. Players keep asking in the group how to dual class
("I can't figure out a way to dual class"), and the players who know keep
explaining it by hand. Lewis: have the bot link the guide instead.

A message gets the reply when it:
  - is from a human (never a bot, so the sheet check's "not dual class"
    lines can never set it off). GMs are answered too (Lewis, 2026-11-27,
    tested it with "How to Dual class");
  - mentions dual class AND reads like a how-to question or a "can't";
  - does not already point at the wiki, a guide or a link (someone
    answering it, like "there's a guide on the wiki", is left alone).

⚠️ Spam guard: one reply per topic per ``TOPIC_COOLDOWN`` and one per
player per ``PLAYER_COOLDOWN``, remembered in ``state[STATE_KEY]``.

An ask in an in-character topic is answered in that campaign's chat topic,
so the guide never lands in the roleplay.

The link is ``config["dual_class_guide_url"]``, defaulting to the guide's
page in the PathWarsWiki repo. Set it to "" to turn the reply off.
"""

import re
from datetime import datetime, timedelta, timezone

import telegram as tg
from helpers_pkg.groups import all_group_ids

STATE_KEY = "dual_class_help"
GUIDE_URL = ("https://github.com/LewisIsWorking/PathWarsWiki/blob/main/"
             "Writerside/topics/Info/Setting-up-dual-class-FoundryVTT.md")
TOPIC_COOLDOWN = timedelta(hours=6)
PLAYER_COOLDOWN = timedelta(hours=24)

DUAL = re.compile(r"\bdual[\s-]?class(?:ed|ing|es)?\b", re.IGNORECASE)
ASKS = re.compile(
    r"\?|\bhow\s+(?:do|can|to|would|does|should|did)\b|\bcan'?t\b|\bcannot\b"
    r"|\bcan not\b|\bcouldn'?t\b|\bunable\b|\bfigure\b|\bwork out\b|\bstuck\b"
    r"|\bhelp\b|\bwhere\s+(?:do|is|can|are)\b|\bnot sure\b|\bno idea\b"
    r"|\bconfused\b|\bstruggling\b|\bdon'?t know\b",
    re.IGNORECASE)
ANSWERED = re.compile(r"\bwiki\b|\bguides?\b|https?://|not dual class",
                      re.IGNORECASE)


def is_dual_class_question(text: str) -> bool:
    """True for a genuine "how do I dual class?" message."""
    if not text or text.startswith("/"):
        return False
    return bool(DUAL.search(text) and ASKS.search(text)
                and not ANSWERED.search(text))


def reply_text(sender: dict, url: str) -> str:
    uname = sender.get("username", "")
    who = f"@{uname}" if uname else (sender.get("first_name") or "there")
    return (f"\U0001f4d8 {who}, there's a step-by-step dual class guide on "
            f"the Path Wars wiki (also the Wiki app on ComeOnOver):\n{url}\n\n"
            "Short version: in Foundry, open the Tongs tray, press "
            "\"Dual class…\" (C×2), pick your sheet, then your 1st and 2nd "
            "class, and send it. No GM needed. A character made in the "
            "ComeOnOver character creator arrives already dual classed.")


def _reply_thread(config: dict, thread_id):
    """The chat topic for an in-character topic, else the same topic."""
    for pair in config.get("topic_pairs", []):
        if thread_id in pair.get("pbp_topic_ids", []):
            return pair.get("chat_topic_id", thread_id)
    return thread_id


def _recent(stamp: str | None, now: datetime, window: timedelta) -> bool:
    if not stamp:
        return False
    try:
        return now - datetime.fromisoformat(stamp) < window
    except (TypeError, ValueError):
        return False


def maybe_answer(msg: dict, config: dict, state: dict,
                 send=None) -> bool:
    """Reply with the guide if ``msg`` asks how to dual class. True when sent."""
    url = config.get("dual_class_guide_url", GUIDE_URL)
    sender = msg.get("from") or {}
    chat_id = msg.get("chat", {}).get("id")
    if not url or not sender.get("id") or sender.get("is_bot", False):
        return False
    if chat_id not in all_group_ids(config):
        return False
    user_id = str(sender["id"])
    if not is_dual_class_question(msg.get("text") or msg.get("caption") or ""):
        return False

    date = msg.get("date")
    now = (datetime.fromtimestamp(date, tz=timezone.utc) if date
           else datetime.now(timezone.utc))
    thread = _reply_thread(config, msg.get("message_thread_id"))
    memory = state.setdefault(STATE_KEY, {"topics": {}, "players": {}})
    topic_key = f"{chat_id}:{thread}"
    if (_recent(memory["topics"].get(topic_key), now, TOPIC_COOLDOWN)
            or _recent(memory["players"].get(user_id), now, PLAYER_COOLDOWN)):
        return False

    if not (send or tg.send_message)(chat_id, thread, reply_text(sender, url)):
        return False
    memory["topics"][topic_key] = now.isoformat()
    memory["players"][user_id] = now.isoformat()
    print(f"Dual class guide sent to {sender.get('first_name', user_id)}")
    return True
