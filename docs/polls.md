# Polls

## Session Polls

Weekly native Telegram polls to schedule live sessions for hybrid campaigns.

### Campaigns

| Campaign | Poll type | Options |
|---|---|---|
| C01 Doomsday Funtime | Single choice | Friday / Saturday / Either / Both / Can't make it |
| C11 Dark Pockets | Multiple choice | Monday–Sunday / Can't make it |

### Lifecycle

1. **Sunday at 07:00 UTC** — poll posted and pinned to the campaign chat topic.
2. **Daily (Mon–Sun)** — players who haven't voted get a ping with a link to the poll.
3. **All voted** — "All X players have voted!" posted once.
4. **Friday 15:00 UTC** — result announced in each campaign's chat topic.

### Cross-campaign notifications

C01 and C11 polls are linked. Every vote in either poll sends an
immediate tally update to **both** chat topics:

```
🗳️ @JackGrah voted Saturday in C11
C01: Friday: 2, Either: 1
C11: Saturday: 2, Thursday: 1
```

This lets both groups track how the other campaign is voting, since C11's
session often follows C01's.

### Poll roster

Players to ping are configured in `poll_user_ids` per campaign. If a player
isn't in the PBP registry (e.g. C11 live-only players), add them to
`poll_user_names` as `{uid: "username"}`.

If a player's ID is unknown, use a placeholder (e.g. `9000000001`).
When they vote, their real ID is captured automatically and can be promoted
with `python3 scripts/promote_poll_voters.py --commit`.

---

## Swimming Poll

A separate weekly poll in the Dark Pockets group for scheduling a
regular swim session.

- **Posted:** Sunday at 07:00 UTC, Dark Pockets main chat (topic 1)
- **Options:** Monday–Sunday / Can't make it (multiple choice)
- **Pinned** immediately after posting
- **Daily ping** to unvoted swimmers with a direct link to the poll

### Swimmers

| Player | Username | Status |
|---|---|---|
| Natasha | @NitNatty | ✅ confirmed |
| Jack | @JackGrah | ✅ confirmed |
| Elicia | @EliciaRoseT | ⏳ pending ID |
| — | @deft_369 | ⏳ pending ID |
| — | @Verminatrix | ⏳ pending ID |
| — | @anweshaborah190 | ⏳ pending ID |
| — | @TwoBad22 | ⏳ pending ID |

IDs for the 5 unknown swimmers are captured automatically when they
vote. The swim poll voter IDs are tracked separately from C11 session
poll IDs — update `swimming_poll.py` directly when promoting.

---

## Vote results history

All session poll results are archived in `state["poll_results"]` and
per-campaign history in `state["poll_history"]`. The history string
(Fridays X/N, Saturdays Y/N) is shown as a follow-up message each Sunday
when the new poll is posted.
