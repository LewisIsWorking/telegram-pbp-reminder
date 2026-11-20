"""The "Oldest waiting" line counts silent campaigns (Lewis, 2026-11-20: "The Chronological queue should be C05 not
Magni Guard"). C05, silent for 10 days, has waited longer than a C04 post from 2 days ago."""
from datetime import datetime, timedelta, timezone

from scheduled.queue_oldest_waiting import (OLDEST_LABEL, SAME_CAMPAIGN_LINE, oldest_waiting_lines,
                                            pick_oldest_any)
from scheduled.queue_silence_rows import IdleRow

NOW = datetime(2026, 11, 20, 13, 42, tzinfo=timezone.utc)
CONFIG = {"topic_pairs": [{"code": "C04", "emoji": "🔍"}]}


def _scanned(days_ago: float) -> dict:
    t = (NOW - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
    return {"76799": {"code": "C04", "campaign": "Magni Guard",
                      "entries": [{"time": t, "name": "Felix Cited", "link": "https://t.me/Path_Wars/76799/190515"}]}}


def _silent(days: float, ever_posted: bool = True) -> IdleRow:
    return IdleRow(pair={}, pid="51357", days=days, icon="🔭", prefix="", label="C05: Grand Explorers",
                   age="10d 8h", link=" 🔗 https://t.me/Path_Wars/51357", ever_posted=ever_posted)


def test_a_longer_silent_campaign_is_the_oldest_wait():
    lines = oldest_waiting_lines(CONFIG, _scanned(2.6), NOW, silent=[_silent(10.3)])
    assert lines[0] == f"{OLDEST_LABEL} 🔭 C05: Grand Explorers, silent: no posts for 10d 8h"
    assert lines[1] == "🔗 https://t.me/Path_Wars/51357"


def test_an_older_post_still_beats_a_newer_silence():
    lines = oldest_waiting_lines(CONFIG, _scanned(12), NOW, silent=[_silent(10.3)])
    assert lines[0].startswith(f"{OLDEST_LABEL} 🔍 C04: Magni Guard, Felix Cited")


def test_a_never_posted_campaign_never_wins():
    assert pick_oldest_any(_scanned(2.6), [_silent(float("inf"), ever_posted=False)], NOW)[0] == "76799"


def test_only_silence_still_names_it():
    assert pick_oldest_any({}, [_silent(10.3)], NOW)[0] == "51357"


def test_when_the_pick_is_that_silent_campaign_one_line_says_so():
    assert oldest_waiting_lines(CONFIG, _scanned(2.6), NOW, silent=[_silent(10.3)], focus_pid="51357") == [SAME_CAMPAIGN_LINE]
