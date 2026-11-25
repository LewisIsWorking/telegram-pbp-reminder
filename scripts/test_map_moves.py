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


# ── 2026-11-25 review fixes ────────────────────────────────────────────────────────────────────────────────────────

def test_move_only_walls_are_used_when_the_server_sends_them():
    from combat.map_moves import move_walls
    z = _token("Zerius", 2, 2, party=True)
    view = _view([z])
    view["moveWalls"] = [{"c": [0, 4 * G, 12 * G, 4 * G]}]          # an invisible wall: blocks moving, not sight
    (r,), _ = resolve(view, parse_moves(" Zerius slide S4"))
    assert (r["moved"], r["why"]) == (1, "a wall") and move_walls(view)[1]
    view = _view([z])                                                  # every wall with Foundry's own flags
    view["walls"] = [{"c": [0, 3 * G, 12 * G, 3 * G], "move": 0, "sight": 20},             # a window-like sight wall
                     {"c": [0, 4 * G, 12 * G, 4 * G], "move": 20, "sight": 20, "door": 1, "ds": 1},   # open door
                     {"c": [0, 5 * G, 12 * G, 5 * G], "move": 20, "sight": 0}]             # an invisible wall
    (r,), _ = resolve(view, parse_moves(" Zerius slide S4"))
    assert (r["moved"], r["why"]) == (2, "a wall")


def test_the_players_map_ignores_walls_that_do_not_block_sight():
    from combat.map_vision import sight_walls
    view = {"walls": [{"c": [0, 0, 1, 1], "move": 20, "sight": 0}, {"c": [0, 0, 2, 2], "sight": 20},
                      {"c": [0, 0, 3, 3], "door": 1, "ds": 1, "sight": 20}, {"c": [0, 0, 4, 4]}]}
    assert [w["c"][2] for w in sight_walls(view)] == [2, 4]


def test_the_caption_warns_when_only_sight_walls_are_known():
    sent = []
    view = _view([_token("Zerius", 2, 2, party=True)])
    post_move_map("C06", parse_moves(" Zerius slide S1"), 777, -100, 1, scene=lambda c: (view, ""),
                  fetch=lambda s: None, send=lambda *a: sent.append(a) or True)
    assert "Only walls that block sight are known" in sent[0][3]
    view["moveWalls"] = []
    sent.clear()
    post_move_map("C06", parse_moves(" Zerius slide S1"), 777, -100, 1, scene=lambda c: (view, ""),
                  fetch=lambda s: None, send=lambda *a: sent.append(a) or True)
    assert "Only walls" not in sent[0][3]


def test_a_stride_passes_through_an_ally_but_not_a_foe_and_never_ends_on_one():
    allies = [_token("Zerius", 2, 2, party=True), _token("Jitte", 2, 3, party=True), _token("Kibwe", 2, 6, party=True)]
    (r,), _ = resolve(_view(allies), parse_moves(" Zerius stride S3"))
    assert (r["end"], r["moved"], r["why"]) == ((2 * G, 5 * G), 3, "")        # through Jitte
    (r,), _ = resolve(_view(allies), parse_moves(" Zerius stride S4"))
    assert (r["end"], r["moved"], r["why"]) == ((2 * G, 5 * G), 3, "Kibwe")   # would end on Kibwe: stops before
    (r,), _ = resolve(_view(allies), parse_moves(" Zerius slide S3"))
    assert (r["moved"], r["why"]) == (0, "Jitte")                              # forced movement still stops
    (r,), _ = resolve(_view([allies[0], _token("Ogre", 2, 3)]), parse_moves(" Zerius stride S3"))
    assert (r["moved"], r["why"]) == (0, "Ogre")                               # a foe blocks a stride


def test_two_tokens_with_one_name_are_not_guessed():
    view = _view([_token("Zerius", 0, 0, party=True), dict(_token("Goblin", 2, 2), id="g1"),
                  dict(_token("Goblin", 5, 5), id="g2")])
    _, missing = resolve(view, parse_moves(" Goblin slide S1"))
    assert missing == ["Goblin"]
    _sent_messages.clear()
    post_move_map("C06", parse_moves(" Goblin slide S1"), 777, -100, 1, scene=lambda c: (view, ""),
                  send=lambda *a: (_ for _ in ()).throw(AssertionError("must not post")))
    assert "C3, F6" in _sent_messages[0]["text"] and _sent_messages[0]["group_id"] == 777
    for named in (" Goblin at F6 slide S1", " Goblin (F6) slide S1"):
        (r,), missing = resolve(view, parse_moves(named))
        assert not missing and r["token"]["id"] == "g2" and r["end"] == (5 * G, 6 * G)


def test_less_than_a_square_says_so():
    view = _view([_token("Zerius", 2, 2, party=True)])
    (r,), _ = resolve(view, parse_moves(" Zerius S 3 ft"))
    assert describe(view, r) == "➖ Zerius: move S 0 squares (less than one square asked). Stays on C3."


def test_a_failed_photo_still_reaches_the_gm_as_text():
    _sent_messages.clear()
    view = _view([_token("Zerius", 2, 2, party=True)])
    ok = post_move_map("C06", parse_moves(" Zerius slide S2"), 777, -100, 1, scene=lambda c: (view, ""),
                       fetch=lambda s: None, send=lambda *a: False)
    assert not ok and [m["group_id"] for m in _sent_messages] == [777]
    assert "C3 to C5" in _sent_messages[0]["text"] and "picture could not be sent" in _sent_messages[0]["text"]


def test_the_bot_name_after_map_is_not_read_as_a_name(monkeypatch):
    from combat import map_move_post, map_view
    from dispatch import cmd_info_ext
    previews, maps = [], []
    monkeypatch.setattr(map_move_post, "post_move_map", lambda *a, **k: previews.append(a))
    monkeypatch.setattr(map_view, "post_map", lambda *a, **k: maps.append(a))
    cmd_info_ext.handle(_ctx(777, "/map@PathWarsBot Zerius slide S4"))
    assert previews and previews[0][1][0]["name"] == "Zerius"
    cmd_info_ext.handle(_ctx(777, "/map@PathWarsBot Zerius"))
    assert maps and maps[0][3].strip() == "Zerius"


def test_a_gms_garbled_move_list_goes_to_the_gm_not_the_group(monkeypatch):
    from combat import map_view
    from dispatch import cmd_info_ext
    maps = []
    monkeypatch.setattr(map_view, "post_map", lambda *a, **k: maps.append(a))
    _sent_messages.clear()
    cmd_info_ext.handle(_ctx(777, "/map Zerius slide 4 S"))
    assert not maps and [m["group_id"] for m in _sent_messages] == [777]
    assert "could not read that move list" in _sent_messages[0]["text"]
