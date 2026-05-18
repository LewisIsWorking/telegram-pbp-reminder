"""Single source of truth for "is this player permanent?".

A player is permanent if EITHER:
  * the per-record ``permanent`` flag in state is True, OR
  * the player's ``user_id`` is listed in
    ``config["permanent_user_ids"]``.

The per-record flag (set via ``/setpermanent`` / ``/unsetpermanent``
in a PBP topic) is the original mechanism and remains useful for
per-campaign overrides. The config list (added 2026-05-17) encodes
the rule "this user is always a permanent member of every campaign
they're in" without requiring per-record state to be set, which
avoids the recurring sync problem where new enrolments inherit
``permanent=False`` by default and someone has to remember to flip
the flag.

See L26 in ``docs/dev/REFACTOR_PROGRESS.md`` for the rationale and
the list of consumer sites that must use this helper rather than
reaching for ``player.get("permanent")`` directly.
"""


def is_permanent(player: dict, config: dict) -> bool:
    """Return True if this player should be treated as permanent.

    Logical OR of the per-record flag and the config list:
      * ``player["permanent"]`` True \u2192 always permanent
      * ``player["user_id"]`` in ``config["permanent_user_ids"]``
        \u2192 also permanent

    Both checks tolerate missing/None values:
      * Missing ``permanent`` key is treated as False.
      * Missing ``permanent_user_ids`` config key is treated as the
        empty list.
      * ``user_id`` is normalised to ``str`` on both sides of the
        comparison so int-vs-str storage doesn't break matching.
        (Telegram returns int IDs but historical state files have
        stored them as either; the bot's other lookups treat both
        forms as equivalent.)

    There is intentionally no "per-record False overrides config True"
    escape hatch. The 2026-05-17 rule is exception-free: A/H/R are
    perm everywhere. If that ever changes, we'll add a separate
    ``not_permanent_user_ids`` config key rather than overloading the
    existing per-record flag's meaning.
    """
    if player.get("permanent"):
        return True
    user_id = str(player.get("user_id", ""))
    if not user_id:
        return False
    perm_ids = config.get("permanent_user_ids", []) or []
    return any(str(uid) == user_id for uid in perm_ids)
