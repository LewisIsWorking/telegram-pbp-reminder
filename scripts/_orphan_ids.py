"""Message IDs the bot orphaned, and why each batch exists.

Extracted from ``test_no_delete_attempted_past_the_wall.py`` on
2026-09-01, which reached 219 lines. Leading underscore so pytest does
not collect it, following ``_test_state_isolation``.

⚠️ These sets may SHRINK as the bounded audit log rotates past them.
They must never GROW without a dated batch and a stated cause: a new ID
means the bot has stranded another message in the group, permanently,
and that is the regression the guard exists to catch.
"""

# The 15 messages already stranded when the guard was written. Still in
# the Path Wars group; only a human can remove them, and the audit log
# will keep reporting them until it rotates past them.
PRE_FIX = {
    167205, 167207, 167324, 167366, 167442, 168070, 168444,
    169729, 170029, 170106, 170125, 170258, 170305, 170414, 171640,
}

# ⛔ STRANDED BY THE 2026-08-31 OUTAGE. Recorded 2026-09-01.
#
# A separate set rather than merged into PRE_FIX, because that one means
# "already broken when the guard was written" and these mean something
# different: **the guard was working and the code was correct.** The bot
# simply did not run for 15 hours.
#
# A cron/condition mismatch made GitHub mark every scheduled run
# `skipped`. ``sweep_aged_caught_up`` deletes a tracked message before
# Telegram's 48h wall, but it can only do that from inside a run. These
# three were **57.5h old** by the time anything executed again.
#
# ⚠️ THE GENERAL LESSON, which no code change removes: **any outage
# longer than (48h - 36h) = 12h strands whatever the bot was holding.**
# A message ID is a perishable asset with a hard expiry, so uptime here
# is not a nice-to-have, it is a correctness requirement. That is the
# strongest argument for `.github/workflows/watchdog.yml`.
OUTAGE_2026_08_31 = {175996, 175998, 176000}

ALL = PRE_FIX | OUTAGE_2026_08_31
