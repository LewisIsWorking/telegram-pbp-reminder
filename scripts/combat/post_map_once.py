"""🗺️ Post one character's battle map on request, without anyone typing /map (2026-11-20).

Telegram never delivers a bot's own messages back to it, and the bot ignores other bots, so a /map posted through
the say endpoint is never seen. post-map.yml runs this instead, in two steps, because Lewis must see every map
before it is posted (2026-11-20: "You NEED to show me the map before you ever post it"):

  preview: draw the map, save it as map.jpg (the workflow uploads it) and print its sha256. Posts nothing.
  post:    draw it again and post it ONLY if its sha256 is the one Lewis approved; a moved token changes the
           picture, and then nothing is posted.

The post can reply to a message (reply_to) and add GM text under the caption (text). Quiet: a failure is printed for
the run log and never posted to the players.
"""
import argparse
import hashlib
import html
import sys

from helpers_pkg.config import load_config


def render(config: dict, code: str, name: str, scene=None, draw=None):
    """(pair, jpeg, view) or (None, None, why)."""
    from combat import map_view
    from combat.map_draw import draw_map, named_on
    scene = scene or map_view.fetch_scene
    draw = draw or (lambda v, n: draw_map(v, map_view.make_fetch(), n))
    pair = next((p for p in config.get("topic_pairs", []) if str(p.get("code", "")).upper() == code.upper()), None)
    if not pair or not pair.get("pbp_topic_ids"):
        return None, None, f"no campaign {code}"
    if not name.strip():
        return None, None, "one character's view only; give a name"  # never the party's view (Lewis, 2026-11-18)
    view, why = scene(str(pair["code"]))
    if view is None:
        return None, None, why
    if not named_on(view, name):
        return None, None, f"{name} has no token on {code}'s active scene"
    return pair, draw(view, name), view


def run(config: dict, mode: str, code: str, name: str, expect: str = "", reply_to: int = 0, text: str = "",
        scene=None, draw=None, send=None, out: str = "map.jpg") -> bool:
    pair, jpeg, view = render(config, code, name, scene, draw)
    if pair is None:
        print(f"post_map_once: {view}")
        return False
    sha = hashlib.sha256(jpeg).hexdigest()
    print(f"post_map_once: {code} {name}: sha256 {sha}")
    if mode == "preview":
        with open(out, "wb") as f:
            f.write(jpeg)
        return True
    if not expect or sha != expect.strip().lower():
        print("post_map_once: not the approved picture (the scene changed, or no sha given); nothing posted")
        return False
    from combat.map_view import caption, send_photo
    send = send or send_photo
    body = caption(str(pair["code"]), view, name) + (f"\n\n{html.escape(text.strip())}" if text.strip() else "")
    topic = pair.get("combat_topic_id") or pair["pbp_topic_ids"][0]
    ok = send(pair.get("group_id", config["group_id"]), topic, jpeg, body, reply_to=reply_to or None)
    print(f"post_map_once: {'posted' if ok else 'Telegram refused it'}")
    return bool(ok)


if __name__ == "__main__":  # pragma: no cover
    a = argparse.ArgumentParser()
    a.add_argument("mode", choices=["preview", "post"])
    a.add_argument("code")
    a.add_argument("name")
    a.add_argument("--expect", default="")
    a.add_argument("--reply-to", type=int, default=0)
    a.add_argument("--text", default="")
    x = a.parse_args()
    import os
    import telegram as tg
    tg.init(os.environ.get("TELEGRAM_BOT_TOKEN", ""))  # checker.py does this; without it sendPhoto has no URL
    sys.exit(0 if run(load_config(), x.mode, x.code, x.name, x.expect, x.reply_to, x.text.replace("\\n", "\n"),
                      out="../map.jpg") else 1)
