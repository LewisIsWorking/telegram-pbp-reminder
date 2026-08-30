"""A campaign with no posts at all is the most silent one, not a skip.

Lewis, 2026-08-30, on C10 The Junction: *"But it doesn't do the 'all
caught up' and such messages, etc"*.

C10 was configured on 2026-08-13 and named in none of the GM queue's
sections until an empty GM post landed on 2026-08-30 12:07. The cause was
one line in ``queue_silence._idle_campaigns``:

```python
if last_dt is None:
    continue  # never posted / untracked — neither silent nor caught up
```

⛔ The docstring on ``caught_up_campaigns`` promised the opposite:
*"Ensures every configured campaign is represented somewhere in the queue
rather than vanishing"*. A docblock can state a rule the predicate does
not enforce; fourth occurrence in this repo.

Replayed against the real 2026-08-30 state with ``topics["146645"]``
removed, the consumers reported:

```
idle pids:  ['25059', '40585']
oldest:     C06: Kibwe — quiet for 1d 3h      <-- C10 had NEVER posted
```

The fix ranks a never-posted campaign first by giving it ``days = inf``,
so every existing ``>= threshold`` comparison and every ``sort`` places it
correctly with no special case to forget.

What the fix must NOT have changed lives in
``test_never_posted_blast_radius``.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _test_never_posted_helpers import NEVER, NEW, NOW, OLD, config, state
from scheduled.queue_silence import (campaign_age_lines, caught_up_campaigns,
                                     oldest_campaign_line, silent_campaigns)


class TestItIsListedAtAll:
    """The bug: absent from every section while it had no posts."""

    def test_silent_section_names_it(self):
        lines = silent_campaigns(config(NEW), NEVER, {}, NOW)
        assert any("C10: The Junction" in line for line in lines), lines

    def test_the_line_says_no_posts_yet(self):
        # Not "no posts for " with an empty age. `age` is "" for these
        # rows because age_str would OverflowError on inf, so a caller
        # formatting `age` directly renders a dangling phrase.
        line = silent_campaigns(config(NEW), NEVER, {}, NOW)[0]
        assert line.endswith("https://t.me/Path_Wars/146645")
        assert "— no posts yet 🔗" in line
        assert "no posts for " not in line
        # ☠️ is entry_age_icon's oldest bucket. It falls out of passing
        # inf, which every comparison in that function fails without
        # converting the float, so the icon needs no special case either.
        assert line.startswith("  ☠️ 🚦 C10")

    def test_age_lines_name_it(self):
        # campaign_age_lines feeds the "All caught up!" post, which is
        # the message Lewis was actually looking at.
        lines = campaign_age_lines(config(NEW, OLD),
                                   state(**{"40585": 1}), {}, NOW)
        assert any("C10" in line for line in lines), lines

    def test_an_unparseable_timestamp_reads_as_never_posted(self):
        """⛔ REVERSED 2026-08-30, moved from test_branch_gaps_11.

        It asserted ``== []``. Deliberately the same wording as a
        genuinely new campaign: the alternative was a fourth state for a
        corruption that should never occur, and surfacing it as
        maximally stale gets it looked at, where a skip hid it entirely.
        """
        bad = {"topics": {"146645": {"last_message_time": "not-a-date"}}}
        lines = silent_campaigns(config(NEW), bad, {}, NOW)
        assert len(lines) == 1 and "no posts yet" in lines[0]

    def test_it_is_not_filed_under_caught_up(self):
        # can-fail counterpart to the first test: a fix that simply put
        # every skipped campaign into both sections would pass that one.
        # Nothing about a campaign with no posts is caught up.
        assert caught_up_campaigns(config(NEW), NEVER, {}, NOW) == []


class TestItOutranksEveryPostedCampaign:
    def test_the_oldest_callout_names_it_over_a_quiet_campaign(self):
        # ⭐⭐ The measured failure. Before the fix this said Kibwe.
        line = oldest_campaign_line(config(NEW, OLD),
                                    state(**{"40585": 1}), {}, NOW)
        assert "C10: The Junction" in line
        assert "no posts yet" in line

    def test_it_outranks_even_a_long_dead_campaign(self):
        # inf beats 200d. A "rank it first" fix using a large constant
        # would eventually lose to a real age; this pins that it cannot.
        line = oldest_campaign_line(config(NEW, OLD),
                                    state(**{"40585": 200}), {}, NOW)
        assert "C10: The Junction" in line

    def test_it_sorts_first_in_the_silent_section(self):
        lines = silent_campaigns(config(OLD, NEW),
                                 state(**{"40585": 200}), {}, NOW)
        assert len(lines) == 2
        assert "C10" in lines[0] and "C06" in lines[1]

    def test_a_posted_campaign_still_wins_when_none_are_new(self):
        # can-fail counterpart: proves the callout is not hardcoded to
        # whichever campaign happens to be listed first.
        line = oldest_campaign_line(config(NEW, OLD),
                                    state(**{"146645": 2, "40585": 30}),
                                    {}, NOW)
        assert "C06: Kibwe" in line and "no posts for 30d" in line
