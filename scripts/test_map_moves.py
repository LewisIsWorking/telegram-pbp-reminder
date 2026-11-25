"""🧭 /map moves (2026-11-25): "/map Zerius slide S4, Little Dread S4" for the GM only.

Lewis said yes to an arrow and a ghost token for each move, the end square in grid coordinates, a slide that stops at
a wall, the edge or a creature and says which, and the picture sent to the GM, not the combat topic. These pin down
each of those, plus squares, feet and metres in the PF2e count.
"""
import io

from PIL import Image

from _test_telegram_mock import _sent_messages
from combat.map_draw import _font, draw_map
from combat.map_move_post import post_move_map
from combat.map_moves import describe, distance, parse_moves, resolve

G = 50


def _token(name, col, row, party=False):
    return {"id": name, "name": name, "party": party, "x": col * G, "y": row * G, "w": 1, "h": 1, "img": None,
            "scale": 1, "disposition": 1 if party else -1, "sight": {"enabled": True, "range": 0, "angle": 360}}


def _view(tokens, walls=(), order=()):
    return {"scene": {"name": "C06 | Temple", "width": 12 * G, "height": 12 * G, "padding": 0,
                      "grid": {"size": G, "distance": 5}, "background": None, "environment": None, "tokenVision": True},
            "combat": {"round": 2, "turn": 0, "order": list(order)}, "tokens": tokens,
            "walls": [{"c": list(w)} for w in walls], "lights": []}


def test_a_move_list_is_read_and_anything_else_is_not():
    moves = parse_moves(" Zerius slide S4, Little Dread S4")
    assert [(m["name"], m["verb"], m["dir"], m["squares"]) for m in moves] == [
        ("Zerius", "slide", "S", 4), ("Little Dread", "move", "S", 4)]
    assert parse_moves(" Zerius") is None
    assert parse_moves(" Zerius slide S4, Little Dread") is None
    assert parse_moves(" Zerius south 20 ft")[0]["squares"] == 4
    assert parse_moves(" Zerius push NE 15ft")[0]["squares"] == 2   # diagonals cost 5 then 10


def test_distance_is_squares_then_feet_with_metres_in_brackets():
    assert distance(4, False) == "4 squares, 20 ft (6 m)"
    assert distance(1, False) == "1 square, 5 ft (1.5 m)"
    assert distance(3, True) == "3 squares, 20 ft (6 m)"


def test_a_clear_slide_goes_the_whole_way_and_names_the_end_square():
    view = _view([_token("Zerius", 2, 2, party=True)])
    (r,), missing = resolve(view, parse_moves(" Zerius slide S4"))
    assert not missing and r["end"] == (2 * G, 6 * G) and r["moved"] == 4 and not r["why"]
    assert describe(view, r) == "➡️ Zerius: slide S 4 squares, 20 ft (6 m), C3 to C7."


def test_a_wall_stops_the_slide_and_says_so():
    view = _view([_token("Zerius", 2, 2, party=True)], walls=[(0, 5 * G, 12 * G, 5 * G)])
    (r,), _ = resolve(view, parse_moves(" Zerius slide S4"))
    assert (r["moved"], r["why"]) == (2, "a wall")
    assert "2 squares, 10 ft (3 m) of 4, C3 to C5, stopped by a wall" in describe(view, r)


def test_a_creature_in_the_next_square_means_no_move_at_all():
    view = _view([_token("Little Dread", 5, 5, party=True), _token("Jitte", 4, 5, party=True)])
    (r,), _ = resolve(view, parse_moves(" Little Dread slide W4"))
    assert r["moved"] == 0
    assert describe(view, r) == "⛔ Little Dread cannot slide W: Jitte is in the way. Stays on F6."


def test_the_edge_of_the_map_stops_a_slide():
    view = _view([_token("Zerius", 1, 3, party=True)])
    (r,), _ = resolve(view, parse_moves(" Zerius W4"))
    assert (r["moved"], r["why"]) == (1, "the edge of the map")


