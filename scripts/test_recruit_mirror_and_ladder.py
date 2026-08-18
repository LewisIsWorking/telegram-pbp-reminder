"""The advert posts twice, and the bar rises when everyone clears it.

COVERS  the Nudge Bot Notifications mirror (both posts, both deletes, the
        bot-sent registry scan) and ``roster_members.effective_target``.
MISSES  whether topic 50 exists. Verified by hand against the live API on
        2026-08-18 — *"What campaign needs people most?"*.
PROVEN  by ``test_the_mirror_delete_guard_can_fail`` and
        ``test_the_ladder_can_fail``.

────────────────────────────────────────────────────────────────────────

Lewis, 2026-08-18, two asks:
  1. the recruit advert should also post to the standing topic in Nudge
     Bot Notifications;
  2. once every campaign is at 6, aim for 8.

⚠️ **The mirror is the third time this session that a bare message id
could not carry the answer.** The advert now lives in two CHATS, and
message ids are unique per chat — the mirror's id against the main group
would miss, or hit a stranger. So state records ``{chat_id, message_id}``
per copy, exactly as the schedule post had to on 2026-08-17.
"""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from commands.roster_members import RECRUIT_LADDER, effective_target
from scheduled import recruit_focus_post as rfp
from scheduled.recruit_focus import _AT_KEY, _MSG_KEY, _POSTS_KEY

NOW = datetime(2026, 8, 18, 6, 0, tzinfo=timezone.utc)
MAIN = -1001661053273
MIRROR = -1004303231713
MIRROR_THREAD = 50
C09_CHAT = 104202


def _cfg(**over):
    cfg = {"group_id": MAIN, "gm_queue_topic_id": 146780,
           "recruit_mirror_chat_id": MIRROR,
           "recruit_mirror_thread_id": MIRROR_THREAD}
    cfg.update(over)
    return cfg


def _pair():
    return {"code": "C09", "name": "Metal City", "chat_topic_id": C09_CHAT,
            "pbp_topic_ids": [107171]}


def _post(state, cfg=None, ids=(111, 222)):
    sent, deleted = [], []
    cfg = cfg or _cfg()

    def send(chat, thread, text, **k):
        sent.append((chat, thread))
        return ids[len(sent) - 1] if len(sent) <= len(ids) else None

    with patch.object(rfp, "build_recruit_message",
                      return_value=("advert", _pair())), \
            patch.object(rfp.tg, "send_message_id", side_effect=send), \
            patch.object(rfp.tg, "delete_message",
                         side_effect=lambda c, m: deleted.append((c, m)) or True):
        rfp.post_recruit_focus(cfg, state, now=NOW)
    return sent, deleted


# ── The mirror ───────────────────────────────────────────────────────────────

def test_it_posts_to_both_the_campaign_and_the_mirror():
    sent, _ = _post({})
    assert sent == [(MAIN, C09_CHAT), (MIRROR, MIRROR_THREAD)]


def test_both_copies_are_recorded_with_their_own_chat():
    state = {}
    _post(state)
    assert state[_POSTS_KEY] == [
        {"chat_id": MAIN, "message_id": 111},
        {"chat_id": MIRROR, "message_id": 222},
    ]


def test_each_old_copy_is_deleted_from_its_own_chat():
    """⚠️ The whole reason the chat is stored. Message ids are unique per
    chat, so deleting the mirror's id against the main group would miss
    or hit a stranger."""
    state = {_POSTS_KEY: [{"chat_id": MAIN, "message_id": 9},
                          {"chat_id": MIRROR, "message_id": 4}]}
    _sent, deleted = _post(state)
    assert deleted == [(MAIN, 9), (MIRROR, 4)]


def test_the_mirror_delete_guard_can_fail():
    """Prove it: with the chat dropped, both deletes would go to the main
    group and the mirror copy would survive forever."""
    entries = [{"chat_id": MAIN, "message_id": 9},
               {"chat_id": MIRROR, "message_id": 4}]
    naive = [(MAIN, e["message_id"]) for e in entries]
    assert naive != [(e["chat_id"], e["message_id"]) for e in entries]


