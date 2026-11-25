"""🧭 /map Zerius slide S4, Little Dread S4: a GM's move preview, sent to that GM privately (2026-11-25).

Lewis said yes to: "The image would go to you, not to the combat topic." A preview shows where creatures COULD end up
before the GM has decided, so nothing about it is posted in the group: the picture, and any reason there is none, go
to the GM's private chat with the bot. Only when that chat cannot be reached (the GM never pressed Start) does the
group hear about it, with no detail of the moves.
"""
import html

import telegram as tg
from combat.map_moves import describe, resolve
from combat.map_view import caption, fetch_scene, make_fetch, send_photo


def post_move_map(code: str, moves: list, gm_uid, group_id: int, reply_topic: int,
                  scene=fetch_scene, fetch=None, send=send_photo) -> bool:
    """Draw the moves on the campaign's live scene and send it to `gm_uid`. False when there was nothing to send."""
    from combat.map_draw import draw_map

    def tell_gm(text):
        if not tg.send_message(int(gm_uid), None, text):
            tg.send_message(group_id, reply_topic, "🗺️ I could not message you privately. Open a chat with me, "
                                                   "press Start, then send the /map again.")

    view, why = scene(code)
    if view is None:
        tell_gm(f"🗺️ {why}")
        return False
    results, missing = resolve(view, moves)
    if missing:
        tell_gm(f"🗺️ No token on {code}'s active scene answers to {html.escape(', '.join(missing))}, "
                "so there is no move preview.")
        return False
    jpeg = draw_map(view, fetch or make_fetch(), moves=results)
    head = caption(code, view, "").split("\n")[0]
    text = "\n".join([head, "Move preview, for you only:"] + [html.escape(describe(view, r)) for r in results])
    if send(int(gm_uid), None, jpeg, text):
        return True
    tg.send_message(group_id, reply_topic, "🗺️ I could not message you privately. Open a chat with me, "
                                           "press Start, then send the /map again.")
    return False
