"""Gist-based state persistence."""

import json
import requests

GIST_TOKEN = ""
GIST_API = ""
STATE_FILENAME = "pbp_state.json"

DEFAULT_STATE = {
    "offset": 0,
    "topics": {},
    "last_alerts": {},
    "players": {},
    "removed_players": {},
    "message_counts": {},
    "last_roster": {},
    "post_timestamps": {},
    "last_potw": {},
    "last_pace": {},
    "last_anniversary": {},
    "combat": {},
    "pending_potw_boons": {},
    "last_recruitment_check": {},
    "last_leaderboard": None,
}


_loaded_from_gist = False


def init(gist_token: str, gist_id: str) -> None:
    """Set gist credentials."""
    global GIST_TOKEN, GIST_API
    GIST_TOKEN = gist_token
    GIST_API = f"https://api.github.com/gists/{gist_id}"


def load() -> dict:
    """Load bot state from GitHub Gist, or return defaults if unavailable."""
    global _loaded_from_gist

    if not GIST_API or not GIST_TOKEN:
        print("Warning: No GIST_ID or GIST_TOKEN set, starting with empty state")
        return dict(DEFAULT_STATE)

    try:
        resp = requests.get(
            GIST_API,
            headers={
                "Authorization": f"token {GIST_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
            },
            timeout=30,
        )
    except requests.RequestException as e:
        print(f"FATAL: Could not connect to gist ({e}), aborting to protect state")
        raise SystemExit(1)

    if resp.status_code != 200:
        print(f"FATAL: Could not load gist (HTTP {resp.status_code}), aborting to protect state")
        raise SystemExit(1)

    gist_data = resp.json()
    files = gist_data.get("files", {})

    if STATE_FILENAME in files:
        content = files[STATE_FILENAME]["content"]
        state = json.loads(content)
        # Backwards compat: ensure all keys exist
        for key, default in DEFAULT_STATE.items():
            if key not in state:
                state[key] = default
        _loaded_from_gist = True
        return state

    _loaded_from_gist = True
    return dict(DEFAULT_STATE)


def save(state: dict) -> None:
    """Persist bot state to GitHub Gist.

    Refuses to save if the state was not successfully loaded from the gist
    (prevents a failed load from wiping all data).
    """
    if not _loaded_from_gist:
        print("REFUSING to save: state was not loaded from gist (would wipe data)")
        return

    if not GIST_API or not GIST_TOKEN:
        print("Warning: No GIST_ID or GIST_TOKEN set, cannot save state")
        return

    try:
        resp = requests.patch(
            GIST_API,
            headers={
                "Authorization": f"token {GIST_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={
                "files": {
                    STATE_FILENAME: {
                        "content": json.dumps(state, indent=2)
                    }
                }
            },
            timeout=30,
        )
    except requests.RequestException as e:
        print(f"Warning: Failed to save state ({e})")
        return

    if resp.status_code == 200:
        print("State saved to gist")
    else:
        print(f"Warning: Failed to save state (HTTP {resp.status_code})")
