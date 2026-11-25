"""🧭 /map moves: where a slide, push or shove leaves each creature, for the GM only (2026-11-25).

Lewis, on a C06 tilting room, asked for "a visual preview of the slide, like an extension of /map, showing where Zerius
and Little Dread end up with an arrow for the movement", then said yes to ``/map Zerius slide S4, Little Dread S4``:
an arrow and a ghost token for each move, the end square named in grid coordinates (H12), and a slide that stops at a
wall, the edge of the map or a creature, saying which.

This file reads the moves and works them out on the live Foundry scene. map_draw.py draws them, map_move_post.py sends
the picture to the GM privately. Moves are straight lines, one square at a time, and are worked out in the order
written, so a creature moved first is where it ended up for the moves after it.
"""
import math
import re

from combat.map_draw import col_name
from combat.map_vision import _ray

DIRS = {"N": (0, -1), "NE": (1, -1), "E": (1, 0), "SE": (1, 1), "S": (0, 1), "SW": (-1, 1), "W": (-1, 0), "NW": (-1, -1)}
WORDS = {"NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W", "NORTHEAST": "NE", "NORTHWEST": "NW",
         "SOUTHEAST": "SE", "SOUTHWEST": "SW", "UP": "N", "DOWN": "S", "LEFT": "W", "RIGHT": "E"}
VERBS = ("slides", "slide", "pushed", "push", "pulled", "pull", "shoved", "shove", "moves", "move", "strides",
         "stride", "steps", "step", "knockback")
# A Stride or Step may pass through an ally's square but not end in one (PF2e "Moving Through a Creature's Space").
# Forced movement (slide, push, shove, pull, knockback) and a bare "move" stop at any creature, as before.
VOLUNTARY = {"stride", "strides", "step", "steps"}
_DIR = "|".join(sorted(list(DIRS) + list(WORDS), key=len, reverse=True))
CLAUSE = re.compile(rf"^\s*(?P<name>.+?)\s+(?:(?P<verb>{'|'.join(VERBS)})\s+)?(?P<dir>{_DIR})\s*(?P<n>\d{{1,3}})"
                    r"\s*(?P<unit>ft|feet|foot|sq|squares?)?\s*$", re.I)


def parse_moves(text: str):
    """[{name, verb, dir, squares}] for "Zerius slide S4, Little Dread S4", or None when it is not a move list."""
    clauses = [c for c in re.split(r"[,;\n]", text or "") if c.strip()]
    found = [CLAUSE.match(c) for c in clauses]
    if not found or not all(found):
        return None
    moves = []
    for m in found:
        d = m["dir"].upper()
        d = WORDS.get(d, d)
        n = int(m["n"])
        diag = 0 not in DIRS[d]
        squares = squares_in(n, diag) if (m["unit"] or "").lower().startswith(("f",)) else n
        verb = (m["verb"] or "move").lower()
        moves.append({"name": m["name"].strip(), "verb": verb, "dir": d, "squares": squares})
    return moves


def looks_like_moves(text: str) -> bool:
    """A GM's /map text that was meant as a move list but did not parse: a comma, or a move verb as a word."""
    return "," in (text or "") or bool(re.search(rf"\b(?:{'|'.join(VERBS)})\b", text or "", re.I))


