"""How the preflight checks tell a human, and where.

Extracted from ``preflight/gate.py`` on 2026-09-04, which reached 205
lines once the debug topic landed. Deciding whether to halt and choosing
who to interrupt are different jobs; this is the second one, and it is
the only part that talks to Telegram.

⭐ **Two destinations with opposite economics**, and that is the whole
design:

  bot topic ("alert")   Rationed hard. Every message here is unrecorded,
                        so it becomes an undeletable orphan after 48h -
                        the exact harm the gate exists to prevent. Only
                        things that bring a human to the keyboard.

  debug topic ("debug") "The Bot is Dead", a separate chat entirely.
                        A log, meant to accumulate. Lewis asked on
                        2026-09-04 for as much detail as we want here,
                        so the verbosity that would be harmful above is
                        the point.
"""

import os

import requests

from preflight.prior_runs import explain
from preflight.run_history import WORKFLOW_FILE


def send_alert(reasons: list, age_hours: float | None, repo: str,
               extra: str = "") -> None:
    """Tell a human, on the streak lengths that warrant it.

    ⚠️ This post is itself an unrecorded bot message, and so becomes an
    orphan - the exact harm the gate exists to prevent. It is worth it at
    most once a day, because it is the only thing that brings a human to
    fix the cause. Nothing else the bot sends earns that trade.

    ⭐ ``extra`` carries the self-repair outcome so it rides on THIS
    message instead of being a second one. Added 2026-09-02: the
    watchdog was notifying on every repair attempt, ungated, which is
    48 messages a day during an outage. Each one is an unrecorded bot
    message that becomes permanently undeletable after 48h, so the
    watchdog was manufacturing the exact harm it exists to prevent,
    during the very window in which posting is forbidden for that reason.
    """
    body = f"\U0001f6d1 Bot posting PAUSED\n\n{explain(reasons, age_hours)}"
    if extra:
        body += f"\n\n{extra}"
    notify(f"{body}\n\nhttps://github.com/{repo}/actions/workflows/{WORKFLOW_FILE}")


def notify(text: str) -> None:
    """Send one message to the bot topic. Never raises.

    Extracted from ``send_alert`` on 2026-09-01 so the self-repair path
    can report what it did through the same channel. ⚠️ Every caller is
    posting an unrecorded message and creating an orphan; that price is
    only worth paying for things that bring a human to the keyboard.
    """
    from helpers_pkg.config import load_config
    config = load_config()
    _send(config.get("group_id"), config.get("bot_topic_id"), text, "alert")


def notify_debug(text: str) -> None:
    """Send the verbose report to the "The Bot is Dead" debug topic.

    ⭐ A different chat AND topic on purpose (2026-09-04, Lewis's ask).
    The bot-topic alert has to stay short and rationed because every
    message there is unrecorded and becomes an undeletable orphan after
    48h. A debug topic is a log; it is *supposed* to accumulate, so the
    verbosity that would be harmful there is the whole point here.
    """
    from helpers_pkg.config import load_config
    config = load_config()
    _send(config.get("debug_chat_id"), config.get("debug_topic_id"),
          text, "debug")


def _send(chat_id, thread_id, text: str, label: str) -> None:
    """One Telegram send. Never raises, and never claims a silent success.

    ⚠️ Until 2026-09-04 this printed "alert sent" without looking at the
    response, so a wrong topic id, a bot removed from the chat, or a
    message over Telegram's 4096-char cap all reported success. An
    alerting path that cannot tell you it failed is worse than none: it
    converts an outage into a silence that looks handled.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token or not chat_id or not thread_id:
        print(f"[preflight] no token or no {label} destination "
              f"(chat={chat_id} thread={thread_id}); skipping {label}")
        return
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "message_thread_id": thread_id,
                  "text": text},
            timeout=20,
        )
        if response.status_code != 200:
            print(f"[preflight] {label} REJECTED by Telegram: HTTP "
                  f"{response.status_code} {response.text[:300]}")
            return
        print(f"[preflight] {label} sent to {chat_id}/{thread_id}")
    except Exception as error:  # noqa: BLE001 - alerting must not break the gate
        print(f"[preflight] {label} failed: {error}")
