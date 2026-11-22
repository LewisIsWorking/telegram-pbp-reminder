"""The GM as voters and readers see them (2026-11-22)."""

from helpers_pkg.config import gm_id_set


def gm_mention(uid: str, config: dict) -> str | None:
    """'@<gm_username>' when uid is a GM (gm_user_ids or gm_user_id), else None.

    2026-11-22: the GM votes in session polls too, and is never in the player registry,
    so a GM vote was reported as an "unknown voter" by uid.
    """
    ids = gm_id_set(config)
    if config.get("gm_user_id"):
        ids.add(str(config["gm_user_id"]))
    if str(uid) not in ids:
        return None
    return f"@{config.get('gm_username', 'PathWars')}"
