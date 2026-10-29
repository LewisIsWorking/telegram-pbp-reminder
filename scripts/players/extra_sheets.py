"""Who may make a second character sheet in which campaign.

Added 2026-10-12 with ``/extrasheet`` (dispatch/cmd_extrasheet.py). Lewis:
a player has one sheet per world, and may have one more, at most two.

The file is ``data/state/extra_sheets.json``, an aux file the workflow
commits like every other state file. ComeOnOverUno reads it from GitHub
and tells Tongs, which offers the second sheet in the Foundry world.

⛔ **The shape is a contract with ComeOnOverUno, not ours to change:**

    {"grants": [{"telegram_user_id": "123", "campaign": "C06",
                 "granted_by": "123", "at": "2026-10-12T03:00:00Z"}]}

Ids are strings, the campaign is the upper-case ``code`` from
config.json. At most ONE grant per (user, campaign): the grant is the
whole cap, so a second one is refused, never stored twice.
"""

from state_store import StateStore

_NAME = "extra_sheets"
_store = StateStore()


def load() -> dict:
    """The file as ``{"grants": [...]}``, tolerating missing or bad data.

    A file that is not that shape counts as no grants rather than an
    error: nobody gaining a sheet is the safe direction.
    """
    data = _store.load_aux(_NAME, default={})
    grants = data.get("grants") if isinstance(data, dict) else None
    return {"grants": grants if isinstance(grants, list) else []}


def has_grant(user_id: str, code: str) -> bool:
    """True when this player already has their extra sheet in ``code``."""
    return any(isinstance(g, dict) and g.get("telegram_user_id") == user_id
               and g.get("campaign") == code for g in load()["grants"])


def grant(user_id: str, code: str, granted_by: str, at: str) -> bool:
    """Record one extra sheet. False, and nothing written, if already held."""
    if has_grant(user_id, code):
        return False
    data = load()
    data["grants"].append({"telegram_user_id": user_id, "campaign": code,
                           "granted_by": granted_by, "at": at})
    _store.save_aux(_NAME, data)
    return True
