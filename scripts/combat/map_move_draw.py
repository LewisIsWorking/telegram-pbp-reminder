"""🧭 Draws /map moves (map_moves.py) on the map: an arrow from each creature to a ghost of it where it ends (2026-11-25).

Lewis: "showing where Zerius and Little Dread end up with an arrow for the movement". The ghost is the token's own art
at half strength (a ring when there is no art), and its label names the end square as the map's grid reads it. A move
that was stopped short gets a red bar on the side it hit.
"""
import math

from PIL import ImageDraw

from combat.map_moves import DIRS, square_of

ARROW = (0, 200, 255, 255)
STOPPED = (230, 40, 40, 255)


def _arrow(draw, a, b, width):
    """A line from a to b with a head at b."""
    draw.line([a, b], fill=ARROW, width=width)
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    head = width * 3.5
    pts = [b] + [(b[0] - head * math.cos(ang + s * 0.45), b[1] - head * math.sin(ang + s * 0.45)) for s in (-1, 1)]
    draw.polygon(pts, fill=ARROW)


def draw_moves(img, view: dict, results: list, fetch, origin) -> list:
    """Draw every move onto `img` (whose top-left is canvas pixel `origin`). Returns (label, x, y, size) for the
    ghosts, for map_draw's label placer, so they stay clear of the token names."""
    g = view["scene"]["grid"]["size"]
    ox, oy = origin
    draw = ImageDraw.Draw(img, "RGBA")
    width = max(3, g // 12)
    labels = []
    for r in results:
        t = r["token"]
        size = int(t["w"] * g)
        sx, sy = r["start"][0] - ox, r["start"][1] - oy
        ex, ey = r["end"][0] - ox, r["end"][1] - oy
        if r["moved"]:
            art = fetch(t.get("img"))
            if art:
                ghost = art.convert("RGBA").resize((size, size))
                ghost.putalpha(ghost.getchannel("A").point(lambda a: a // 2))
                img.alpha_composite(ghost, (max(0, int(ex)), max(0, int(ey))))
            draw.ellipse([ex + 2, ey + 2, ex + size - 2, ey + size - 2], outline=ARROW, width=width)
            _arrow(draw, (sx + size / 2, sy + size / 2), (ex + size / 2, ey + size / 2), width)
        if r["why"]:  # the side it hit: half a square past its centre, across the direction of travel
            dx, dy = DIRS[r["dir"]]
            cx, cy = ex + size / 2 + dx * size / 2, ey + size / 2 + dy * size / 2
            px, py = -dy * size / 3, dx * size / 3
            draw.line([(cx - px, cy - py), (cx + px, cy + py)], fill=STOPPED, width=width * 2)
        labels.append((f"{t['name'][:14]} > {square_of(view, *r['end'])}", int(ex), int(ey), size))
    return labels

