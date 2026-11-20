"""🗺️ /map: the battle map as the party sees it (2026-11-18).

Lewis: "make sure it sees through a token's vision". These pin down that a wall hides what is behind it, that a
creature out of sight is not drawn, that the map goes to the campaign's combat topic, and that every failure says so
in chat instead of posting nothing.
"""
import io

import requests
from PIL import Image

from _test_telegram_mock import _sent_messages
from combat import map_view
from combat.map_draw import col_name, draw_map, viewers_of
from combat.map_vision import vision_mask

G = 50


def _token(name, col, row, party=False, disposition=-1):
    return {"id": name, "name": name, "party": party, "x": col * G, "y": row * G, "w": 1, "h": 1,
            "img": None, "scale": 1, "disposition": disposition, "sight": {"enabled": True, "range": 0, "angle": 360}}


def _view(walls=(), tokens=None, lit=True):
    env = {"globalLight": {"enabled": lit, "darkness": {"min": 0, "max": 1}}, "darknessLevel": 0}
    return {"scene": {"name": "C06 | Temple", "width": 20 * G, "height": 10 * G, "padding": 0,
                      "grid": {"size": G, "distance": 5}, "background": None, "environment": env, "tokenVision": True},
            "combat": {"round": 3, "turn": 0, "order": []},
            "tokens": tokens if tokens is not None else [_token("Zerius", 2, 5, party=True), _token("Ogre", 6, 5),
                                                         _token("Lurker", 15, 5)],
            "walls": [{"c": list(w)} for w in walls], "lights": []}


WALL = (10 * G, 0, 10 * G, 10 * G)  # a wall from top to bottom down column K


def test_a_wall_hides_what_is_behind_it():
    view = _view(walls=[WALL])
    mask = vision_mask(view, viewers_of(view), (20 * G, 10 * G), (0, 0))
    assert mask.getpixel((6 * G, 5 * G)) == 255      # the Ogre's side
    assert mask.getpixel((15 * G, 5 * G)) == 0       # behind the wall


def test_in_the_dark_a_token_sees_only_its_own_range():
    view = _view(lit=False)
    view["tokens"][0]["sight"]["range"] = 10      # 10 ft = 2 squares
    mask = vision_mask(view, viewers_of(view), (20 * G, 10 * G), (0, 0))
    assert mask.getpixel((int(3.5 * G), int(5.5 * G))) == 255
    assert mask.getpixel((int(9.5 * G), int(5.5 * G))) == 0


def _jpeg_pixel(jpeg, xy):
    return Image.open(io.BytesIO(jpeg)).convert("RGB").getpixel(xy)


def test_the_map_is_lit_in_front_of_the_wall_and_cropped_behind_it():
    """2026-11-20: behind the wall used to be drawn black; the map is now cropped one square past what is seen."""
    gutter = Image.open(io.BytesIO(draw_map(_view(), lambda src: None, margin=20, max_side=5000))).width - 20 * G
    jpeg = draw_map(_view(walls=[WALL]), lambda src: None, margin=20, max_side=5000)
    assert Image.open(io.BytesIO(jpeg)).width == gutter + 11 * G
    front = _jpeg_pixel(jpeg, (gutter + 4 * G + 20, gutter + 2 * G + 20))
    assert sum(front) > 60


def test_naming_a_token_looks_through_that_token_only():
    view = _view(tokens=[_token("Zerius", 2, 5, party=True), _token("Lorn", 15, 5, party=True)])
    assert [t["name"] for t in viewers_of(view, "zerius")] == ["Zerius"]
    assert [t["name"] for t in viewers_of(view, "nobody")] == ["Zerius", "Lorn"]


def test_an_open_room_is_seen_to_every_corner():
    """2026-11-18: rays sorted in two angle ranges made the polygon cross itself and blacked out a wedge."""
    from combat.map_vision import vision_mask
    view = _view(tokens=[_token("Zerius", 10, 4, party=True)])
    g = view["scene"]["grid"]["size"]
    mask = vision_mask(view, view["tokens"], (20 * g, 10 * g), (0, 0))
    assert all(mask.getpixel((x, y)) == 255 for x in range(5, 20 * g, g) for y in range(5, 10 * g, g))


