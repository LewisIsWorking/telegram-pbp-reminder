"""post_map_once: preview draws and saves, posting nothing; post sends only the approved picture (Lewis, 2026-11-20:
"You NEED to show me the map before you ever post it")."""
import hashlib

from combat.post_map_once import run

CONFIG = {"group_id": -100, "topic_pairs": [{"code": "C06", "pbp_topic_ids": [40585], "combat_topic_id": 137075}]}
VIEW = {"scene": {"name": "Temple"}, "combat": {"round": 1}, "tokens": [{"name": "Zerius", "party": True}]}
JPEG = b"picture"
SHA = hashlib.sha256(JPEG).hexdigest()


def _go(mode, tmp_path, name="Zerius", expect="", **kw):
    sent = []

    def send(*a, **k):
        sent.append((a, k))
        return True
    ok = run(CONFIG, mode, "c06", name, expect, scene=lambda code: (VIEW, ""), draw=lambda v, n: JPEG,
             send=send, out=str(tmp_path / "map.jpg"), **kw)
    return ok, sent


def test_preview_saves_the_picture_and_posts_nothing(tmp_path):
    ok, sent = _go("preview", tmp_path)
    assert ok and sent == [] and (tmp_path / "map.jpg").read_bytes() == JPEG


def test_post_without_the_approved_sha_posts_nothing(tmp_path):
    assert _go("post", tmp_path) == (False, [])
    assert _go("post", tmp_path, expect="0" * 64) == (False, [])


def test_post_with_the_approved_sha_replies_in_the_combat_topic(tmp_path):
    ok, sent = _go("post", tmp_path, expect=SHA, reply_to=191007, text="Zerius, please roll a Reflex save.")
    (group, topic, jpeg, body), kw = sent[0]
    assert ok and (group, topic, jpeg) == (-100, 137075, JPEG) and kw == {"reply_to": 191007}
    assert body.endswith("\n\nZerius, please roll a Reflex save.")


def test_no_name_is_refused_never_the_party_view(tmp_path):
    assert _go("post", tmp_path, name=" ", expect=SHA) == (False, [])
