"""
Gist I/O for state backup.

State.py persists the bot's mutable state to local JSON files (the
authoritative store) and mirrors a copy to a GitHub Gist as an
emergency read-only backup. This module isolates the gist HTTP
plumbing from state.py so that file I/O and network I/O are
single-responsibility modules.

The credentials (gist API URL, token) and filename are passed in by
state.py rather than read from a module-level singleton, keeping this
module free of side-effects at import time and trivial to unit-test.
"""

import json

import requests


def _headers(token: str) -> dict:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }


def gist_load(api: str, token: str, filename: str) -> dict | None:
    """Load state blob from gist. Returns None on any failure.

    Raises SystemExit on hard network failure or non-200 response so
    we never silently fall back to an empty state and clobber gist
    history with an empty save on the next tick.
    """
    if not api or not token:
        return None
    try:
        resp = requests.get(api, headers=_headers(token), timeout=30)
    except requests.RequestException as e:
        print(f"FATAL: Could not connect to gist ({e}), aborting to protect state")
        raise SystemExit(1)
    if resp.status_code != 200:
        print(f"FATAL: Gist returned HTTP {resp.status_code}, aborting")
        raise SystemExit(1)
    files = resp.json().get("files", {})
    if filename not in files:
        return None
    state = json.loads(files[filename]["content"])
    print(f"State loaded from gist (offset={state.get('offset', 0)})")
    return state


def gist_save(api: str, token: str, filename: str, state: dict) -> None:
    """Write full state blob to gist as backup. Logs but never raises."""
    if not api or not token:
        return
    try:
        resp = requests.patch(
            api, headers=_headers(token), timeout=30,
            json={"files": {filename: {
                "content": json.dumps(state, indent=2, default=str)
            }}},
        )
        if resp.status_code == 200:
            print("State backup saved to gist")
        else:
            print(f"Warning: gist backup failed (HTTP {resp.status_code})")
    except requests.RequestException as e:
        print(f"Warning: gist backup failed ({e})")
