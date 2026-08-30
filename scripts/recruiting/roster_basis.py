"""How many players there are, on all three bases, in one command.

Lewis, 2026-08-30: *"Are there actually 44 active players?"* There were
not. 44 was the number of records in ``players.json``, quoted in the
recruiting README under the heading "seats", and read as reach.

Three questions, three answers, all correct
-------------------------------------------
* **records** - rows in ``players.json``. Enrolment, including seats in
  campaigns that no longer exist.
* **seats** - records whose ``pbp_topic_id`` is a campaign the config
  still knows about. Two rows currently fail this: C11 Dark Pockets
  retired and its roster rows did not.
* **active** - seats that posted inside the window (30 days, matching
  ``roster_members._ACTIVE_DAYS``). This is the only one that answers
  "is anybody playing".

Each is also reported by **people** as well as by seats, because one
person holding five seats is five seats and one person, and which of
those two you quote decides whether recruiting looks solved.

Why this is a module and not a paragraph
----------------------------------------
The README carried these numbers as prose twice and they were wrong the
second time, because they were re-derived by hand against a checkout that
had moved. A measurement written into prose has no expiry; a measurement
you can re-run does. Point this at any revision:

    python -m recruiting.roster_basis
    git show <rev>:data/state/players.json | python -m recruiting.roster_basis -

⚠️ Read-only, deliberately. It never writes state, so it is safe to run
against production data at any time.
"""

import collections
import datetime
import json
import pathlib
import sys

WINDOW_DAYS = 30


def configured_pids(config: dict) -> set:
    """Every pbp topic id the config still claims, as strings."""
    return {str(t) for pair in config.get("topic_pairs", [])
            for t in pair.get("pbp_topic_ids", [])}


def posted_days_ago(player: dict, asof: datetime.datetime) -> float | None:
    """Days since this seat last posted, or ``None`` if it never has.

    ``None`` rather than a large number: "never posted" and "posted long
    ago" are different states, and only one of them means the record was
    created by something other than a message.
    """
    stamp = player.get("last_post_time")
    if not stamp:
        return None
    try:
        when = datetime.datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=datetime.timezone.utc)
    return (asof - when).total_seconds() / 86400.0


def _humans(records) -> int:
    return len({str(p.get("user_id")) for p in records})


def counts(players: dict, config: dict,
           asof: datetime.datetime, window: int = WINDOW_DAYS) -> dict:
    """The three bases, by seat and by person, plus concentration."""
    records = list(players.values())
    live_pids = configured_pids(config)
    seats = [p for p in records if str(p.get("pbp_topic_id")) in live_pids]
    # ⚠️ `ago is not None`, never `if ago`. A seat that posted moments ago
    # measures 0.0 days, which is falsy, so the terse form would file the
    # most active player in the group under "never posted". Same None-vs-0
    # trap as `days_since` in log.py.
    active = []
    for player in seats:
        ago = posted_days_ago(player, asof)
        if ago is not None and ago <= window:
            active.append(player)

    held = collections.Counter(str(p.get("user_id")) for p in active)
    top_five = sum(n for _uid, n in held.most_common(5))
    return {
        "records": len(records), "record_humans": _humans(records),
        "seats": len(seats), "seat_humans": _humans(seats),
        "active_seats": len(active), "active_humans": len(held),
        "top_five_seats": top_five,
        "top_five_pct": round(100 * top_five / len(active)) if active else 0,
        "window_days": window,
    }


def render(figures: dict) -> str:
    """A block that names the basis of every number in it."""
    rows = [("records (enrolment)", "records", "record_humans"),
            ("seats in a live campaign", "seats", "seat_humans"),
            (f"active (<={figures['window_days']}d)", "active_seats",
             "active_humans")]
    lines = [f"{label:<25}{figures[s]:>4} seats  {figures[h]:>3} people"
             for label, s, h in rows]
    lines.append(f"{'top five hold':<25}{figures['top_five_seats']:>4} of "
                 f"{figures['active_seats']} active seats "
                 f"({figures['top_five_pct']}%)")
    return "\n".join(lines)


def repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent.parent


def load_players(source: str, stdin=None) -> dict:
    """Read a ``players.json`` blob from a path, or from stdin for ``-``.

    Accepts both the wrapped ``{"players": {...}}`` shape and a bare
    mapping, because ``git show <rev>:data/state/players.json`` has been
    both over the life of the file.
    """
    raw = ((stdin or sys.stdin).read() if source == "-"
           else pathlib.Path(source).read_text(encoding="utf-8"))
    blob = json.loads(raw)
    return blob.get("players", blob)


def asof_from(argv: list, default: datetime.datetime) -> datetime.datetime:
    """``--asof YYYY-MM-DD``, or ``default``.

    ⭐⭐ This option is the whole reason the tool is trustworthy on an old
    revision. Piping ``git show <rev>:data/state/players.json`` without it
    measures a 2026-08-20 roster against today's clock, which answers
    "how many of the people enrolled then have posted recently" and prints
    it under the heading "active". Plausible, differently defined, and
    wrong for the comparison you were making. Measured live: 23 active
    seats against today, 29 against 2026-08-20.
    """
    if "--asof" not in argv:
        return default
    raw = argv[argv.index("--asof") + 1]
    return datetime.datetime.fromisoformat(raw).replace(
        tzinfo=datetime.timezone.utc)


def main(argv: list, now: datetime.datetime | None = None,
         stdin=None, out=print) -> int:
    """``python -m recruiting.roster_basis [players.json|-] [--asof DATE]``.

    Reads ``config.json`` for the live campaign list whatever the source
    of the roster, so an old ``players.json`` is measured against today's
    campaigns. That is the right basis for "has recruiting worked": a
    campaign retired since should not count as reach at either end of the
    comparison.

    ``now``, ``stdin`` and ``out`` are injected rather than reached for so
    this is testable without a coverage pragma.
    """
    root = repo_root()
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    positional = [a for a in argv[1:] if not a.startswith("--")]
    if "--asof" in argv:
        positional = [a for a in positional
                      if a != argv[argv.index("--asof") + 1]]
    source = positional[0] if positional else str(
        root / "data/state/players.json")
    players = load_players(source, stdin)
    asof = asof_from(argv, now or datetime.datetime.now(datetime.timezone.utc))
    out(f"{source}  measured as of {asof.date().isoformat()}")
    out(render(counts(players, config, asof)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
