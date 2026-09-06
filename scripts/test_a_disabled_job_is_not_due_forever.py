"""A job switched off for a campaign must not read as permanently due.

Split from ``test_schedule_post.py`` on 2026-09-06 at 218 lines.
"""

from datetime import datetime, timezone


class TestASwitchedOffCampaignIsNotDueForever:
    """⛔⛔ The post said "Recruitment check - due now (1 of 8 campaigns)"
    every single day from 2026-08-13 to 2026-09-06.

    The Junction has ``disabled_features: ["recruitment"]``, so that job
    never iterates it, so its timestamp never advances, so the earliest
    stamp was permanently in the past. The job itself was running fine
    for all seven campaigns that have it enabled; the POST was wrong,
    which is worse than a broken job because it trains the reader to
    ignore "due now".

    Found on 2026-09-06 by the stale-feature check, which cried wolf
    about the same frozen timestamp the first time it ran. Same shape as
    the removed-campaign trap one level down: not "is this campaign
    still here" but "does this campaign run this job at all".
    """

    def _config(self, disabled):
        junction = {"name": "Junction", "chat_topic_id": 2,
                    "pbp_topic_ids": [146645]}
        if disabled:
            junction["disabled_features"] = ["recruitment"]
        return {"group_id": -100, "gm_user_ids": [1], "topic_pairs": [
            {"name": "Live", "chat_topic_id": 1, "pbp_topic_ids": [51357]},
            junction]}

    _STATE = {"last_recruitment_check": {
        "51357": "2026-09-04T00:00:00+00:00",
        "146645": "2026-08-13T00:00:00+00:00"}}

    def _line(self, disabled):
        from scheduled.schedule_intervals import interval_lines
        now = datetime(2026, 9, 6, 14, 0, tzinfo=timezone.utc)
        rows = [r for r in interval_lines(self._config(disabled), self._STATE, now)
                if "Recruitment" in r]
        assert len(rows) == 1, rows
        return rows[0]

    def test_the_frozen_campaign_does_not_pin_it_to_due_now(self):
        assert "due now" not in self._line(disabled=True), (
            "a campaign with the feature switched off is still counted")

    def test_but_an_ENABLED_campaign_that_is_late_still_shows_due_now(self):
        """⭐⭐ Can-fail counterpart. Identical state and dates; only the
        feature flag differs. Without it the test above would pass on an
        implementation that never says "due now" at all."""
        assert "due now" in self._line(disabled=False)