def feet(squares: int, diagonal: bool) -> int:
    """PF2e distance: 5 ft a square, every second diagonal 10 ft."""
    return 5 * squares + (5 * (squares // 2) if diagonal else 0)


def squares_in(ft: int, diagonal: bool) -> int:
    """How many squares `ft` feet covers in a line (diagonals cost 5, 10, 5, 10...)."""
    n = 0
    while feet(n + 1, diagonal) <= ft:
        n += 1
    return n


def distance(squares: int, diagonal: bool) -> str:
    """'4 squares, 20 ft (6 m)': squares and feet, metres in brackets (5 ft = 1.5 m)."""
    ft = feet(squares, diagonal)
    return f"{squares} square{'' if squares == 1 else 's'}, {ft} ft ({ft * 0.3:g} m)"


_AT = re.compile(r"^(?P<name>.+?)\s*(?:\s(?:at|on)\s+|\()(?P<sq>[A-Z]{1,2}\d{1,3})\)?$", re.I)


def find_token(view: dict, name: str):
    """The token answering to `name`, or None: an exact name first, then the one matching all of its words.

    2026-11-25: when several tokens share the name (three "Goblin Warrior"s), none is guessed; the GM names the
    square too, "Goblin Warrior at F6" or "Goblin Warrior (F6)". See ambiguous()."""
    found = _candidates(view, name)
    return found[0] if len(found) == 1 else None


def ambiguous(view: dict, name: str) -> list:
    """The squares of every token `name` could mean, when it could mean more than one (else [])."""
    found = _candidates(view, name)
    return sorted(square_of(view, t["x"], t["y"]) for t in found) if len(found) > 1 else []


def _candidates(view: dict, name: str) -> list:
    m = _AT.match(name.strip())
    if m:
        on = [t for t in _candidates(view, m["name"]) if square_of(view, t["x"], t["y"]).upper() == m["sq"].upper()]
        if on:
            return on
    tokens = [t for t in view["tokens"] if t.get("name")]
    exact = [t for t in tokens if t["name"].strip().lower() == name.strip().lower()]
    if exact:
        return exact
    words = [w.lower() for w in name.split()]
    return [t for t in tokens if words and all(w in t["name"].lower() for w in words)]


def square_of(view: dict, x: float, y: float) -> str:
    """Grid coordinates of the square whose top-left canvas pixel is (x, y), as the map labels them: 'H12'."""
    s, g = view["scene"], view["scene"]["grid"]["size"]
    pad_x = math.ceil(s["width"] * s.get("padding", 0) / g) * g
    pad_y = math.ceil(s["height"] * s.get("padding", 0) / g) * g
    return f"{col_name(int((x - pad_x) // g))}{int((y - pad_y) // g) + 1}"


def _blocked_by(view, t, x, y, dx, dy, walls, others):
    """Why `t` at (x, y) cannot step one square along (dx, dy), or "" when it can."""
    s, g = view["scene"], view["scene"]["grid"]["size"]
    pad_x = math.ceil(s["width"] * s.get("padding", 0) / g) * g
    pad_y = math.ceil(s["height"] * s.get("padding", 0) / g) * g
    nx, ny, w, h = x + dx * g, y + dy * g, t["w"] * g, t["h"] * g
    if nx < pad_x or ny < pad_y or nx + w > pad_x + s["width"] or ny + h > pad_y + s["height"]:
        return "the edge of the map"
    for i in range(max(1, int(t["w"]))):
        for j in range(max(1, int(t["h"]))):
            cx, cy = x + (i + 0.5) * g, y + (j + 0.5) * g
            if _ray(cx, cy, dx * g, dy * g, walls, 1.0) < 1.0:
                return "a wall"
    for o in others:
        if _overlaps(t, nx, ny, o, g):
            return o.get("name") or "a creature"
    return ""


def _overlaps(t, x, y, o, g) -> bool:
    """Would `t` at (x, y) share a square with `o`?"""
    return x < o["x"] + o["w"] * g and o["x"] < x + t["w"] * g and y < o["y"] + o["h"] * g and o["y"] < y + t["h"] * g


def move_walls(view: dict) -> tuple[list, bool]:
    """(segments that block movement, True when they are the real movement walls).

    The COO scene view sends only the walls that block SIGHT (2026-11-25), so an invisible wall, a window or a
    terrain-only wall is not known; False then, and the caption says so. Ready for either way the server may grow:
    a separate `moveWalls` list, or every wall carrying Foundry's own `move` (0 = none) and `ds` (1 = an open door)."""
    if view.get("moveWalls") is not None:
        return [tuple(w["c"]) for w in view["moveWalls"]], True
    walls = view.get("walls") or []
    if walls and all("move" in w for w in walls):
        return [tuple(w["c"]) for w in walls if w["move"] and not (w.get("door") and w.get("ds") == 1)], True
    return [tuple(w["c"]) for w in walls], False


def resolve(view: dict, moves: list) -> tuple[list, list]:
    """(results, names not found). Each result: token, start/end (x, y), squares moved, wanted, why it stopped."""
    walls, _ = move_walls(view)
    down = {o["tokenId"] for o in ((view.get("combat") or {}).get("order") or []) if o.get("defeated")}
    where = {t["id"]: (t["x"], t["y"]) for t in view["tokens"]}
    results, missing = [], []
    for mv in moves:
        t = find_token(view, mv["name"])
        if t is None:
            missing.append(mv["name"])
            continue
        others = [dict(o, x=where[o["id"]][0], y=where[o["id"]][1]) for o in view["tokens"]
                  if o["id"] != t["id"] and o["id"] not in down]
        dx, dy, g = *DIRS[mv["dir"]], view["scene"]["grid"]["size"]
        if mv["verb"] in VOLUNTARY:   # allies are passed through, but the move cannot end on one
            allies = [o for o in others if o.get("disposition") == t.get("disposition")]
            blockers = [o for o in others if o not in allies]
        else:
            allies, blockers = [], others
        x, y = start = where[t["id"]]
        why, moved, free = "", 0, (x, y, 0)
        while moved < mv["squares"]:
            why = _blocked_by(view, t, x, y, dx, dy, walls, blockers)
            if why:
                break
            x, y, moved = x + dx * g, y + dy * g, moved + 1
            if not any(_overlaps(t, x, y, o, g) for o in allies):
                free = (x, y, moved)
        if (x, y) != free[:2]:   # it would end on an ally: back to the last free square
            why = next(o.get("name") or "a creature" for o in allies if _overlaps(t, x, y, o, g))
            x, y, moved = free
        where[t["id"]] = (x, y)
        results.append(dict(mv, token=t, start=start, end=(x, y), moved=moved, why=why))
    return results, missing


def describe(view: dict, r: dict) -> str:
    """One caption line: 'Zerius slides S 4 squares, 20 ft (6 m): G9 to G13.' or where it stopped and why."""
    diag = 0 not in DIRS[r["dir"]]
    name, a, b = r["token"]["name"], square_of(view, *r["start"]), square_of(view, *r["end"])
    if r["squares"] == 0:
        return f"➖ {name}: {r['verb']} {r['dir']} 0 squares (less than one square asked). Stays on {a}."
    if r["moved"] == 0:
        return f"⛔ {name} cannot {r['verb']} {r['dir']}: {r['why']} is in the way. Stays on {a}."
    if r["why"]:
        return (f"⛔ {name}: {r['verb']} {r['dir']} {distance(r['moved'], diag)} of {r['squares']}, {a} to {b}, "
                f"stopped by {r['why']}.")
    return f"➡️ {name}: {r['verb']} {r['dir']} {distance(r['moved'], diag)}, {a} to {b}."
