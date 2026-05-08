"""One-off: delete legacy GM queue messages from the GM Queue topic.

Sweeps message IDs 146781 → 151517 (just before first tracked batch).
Bot can only delete its own messages — others silently fail.
"""

import os, time
import requests

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
BASE = f"https://api.telegram.org/bot{TOKEN}"
GROUP_ID = -1001661053273  # Path Wars group

START, END = 146781, 151517
print(f"Sweeping IDs {START}-{END} in group {GROUP_ID}")

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
    time.sleep(0.05)

print(f"Done: {deleted} deleted, {failed} skipped.")
