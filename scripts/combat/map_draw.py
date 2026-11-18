"""🗺️ Draws a campaign's battle map as its party sees it, for /map (2026-11-18).

Lewis: "Building a Foundry screenshot tool that's player view / party view could be really good for telegram based
combat visualising and strategy", and "make sure it sees through a token's vision".

The COO server sends the scene with hidden tokens already removed and unrevealed foes unnamed
(infra/foundry/provisioner/scene-rules.mjs). This adds the rest: what the viewers' tokens can see (map_vision.py),
black everywhere else, and no creature drawn outside that. A grid labelled with column letters and row numbers lets a
post say "Zerius to AG76". Asset fetching is passed in, so tests never touch the network.
"""
import io
import math
import re

from PIL import Image, ImageDraw, ImageFont

from combat.map_vision import vision_mask

DARK = (8, 8, 10, 255)


def col_name(i: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA, as Foundry's grid coordinates are usually read."""
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _font(size: int):
    for f in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default(size)


def named_on(view: dict, wanted: str) -> bool:
    """Whether a party token on the map answers to `wanted`, so it can be looked through."""
    rx = re.compile("|".join(re.escape(w) for w in wanted.split()), re.I)
    return any(t.get("party") and rx.search(t.get("name") or "") for t in view["tokens"])


def viewers_of(view: dict, wanted: str = "") -> list:
    """The party tokens /map looks through: those named in `wanted`, else the whole party.

    During a combat, "the party" is the party tokens IN it: on C06 (2026-11-18) a companion parked 40 squares away
    stretched the frame until the fight was a speck. Naming a token still finds it anywhere on the scene.
    """
    party = [t for t in view["tokens"] if t.get("party")]
    fighting = {o["tokenId"] for o in ((view.get("combat") or {}).get("order") or [])}
    in_fight = [t for t in party if t["id"] in fighting]
    if wanted.strip():
        # A token named exactly (the turn-end map, 2026-11-18) is that token alone: "Kibwe the Bold" must not also
        # match every token with "the" in its name.
        exact = [t for t in party if (t.get("name") or "").strip().lower() == wanted.strip().lower()]
        if exact:
            return exact
        rx = re.compile("|".join(re.escape(w) for w in wanted.split()), re.I)
        named = [t for t in party if rx.search(t.get("name") or "")]
        return named or in_fight or party
    return in_fight or party


def _sees(mask, t, dx, dy, g) -> bool:
    for i in range(max(1, int(t["w"]))):
        for j in range(max(1, int(t["h"]))):
            x, y = int(t["x"] + dx + (i + 0.5) * g), int(t["y"] + dy + (j + 0.5) * g)
            if 0 <= x < mask.width and 0 <= y < mask.height and mask.getpixel((x, y)) > 0:
                return True
    return False


def _background(view, fetch, box):
    """The background cropped to `box` (scene pixels) at scene scale, without resizing the whole map first."""
    s = view["scene"]
    x0, y0, x1, y1 = box
    out = Image.new("RGBA", (x1 - x0, y1 - y0), (40, 40, 40, 255))
    bg = fetch(s.get("background"))
    if bg:
        kx, ky = bg.width / s["width"], bg.height / s["height"]
        part = bg.crop((int(x0 * kx), int(y0 * ky), int(x1 * kx), int(y1 * ky))).resize(out.size)
        out.paste(part.convert("RGBA"), (0, 0))
    return out


def draw_map(view: dict, fetch, wanted: str = "", margin: int = 6, max_side: int = 1400) -> bytes:
    """JPEG bytes of the party's view. `fetch(src)` returns a PIL image or None."""
    s, g = view["scene"], view["scene"]["grid"]["size"]
    pad_x = math.ceil(s["width"] * s.get("padding", 0) / g) * g
    pad_y = math.ceil(s["height"] * s.get("padding", 0) / g) * g
    viewers = viewers_of(view, wanted)
    # The frame: the viewers plus everyone in the combat (the server never sends a hidden one), so a foe in sight
    # is not cut off at the edge. One out of sight still is not drawn; it only widens the frame.
    fighting = {o["tokenId"] for o in ((view.get("combat") or {}).get("order") or [])}
    focus = viewers + [t for t in view["tokens"] if t["id"] in fighting and t not in viewers] or view["tokens"]
    if not focus:
        raise ValueError("no tokens on the scene")
    x0 = max(0, (min(t["x"] for t in focus) - pad_x - margin * g) // g * g)
    y0 = max(0, (min(t["y"] for t in focus) - pad_y - margin * g) // g * g)
    x1 = min(s["width"], -(-(max(t["x"] + t["w"] * g for t in focus) - pad_x + margin * g) // g) * g)
    y1 = min(s["height"], -(-(max(t["y"] + t["h"] * g for t in focus) - pad_y + margin * g) // g) * g)

    img = _background(view, fetch, (x0, y0, x1, y1))
    mask = vision_mask(view, viewers, img.size, (x0 + pad_x, y0 + pad_y))
    img = Image.composite(img, Image.new("RGBA", img.size, DARK), mask)
    tokens = [t for t in view["tokens"] if t.get("party") or _sees(mask, t, -pad_x - x0, -pad_y - y0, g)]
    draw = ImageDraw.Draw(img, "RGBA")
    for x in range(0, x1 - x0 + 1, g):
        draw.line([(x, 0), (x, y1 - y0)], fill=(0, 0, 0, 90), width=1)
    for y in range(0, y1 - y0 + 1, g):
        draw.line([(0, y), (x1 - x0, y)], fill=(0, 0, 0, 90), width=1)

    small, labels = _font(max(10, g // 4)), []
    for t in sorted(tokens, key=lambda t: t["w"], reverse=True):  # big creatures first, small ones on top
        tx, ty, size = int(t["x"] - pad_x - x0), int(t["y"] - pad_y - y0), int(t["w"] * g)
        inner = max(1, int(size * min(abs(t.get("scale") or 1), 1.4)))
        off = (size - inner) // 2
        art = fetch(t.get("img"))
        if art:
            art = art.convert("RGBA").resize((inner, inner))
            if (t.get("scale") or 1) < 0:
                art = art.transpose(Image.FLIP_LEFT_RIGHT)
            img.alpha_composite(art, (max(0, tx + off), max(0, ty + off)))
        else:
            ring = {-1: (200, 40, 40, 255), 1: (40, 160, 60, 255)}.get(t.get("disposition"), (220, 200, 40, 255))
            draw.ellipse([tx + 2, ty + 2, tx + size - 2, ty + size - 2], fill=ring)
        if t.get("name"):
            labels.append((t["name"][:18], tx, ty, size))

    taken = []  # names after all the art, below a token, else above, else further out, until clear
    for name, tx, ty, size in labels:
        tw, th = draw.textlength(name, font=small), small.size + 3
        lx = tx + size / 2 - tw / 2
        for ly in (ty + size, ty - th, ty + size + th, ty - 2 * th, ty + size + 2 * th, ty - 3 * th):
            box = (lx - 2, ly, lx + tw + 2, ly + th)
            if not any(box[0] < b[2] and b[0] < box[2] and box[1] < b[3] and b[1] < box[3] for b in taken):
                break
        taken.append(box)
        draw.rectangle(box, fill=(0, 0, 0, 170))
        draw.text((lx, ly + 1), name, font=small, fill=(255, 255, 255, 255))

    lab = _font(max(11, g // 3))
    frame = int(lab.size * 2.2)
    out = Image.new("RGBA", (img.width + frame, img.height + frame), (20, 20, 20, 255))
    out.alpha_composite(img, (frame, frame))
    od = ImageDraw.Draw(out)
    for x in range(0, x1 - x0, g):
        c = col_name((x0 + x) // g)
        od.text((frame + x + g / 2 - od.textlength(c, font=lab) / 2, 4), c, font=lab, fill=(230, 230, 230, 255))
    for y in range(0, y1 - y0, g):
        r = str((y0 + y) // g + 1)
        od.text((frame - od.textlength(r, font=lab) - 4, frame + y + g / 2 - lab.size / 2), r, font=lab,
                fill=(230, 230, 230, 255))
    if max(out.size) > max_side:
        k = max_side / max(out.size)
        out = out.resize((int(out.width * k), int(out.height * k)), Image.LANCZOS)
    buf = io.BytesIO()
    out.convert("RGB").save(buf, "JPEG", quality=88)
    return buf.getvalue()
