"""
One-time migration: split gist pbp_state.json into partition files.

Usage (from repo root):
    GIST_TOKEN=<token> GIST_ID=<id> python3 scripts/migrate_gist_to_files.py

What it does:
    1. Downloads the full state from the gist
    2. Splits it into data/state/{live,players,queue,activity}.json
    3. Writes data/state/manifest.json with metadata
    4. Verifies all keys are accounted for
    5. Prints a summary — does NOT modify the gist

After running:
    git add data/state/
    git commit -m "feat(state): migrate gist state to file partitions"
    git push

The bot will then use files as primary state on next run.
"""

import json
import os
import sys
import requests
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from state import PARTITIONS

GIST_TOKEN = os.environ.get("GIST_TOKEN", "")
GIST_ID    = os.environ.get("GIST_ID", "")
STATE_FILE = "pbp_state.json"
STATE_DIR  = Path(__file__).parent.parent / "data" / "state"

# Keys excluded from file storage (transient / regenerated each run)
EXCLUDED_KEYS = {"_config_cache"}


def main() -> None:
    _check_env()
    raw_state = _download_gist()
    _validate_coverage(raw_state)
    _write_partitions(raw_state)
    _write_manifest(raw_state)
    _print_summary(raw_state)


def _check_env() -> None:
    missing = [v for v in ("GIST_TOKEN", "GIST_ID") if not os.environ.get(v)]
    if missing:
        print(f"Error: missing environment variable(s): {', '.join(missing)}")
        sys.exit(1)


def _download_gist() -> dict:
    print(f"Downloading gist {GIST_ID}...")
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {
        "Authorization": f"token {GIST_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=30)
    except requests.RequestException as e:
        print(f"Error: could not connect to gist: {e}")
        sys.exit(1)

    if resp.status_code != 200:
        print(f"Error: gist returned HTTP {resp.status_code}")
        sys.exit(1)

    files = resp.json().get("files", {})
    if STATE_FILE not in files:
        print(f"Error: '{STATE_FILE}' not found in gist")
        sys.exit(1)

    state = json.loads(files[STATE_FILE]["content"])
    total = len(files[STATE_FILE]["content"])
    print(f"Downloaded {total:,} bytes, {len(state)} top-level keys")
    return state


def _validate_coverage(state: dict) -> None:
    """Warn about any gist keys not mapped to a partition."""
    all_mapped = {k for keys in PARTITIONS.values() for k in keys}
    unmapped = {k for k in state if k not in all_mapped and k not in EXCLUDED_KEYS}
    if unmapped:
        print(f"\n⚠️  Unmapped keys (will NOT be migrated): {sorted(unmapped)}")
        print("   Add them to PARTITIONS in state.py before committing.\n")
    else:
        print("✅ All gist keys are mapped to partitions")


def _write_partitions(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    for partition, keys in PARTITIONS.items():
        data = {k: state[k] for k in keys if k in state}
        path = STATE_DIR / f"{partition}.json"
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        size = path.stat().st_size
        print(f"  Wrote {partition}.json — {len(data)} keys, {size:,} bytes")


def _write_manifest(state: dict) -> None:
    manifest = {
        "migrated_at": datetime.now(timezone.utc).isoformat(),
        "source": f"gist:{GIST_ID}",
        "total_keys_in_gist": len(state),
        "partitions": {p: list(keys) for p, keys in PARTITIONS.items()},
        "excluded_keys": sorted(EXCLUDED_KEYS),
    }
    path = STATE_DIR / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"  Wrote manifest.json")


def _print_summary(state: dict) -> None:
    all_mapped = {k for keys in PARTITIONS.values() for k in keys}
    migrated   = [k for k in state if k in all_mapped]
    excluded   = [k for k in state if k in EXCLUDED_KEYS]
    unmapped   = [k for k in state if k not in all_mapped and k not in EXCLUDED_KEYS]

    print("\n" + "─" * 50)
    print(f"Migration complete")
    print(f"  Migrated:  {len(migrated)} keys → data/state/")
    print(f"  Excluded:  {len(excluded)} keys (transient, not stored)")
    if unmapped:
        print(f"  ⚠️ Unmapped: {len(unmapped)} keys — {unmapped}")
    print("\nNext steps:")
    print("  git add data/state/")
    print('  git commit -m "feat(state): migrate gist state to file partitions"')
    print("  git push")
    print("─" * 50)


if __name__ == "__main__":
    main()
