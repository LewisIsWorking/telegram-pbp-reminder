# Player of the Week & Boons

## Overview

Each campaign independently awards a Player of the Week (POTW) to the
most consistently posting player. Winners receive a choice of flavour
boons — small narrative advantages that carry into play.

---

## Selection criteria

The winner is the non-GM player who posted at least `potw_min_posts`
(default 5) times in the period with the **lowest average gap** between
posts — rewarding consistency over volume.

GMs and away players are excluded.

---

## Boon offer

The winner receives 4 boons:
- **3 flavour boons** — randomly selected from `boons.json` (1000 entries).
  These are subtle narrative advantages ("A cat follows you and hisses at
  anyone who lies to you.").
- **1 mechanical boon** — chosen from `helpers.MECHANICAL_BOONS`. These have
  direct game effects ("Recover 1d6 extra HP during your next rest.").

The offer is posted in the campaign's chat topic with inline buttons **and**
the text `/chooseboon N` as a fallback.

---

## Choosing a boon

In the **PBP topic** (not the chat topic), type:
```
/chooseboon 1
/chooseboon 2
/chooseboon 3
/chooseboon 4
```

Only the POTW winner can choose. The choice is permanent.

The original POTW message is then edited to show the chosen boon and
the inline buttons are removed.

**Note:** If the command includes `@BotName` (e.g. `/chooseboon@PathWarsNudgeBot 2`),
this is handled correctly since v4.26.0.

---

## History

Every POTW event is recorded in `state["potw_history"]` regardless of
whether the winner chooses a boon. Fields:

| Field | Description |
|---|---|
| `week` | ISO week (e.g. `W13`) |
| `year` | Calendar year |
| `date` | Date posted |
| `campaign` | Campaign name |
| `campaign_pid` | Campaign topic ID |
| `user_id` | Winner's Telegram user ID |
| `first_name` | Winner's display name |
| `username` | @username if known |
| `post_count` | Posts during the period |
| `avg_gap_h` | Average gap between posts (hours) |
| `boons_offered` | All 4 boons presented |
| `boon_chosen` | Chosen boon text, or `null` |

Use `/boons` in a PBP topic to see your current boons for that campaign.
Use `/boonsall` to see all boons across all campaigns.

---

## Streaks

### Campaign streak
Consecutive weeks winning POTW in the same campaign.
Announced in the campaign chat topic at **2, 3, 5, 10 weeks**.

### Community streak
Consecutive weeks winning POTW in **any** campaign (one win per ISO week counts).
Announced in the bot topic at **2, 3, 5 weeks**.

---

## Expiry

Pending boon offers that are not claimed expire after a configurable
period (handled by `expire_pending_boons` in `boons/reminders.py`).