def test_a_160_degree_cone_sees_ahead_not_behind():
    """Rotation 0 looks down the map in Foundry; the token's own square is always seen."""
    from combat.map_vision import vision_mask
    view = _view(tokens=[_token("Zerius", 10, 4, party=True)])
    view["tokens"][0].update(sight={"enabled": True, "range": 0, "angle": 160}, rotation=0)
    g = view["scene"]["grid"]["size"]
    mask = vision_mask(view, view["tokens"], (20 * g, 10 * g), (0, 0))
    cx, cy = 10 * g + g // 2, 4 * g + g // 2
    assert mask.getpixel((cx, cy + 3 * g)) == 255   # three squares in front
    assert mask.getpixel((cx, cy - 3 * g)) == 0     # three squares behind
    assert mask.getpixel((cx, cy - g // 4)) == 255  # its own square
    view["tokens"][0]["rotation"] = 180
    turned = vision_mask(view, view["tokens"], (20 * g, 10 * g), (0, 0))
    assert turned.getpixel((cx, cy - 3 * g)) == 255 and turned.getpixel((cx, cy + 3 * g)) == 0


def test_in_a_combat_the_party_is_whoever_of_it_is_fighting():
    view = _view(tokens=[_token("Zerius", 2, 5, party=True), _token("Jiufeng", 19, 9, party=True)])
    view["combat"]["order"] = [{"tokenId": "Zerius", "defeated": False}]
    assert [t["name"] for t in viewers_of(view)] == ["Zerius"]
    assert [t["name"] for t in viewers_of(view, "jiufeng")] == ["Jiufeng"]


def test_columns_read_like_foundry_grids():
    assert [col_name(i) for i in (0, 25, 26, 57)] == ["A", "Z", "AA", "BF"]


class _Resp:
    def __init__(self, status, body=None):
        self.status_code, self._body, self.text = status, body, ""

    def json(self):
        return self._body


ENV = {"PATHWARS_BOT_READ_KEY": "k", "COO_SERVER_URL": "https://coo.example"}


def test_fetch_scene_reads_the_campaigns_view_with_the_bots_key():
    seen = {}

    def get(url, headers, timeout):
        seen.update(url=url, headers=headers)
        return _Resp(200, {"code": "C06", "view": _view()})

    view, why = map_view.fetch_scene("C06", get=get, env=ENV)
    assert view["scene"]["name"] == "C06 | Temple" and why == ""
    assert seen["url"] == "https://coo.example/api/pathwars/scene/C06"
    assert seen["headers"] == {"X-PathWars-Bot-Key": "k"}


def test_fetch_scene_says_why_there_is_no_map():
    assert map_view.fetch_scene("C06", get=lambda *a, **k: _Resp(404), env=ENV)[1] == "C06 has no active Foundry scene to show."
    assert "key" in map_view.fetch_scene("C06", env={})[1]

    def down(*a, **k):
        raise requests.ConnectionError()
    assert "did not answer" in map_view.fetch_scene("C06", get=down, env=ENV)[1]


CONFIG = {"group_id": -100, "topic_pairs": [
    {"code": "C06", "pbp_topic_ids": [40585, 137075], "chat_topic_id": 21528, "combat_topic_id": 137075}]}


def test_the_map_goes_to_the_combat_topic_with_scene_and_round():
    sent = []
    ok = map_view.post_map(CONFIG, "40585", "C06", "Zerius", -100, 21528, scene=lambda code: (_view(), ""),
                           fetch=lambda src: None, send=lambda *a: sent.append(a) or True)
    assert ok
    group, topic, jpeg, text = sent[0]
    assert (group, topic) == (-100, 137075)
    assert jpeg[:2] == b"\xff\xd8"
    assert "C06 | Temple" in text and "round 3" in text and "what Zerius can see" in text


def test_no_map_is_said_in_chat_not_posted_silently():
    _sent_messages.clear()
    ok = map_view.post_map(CONFIG, "40585", "C06", "", -100, 21528, scene=lambda code: (None, "C06 has no Foundry map to show."),
                           send=lambda *a: (_ for _ in ()).throw(AssertionError("must not post")))
    assert not ok
    assert any("no Foundry map" in m.get("text", "") for m in _sent_messages)
