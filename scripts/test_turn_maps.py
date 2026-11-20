"""🗺️ A map after each player's combat turn, from that player's token only (Lewis, 2026-11-18)."""
from combat.map_draw import viewers_of
from combat.turn_maps import due_maps, post_turn_maps

CONFIG = {"group_id": -100, "topic_pairs": [
    {"code": "C06", "name": "Six", "pbp_topic_ids": [700, 701], "combat_topic_id": 701}]}


def _enc(rnd=1, acted=(), encounter="E1", ended=False):
    allies = [{"name": n, "acted": n in acted, "telegramUserId": uid}
              for n, uid in (("Kibwe", "1"), ("Ji Yun", "2"))] + [{"name": "Drone", "acted": True, "telegramUserId": None}]
    return {"code": "C06", "snapshot": {"encounterId": encounter, "round": rnd, "allies": allies, "ended": ended}}


def _run(state, *encs):
    calls = []
    post = lambda config, pid, code, wanted, gid, topic, quiet: calls.append((pid, code, wanted, gid, topic, quiet)) or True
    for e in encs:
        post_turn_maps(CONFIG, state, [e], post=post)
    return calls


def test_each_turn_end_posts_that_players_view_once_per_round():
    state = {}
    calls = _run(state, _enc(), _enc(acted=("Kibwe",)), _enc(acted=("Kibwe",)), _enc(acted=("Kibwe", "Ji Yun")))
    assert calls == [("700", "C06", "Kibwe", -100, 701, True), ("700", "C06", "Ji Yun", -100, 701, True)]
    assert [c[2] for c in _run(state, _enc(rnd=2, acted=("Ji Yun",)))] == ["Ji Yun"], "a new round, a new map"


def test_a_fight_first_seen_mid_round_posts_no_burst_of_old_turns():
    state = {}
    assert _run(state, _enc(acted=("Kibwe",))) == []
    assert [c[2] for c in _run(state, _enc(acted=("Kibwe", "Ji Yun")))] == ["Ji Yun"]


def test_an_ended_fight_or_a_campaign_with_no_combat_topic_posts_nothing():
    assert _run({}, _enc(), _enc(acted=("Kibwe",), ended=True)) == []
    assert due_maps({}, "700", {"encounterId": "E", "round": 1, "allies": []}) == []


def test_a_token_named_exactly_is_seen_through_alone():
    view = {"tokens": [{"id": "a", "name": "Kibwe the Bold", "party": True}, {"id": "b", "name": "Ana the Red", "party": True}],
            "combat": {"order": []}}
    assert [t["id"] for t in viewers_of(view, "Kibwe the Bold")] == ["a"]
    assert len(viewers_of(view, "the")) == 1, "a loose name is still ONE character, never a group"
    assert [t["id"] for t in viewers_of(view, "Ana Red")] == ["b"], "the most words matched wins"
