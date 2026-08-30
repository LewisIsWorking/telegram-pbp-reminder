"""Whether a campaign warns its quiet players, sweeps them, or neither.

Lewis, 2026-08-30, looking at five C08 Theria seats silent 110 to 176
days: *"Well if people have been gone from 08 for 100 days, they should
have been kicked as players."*

They should have been. The reason they were not is that one flag named
``warnings`` was gating two different things:

* the 1, 2 and 3 week nudges, which are **messages to a player**;
* the 4 week removal, which is **roster hygiene** and sends only a note
  saying the seat is no longer tracked.

C08 had ``warnings`` in ``disabled_features`` because it is another GM's
table and the bot should not nag their players. That silently also
switched off the sweep, so the campaign accumulated five dead seats and
read one to five players larger than it was everywhere the roster is
counted.

⛔ The comment on the removal block still says *"ALWAYS fires, even when
GM is bottleneck"*, and it was true of the one condition it was written
about and false of the function as a whole. A docblock can state a rule
the predicate does not enforce, which is the third time that shape has
turned up in this repo.

Two names, two behaviours
-------------------------
``warnings`` now means only "message the player", and ``removals`` means
"sweep the seat". A campaign can have either, both or neither, and the
common case for somebody else's table is exactly the mixed one: do not
nag my players, do keep my roster honest.

``paused_campaigns`` remains the way to stop **both** at once, which is
what a table on a deliberate hiatus wants.
"""

import helpers


def sweep_and_warn(config: dict, state: dict, pbp_topic_id) -> tuple:
    """``(may_remove, may_warn)`` for one campaign.

    A paused campaign gets neither. Pausing is a statement about the
    table rather than about the bot's manners, so it outranks both
    feature flags rather than sitting beside them.
    """
    if pbp_topic_id in state.get("paused_campaigns", {}):
        return False, False
    return (helpers.feature_enabled(config, pbp_topic_id, "removals"),
            helpers.feature_enabled(config, pbp_topic_id, "warnings"))
