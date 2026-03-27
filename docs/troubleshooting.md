## Troubleshooting

**Bot not seeing messages:**
Privacy mode must be disabled (`/setprivacy` > Disable via @BotFather)
and the bot must be a group admin.

**No updates showing:**
Send a message in a monitored topic after the bot is added, then check logs.

**Wrong topic IDs:**
Topic IDs are the `message_thread_id` field in the Telegram API response,
not the message ID. Each forum topic has a unique thread ID.

**GitHub Actions not running:**
Check the Actions tab for errors. Free tier allows 2,000 minutes/month;
this bot uses roughly 30 minutes/month.

**Features not activating:**
Most features need accumulated data. Rosters need posts with timestamps,
POTW needs a week of data, pace reports need two weeks. Give it time.

---

## Cost

Zero. GitHub Actions free tier gives 2,000 minutes/month.
This bot uses about 30 seconds per run, 720 runs/month = ~36 minutes.
The Gist and Telegram Bot API are also free.

---

## Archive Dashboard

**Live dashboard:** [lewisisworking.github.io/telegram-pbp-reminder](https://lewisisworking.github.io/telegram-pbp-reminder/)

The bot archives weekly stats to `data/weekly_archive.json`.
The dashboard at `docs/index.html` visualizes this with charts and tables:
summary cards, health indicators, trend arrows, player drill-down,
week filter, and sortable columns. Mobile-responsive.

To enable GitHub Pages on your own fork:
1. Go to repo **Settings > Pages**.
2. Set source to **Deploy from a branch**, branch `main`, folder `/docs`.
3. Visit `https://yourusername.github.io/your-repo-name/`.

