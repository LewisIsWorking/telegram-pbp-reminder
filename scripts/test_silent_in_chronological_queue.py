"""Silent campaigns sit in the GM queue body, ranked by age (2026-11-19).

Lewis: silent campaigns should be in the chronological queue, with equal
priority to campaigns waiting for a reply. Before this they had their own
"💤 Silent campaigns" section under the body, outside the age order.

A silent campaign's age is the time since its last post; a waiting
campaign's is the time its oldest unreplied post has waited. Priority rank
still comes first for both.
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

NOW = datetime(2026, 11, 19, 10, 0, tzinfo=timezone.utc)
FAST, SLOW, QUIET, PRIO = "100", "200", "300", "400"


def _pair(pid, code, name, **extra):
    return {"pbp_topic_ids": [int(pid)], "code": code, "name": name, **extra}


def _config(*, quiet_rank=None, prio_rank=None):
    quiet = {"queue_priority": quiet_rank} if quiet_rank is not None else {}
    prio = {"queue_priority": prio_rank} if prio_rank is not None else {}
    return {"group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
            "queue_daily_hours": [NOW.hour],
            "topic_pairs": [_pair(FAST, "C01", "Fast"),
                            _pair(SLOW, "C02", "Slow"),
                            _pair(QUIET, "C03", "Quiet", **quiet),
                            _pair(PRIO, "C04", "Prio", **prio)]}


def _entry(hours_ago, mid):
    return {"name": "P", "preview": "hi", "link": "", "message_id": mid,
            "time": (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S")}


def _scanned(fast_h=2 * 24, slow_h=8 * 24, prio_h=None):
    out = {FAST: {"campaign": "Fast", "code": "C01", "entries": [_entry(fast_h, "11")]},
           SLOW: {"campaign": "Slow", "code": "C02", "entries": [_entry(slow_h, "22")]}}
    if prio_h is not None:
        out[PRIO] = {"campaign": "Prio", "code": "C04", "entries": [_entry(prio_h, "44")]}
    return out


def _state(quiet_days=6, prio_days=None):
    topics = {}
    if quiet_days is not None:
        topics[QUIET] = {"last_message_time": (NOW - timedelta(days=quiet_days)).isoformat()}
    for pid in (FAST, SLOW):
        topics[pid] = {"last_message_time": (NOW - timedelta(hours=1)).isoformat()}
    topics[PRIO] = {"last_message_time": (NOW - timedelta(
        days=prio_days if prio_days is not None else 0, hours=1)).isoformat()}
    return {"last_queue_fingerprint": "OLD", "queue_post_count": 0,
            "last_queue_pin_id": None, "last_queue_daily_slots": [],
            "topics": topics}


def _post(config, scanned, state):
    from scheduled.queue_reminder import post_queue_reminder
    sent = []
    with patch("scheduled.queue_reminder.scan_transcripts", return_value=scanned), \
         patch("scheduled.queue_reminder.post_topic_queues"), \
         patch("scheduled.queue_reminder.tg.send_message_id",
               side_effect=lambda gid, tid, text: sent.append(text) or 42), \
         patch("scheduled.queue_reminder.tg.pin_message"), \
         patch("scheduled.queue_reminder.tg.unpin_message"):
        post_queue_reminder(config, state, now=NOW)
    return "\n".join(sent)


def _section_order(text, *labels):
    return sorted(labels, key=lambda lab: text.index(f"{lab} ("))


class TestTheBodyOrder:
    def test_a_silent_campaign_takes_its_place_by_age(self):
        # Slow waited 8d, Quiet silent 6d, Fast waited 2d.
        text = _post(_config(), _scanned(), _state(quiet_days=6))
        assert _section_order(text, "C01: Fast", "C02: Slow", "C03: Quiet") == [
            "C02: Slow", "C03: Quiet", "C01: Fast"]

    def test_the_separate_silent_section_is_gone_and_nothing_is_listed_twice(self):
        text = _post(_config(), _scanned(), _state(quiet_days=6))
        assert "Silent campaigns" not in text
        assert text.count("C03: Quiet") == 1
        assert "no posts for 6d" in text

    def test_a_silent_section_takes_no_markdone_number(self):
        # Numbering runs 01, 02 across the body; the silent section sits
        # between them without consuming a number.
        text = _post(_config(), _scanned(), _state(quiet_days=6))
        assert "01 [22]" in text and "02 [11]" in text
        assert text.index("01 [22]") < text.index("C03: Quiet") < text.index("02 [11]")

    def test_a_prioritised_waiting_campaign_still_jumps_an_older_silent_one(self):
        text = _post(_config(prio_rank=1), _scanned(prio_h=3), _state(quiet_days=20))
        assert _section_order(text, "C04: Prio", "C03: Quiet")[0] == "C04: Prio"

    def test_a_prioritised_silent_campaign_jumps_the_age_queue(self):
        text = _post(_config(quiet_rank=1), _scanned(), _state(quiet_days=6))
        assert _section_order(text, "C01: Fast", "C02: Slow", "C03: Quiet")[0] == "C03: Quiet"
        assert "📌 💤" in text

    def test_a_never_posted_campaign_goes_last_in_its_tier(self):
        text = _post(_config(), _scanned(), _state(quiet_days=None))
        assert _section_order(text, "C01: Fast", "C02: Slow", "C03: Quiet")[-1] == "C03: Quiet"
        assert "no posts yet" in text

    def test_a_queue_with_only_a_silent_campaign_lists_it_in_the_body(self):
        text = _post(_config(), {}, _state(quiet_days=6))
        assert "💤" in text and "C03: Quiet (silent)" in text


class TestTheFocusPick:
    def _msg(self, config, scanned, state):
        from commands.queue_format import build_priority_map
        from scheduled.queue_focus import build_focus_message
        return build_focus_message(config, scanned, build_priority_map(config),
                                   NOW, state=state)

    def test_a_silent_campaign_older_than_every_reply_is_next(self):
        msg = self._msg(_config(), _scanned(slow_h=5 * 24), _state(quiet_days=6))
        assert "Post here next" in msg and "C03: Quiet" in msg

    def test_an_older_reply_beats_a_younger_silent_campaign(self):
        msg = self._msg(_config(), _scanned(), _state(quiet_days=6))
        assert "Reply to this next" in msg and "Slow" in msg

    def test_a_prioritised_silent_campaign_beats_an_older_unprioritised_reply(self):
        msg = self._msg(_config(quiet_rank=4), _scanned(slow_h=20 * 24), _state(quiet_days=6))
        assert "Post here next" in msg and "C03: Quiet" in msg
        assert "📌 Prioritised campaign" in msg
        assert "longer than the oldest reply" not in msg

    def test_an_owed_reply_in_a_higher_ranked_campaign_still_wins(self):
        msg = self._msg(_config(quiet_rank=4, prio_rank=1), _scanned(prio_h=1),
                        _state(quiet_days=30))
        assert "Reply to this next" in msg and "Prio" in msg

    def test_a_higher_ranked_silent_campaign_beats_a_lower_ranked_owed_reply(self):
        msg = self._msg(_config(quiet_rank=1, prio_rank=4), _scanned(prio_h=1),
                        _state(quiet_days=6))
        assert "Post here next" in msg and "C03: Quiet" in msg

    def test_a_prioritised_caught_up_campaign_does_not_jump(self):
        # Quiet 2 days is caught up, not silent: no rank, so the 8d reply wins.
        msg = self._msg(_config(quiet_rank=1), _scanned(), _state(quiet_days=2))
        assert "Reply to this next" in msg and "Slow" in msg
