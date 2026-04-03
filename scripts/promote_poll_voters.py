"""
Promote unknown poll voter IDs from state into config.

After running, unknown voters captured from poll_answer updates are
printed alongside their vote patterns and the remaining placeholder IDs,
so you can match them up and confirm the promotion.

Usage (from repo root):
    python3 scripts/promote_poll_voters.py [--commit]

Without --commit: dry-run, prints what would change.
With --commit:    writes config.json with confirmed matches.
"""

import json
import sys
from pathlib import Path

ROOT   = Path(__file__).parent.parent
CONFIG = ROOT / "config.json"
STATE  = ROOT / "data" / "state" / "live.json"

PLACEHOLDER_PREFIX = 9000000000


def _is_placeholder(uid: int) -> bool:
    return PLACEHOLDER_PREFIX <= uid < PLACEHOLDER_PREFIX + 100


def main() -> None:
    commit = "--commit" in sys.argv
    config = json.loads(CONFIG.read_text())
    state  = json.loads(STATE.read_text())

    unknown_by_code = state.get("poll_unknown_voters", {})
    if not unknown_by_code:
        print("No unknown voters in state — nothing to promote.")
        return

    for code, unknown_uids in unknown_by_code.items():
        pair = next((p for p in config["topic_pairs"]
                     if p.get("code") == code), None)
        if not pair:
            continue

        placeholders = [(str(u), pair["poll_user_names"].get(str(u), "?"))
                        for u in pair.get("poll_user_ids", [])
                        if _is_placeholder(u)]

        polls = state.get("session_poll", {}).get(code, {})
        votes = polls.get("votes", {})
        options = pair.get("poll_options", [])

        print(f"\n{'─'*50}")
        print(f"{code}: {len(unknown_uids)} unknown voter(s), "
              f"{len(placeholders)} placeholder(s) remaining")
        print()

        print("Unknown voters (real IDs captured from poll):")
        for uid in unknown_uids:
            voted_opts = [options[int(k)] if int(k) < len(options) else k
                          for k, uids in votes.items() if uid in uids]
            print(f"  {uid} → voted: {', '.join(voted_opts) or '?'}")

        print("\nRemaining placeholders:")
        for ph_uid, uname in placeholders:
            print(f"  {ph_uid} → @{uname}")

        if not placeholders:
            print("  (none — all placeholders resolved)")
            continue

        if len(unknown_uids) == 1 and len(placeholders) == 1:
            real_uid = unknown_uids[0]
            ph_uid, uname = placeholders[0]
            print(f"\nAuto-match: {ph_uid} (@{uname}) → {real_uid}")
            if commit:
                _promote(pair, ph_uid, real_uid, uname)
        else:
            print("\nMultiple unknowns — manual match required.")
            print("Edit config.json manually or re-run after more votes narrow it down.")

    if commit:
        CONFIG.write_text(json.dumps(config, indent=2))
        STATE_live = state
        STATE_live["poll_unknown_voters"] = {}
        STATE.write_text(json.dumps(STATE_live, indent=2))
        print("\nconfig.json and live.json updated.")
        print("Run: git add config.json data/state/live.json && git commit && git push")
    else:
        print("\nDry run — pass --commit to apply changes.")


def _promote(pair: dict, placeholder: str, real_uid: str, uname: str) -> None:
    ids = pair.get("poll_user_ids", [])
    pair["poll_user_ids"] = [
        int(real_uid) if str(u) == placeholder else u for u in ids
    ]
    names = pair.get("poll_user_names", {})
    if placeholder in names:
        del names[placeholder]
    names[real_uid] = uname


if __name__ == "__main__":  # pragma: no cover
    main()
