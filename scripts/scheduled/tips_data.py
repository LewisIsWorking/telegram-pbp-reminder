"""Daily tip messages for PBP bot features."""

_TIPS = [
    "💡 <b>/mystats</b> — Check your personal stats in any PBP topic. "
    "See your total posts, sessions, average gap, weekly activity, and current posting streak.",

    "💡 <b>/whosturn</b> — During combat, see who has acted and who the party is waiting on. "
    "Works for any player, not just the GM.",

    "💡 <b>/campaign</b> — Get a full scoreboard for the current campaign: "
    "party roster, weekly pace with trends, at-risk players, and combat state. All in one message.",

    "💡 <b>/status</b> — Quick health check: party size, last post time, "
    "posts this week, and any at-risk players. Faster than /campaign when you just need the headlines.",

    "💡 <b>/help</b> — Forgot a command? Type /help to see the full list of bot features and GM commands.",

    "💡 <b>Player of the Week</b> — Every week, the bot picks the most consistent poster "
    "(lowest average gap between posts, not just highest count). The winner picks a flavour boon!",

    "💡 <b>Inactivity warnings</b> — The bot notices if you go quiet. "
    "Week 1: friendly nudge. Week 2: concerned check-in. Week 3: urgent. Week 4: removed from roster. "
    "Just post to reset the timer!",

    "💡 <b>Combat tracking</b> — Type <code>/combat Ogre, 2 Skeletons</code> to start. "
    "The bot tracks who posts their actions. When everyone's done, the GM gets auto-pinged! "
    "Use /whosturn to see who's still needed.",

    "💡 <b>/next</b> — Advance combat phases: players → enemies → next round. "
    "No more typing <code>/round 2 players</code> — just /next! "
    "Use <code>/clog The ogre crits Cardigan!</code> to log key moments, "
    "and /endcombat for a summary.",

    "💡 <b>Roster reports</b> — Every few days the bot posts a roster showing everyone's "
    "post count, sessions, weekly activity, average gap, and last post time. "
    "It's the campaign's health dashboard.",

    "💡 <b>Pace reports</b> — Weekly comparison of this week vs last week: "
    "total posts, GM vs player split, posts per day, and trend arrows. "
    "See if your campaign is speeding up or slowing down.",

    "💡 <b>Posting streaks</b> — Post on consecutive days to build a streak. "
    "Check yours with /mystats. The longer the streak, the bigger the 🔥!",

    "💡 <b>/myhistory</b> — See a visual sparkline of your posting activity over the last 8 weeks. "
    "Track your peak weeks and whether you're trending up or down.",

    "💡 <b>/pause</b> and <b>/resume</b> (GM only) — Going on holiday or taking a break between arcs? "
    "Type <code>/pause on holiday</code> to stop inactivity warnings. <code>/resume</code> to restart.",

    "💡 <b>/kick</b> (GM only) — Need to remove a player from tracking? "
    "Type <code>/kick @username</code> or <code>/kick PlayerName</code>. "
    "They can rejoin by posting in PBP again.",

    "💡 <b>/addplayer</b> (GM only) — Want someone on the roster before they've posted? "
    "Type <code>/addplayer @username Player Name</code> to pre-register them.",

    "💡 <b>/catchup</b> — Been away? Type <code>/catchup</code> to see what happened "
    "since your last post — who posted, how many messages, and a preview of recent posts "
    "so you can jump back in without scrolling.",

    "💡 <b>Message milestones</b> — The bot celebrates every 500th PBP message in each campaign, "
    "and every 5,000th message across all campaigns combined. Keep posting!",

    "💡 <b>/party</b> — See the in-fiction party composition: character names, "
    "who plays them, and when they were last active. Requires character config.",

    "💡 <b>Smart alerts</b> — The bot watches for campaigns that lose momentum. "
    "If weekly posts drop by 40%+, or if everyone goes silent for 2+ days, "
    "you'll get a gentle heads-up. Use /pause to silence during planned breaks.",

    "💡 <b>/overview</b> — See a compact summary of ALL campaigns at once: "
    "health status, weekly posts, player count, and last post time. "
    "Perfect for GMs juggling multiple games.",

    "💡 <b>/scene</b> (GM only) — Mark a scene boundary in the transcript. "
    "Type <code>/scene The Docks at Midnight</code> and it'll appear as a divider "
    "in the archived logs. Keeps your campaign history organised by narrative beats.",

    "💡 <b>/note</b> (GM only) — Keep persistent notes for any campaign. "
    "Type <code>/note Party agreed to meet the informant at dawn</code>. "
    "View with /notes, delete with /delnote. Notes also appear in /campaign output.",

    "💡 <b>/activity</b> — See when your campaign is most active: busiest days, "
    "peak hours, and time blocks. Great for knowing when to expect replies "
    "and when to post for maximum engagement.",

    "💡 <b>/profile</b> — Look up any player across all campaigns. "
    "Type <code>/profile @alice</code> to see their character, post counts, "
    "streaks, and last activity in every game they're in.",

    "💡 <b>Word Count Tracking</b> — The bot now tracks total words written per player. "
    "Check /mystats to see your word count and average words per post. "
    "Quality and quantity both matter in PBP!",

    "💡 <b>/away</b> — Going on holiday? Type <code>/away 5 days vacation</code> "
    "and the bot will skip you for inactivity warnings and combat pings. "
    "Use /back when you return, or the bot clears it automatically when you post.",

    "💡 <b>/recap</b> — Read back the story! <code>/recap</code> shows the last 10 posts "
    "with character names, GM tags 🎲, scene markers, and time gaps so you can feel the "
    "rhythm of the conversation. Use <code>/recap 20</code> for more.",

    "💡 <b>/roll</b> — Roll dice right in chat! "
    "<code>/roll 1d20+5 Stealth</code> for a skill check, "
    "<code>/roll 2d6+3</code> for damage, or "
    "<code>/roll 4d6kh3</code> to keep the highest 3. "
    "Uses your character name if one is configured.",

    "💡 <b>/quests</b> — Your GM can track active quest objectives with "
    "<code>/quest Find the missing merchant</code>. View them with /quests. "
    "When you complete one, the GM uses /done to check it off. "
    "Never lose track of what you're supposed to be doing!",

    "💡 <b>/gm</b> (GM only) — A compact dashboard showing every campaign's health "
    "at a glance: weekly post count, player count, away/at-risk flags, "
    "active quests, and combat status. One command to check all your games.",

    "💡 <b>/dc</b> — Quick DC lookup for Pathfinder 2e! "
    "<code>/dc 5</code> shows all difficulty DCs for level 5. "
    "<code>/dc 5 hard</code> gives just the hard DC. "
    "<code>/dc trained</code> for proficiency DCs. Never flip through the CRB again.",

    "💡 <b>/pins</b> — The GM can bookmark key story moments with "
    "<code>/pin The party found the dragon's weakness</code>. "
    "View them with /pins. Great for tracking reveals, clues, and plot twists.",

    "💡 <b>/lootlist</b> — Track party loot with "
    "<code>/loot +1 striking longsword</code>. View everything with /lootlist. "
    "Remove claimed items with /delloot. Never forget what you picked up!",

    "💡 <b>/npcs</b> — Can't remember who that merchant was? "
    "GMs can add NPCs with <code>/npc Gorund — Dwarven blacksmith, owes party a favour</code>. "
    "View them all with /npcs. A living dramatis personae for your campaign.",

    "💡 <b>/conditions</b> — Track buffs, debuffs, and persistent effects. "
    "<code>/condition Cardigan — Frightened 2 | until end of next turn</code>. "
    "View active conditions with /conditions, end them with /endcondition, "
    "or /clearconditions to wipe the slate.",

    "💡 <b>/hp</b> — Track enemy HP in combat! "
    "<code>/hp set Ogre 45/45</code> to start, "
    "<code>/hp d Ogre 12</code> to deal damage, "
    "<code>/hp h Ogre 5</code> to heal. "
    "Visual HP bars show who's hurting. /hp clear when combat ends.",

    "💡 <b>/clocks</b> — Progress clocks for investigations, rituals, countdowns. "
    "<code>/clock Investigation 6</code> creates a 6-segment clock. "
    "<code>/tick Investigation</code> fills a segment. "
    "Great for tracking anything that builds over time. ◉◉◉○○○",

    "💡 <b>/vote</b> — Stuck on a group decision? GMs can start a vote: "
    "<code>/vote Where do we go? | North gate | Sewers | Rest first</code>. "
    "Players use /pick N to cast their vote. /endvote closes it and shows the winner.",

    "💡 <b>/timer</b> — Set a response deadline for the party. "
    "<code>/timer 24h Post your combat actions</code>. "
    "The bot will post a notification when time's up. "
    "Check with /showtimer, cancel with /canceltimer.",

    "💡 <b>/summary</b> — Everything at a glance: current scene, combat state, "
    "active quests, conditions, NPCs, loot, and pins. "
    "One command to see the full state of your campaign.",
]
