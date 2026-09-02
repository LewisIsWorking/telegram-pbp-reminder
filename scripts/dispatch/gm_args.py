"""Resolving a GM command's campaign and its argument text.

Extracted from dispatch/cmd_gm.py 2026-09-02, when that file went past
the 200-line limit. Three small functions with one job between them:
turn what the router happened to pass into the campaign the command
actually means, and the argument the GM actually typed.

## Why `canonical_pid` exists

Player records, ``paused_campaigns``, ``current_scenes`` and
``characters`` are all keyed on a campaign's **first** pbp topic, and
every reader of those (``scheduled/alerts.py``,
``scheduled/inactivity_policy.py``, ``helpers_pkg/topic_maps``) looks
them up by that canonical pid. A caller passing a raw thread id would
have ``/pause`` answer "paused" while writing somewhere nobody reads,
and the bot would keep nudging.

⚠️ **HONEST SCOPE, measured 2026-09-02, not inferred.** Both of
cmd_gm's callers already hand it a canonical pid:

- ``parsing/message.py:50`` does ``maps.to_canonical[thread_id_str]``,
  and line 46 rejects any thread that is not a pbp topic at all.
- ``dispatch/bot_topic.py`` resolves via ``maps.name_to_pid`` /
  ``to_name``, both canonical-keyed.

So this is defence in depth, **not** a live bug being fixed. An earlier
version of this note claimed "17 topics affected across every
campaign"; that came from counting secondary and chat topics in the
config instead of tracing which of them can deliver a message here, and
it was wrong. ⭐ **Counting things in the config is not measuring the
code.**

It stays, called once at the top of ``handle()``, because four branches
canonicalised by hand and seven did not, and ``/setproxy`` was written
the day before by copying the shape of one that did not. Doing it once
removes the asymmetry that made the wrong shape available to copy.
"""

import re


def canonical_pid(pid: str, config: dict) -> str:
    """Return the primary pbp_topic_id for the campaign containing pid.

    An unknown pid is returned unchanged: rewriting it into some
    arbitrary campaign's would be worse than not resolving it.
    """
    for pair in config.get("topic_pairs", []):
        all_pids = [str(t) for t in pair.get("pbp_topic_ids", [])]
        chat = str(pair.get("chat_topic_id", ""))
        if pid in all_pids or pid == chat:
            return str(pair["pbp_topic_ids"][0])
    return pid


def campaign_name(pid: str, config: dict) -> str:
    """Return the campaign name for a given primary pid, or ""."""
    for pair in config.get("topic_pairs", []):
        if str(pair["pbp_topic_ids"][0]) == pid:
            return pair.get("name", "")
    return ""


def arg(raw_text: str, cmd_len: int) -> str:
    """Extract the argument from raw_text, stripping any @BotName suffix.

    e.g. '/scene@PathWarsNudgeBot The Docks' -> 'The Docks'
    """
    # Strip @BotName appended by Telegram in group commands
    cleaned = re.sub(r"^(/\w+)@\S+", r"\1", raw_text)
    return cleaned[cmd_len:].strip()
