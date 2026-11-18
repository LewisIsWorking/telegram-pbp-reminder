"""🗺️ /map: the campaign's battle map as its party sees it, posted to its combat topic (2026-11-18).

Lewis: "Building a Foundry screenshot tool that's player view / party view could be really good for telegram based
combat visualising and strategy", then "make sure it sees through a token's vision".

``/map`` draws what the whole party sees; ``/map Zerius`` only what Zerius sees. The scene comes from the COO server
(``api/pathwars/scene/{code}``, the bot's read key, as for encounters), which reads the campaign's Foundry world and
sends only what players could see. Drawing is map_draw.py. Art comes from the public Foundry server.

⚠️ The bot runs on a schedule, so the map is as of that run, and the caption says which scene and round it shows.
"""
import html
import io
import os
import urllib.parse

import requests
from PIL import Image

import telegram as tg
from combat.foundry_sync import DEFAULT_SERVER, KEY_HEADER
from combat.map_draw import draw_map, named_on

FOUNDRY = "https://foundry.cooserver.duckdns.org/"
MAX_ASSET = 25_000_000  # bytes; a map larger than this is not worth the run's memory


def fetch_scene(code: str, get=requests.get, env=os.environ) -> tuple[dict | None, str]:
    """(view, "") or (None, why), for the reply."""
    key = env.get("PATHWARS_BOT_READ_KEY", "").strip()
    if not key:
        return None, "The map needs the server key, which this bot run does not have."
    base = env.get("COO_SERVER_URL", DEFAULT_SERVER).rstrip("/")
    try:
        r = get(f"{base}/api/pathwars/scene/{urllib.parse.quote(code)}", headers={KEY_HEADER: key}, timeout=60)
    except requests.RequestException as e:
        print(f"/map: server unreachable ({type(e).__name__})")
        return None, "The server did not answer, so there is no map right now."
    if r.status_code == 404:
        return None, f"{code} has no Foundry map to show."
    if r.status_code != 200:
        print(f"/map: server answered {r.status_code}")
        return None, "The server could not read the map right now."
    body = r.json()
    view = body.get("view") if isinstance(body, dict) else None
    return (view, "") if isinstance(view, dict) else (None, f"{code} has no Foundry map to show.")


def make_fetch(get=requests.get):
    """An asset fetcher for map_draw: Foundry paths become public URLs; a failure draws a plain disc instead."""
    cache: dict = {}

    def fetch(src):
        if not src:
            return None
        if src not in cache:
            url = src if src.startswith("http") else FOUNDRY + urllib.parse.quote(urllib.parse.unquote(src.split("?")[0]), safe="/")
            try:
                r = get(url, timeout=60)
                ok = r.status_code == 200 and len(r.content) <= MAX_ASSET
                cache[src] = Image.open(io.BytesIO(r.content)) if ok else None
            except Exception as e:  # svg, broken image or network: the token is still drawn, as a disc
                print(f"/map: could not use {src[:80]}: {type(e).__name__}")
                cache[src] = None
        return cache[src]
    return fetch


def caption(code: str, view: dict, wanted: str) -> str:
    combat = view.get("combat")
    whose = f"what {html.escape(wanted.strip())} can see" if wanted.strip() else "what the party can see"
    when = f", round {combat['round']}" if combat and combat.get("round") else ""
    return f"🗺️ <b>{html.escape(code)}</b>: {html.escape(view['scene']['name'])}{when}\nShowing {whose}."


def send_photo(chat_id: int, thread_id: int | None, jpeg: bytes, text: str, post=requests.post) -> bool:
    data = {"chat_id": chat_id, "caption": text, "parse_mode": "HTML"}
    if thread_id is not None:
        data["message_thread_id"] = thread_id
    try:
        r = post(f"{tg.TELEGRAM_API}/sendPhoto", data=data, files={"photo": ("map.jpg", jpeg, "image/jpeg")}, timeout=60)
    except requests.RequestException as e:
        print(f"/map: sendPhoto network error: {type(e).__name__}")
        return False
    if r.status_code != 200:
        print(f"/map: sendPhoto failed: {r.text[:300]}")
    return r.status_code == 200


def post_map(config: dict, pid: str, code: str, wanted: str, group_id: int, reply_topic: int,
             scene=fetch_scene, fetch=None, send=send_photo, quiet: bool = False) -> bool:
    """Draw and post the map to the campaign's combat topic (else where it was asked). False when there is none.

    `quiet` (the turn-end map, combat/turn_maps.py): a failure only returns False, so a fight with no map never
    posts an error after every turn.
    """
    pair = next((p for p in config.get("topic_pairs", []) if str(p["pbp_topic_ids"][0]) == pid), {})
    view, why = scene(code)
    if view is None:
        if not quiet:
            tg.send_message(group_id, reply_topic, f"🗺️ {why}")
        return False
    # 🧭 2026-11-18: /map works outside a fight too, answered where it was asked; a fight's map goes to its combat topic.
    topic = (pair.get("combat_topic_id") if view.get("combat") else None) or reply_topic
    # One character's map (Lewis: one character's view) never falls back to the party's: say so instead.
    if wanted.strip() and not named_on(view, wanted):
        if not quiet:
            tg.send_message(group_id, reply_topic, f"🗺️ No party character called {wanted.strip()} is on {code}'s map.")
        return False
    try:
        jpeg = draw_map(view, fetch or make_fetch(), wanted)
    except ValueError:
        if not quiet:
            tg.send_message(group_id, reply_topic, f"🗺️ {code}'s map has no tokens on it.")
        return False
    return send(group_id, topic, jpeg, caption(code, view, wanted))
