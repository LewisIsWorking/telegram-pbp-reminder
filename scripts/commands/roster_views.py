"""Multi-campaign roster views for /rostercampaigns and /rosterall.

Two companion commands to /roster (count-only overview) and
/rosterplayers (cross-campaign player table):

* /rostercampaigns \u2014 per-campaign full breakdown for every campaign.
  Equivalent to running /roster <code> for each campaign in turn,
  emitted as one combined message.
* /rosterall \u2014 per-campaign blocks followed by the at-risk and
  recent-history footer from roster_players. The footer surfaces
  the actionable bits (who's at risk, who joined / left) without
  duplicating the per-player table that's already implicit in the
  per-campaign blocks.

Both reuse build_roster_campaign from commands.roster for the
per-campaign blocks, so the X/Y +Z perm format and [perm] tags
flow through automatically.
"""

from datetime import datetime, timezone

from commands.roster import build_roster_campaign
from commands.roster_players import (
    _aggregate_by_user,
    _pid_to_code,
    build_footer,
)


_SEP = "\n\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
_RULE = ("\n\n"
         "\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550"
         "\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550"
         "\n")


def build_roster_campaigns(config: dict, state: dict) -> str:
    """Shape 1: per-campaign full breakdown for every campaign.

    Iterates config['topic_pairs'] in declaration order (no priority
    sort) so output is predictable. Each block uses the same shape
    as /roster <code> via build_roster_campaign, which means the
    X/Y +Z perm header and the [perm] tags in the name lists flow
    through unchanged.
    """
    pairs = list(config.get("topic_pairs", []))
    blocks = [build_roster_campaign(pair, config, state) for pair in pairs]
    title = "\U0001f4cb Full Roster (every campaign)"
    if not blocks:
        return title + "\n\n(no campaigns configured)"
    return title + _SEP + _SEP.join(blocks)


def build_roster_all(config: dict, state: dict) -> str:
    """Shape 3: per-campaign blocks + actionable footer.

    The footer (at-risk players + recent joiners / leavers) is
    appended below the per-campaign blocks via a thick rule. The
    full cross-campaign player table from /rosterplayers is NOT
    re-emitted here \u2014 it's redundant with the per-campaign blocks
    that already list every player by name. Only the actionable
    summary carries over.
    """
    campaigns_block = build_roster_campaigns(config, state)

    # Reuse roster_players' aggregation and footer builder rather
    # than duplicating the at-risk / history logic. _aggregate_by_user
    # returns (by_user, at_risk); we only need at_risk for the footer.
    now = datetime.now(timezone.utc)
    pid_to_code = _pid_to_code(config)
    _by_user, at_risk = _aggregate_by_user(state, pid_to_code, now)
    footer_lines = build_footer(state, pid_to_code, now, at_risk)

    if not footer_lines:
        return campaigns_block
    footer = "\n".join(footer_lines).lstrip("\n")
    return campaigns_block + _RULE + footer
