"""What the never-posted fix must NOT have changed.

Companion to ``test_never_posted_is_the_silent_one``, which pins the bug
itself. Split from it on 2026-08-30 at the 200-line limit.

Three things were at risk when ``_idle_campaigns`` stopped skipping
untracked campaigns, and only one of them is obvious:

1. **Wording.** Three phrasings existed and two of them nearly got
   merged. The queue sections say "last post 1d ago"; the oldest-campaign
   callout says "quiet for 1d". Routing both through one ``phrase()``
   silently rewrote the callout, which is why ``callout_phrase`` exists.
2. **Repost frequency.** ``silent_campaigns`` feeds the fingerprint that
   decides whether the GM queue reposts. A ticking age there would have
   reposted it hourly, forever.
3. **Exclusions.** ``queue_exclude`` (C08 Theria) and "already in the
   queue body" must still suppress a campaign, including one that has
   never posted.
"""

import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(__file__))

from _test_never_posted_helpers import NEVER, NEW, NOW, OLD, config, state
from scheduled.queue_silence import (campaign_age_lines, caught_up_campaigns,
                                     oldest_campaign_line, silent_campaigns)


class TestTheWordingDidNotDrift:
    """The three phrasings are byte-identical to pre-2026-08-30."""

    def test_silent_reads_no_posts_for(self):
        line = silent_campaigns(config(OLD), state(**{"40585": 12}),
                                {}, NOW)[0]
        assert "— no posts for 12d 🔗" in line

    def test_caught_up_reads_last_post_ago(self):
        line = caught_up_campaigns(config(OLD), state(**{"40585": 1}),
                                   {}, NOW)[0]
        assert "— last post 1d ago 🔗" in line

    def test_the_callout_reads_quiet_for(self):
        # ⚠️ The callout says "quiet for", the section says "last post X
        # ago". One shared phrase() would have rewritten this line.
        line = oldest_campaign_line(config(OLD), state(**{"40585": 1}),
                                    {}, NOW)
        assert "— quiet for 1d." in line


class TestItDoesNotRepostForever:
    """⭐⭐ The reason the never-posted line carries no age.

    ``queue_reminder`` folds ``silent_campaigns`` into the fingerprint it
    compares against ``state["last_queue_fingerprint"]`` to decide
    whether anything changed. Ages tick, which is why the caught-up
    section is deliberately kept OUT of that fingerprint.

    'no posts yet' is constant, so a never-posted campaign is stable
    across runs. Had it rendered an age, adding C10 would have made the
    GM queue repost itself every hour, forever. That is the kind of
    consequence a correct-looking fix ships with and nobody measures.
    """

    def test_the_line_is_identical_an_hour_later(self):
        assert (silent_campaigns(config(NEW), NEVER, {}, NOW) ==
                silent_campaigns(config(NEW), NEVER, {},
                                 NOW + timedelta(hours=1)))

    def test_it_is_still_identical_a_year_later(self):
        assert (silent_campaigns(config(NEW), NEVER, {}, NOW) ==
                silent_campaigns(config(NEW), NEVER, {},
                                 NOW + timedelta(days=365)))

    def test_a_posted_campaign_line_DOES_move(self):
        # can-fail counterpart: proves the two above test stability, not
        # a renderer that ignores `now` entirely.
        assert (silent_campaigns(config(OLD), state(**{"40585": 12}), {}, NOW) !=
                silent_campaigns(config(OLD), state(**{"40585": 12}), {},
                                 NOW + timedelta(days=1)))


class TestWhatIsStillExcluded:
    def test_queue_exclude_still_hides_a_campaign(self):
        # ⭐ C08 Theria carries queue_exclude. The fix must not have
        # turned "excluded" into "listed as never posted".
        pair = dict(NEW, queue_exclude=True)
        assert silent_campaigns(config(pair), NEVER, {}, NOW) == []
        assert campaign_age_lines(config(pair), NEVER, {}, NOW) == []
        assert oldest_campaign_line(config(pair), NEVER, {}, NOW) is None

    def test_a_campaign_with_unreplied_entries_stays_in_the_body(self):
        # Entries mean it is shown in the queue body, so it must not be
        # duplicated into a section, whether or not it has any posts.
        scanned = {"146645": {"campaign": "The Junction", "code": "C10",
                              "entries": [{"time": "2026-08-30 11:00:00"}]}}
        assert silent_campaigns(config(NEW), NEVER, scanned, NOW) == []
