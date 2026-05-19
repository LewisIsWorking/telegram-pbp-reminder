"""Per-topic "All caught up!" message builder.

The per-topic pinned queue lifecycle (managed by
``scheduled/topic_queue_poster.py``) emits a caught-up message when
the thread transitions from "unreplied" to "everyone replied."

Format (Lewis 2026-05-19, Option A — full pings):
    📋 All caught up. Time for players to post!
    @user1 @user2 @user3 ...

Active roster = ``commands.roster._active_players(pid, state, config)``
which returns non-perm-recent + perm players (everyone counted on
the campaign's roster). All of them get @-mentioned so the message
fires notifications on every transition. The notification cost is
intentional per Lewis's call: the bot's purpose is GM accountability
AND nudging players to post when the queue clears, so a full ping
on the transition is the design.

Edge cases:
  * No active roster (state=None or 0 active) → returns
    ``📋 All caught up here.`` (drop tag line and nudge text).
  * Player without ``username`` → ``helpers.player_mention`` returns a
    first-name fallback; that won't ping but still appears in the
    line so the GM can see who'd been intended.

Why this lives in its own file: ``topic_queue_poster.py`` sits at
or near the 200-line cap. Keeping the caught-up builder separate
preserves room there and follows L25/L26's pattern of extracting
single-purpose helpers into sibling modules.

See L27 in ``docs/dev/REFACTOR_PROGRESS.md`` for the broader
feedback-driven UX-trim rationale.
"""

import helpers


_BARE_CAUGHT_UP = "📋 All caught up here."
_NUDGE_HEADER = "📋 All caught up. Time for players to post!"


def build_caught_up_text(pid: str, state: dict | None,
                         config: dict) -> str:
    """Return the per-topic caught-up message text.

    When ``state`` is None or the campaign has no active players,
    falls back to the bare "📋 All caught up here." form
    (no tag line, no nudge — nobody to nudge). When the active
    roster is non-empty, every player gets an @-mention so the
    transition fires notifications.

    The active roster is computed via the same helper that builds
    ``/roster``: ``commands.roster._active_players``, which folds in
    non-perm-recent posters AND every permanent player (per-record
    or config-listed). One source of truth.
    """
    if state is None:
        return _BARE_CAUGHT_UP
    # Lazy import to avoid commands/roster pulling in this module's
    # parent package at import time (the modules don't depend on each
    # other functionally, only at call time).
    from commands.roster import _active_players

    active = _active_players(pid, state, config)
    if not active:
        return _BARE_CAUGHT_UP
    mentions = " ".join(helpers.player_mention(p) for p in active)
    return f"{_NUDGE_HEADER}\n{mentions}"