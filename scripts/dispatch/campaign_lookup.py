"""Turning a bot-topic command's argument into a campaign.

Extracted from dispatch/bot_topic.py 2026-09-02 when that file went
past the 200-line limit.

⛔ Until then this matched the WHOLE argument string and nothing else,
so any command carrying an argument after the campaign name failed to
resolve at all. ``/markdone Kibwe 3`` looked up a campaign called
"kibwe 3", found none, and answered *"Specify a campaign: /markdone
<name>"*, while markdone.py's own docstring says it works "in any PBP
topic or bot topic". ``handle_bot_topic_cmd`` already strips the
campaign words back out of ``args`` before dispatching, so the trailing
argument was always the intended shape. Only the lookup disagreed.

⚠️ It was also what made two regression tests hollow: they drove
``/markdone Kibwe 1`` at the bot topic to prove a crash was fixed, and
the command bounced off "Specify a campaign" without reaching a handler
at all. Both passed, and the mutation restoring the crash survived
them.
"""


def resolve_campaign(args: str, maps) -> tuple[str | None, str | None]:
    """Resolve a campaign name/keyword to (pid, campaign_name).

    Returns ``(None, None)`` when the argument names no campaign.
    Longest prefix first, so a multi-word campaign name ("The Junction")
    still beats its own first word.
    """
    key = args.strip().lower()
    if not key:
        return None, None
    words = key.split()
    for n in range(len(words), 0, -1):
        candidate = " ".join(words[:n])
        pid = maps.name_to_pid.get(candidate)
        if pid:
            return pid, maps.to_name[pid]
        for name, p in maps.name_to_pid.items():
            if name.startswith(candidate):
                return p, maps.to_name[p]
    return None, None
