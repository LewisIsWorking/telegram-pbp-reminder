"""🗺️ Post one character's battle map on request, without anyone typing /map (2026-11-20).

Telegram never delivers a bot's own messages back to it, and the bot ignores other bots, so a /map posted through
the say endpoint is never seen. post-map.yml runs this instead: the same post_map a /map Name from a GM makes, to the
campaign's combat topic. Quiet: a failure is printed for the run log and never posted to the players.

Usage (from scripts/): python -m combat.post_map_once C06 Kibwe
"""
import sys

from helpers_pkg.config import load_config


def post_once(config: dict, code: str, name: str, post=None) -> bool:
    if post is None:
        from combat.map_view import post_map as post
    pair = next((p for p in config.get("topic_pairs", []) if str(p.get("code", "")).upper() == code.upper()), None)
    if not pair or not pair.get("pbp_topic_ids"):
        print(f"post_map_once: no campaign {code}")
        return False
    if not name.strip():
        print("post_map_once: one character's view only; give a name")  # never the party's view (Lewis, 2026-11-18)
        return False
    topic = pair.get("combat_topic_id") or pair["pbp_topic_ids"][0]
    group_id = pair.get("group_id", config["group_id"])
    ok = bool(post(config, str(pair["pbp_topic_ids"][0]), str(pair["code"]), name.strip(), group_id, topic, quiet=True))
    print(f"post_map_once: {code} {name}: {'posted' if ok else 'no map (no scene, or no such token on it)'}")
    return ok


if __name__ == "__main__":  # pragma: no cover
    sys.exit(0 if post_once(load_config(), sys.argv[1], " ".join(sys.argv[2:])) else 1)
