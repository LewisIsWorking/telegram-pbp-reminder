"""CI alert script — reads pytest output and posts failure details to bot topic.

Called by the GitHub Actions test job when pytest exits non-zero.
Reads /tmp/pytest_output.txt and posts FAILED test names + coverage gaps.
"""

import os
import sys
import requests

sys.path.insert(0, "scripts")
from helpers_pkg.config import load_config

token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
sha = os.environ.get("GITHUB_SHA", "?")[:8]

try:
    raw = open("/tmp/pytest_output.txt", encoding="utf-8").read()
    lines = raw.splitlines()
    failed = [l for l in lines if l.startswith("FAILED ")]
    missing = [l for l in lines if "MISSING" in l or ("Miss" in l and "%" in l)]
    summary = []
    if failed:
        summary.append("Failed tests:")
        summary.extend(f"  {l}" for l in failed[:10])
    if missing and not failed:
        summary.append("Coverage gaps:")
        summary.extend(f"  {l.strip()}" for l in missing[:5])
    detail = "\n".join(summary) if summary else "(see GitHub Actions for details)"
except Exception as e:
    detail = f"(could not read output: {e})"

config = load_config()
gid = config["group_id"]
tid = config.get("bot_topic_id")

if tid and token:
    text = f"\u26a0\ufe0f Tests failed on push (sha: {sha})\n\n{detail}"
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": gid, "message_thread_id": tid, "text": text},
    )
    print(f"Alert posted for sha {sha}")
else:
    print("No bot_topic_id or token — skipping alert")
