"""👀 on unreplied posts, ✍ once replied (scheduled/queue_reactions.py, 2026-11-23)."""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from scheduled.queue_reactions import (EYES, MAX_CALLS, MAX_FAILS, STATE_KEY,  # noqa: E402
                                       WRITING, sync_queue_reactions)

NOW = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)
GROUP = -100123
CONFIG = {"group_id": GROUP, "topic_pairs": [{"code": "C04", "pbp_topic_ids": [76799]}]}


def _scanned(*mids):
    return {"76799": {"entries": [{"message_id": str(m)} for m in mids]}} if mids else {}


class _Fake:
    def __init__(self, ok=True):
        self.calls, self.ok = [], ok

    def __call__(self, chat, mid, emoji):
        self.calls.append((chat, mid, emoji))
        return self.ok


def _sync(state, scanned, fake, replied=()):
    return sync_queue_reactions(CONFIG, state, scanned, NOW, react=fake,
                                replied=lambda pid: set(replied), pause=0)


def test_unreplied_gets_eyes_then_replied_gets_writing_hand():
    state, fake = {}, _Fake()
    _sync(state, _scanned(190527), fake)
    assert fake.calls == [(GROUP, 190527, EYES)]
    _sync(state, _scanned(), fake, replied={"msg:190527"})
    assert fake.calls[-1] == (GROUP, 190527, WRITING)
    assert state[STATE_KEY][f"{GROUP}:190527"]["emoji"] == WRITING


def test_no_api_call_when_state_already_matches():
    state, fake = {}, _Fake()
    _sync(state, _scanned(1, 2), fake)
    _sync(state, _scanned(1, 2), fake)
    assert len(fake.calls) == 2


def test_a_post_that_leaves_without_a_reply_loses_its_eyes():
    state, fake = {}, _Fake()
    _sync(state, _scanned(5), fake)
    _sync(state, _scanned(), fake)
    assert fake.calls[-1] == (GROUP, 5, "")
    assert f"{GROUP}:5" not in state[STATE_KEY]


def test_backfill_is_capped_per_run_oldest_first():
    state, fake = {}, _Fake()
    _sync(state, _scanned(*range(100, 100 + MAX_CALLS + 5)), fake)
    assert len(fake.calls) == MAX_CALLS
    assert fake.calls[0][1] == 100


def test_failures_stop_after_max_and_stay_remembered():
    state, fake = {}, _Fake(ok=False)
    for _ in range(MAX_FAILS + 2):
        _sync(state, _scanned(9), fake)
    assert len(fake.calls) == MAX_FAILS


def test_off_switch():
    state, fake = {}, _Fake()
    sync_queue_reactions({**CONFIG, "queue_reactions_enabled": False}, state,
                         _scanned(1), NOW, react=fake, pause=0)
    assert fake.calls == []


def test_the_bots_own_reaction_is_not_counted_as_engagement():
    from commands.reactions import process_reaction

    class Maps:
        all_pbp_ids = {"76799"}
        to_canonical = {"76799": "76799"}

    update = {"message_reaction": {
        "chat": {"id": GROUP}, "message_id": 1, "message_thread_id": 76799,
        "user": {"id": 42, "is_bot": True, "first_name": "Nudge"},
        "old_reaction": [], "new_reaction": [{"type": "emoji", "emoji": EYES}]}}
    state = {}
    process_reaction(update, CONFIG, state, Maps())
    assert state.get("reactions", {}) == {}
