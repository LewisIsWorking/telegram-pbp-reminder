"""🙈 A map shows only the viewer and what the viewer sees (2026-11-20). Party tokens were drawn even behind the
viewer's vision cone; Lewis: "I wouldn't show tokens outside of his cone"."""
from combat.map_draw import draw_map
from test_map_command import _token, _view


def _drawn(view, wanted):
    drawn = []

    def fetch(src):
        if src:
            drawn.append(src)
        return None
    draw_map(view, fetch, wanted, margin=20, max_side=5000)
    return set(drawn)


def test_tokens_behind_the_cone_are_not_drawn_party_or_not():
    zerius, ally_behind, foe_ahead, foe_behind = (_token("Zerius", 10, 4, party=True), _token("Lorn", 10, 1, party=True),
                                                  _token("Xeric", 10, 8), _token("Conf", 12, 1))
    zerius.update(sight={"enabled": True, "range": 0, "angle": 160}, rotation=0)  # rotation 0 looks down the map
    for t in (zerius, ally_behind, foe_ahead, foe_behind):
        t["img"] = t["name"]
    assert _drawn(_view(tokens=[zerius, ally_behind, foe_ahead, foe_behind]), "Zerius") == {"Zerius", "Xeric"}
