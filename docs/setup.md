## Setup

Takes about 15 minutes.

### 1. Create a Telegram bot

1. Message **@BotFather** on Telegram.
2. Send `/newbot`, follow the prompts, copy the **bot token**.
3. Send `/setprivacy`, select your bot, set to **Disable**
   (so it can read all messages, not just `/commands`).
4. Add the bot to your supergroup.
5. Make it an **admin** (needs: Read Messages, Send Messages).

### 2. Find your topic IDs

Open this URL in a browser (replace `YOUR_TOKEN`):
```
https://api.telegram.org/botYOUR_TOKEN/getUpdates
```

Send one message in each PBP topic and each Chat topic, then refresh.
You'll see JSON like:
```json
{
  "message": {
    "chat": { "id": -1001234567890 },
    "message_thread_id": 12345
  }
}
```

Note down:
- `chat.id` is your **group_id** (same for all topics).
- `message_thread_id` is the **topic ID** (unique per topic).
- Your Telegram **user ID** (visible in the `from.id` field). This is your GM ID.

### 3. Create a GitHub Gist

1. Go to [gist.github.com](https://gist.github.com).
2. Create a gist with filename `pbp_state.json` and content `{}`.
3. Save it. Copy the **Gist ID** from the URL.

### 4. Create a GitHub token

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens).
2. Generate a classic token with the **gist** scope only.
3. Copy the token.

### 5. Fork or create the repo

1. Fork this repo (or create a new one and copy the files).
2. Go to **Settings > Secrets and variables > Actions** and add:

| Secret               | Value                      |
|----------------------|----------------------------|
| `TELEGRAM_BOT_TOKEN` | Bot token from BotFather   |
| `GIST_TOKEN`         | GitHub PAT with gist scope |
| `GIST_ID`            | Gist ID from step 3        |

### 6. Configure

Copy `config.example.json` to `config.json` and fill it in:

```json
{
    "group_id": -1001234567890,
    "alert_after_hours": 4,
    "gm_user_ids": [123456789],
    "leaderboard_topic_id": null,
    "bot_topic_id": null,
    "topic_pairs": [
        {
            "name": "My Campaign",
            "chat_topic_id": 11111,
            "pbp_topic_ids": [22222],
            "created": "2025-01-15"
        }
    ]
}
```

Key fields:
- **group_id**: Your supergroup's chat ID (negative number).
- **gm_user_ids**: Array of GM Telegram user IDs. GMs are excluded from player stats.
- **leaderboard_topic_id**: Topic ID for the cross-campaign leaderboard (or `null` to disable).
- **bot_topic_id**: Topic ID for the dedicated bot channel. All scheduled output (rosters, alerts, tips, POTW, etc.) posts here instead of campaign chats. Also enables `/search`, `/queue`, `/timeline` from the bot channel. Set to `null` to post in campaign chat topics instead.
- **topic_pairs**: One entry per campaign. Each needs a name, a chat topic, and one or more PBP topics.
- **created**: Campaign start date for anniversary alerts (optional, `YYYY-MM-DD`).
- **gm_user_ids** (per-campaign): Optional override that replaces the global GM list for this campaign only. Useful when a campaign has a different GM.
- **characters** (per-campaign): Optional mapping of `"user_id": "Character Name"`. Enables `/party` command and shows character names in rosters, stats, and transcripts.
- **disabled_features**: Optional list of features to disable for this campaign.
  Valid values: `alerts`, `warnings`, `roster`, `potw`, `pace`, `recruitment`, `combat`, `anniversary`, `smart_alerts`.

### 7. Add boons (optional)

The Player of the Week feature picks 3 random flavour boons from `boons.json`
plus 1 mechanical boon. Copy `boons.example.json` to `boons.json` and add your own,
or use the example as-is. Each entry is a plain string.

### 8. Test

Go to **Actions > PBP Inactivity Reminder > Run workflow**.
Check the logs. You should see:
```
Loaded state. Offset: 0 | Tracking 0 topics, 0 players
Received N new updates
Done
```

The bot will start tracking from this point. Features like rosters and POTW
will activate once enough data has accumulated.

---

