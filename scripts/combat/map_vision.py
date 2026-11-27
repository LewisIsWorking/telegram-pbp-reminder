"""🗺️ What a token can see, from the COO scene view (combat/map_view.py): line of sight past the scene's walls, limited by darkness.

Lewis, 2026-11-18: "Just make sure it sees through a token's vision." So a map posted to players shows only what their
tokens see, and no creature outside it.

How: rays from the token's centre towards every wall corner (and a hair either side), each stopped by the nearest
sight-blocking wall, give the line-of-sight polygon (the standard visibility-polygon method Foundry uses too). In a lit
scene (global light on, darkness inside its range) that polygon is the vision. In the dark it is cut down to the token's
own sight range plus any light source's radius. A token's vision cone (sight.angle, 160 on most Path Wars tokens since
Lewis asked for it on 2026-11-18) cuts it down again to what is in front of the token, as Foundry's LimitedAnglePolygon
does: centred on rotation + 90 degrees (rotation 0 looks down the map), and the token's own square always seen.
Simplified on purpose (each errs towards showing LESS): one-way walls and limited/proximity walls block both ways,
darkvision beyond the token's configured sight range is ignored, fog of war (areas seen before) is not shown.
"""
import math

from PIL import Image, ImageChops, ImageDraw


def _ray(ox, oy, dx, dy, segments, limit):
    best = limit
    for (x1, y1, x2, y2) in segments:
        sx, sy = x2 - x1, y2 - y1
        den = dx * sy - dy * sx
        if abs(den) < 1e-12:
            continue
        t = ((x1 - ox) * sy - (y1 - oy) * sx) / den
        u = ((x1 - ox) * dy - (y1 - oy) * dx) / den
        if 1e-9 < t < best and -1e-9 <= u <= 1 + 1e-9:
            best = t
    return best


def sight_polygon(ox, oy, segments, limit):
    """The points of the visibility polygon round (ox, oy), out to `limit` pixels."""
    angles = set()
    for (x1, y1, x2, y2) in segments:
        for (px, py) in ((x1, y1), (x2, y2)):
            if math.hypot(px - ox, py - oy) > limit + 1:
                continue
            a = math.atan2(py - oy, px - ox)
            angles.update((a - 1e-4, a, a + 1e-4))
    angles.update(i * math.tau / 180 for i in range(180))  # round the edge of the range, and open ground
    # ⚠️ Sorted in ONE range (-pi..pi], or the polygon crosses itself. 2026-11-18: the even rays ran 0..2pi while the
    # corners ran -pi..pi, and an open room came out with a black wedge (and could show squares behind a wall).
    pts = []
    for a in sorted({math.atan2(math.sin(a), math.cos(a)) for a in angles}):
        dx, dy = math.cos(a), math.sin(a)
        t = _ray(ox, oy, dx, dy, segments, limit)
        pts.append((ox + dx * t, oy + dy * t))
    return pts


def cone_polygon(ox, oy, rotation, angle, far):
    """The token's vision cone as a polygon, or None for a full circle. Foundry: aMin = rotation + 90 - angle / 2."""
    if not angle or angle >= 360:
        return None
    a0 = math.radians(rotation + 90 - angle / 2)
    steps = max(8, int(angle / 3))
    return [(ox, oy)] + [(ox + far * math.cos(a0 + math.radians(angle) * i / steps),
                          oy + far * math.sin(a0 + math.radians(angle) * i / steps)) for i in range(steps + 1)]


def scene_is_lit(environment):
    """Global light on and the darkness level inside its range: everything in line of sight is visible."""
    env = environment or {}
    gl = env.get('globalLight') or {}
    if not gl.get('enabled'):
        return False
    darkness = env.get('darknessLevel', 0) or 0
    rng = gl.get('darkness') or {}
    return (rng.get('min', 0) or 0) <= darkness <= (rng.get('max', 1) if rng.get('max') is not None else 1)


def sight_walls(d):
    """The walls that block sight. Today the server sends only those (2026-11-25); should it ever send every wall with
    Foundry's own `sight` (0 = none) and `ds` (1 = an open door) for move previews (map_moves.move_walls), a window or
    an open door must not start blinding the player's map."""
    return [w for w in d.get('walls') or []
            if w.get('sight', 1) and not (w.get('door') and w.get('ds') == 1)]


def vision_mask(d, viewers, size, origin):
    """An 'L' mask the size of the cropped image: 255 where at least one viewer sees.

    size = (w, h) of the crop; origin = the crop's top-left in canvas coordinates (padding included)."""
    s, g = d['scene'], d['scene']['grid']['size']
    px_per_ft = g / (s['grid'].get('distance') or 5)
    pad_x = math.ceil(s['width'] * s['padding'] / g) * g
    pad_y = math.ceil(s['height'] * s['padding'] / g) * g
    x0, y0 = origin
    # The scene's own edge blocks sight too, so a polygon never runs off into the padding.
    bx0, by0, bx1, by1 = pad_x, pad_y, pad_x + s['width'], pad_y + s['height']
    segments = [tuple(w['c']) for w in sight_walls(d)] + [
        (bx0, by0, bx1, by0), (bx1, by0, bx1, by1), (bx1, by1, bx0, by1), (bx0, by1, bx0, by0)]
    lit = scene_is_lit(s.get('environment')) or not s.get('tokenVision', True)
    far = math.hypot(s['width'], s['height']) * 2
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    lights = d.get('lights', [])
    for t in viewers:
        ox, oy = t['x'] + t['w'] * g / 2, t['y'] + t['h'] * g / 2
        poly = [(x - x0, y - y0) for (x, y) in sight_polygon(ox, oy, segments, far)]
        sight = t.get('sight') or {}
        cone = cone_polygon(ox - x0, oy - y0, t.get('rotation') or 0, sight.get('angle') or 360, far)
        if lit and cone is None:
            draw.polygon(poly, fill=255)
            continue
        los = Image.new('L', size, 0)
        ImageDraw.Draw(los).polygon(poly, fill=255)
        if cone is not None:  # line of sight AND (in front of the token OR its own square)
            front = Image.new('L', size, 0)
            fd = ImageDraw.Draw(front)
            fd.polygon(cone, fill=255)
            own = t['w'] * g / 2
            fd.ellipse([ox - x0 - own, oy - y0 - own, ox - x0 + own, oy - y0 + own], fill=255)
            los = ImageChops.multiply(los, front)
        if lit:
            mask.paste(255, (0, 0), los)
            continue
        # Dark: line of sight AND (own sight range OR inside a light).
        reach = Image.new('L', size, 0)
        rd = ImageDraw.Draw(reach)
        r = (sight.get('range') or 0) * px_per_ft + t['w'] * g / 2
        if r > 0:
            rd.ellipse([ox - x0 - r, oy - y0 - r, ox - x0 + r, oy - y0 + r], fill=255)
        for l in lights:
            lr = max(l['dim'], l['bright']) * px_per_ft
            rd.ellipse([l['x'] - x0 - lr, l['y'] - y0 - lr, l['x'] - x0 + lr, l['y'] - y0 + lr], fill=255)
        mask.paste(255, (0, 0), ImageChops.multiply(los, reach))
    return mask
