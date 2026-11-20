"""✂️ The map is cropped to what the viewer can see (2026-11-20, Lewis: "auto crop, that should be built in as a
feature"). Zerius looks down the map, so the rows behind him are cut, not drawn black."""
import io

from PIL import Image

from combat.map_draw import draw_map
from test_map_command import _token, _view


def _size(tokens):
    jpeg = draw_map(_view(tokens=tokens), lambda src: None, "Zerius", margin=20, max_side=5000)
    return Image.open(io.BytesIO(jpeg)).size


def test_the_rows_behind_a_cone_are_cropped_away():
    zerius = _token("Zerius", 10, 6, party=True)
    full = _size([zerius])
    zerius.update(sight={"enabled": True, "range": 0, "angle": 160}, rotation=0)  # looks down the map
    cropped = _size([zerius])
    assert cropped[1] < full[1]
    assert cropped[0] == full[0]  # a 160 degree cone still reaches both sides
