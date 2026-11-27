"""🧭 /map Zerius slide S4, Little Dread S4: a GM's move preview, sent to that GM privately (2026-11-25).

Lewis said yes to: "The image would go to you, not to the combat topic." A preview shows where creatures COULD end up
before the GM has decided, so nothing about it is posted in the group: the picture, and any reason there is none, go
to the GM's private chat with the bot. Only when that chat cannot be reached (the GM never pressed Start) does the
group hear about it, with no detail of the moves.
"""
import html

import telegram as tg
from combat.map_moves import ambiguous, describe, move_walls, resolve
from combat.map_view import caption, fetch_scene, make_fetch, send_photo


def tell_gm_privately(gm_uid, group_id: int, reply_topic: int, text: str) -> bool:
    """Send `text` (HTML) to the GM's private chat; if that cannot be reached, only a one-line note goes to the group."""
    if tg.send_message(int(gm_uid), None, text, parse_mode="HTML"):
        return True
    tg.send_message(group_id, reply_topic, "🗺️ I could not message you privately. Open a chat with me, "
                                           "press Start, then send the /map again.")
    return False


def post_move_map(code: str, moves: list, gm_uid, group_id: int, reply_topic: int,
                  scene=fetch_scene, fetch=None, send=send_photo) -> bool:
    """Draw the moves on the campaign's live scene and send it to `gm_uid`. False when there was nothing to send."""
    from combat.map_draw import draw_map

    def tell_gm(text):
        tell_gm_privately(gm_uid, group_id, reply_topic, text)

    view, why = scene(code)
    if view is None:
        tell_gm(f"🗺️ {html.escape(why)}")
        return False
    results, missing = resolve(view, moves)
    if missing:
        lines = []
        for name in missing:
            where = ambiguous(view, name)
            lines.append(f"{html.escape(name)} could be the one on {', '.join(where)}. Name the square too, "
                         f"e.g. {html.escape(name)} at {where[0]} slide S4." if where else
                         f"No token on {html.escape(code)}'s active scene answers to {html.escape(name)}.")
        tell_gm("🗺️ No move preview: " + " ".join(lines))
        return False
    jpeg = draw_map(view, fetch or make_fetch(), moves=results)
    head = caption(code, view, "").split("\n")[0]
    lines = [head, "Move preview, for you only:"] + [html.escape(describe(view, r)) for r in results]
    if not move_walls(view)[1]:
        lines.append("<i>Only walls that block sight are known; check for invisible or move-only walls.</i>")
    text = "\n".join(lines)
    if send(int(gm_uid), None, jpeg, text):
        return True
    # 2026-11-25: the photo can fail for other reasons than a GM who never pressed Start (Telegram refusing the
    # image, a network blip), so the moves still reach the GM as text if they can; the group hears only if not.
    tell_gm(text + "\n(The picture could not be sent.)")
    return False
