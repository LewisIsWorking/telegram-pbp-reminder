"""The map caption names the campaign once, not "C06: C06 | ..." (2026-11-20)."""
from combat.map_view import caption


def test_scene_prefix_is_not_repeated():
    view = {"scene": {"name": "C06 | 10/The Sun Temple of Kibwe"}, "combat": {"round": 1}}
    assert caption("C06", view, "Zerius").startswith("🗺️ <b>C06</b>: 10/The Sun Temple of Kibwe, round 1\n")


def test_a_scene_without_the_prefix_is_kept_whole():
    assert "Docks" in caption("C01", {"scene": {"name": "Docks"}, "combat": None}, "Cardigan")
