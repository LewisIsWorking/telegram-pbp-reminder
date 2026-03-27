## Example output

**Inactivity alert:**
```
No new posts in Grand Explorers PBP for 1d 6h.
Last post was from Tyler Link (42 total posts) on 2026-02-20.
```

**Party roster:**
```
Party roster for Riddleport:

GM
- 60 posts total.
- 12 posting sessions.
- 9 posts in the last week.
- Average gap between posting: 21.4 hours.
- Last post: today (2026-02-24).

Lunnes
- @LuNneS_B.
- 15 posts total.
- 6 posting sessions.
- 4 posts in the last week.
- Average gap between posting: 47.5 hours.
- Last post: today (2026-02-24).

Party size: 5/6.
Riddleport needs 1 more player!
```

**Player of the Week:**
```
Player of the Week for Riddleport: Lunnes (@LuNneS_B)!
(2026-02-17 to 2026-02-24)

6 posts this week with an average gap of 18.3h between posts.
The most consistent driver of the story.

Choose your boon:
1. A stray cat follows you and hisses at anyone who lies to you.
2. You find a coin in your boot that wasn't there before.
3. The next innkeeper insists your money is no good here.
4. +1 circumstance bonus on your next skill check.

Tap a button below, or type /chooseboon N
```

---

## How it works

```
GitHub Actions (hourly cron)
    │
    ▼
checker.py (orchestrator)
    │
    ├── dispatch/       Process Telegram updates, route commands
    ├── commands/       Build responses for /status, /campaign, etc.
    ├── scheduled/      Run 18 cron tasks (alerts, rosters, POTW, etc.)
    ├── combat/         Combat turn tracking
    ├── boons/          Player of the Week boon system
    ├── transcript/     PBP transcript archiving
    ├── helpers_pkg/    Shared utilities (config, formatting, dice, DC)
    │
    ├── telegram.py     Telegram Bot API (fetch updates, send messages)
    └── state.py        GitHub Gist (persist state between runs)
```

The codebase is split into 91 production files across 9 packages, with every
file held to a strict 200-line maximum. 339 tests (286 + 37 + 16) run on
every push before deployment.

The bot expects a Telegram supergroup with **forum topics** enabled.
Each campaign needs two topics: a **PBP topic** (where the game happens)
and a **Chat topic** (where the bot posts summaries and alerts).

Posts within 10 minutes of each other are treated as a single "posting session"
so rapid back-and-forth doesn't inflate counts.

Campaigns can have multiple PBP topics (e.g. if you split scenes across threads).
The bot merges them under one canonical ID for all tracking.

---
