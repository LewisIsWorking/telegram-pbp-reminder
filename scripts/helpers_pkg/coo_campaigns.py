"""COO is the source of truth for which campaigns exist (2026-11-17).

Lewis decided the ComeOnOverUno server owns the campaign list and each
campaign's Telegram topics. ``apply`` overlays COO's list onto
``config["topic_pairs"]`` once per run, in ``checker.main``:

* matched by ``code``: name and Telegram topic ids come from COO, every
  bot-only setting (queue priority, polls, emoji ...) stays from
  config.json;
* a COO campaign with no config.json pair gets a pair with defaults, if it
  is active and has a PbP topic and a chat topic;
* a config.json pair COO does not list is kept unchanged (COO may not have
  it yet);
* COO's ``status`` is carried through as ``pair["status"]``; nothing is
  deleted for being archived or closed.

⚠️ No key, COO down, a non-200 or a body that does not parse: config.json
is used exactly as before, with one printed line. The run never fails
because COO did.

⚠️ A pair's FIRST pbp topic id is its key in state (``campaigns.get_pair``).
COO's ids are reordered so that id stays first, and if COO does not list
it at all the pair keeps its config.json ids, so a campaign's history is
never orphaned by a reordering on the server.
"""

import os

import requests

from combat.foundry_sync import DEFAULT_SERVER, KEY_HEADER

# /api/pathwars/campaigns was already taken on COO. 404 means the server
# has no bot key configured, 401 a wrong key: both fall back.
PATH = "/api/pathwars/campaign-links"

_fetched: dict = {}


def _topic(value):
    """A Telegram topic id, or None. bool is an int in Python; refuse it."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if value is None:
        return None
    raise ValueError(f"not a topic id: {value!r}")


def parse_campaigns(body) -> list[dict] | None:
    """COO's JSON array in the bot's own field names, or None if malformed.

    ⭐ The ONLY place COO's field names are read. If the endpoint renames a
    field, this is the one function to change.
    """
    if not isinstance(body, list):
        return None
    out = []
    try:
        for item in body:
            code = item.get("code")
            pbp = item.get("pbpTopicIds")
            if not isinstance(code, str) or not code.strip() \
                    or not isinstance(pbp, list):
                return None
            out.append({
                "code": code.strip(),
                "name": item.get("name") or None,
                "status": item.get("status") or None,
                "pbp_topic_ids": [_topic(t) for t in pbp if t is not None],
                "chat_topic_id": _topic(item.get("chatTopicId")),
                "combat_topic_id": _topic(item.get("combatTopicId")),
            })
    except (AttributeError, ValueError):
        return None
    return out


def fetch_campaigns(get=requests.get, env=os.environ) -> list[dict] | None:
    """COO's campaigns, or None (with one printed line) when unknown."""
    key = env.get("PATHWARS_BOT_READ_KEY", "").strip()
    if not key:
        print("COO campaigns: no read key, using config.json")
        return None
    base = env.get("COO_SERVER_URL", DEFAULT_SERVER).rstrip("/")
    try:
        response = get(f"{base}{PATH}", headers={KEY_HEADER: key}, timeout=20)
    except requests.RequestException as e:
        print(f"COO campaigns: server unreachable ({type(e).__name__}), "
              "using config.json")
        return None
    if response.status_code != 200:
        print(f"COO campaigns: server answered {response.status_code}, "
              "using config.json")
        return None
    try:
        campaigns = parse_campaigns(response.json())
    except ValueError:
        campaigns = None
    if campaigns is None:
        print("COO campaigns: malformed answer, using config.json")
    return campaigns


def coo_campaigns(fetch=fetch_campaigns) -> list[dict] | None:
    """``fetch_campaigns`` once per run; ``reset`` forgets it."""
    if "campaigns" not in _fetched:
        _fetched["campaigns"] = fetch()
    return _fetched["campaigns"]


def reset() -> None:
    _fetched.clear()


def _merged_ids(old: list, new: list) -> list | None:
    """COO's ids with config.json's first id kept first; None if COO lost it."""
    if not new:
        return None
    if old and old[0] not in new:
        return None
    kept = [t for t in old if t in new]
    return kept + [t for t in new if t not in kept]


def _update(pair: dict, camp: dict, notes: list) -> None:
    ids = _merged_ids(pair.get("pbp_topic_ids") or [], camp["pbp_topic_ids"])
    if ids is None:
        notes.append(f"{camp['code']} ids kept from config.json")
    else:
        pair["pbp_topic_ids"] = ids
    for field in ("name", "chat_topic_id", "combat_topic_id", "status"):
        if camp[field] is not None:
            pair[field] = camp[field]


def _new_pair(camp: dict) -> dict | None:
    """A pair for a campaign only COO knows, or None if it cannot be run."""
    if camp["status"] not in (None, "active") or not camp["pbp_topic_ids"] \
            or camp["chat_topic_id"] is None:
        return None
    pair = {"name": camp["name"] or camp["code"], "code": camp["code"],
            "pbp_topic_ids": list(camp["pbp_topic_ids"]),
            "chat_topic_id": camp["chat_topic_id"]}
    for field in ("combat_topic_id", "status"):
        if camp[field] is not None:
            pair[field] = camp[field]
    return pair


def overlay(config: dict, campaigns: list[dict]) -> tuple[dict, list[str]]:
    """config with COO's campaigns laid over ``topic_pairs``, plus notes.

    Pure: the given config and its pairs are not modified.
    """
    pairs = [dict(p) for p in config.get("topic_pairs", [])]
    by_code = {p["code"]: p for p in pairs if p.get("code")}
    notes, added, skipped = [], [], []
    for camp in campaigns:
        pair = by_code.get(camp["code"])
        if pair is not None:
            _update(pair, camp, notes)
            continue
        new = _new_pair(camp)
        if new is None:
            skipped.append(camp["code"])
            continue
        pairs.append(new)
        by_code[camp["code"]] = new
        added.append(camp["code"])
    listed = {c["code"] for c in campaigns}
    only_config = [c for c in by_code if c not in listed]
    if added:
        notes.append(f"added {', '.join(added)}")
    if skipped:
        notes.append(f"not added (inactive or no topics) {', '.join(skipped)}")
    if only_config:
        notes.append(f"config.json only, kept {', '.join(only_config)}")
    return {**config, "topic_pairs": pairs}, notes


def apply(config: dict, validate, fetch=coo_campaigns) -> dict:
    """The config the run should use. Falls back to ``config`` unchanged.

    ``validate`` is ``helpers.validate_config``: an overlay that would add
    an ERROR the config.json alone does not have is refused, so a bad COO
    record cannot abort the run.
    """
    campaigns = fetch()
    if campaigns is None:
        return config
    merged, notes = overlay(config, campaigns)
    before = {i for i in validate(config) if i.startswith("ERROR:")}
    new_errors = [i for i in validate(merged)
                  if i.startswith("ERROR:") and i not in before]
    if new_errors:
        print(f"COO campaigns: refused, {new_errors[0]}; using config.json")
        return config
    print(f"COO campaigns: {len(campaigns)} from COO"
          + "".join(f"; {n}" for n in notes))
    return merged
