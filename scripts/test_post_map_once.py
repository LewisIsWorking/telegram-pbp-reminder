"""post_map_once: a map posted on request goes to the campaign's combat topic, one named character only."""
from combat.post_map_once import post_once

CONFIG = {"group_id": -100, "topic_pairs": [{"code": "C06", "pbp_topic_ids": [40585], "combat_topic_id": 137075}]}


def _recorder(result=True):
    calls = []

    def post(config, pid, code, name, group_id, topic, quiet=False):
        calls.append((pid, code, name, group_id, topic, quiet))
        return result
    return calls, post


def test_posts_the_named_view_to_the_combat_topic_quietly():
    calls, post = _recorder()
    assert post_once(CONFIG, "c06", " Kibwe ", post=post)
    assert calls == [("40585", "C06", "Kibwe", -100, 137075, True)]


def test_no_name_is_refused_never_the_party_view():
    calls, post = _recorder()
    assert not post_once(CONFIG, "C06", "  ", post=post)
    assert calls == []


def test_unknown_campaign_posts_nothing():
    calls, post = _recorder()
    assert not post_once(CONFIG, "C42", "Kibwe", post=post)
    assert calls == []


def test_a_failed_map_is_reported_false():
    _, post = _recorder(result=False)
    assert not post_once(CONFIG, "C06", "Kibwe", post=post)
