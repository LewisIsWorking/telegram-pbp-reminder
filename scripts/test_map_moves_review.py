"""🧭 /map move preview, review fixes (2026-11-25): move-only walls, strides through allies, two tokens with one name,
a photo that fails, the bot's name after /map, and a mistyped move list that must not reach the group."""
from _test_telegram_mock import _sent_messages
from combat.map_move_post import post_move_map
from combat.map_moves import describe, parse_moves, resolve
from test_map_moves import G, _ctx, _token, _view

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
