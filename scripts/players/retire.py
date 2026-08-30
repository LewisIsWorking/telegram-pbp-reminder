"""Take a seat off a roster, once, in one place.

Extracted 2026-08-30. The same twelve lines existed twice: in
``scheduled/alerts.check_player_activity`` for the 4-week auto-sweep and
in ``players/management.handle_kick`` for the GM command. They agreed on
the important parts and differed on one field, ``kicked``, which is
exactly the shape that drifts.

Three things have to happen together, and a copy that forgets one is
silently wrong rather than broken:

* the record leaves ``players``, or the seat still counts in every
  roster total;
* ``on_leave`` records it in ``player_history``, or ``/roster C08`` shows
  a player vanishing with no event to explain it;
* ``removed_players`` gains an entry, or ``_track_player`` treats their
  next message as a **first** join rather than a rejoin.
"""

from datetime import datetime, timezone


def retire_seat(player_key: str, state: dict, config: dict | None = None,
                *, now: datetime | None = None, kicked: bool = False,
                announce: bool = True,
                campaign_name: str | None = None) -> dict:
    """Remove one seat and record why. Returns the popped record.

    ``kicked`` distinguishes a GM's deliberate ``/kick`` from the
    inactivity sweep. Both end the seat; only one of them is a decision
    somebody made about a person, and the history should say which.

    ``announce=False`` suppresses the per-event roster post so a caller
    retiring several seats at once can post the roster once at the end.
    It is a separate argument rather than "pass ``config=None``", which
    is how ``on_leave`` expresses it: that overloads one parameter to
    mean both "here is the config" and "stay quiet", and a caller that
    genuinely has no config then looks like a caller asking for silence.

    ``campaign_name`` overrides the record's own, for the ``/kick`` path
    where the command already knows which campaign it is acting in.
    """
    now = now or datetime.now(timezone.utc)
    removed = state["players"].pop(player_key)

    from players.history import on_leave
    on_leave(str(removed.get("pbp_topic_id", "")),
             str(removed.get("user_id", "")),
             removed["first_name"], removed.get("username", ""),
             state, config if announce else None)

    entry = {
        "removed_at": now.isoformat(),
        "first_name": removed["first_name"],
        "username": removed.get("username", ""),
        "campaign_name": campaign_name or removed.get("campaign_name", ""),
    }
    if kicked:
        # Only written when true, matching every historical entry. A
        # `"kicked": false` on 39 old records would look like a fact
        # somebody established rather than a field that did not exist.
        entry["kicked"] = True
    state.setdefault("removed_players", {})[player_key] = entry
    return removed
