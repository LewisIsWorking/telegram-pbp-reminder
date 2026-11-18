"""🗺️ /map is one character's view: a player's own only, a GM's anyone's, never the party's (Lewis, 2026-11-18)."""
from _test_telegram_mock import _sent_messages
from combat import map_view
from test_map_command import CONFIG, _view


def test_outside_a_fight_the_map_answers_where_it_was_asked():
    sent = []
    view = _view()
    view["combat"] = None
    assert map_view.post_map(CONFIG, "40585", "C06", "Zerius", -100, 21528, scene=lambda code: (view, ""),
                             fetch=lambda src: None, send=lambda *a: sent.append(a) or True)
    assert sent[0][1] == 21528 and "what Zerius can see" in sent[0][3]


def test_a_character_not_on_the_map_is_said_never_swapped_for_the_party():
    _sent_messages.clear()
    ok = map_view.post_map(CONFIG, "40585", "C06", "Nobody", -100, 21528, scene=lambda code: (_view(), ""),
                           send=lambda *a: (_ for _ in ()).throw(AssertionError("must not post the party's view")))
    assert not ok
    assert any("No party character called Nobody" in m.get("text", "") for m in _sent_messages)


def test_no_name_is_asked_for_never_the_partys_view():
    _sent_messages.clear()
    ok = map_view.post_map(CONFIG, "40585", "C06", "", -100, 21528, scene=lambda code: (_view(), ""),
                           send=lambda *a: (_ for _ in ()).throw(AssertionError("must not post the party's view")))
    assert not ok
    assert any("Whose view?" in m.get("text", "") for m in _sent_messages)


def test_a_player_sees_only_their_own_character_a_gm_anyone():
    config = {"topic_pairs": [{"code": "C06", "pbp_topic_ids": [40585], "characters": {"9": "Kibwe"}}]}
    look = lambda uid, asked: map_view.whose_map(config, {}, "40585", uid, ["1"], asked)
    assert look("9", "") == ("Kibwe", "")
    assert look("9", "kibwe") == ("Kibwe", "")
    assert look("9", "Zerius")[0] == "" and "only see through your own" in look("9", "Zerius")[1]
    assert look("8", "")[0] == "" and "don't know your character" in look("8", "")[1]
    assert look("1", "Zerius") == ("Zerius", "")
    assert look("1", "")[0] == "" and "Whose view" in look("1", "")[1]


def test_a_plain_map_is_the_callers_own_character(monkeypatch):
    from dispatch import cmd_info_ext
    calls = []
    monkeypatch.setattr(map_view, "post_map", lambda config, pid, code, wanted, gid, reply: calls.append(wanted) or True)
    config = {"group_id": -100, "topic_pairs": [{"code": "C06", "pbp_topic_ids": [40585], "characters": {"9": "Kibwe"}}]}
    ctx = {"cmd_word": "/map", "group_id": -100, "reply_topic": 1, "pid": "40585", "campaign_name": "C06", "user_id": "9",
           "user_name": "P", "state": {}, "config": config, "gm_ids": ["1"], "parsed": {"raw_text": "/map"}, "text": "/map"}
    assert cmd_info_ext.handle(ctx)
    ctx["parsed"]["raw_text"] = "/map Zerius"
    cmd_info_ext.handle(ctx)
    ctx["user_id"] = "1"
    cmd_info_ext.handle(ctx)
    assert calls == ["Kibwe", "Zerius"], "the player's /map Zerius is refused; the GM's is drawn"