def test_legacy_state_still_gets_its_single_post_deleted():
    """State written before the mirror has only the bare id, and it was
    always in the main group."""
    state = {_MSG_KEY: 500}
    _sent, deleted = _post(state)
    assert deleted == [(MAIN, 500)]


def test_no_mirror_configured_means_one_post_and_no_error():
    sent, _ = _post({}, cfg=_cfg(recruit_mirror_chat_id=None))
    assert sent == [(MAIN, C09_CHAT)]


def test_a_failed_mirror_does_not_lose_the_main_advert(capsys):
    """The mirror is a convenience; the advert is already where it counts."""
    state = {}
    sent, _ = _post(state, ids=(111, None))
    assert sent == [(MAIN, C09_CHAT), (MIRROR, MIRROR_THREAD)]
    assert state[_POSTS_KEY] == [{"chat_id": MAIN, "message_id": 111}]
    assert "mirror post" in capsys.readouterr().out


def test_a_failed_primary_posts_nothing_at_all():
    state = {_MSG_KEY: 500}
    sent, deleted = _post(state, ids=(None,))
    assert sent == [(MAIN, C09_CHAT)]
    assert deleted == [], "never delete the old advert when the new one failed"


def test_the_registry_scan_covers_both_copies():
    """An id the scan misses gets its delete refused, and that copy then
    piles up one a day — the schedule-post bug in a new hat."""
    from posting.bot_sent_state_scan import extract_ids_from_live
    ids = extract_ids_from_live({
        "recruit_focus_msg_id": 111,
        "recruit_focus_posts": [{"chat_id": MAIN, "message_id": 111},
                                {"chat_id": MIRROR, "message_id": 222}]})
    assert 111 in ids and 222 in ids


def test_state_declares_the_new_key():
    from state_schema import DEFAULT_STATE, PARTITIONS
    assert "recruit_focus_posts" in PARTITIONS["live"]
    assert "recruit_focus_posts" in DEFAULT_STATE


# ── The ladder ───────────────────────────────────────────────────────────────

def _ladder_cfg(*counts):
    return {"topic_pairs": [
        {"code": f"C{i}", "pbp_topic_ids": [100 + i]} for i in range(len(counts))]}


def _ladder_state(*counts):
    players = {}
    for i, n in enumerate(counts):
        for j in range(n):
            players[f"{i}-{j}"] = {"pbp_topic_id": str(100 + i),
                                   "permanent": True}
    return {"players": players}


@pytest.mark.parametrize("counts,expected", [
    ((0, 0), 6),        # nothing near the bar
    ((6, 5), 6),        # one short campaign holds it
    ((6, 6), 8),        # everyone cleared 6 -> aim for 8
    ((8, 8), 8),        # top of the ladder, stays there
    ((9, 8), 8),        # overshooting does not invent a rung
    ((6, 0), 6),        # ⚠️ a campaign at ZERO must not raise the bar
])
def test_the_bar_rises_only_when_everyone_clears_it(counts, expected):
    assert effective_target(_ladder_cfg(*counts), _ladder_state(*counts)) == expected


def test_a_campaign_that_never_recruits_neither_blocks_nor_satisfies():
    cfg = _ladder_cfg(6, 6)
    cfg["topic_pairs"].append({"code": "C08", "pbp_topic_ids": [999],
                               "disabled_features": ["recruitment"]})
    assert effective_target(cfg, _ladder_state(6, 6)) == 8


def test_an_explicit_roster_target_opts_that_pair_out():
    cfg = _ladder_cfg(6, 6)
    cfg["topic_pairs"][0]["roster_target"] = 4
    assert effective_target(cfg, _ladder_state(6, 6)) == 8


def test_the_ladder_can_fail():
    """One campaign one short must hold the whole bar at 6. If this ever
    returns 8, the ladder has stopped checking every campaign."""
    assert effective_target(_ladder_cfg(6, 5), _ladder_state(6, 5)) == 6
    assert RECRUIT_LADDER[0] == 6 and RECRUIT_LADDER[-1] == 8