def test_moves_happen_in_order_and_a_fallen_creature_does_not_block():
    view = _view([_token("Zerius", 2, 2, party=True), _token("Little Dread", 2, 7, party=True), _token("Corpse", 2, 4)],
                 order=[{"tokenId": "Corpse", "defeated": True}])
    (z, ld), _ = resolve(view, parse_moves(" Zerius slide S4, Little Dread slide N4"))
    assert z["end"] == (2 * G, 6 * G)                 # straight over the fallen foe
    assert (ld["moved"], ld["why"]) == (0, "Zerius")  # Zerius is already in the way


def test_the_map_shows_an_arrow_and_hides_no_creature_from_the_gm():
    view = _view([_token("Zerius", 2, 2, party=True), _token("Ogre", 11, 11)], walls=[(6 * G, 0, 6 * G, 12 * G)],
                 order=[{"tokenId": "Ogre"}])
    results, _ = resolve(view, parse_moves(" Zerius slide S4"))
    img = Image.open(io.BytesIO(draw_map(view, lambda src: None, moves=results, max_side=5000))).convert("RGB")
    frame = int(_font(G // 3).size * 2.2)
    assert img.size == (12 * G + frame, 12 * G + frame)   # the whole scene: the auto-crop no longer cuts the last square
    r, g, b = img.getpixel((frame + int(2.5 * G) + 1, frame + int(4.2 * G)))   # the arrow's shaft
    assert b > 180 and r < 90
    r, g, b = img.getpixel((frame + int(11.5 * G), frame + int(11.5 * G)))     # the Ogre, behind a wall from Zerius
    assert r > 150 and g < 90


def test_the_preview_goes_to_the_gm_privately_with_a_line_per_move():
    sent = []
    view = _view([_token("Zerius", 2, 2, party=True), _token("Little Dread", 5, 5, party=True), _token("Jitte", 4, 5)])
    ok = post_move_map("C06", parse_moves(" Zerius slide S4, Little Dread slide W4"), 777, -100, 21528,
                       scene=lambda code: (view, ""), fetch=lambda src: None, send=lambda *a: sent.append(a) or True)
    assert ok
    chat, topic, jpeg, text = sent[0]
    assert (chat, topic) == (777, None) and jpeg[:2] == b"\xff\xd8"
    assert "C3 to C7" in text and "Little Dread cannot slide W: Jitte is in the way" in text


def test_an_unknown_name_is_told_to_the_gm_not_the_group():
    _sent_messages.clear()
    ok = post_move_map("C06", parse_moves(" Nobody slide S4"), 777, -100, 21528,
                       scene=lambda code: (_view([_token("Zerius", 2, 2, party=True)]), ""),
                       send=lambda *a: (_ for _ in ()).throw(AssertionError("must not post")))
    assert not ok
    assert [m["group_id"] for m in _sent_messages] == [777] and "Nobody" in _sent_messages[0]["text"]


def _ctx(uid, text):
    return {"cmd_word": "/map", "group_id": -100, "reply_topic": 21528, "pid": "40585", "campaign_name": "Kibwe",
            "user_id": uid, "user_name": "x", "state": {}, "gm_ids": [777], "text": text, "parsed": {"raw_text": text},
            "config": {"topic_pairs": [{"code": "C06", "pbp_topic_ids": [40585], "combat_topic_id": 137075}]}}


def test_only_a_gm_move_list_becomes_a_preview(monkeypatch):
    from combat import map_move_post, map_view
    from dispatch import cmd_info_ext
    previews, maps = [], []
    monkeypatch.setattr(map_move_post, "post_move_map", lambda *a, **k: previews.append(a))
    monkeypatch.setattr(map_view, "post_map", lambda *a, **k: maps.append(a))
    cmd_info_ext.handle(_ctx(777, "/map Zerius slide S4, Little Dread S4"))
    assert previews and previews[0][0] == "C06" and previews[0][2] == 777 and not maps
    cmd_info_ext.handle(_ctx(777, "/map Zerius"))   # a GM's plain /map is the normal map
    assert len(previews) == 1 and len(maps) == 1
    _sent_messages.clear()
    cmd_info_ext.handle(_ctx(555, "/map Zerius slide S4"))   # a player gets no preview
    assert len(previews) == 1
