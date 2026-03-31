## Commands

The bot responds to these commands in any monitored PBP topic:

**Everyone:**
- `/help` - List bot features and commands.
- `/status` - Campaign health snapshot: party size, last post, posts this week, at-risk players, current scene.
- `/campaign` - Full scoreboard: header, weekly pace with trends, complete roster with stats, at-risk warnings, combat state, scene, notes.
- `/mystats` (alias `/me`) - Your personal stats: total posts, sessions, average gap, weekly count, streak.
- `/myhistory` - 8-week posting sparkline with trend.
- `/whosturn` - Combat status: who has acted, who the party is waiting on.
- `/combatlog` - View combat log entries.
- `/catchup` - What happened since your last post.
- `/overview` - Compact summary of all campaigns.
- `/party` - In-fiction party composition (requires character config).
- `/notes` - View GM notes for the current campaign.
- `/activity` - Posting patterns: busiest hours, days, and time blocks.
- `/profile @player` - Cross-campaign stats for any player.
- `/away [duration] [reason]` - Declare an absence (skips warnings/combat pings).
- `/back` - Return from absence.
- `/recap [N]` - Show last N transcript entries (default 10, max 25).
- `/roll <dice> [label]` - Roll dice (e.g. `1d20+5 Stealth`, `4d6kh3`).
- `/quests` - View active and completed quest objectives.
- `/pins` - View bookmarked story moments and clues.
- `/lootlist` - View party loot.
- `/npcs` - View tracked NPCs.
- `/conditions` - View active conditions/buffs/debuffs.
- `/hp` - View enemy HP tracker with visual bars.
- `/clocks` - View progress clocks.
- `/dc <level> [difficulty]` - PF2e DC lookup (e.g. `/dc 5 hard`).
- `/summary` - Campaign summary dashboard with trackers.
- `/showvote` - View current vote/poll.
- `/showtimer` - View active response timer.
- `/boons` - View your POTW boons for this campaign.
- `/boonsall` - View all your boons across campaigns.
- `/chooseboon <N>` - Choose a POTW boon by number.
- `/pick <choice>` - Vote in an active poll.
- `/search <query>` - Search Archives of Nethys (spells, feats, items — no creatures).
- `/reactions` - Reaction stats for the current campaign.
- `/timeline` - Cross-campaign event timeline.
- `/available <days>` - Set your posting days (e.g. `/available mon wed fri`).
- `/available` - Show everyone's availability.
- `/available clear` - Remove your availability.
- `/waiting` - See what the GM owes you (unreplied messages).
- `/session` - Current session number for this campaign.
- `/health` - Campaign health dashboard (color-coded overview of all campaigns).
- `/queuestats` - GM reply stats: cleared today/week, progress bar, avg reply time, peak hours.
- `/registry` - All players who have ever played in this campaign (with permanent IDs).

### GM commands

- `/queue` - Unreplied player messages across all campaigns. Messages clear when you reply to them using Telegram's reply feature. Priority campaigns pinned first. Shows player momentum.
- `/event <text>` - Log a story event to the cross-campaign timeline.
- `/session set <N>` - Set session counter for the current campaign.
- `/setchar @username CharacterName` - Set a player's character name (shown on rosters).

- `/combat [enemies]` - Start combat (e.g. `/combat Ogre, 2 Skeletons`).
- `/next` - Advance to next phase (players→enemies→next round).
- `/round <N> <players|enemies>` - Set specific round and phase.
- `/endcombat` - End combat with log summary.
- `/enemies [list]` - View or set enemy roster.
- `/clog <event>` - Add combat log entry.
- `/pause [reason]` - Pause inactivity tracking (for breaks, holidays, between arcs).
- `/resume` - Resume inactivity tracking.
- `/markdone [N|msg_id|url|all]` - Manually clear queue entries. Accepts queue position, message ID, full t.me link, or "all".
- `/kick @player` - Remove a player from tracking.
- `/addplayer @user Name` - Pre-register a player before they post.
- `/scene <n>` - Mark a scene boundary in the transcript.
- `/note <text>` - Add a persistent GM note (max 20 per campaign).
- `/delnote <N>` - Delete a GM note by number.
- `/quest <text>` - Add an active quest/objective.
- `/done <N>` - Mark quest N as completed.
- `/delquest <N>` - Delete quest N.
- `/pin <text>` - Bookmark a story moment or key info.
- `/delpin <N>` - Delete a pin.
- `/loot <item>` - Add item to party loot tracker.
- `/delloot <N>` - Remove item from loot.
- `/npc <n> — <desc>` - Add NPC to tracker.
- `/delnpc <N>` - Remove NPC.
- `/condition <target> — <effect> [| duration]` - Track a condition.
- `/endcondition <N>` - Remove a condition.
- `/clearconditions` - Clear all conditions.
- `/hp set <n> <cur>/<max>` - Track enemy HP.
- `/hp d <n> <amount>` - Deal damage.
- `/hp h <n> <amount>` - Heal.
- `/hp remove <n>` - Remove HP entry.
- `/hp clear` - Clear all HP entries.
- `/clock <n> <segments>` - Create a progress clock.
- `/tick <n> [N]` - Advance a clock.
- `/untick <n> [N]` - Reverse a clock.
- `/delclock <n>` - Delete a clock.
- `/vote <question> | <opt1> | <opt2> [| ...]` - Start a vote/poll.
- `/endvote` - End a vote and show results.
- `/timer <duration> [reason]` - Set a response timer (e.g. `/timer 2h Post your actions`).
- `/canceltimer` - Cancel active timer.
- `/gm` - GM dashboard: all campaigns at a glance.

