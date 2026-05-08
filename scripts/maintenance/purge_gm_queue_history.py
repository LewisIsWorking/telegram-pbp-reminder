"""One-off: delete legacy GM queue messages from the GM Queue topic.

Sweeps message IDs 146781 → 151517 (just before first tracked batch).
Bot can only delete its own messages — others silently fail.
"""

import os, sys, time
import requests

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
BASE = f"https://api.telegram.org/bot{TOKEN}"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from helpers_pkg.config import load_config
from state import load as load_state

config = load_config()
state, _ = load_state(config)
GROUP_ID = config["group_id"]

# Range: topic created at 146780, first tracked batch starts at 151518
START, END = 146781, 151517
print(f"Sweeping IDs {START}–{END} in group {GROUP_ID}")

deleted = failed = 0
for mid in range(START, END + 1):
    r = requests.post(f"{BASE}/deleteMessage",
                      json={"chat_id": GROUP_ID, "message_id": mid})
    if r.json().get("ok"):
        deleted += 1
        if deleted % 50 == 0:
            print(f"  {deleted} deleted (current: {mid})")
    else:
        failed += 1
    time.sleep(0.05)  # ~20 req/s, well under Telegram rate limit

print(f"Done: {deleted} deleted, {failed} skipped.")
