"""``/setproxy`` and ``/clearproxy``: who actually posts for a character.

Added 2026-09-01. See ``players/proxy.py`` for why this is not just
another ``/setpermanent``.

Its own module rather than another branch in ``cmd_gm.py``, which was at
183 lines and had no room for a two-argument command.
"""

import telegram as tg
from players.proxy import proxy_username


def _seats(target: str, pid: str, state: dict) -> list:
    """Every record in this campaign whose username matches ``target``."""
    wanted = target.lower().lstrip("@")
    return [p for p in state.get("players", {}).values()
            if str(p.get("pbp_topic_id", "")) == str(pid)
            and str(p.get("username") or "").lower().lstrip("@") == wanted]


def handle_proxy(text: str, raw_text: str, pid: str, name: str,
                 state: dict, gid: int, tid: int) -> bool:
    """Set or clear ``played_by`` on a seat in this campaign."""
    clearing = text.startswith("/clearproxy")
    args = raw_text.split()[1:]

    if clearing:
        if len(args) != 1:
            tg.send_message(gid, tid, "Usage: /clearproxy @absent_player")
            return True
        absent = args[0]
        seats = _seats(absent, pid, state)
        if not seats:
            tg.send_message(gid, tid,
                            f"Player {absent} not found in {name}.")
            return True
        for seat in seats:
            seat.pop("played_by", None)
        tg.send_message(
            gid, tid,
            f"✅ {seats[0].get('first_name', absent)} ({absent}) is measured "
            f"on their own posting again in {name}.")
        return True

    if len(args) != 2:
        tg.send_message(gid, tid,
                        "Usage: /setproxy @absent_player @who_posts_for_them")
        return True

    absent, proxy = args[0], args[1]
    seats = _seats(absent, pid, state)
    if not seats:
        tg.send_message(gid, tid, f"Player {absent} not found in {name}.")
        return True

    proxy_name = proxy.lstrip("@")
    if proxy_name.lower() == absent.lower().lstrip("@"):
        # ⛔ Self-proxy would resolve to the seat's own time and read as
        # a working proxy on the roster. Silently doing nothing while
        # displaying "[played by @them]" is worse than refusing.
        tg.send_message(gid, tid, "A player cannot be their own proxy.")
        return True

    # ⚠️ NOT an error if the proxy is not on this roster yet: they may
    # join, or be added later. But say so, because an unresolved proxy
    # measures the seat NORMALLY and the GM must not think it is covered.
    unknown = not _seats(proxy_name, pid, state)
    for seat in seats:
        seat["played_by"] = proxy_name

    who = seats[0].get("first_name", absent)
    message = (f"✅ {who} ({absent}) in {name} is now measured through "
               f"@{proxy_name}, who posts for them.\n"
               f"They will not be nudged, and they stay on the roster for as "
               f"long as @{proxy_name} keeps posting.")
    if unknown:
        message += (f"\n\n⚠️ @{proxy_name} is not on {name}'s roster, so until "
                    f"they are, {who} is measured on their own posting as "
                    f"before.")
    tg.send_message(gid, tid, message)
    print(f"Proxy set: {absent} played by {proxy_name} in {name}")
    return True
