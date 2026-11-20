"""🚪 A player who leaves is announced only in the campaigns they actually play in, with the count without them
(Lewis, 2026-11-20)."""
from datetime import datetime, timedelta, timezone

from players.left_notice import announce_left, on_telegram_leave

NOW = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
CONFIG = {"group_id": -100, "topic_pairs": [
    {"code": "C04", "name": "Magni Guard", "pbp_topic_ids": [76799], "chat_topic_id": 4, "roster_target": 6},
    {"code": "C06", "name": "Kibwe", "pbp_topic_ids": [40585], "chat_topic_id": 6, "roster_target": 6},
]}


def _player(pid, uid, days_ago):
    return {"user_id": uid, "first_name": f"P{uid}", "pbp_topic_id": str(pid),
            "last_post_time": (NOW - timedelta(days=days_ago)).isoformat()}


def _state():
    players = [_player(76799, 1, 2), _player(76799, 2, 3), _player(76799, 3, 40), _player(40585, 2, 1)]
    return {"players": {f"{p['pbp_topic_id']}:{p['user_id']}": p for p in players}}


def _go(state, uid, **kw):
    sent = []
    n = announce_left(CONFIG, state, uid, "Ana", "Discord server", now=NOW,
                      send=lambda g, t, text: sent.append((g, t, text)) or True, **kw)
    return n, sent


def test_told_only_where_they_play_with_the_count_without_them():
    n, sent = _go(_state(), 1)
    assert n == 1 and sent == [(-100, 4, "🚪 Ana has left the Path Wars Discord server.\n"
                                        "📋 C04: Magni Guard now has 1/6 players.")]


def test_every_campaign_they_play_in_is_told():
    n, sent = _go(_state(), 2)
    assert n == 2 and [t for _, t, _ in sent] == [4, 6]


def test_someone_who_never_posted_or_went_quiet_gets_no_notice():
    assert _go(_state(), 99) == (0, [])
    assert _go(_state(), 3) == (0, [])  # last post 40 days ago


def test_leaving_discord_and_telegram_posts_once():
    state = _state()
    assert _go(state, 1)[0] == 1
    assert _go(state, 1) == (0, [])


def test_a_telegram_chat_member_leave_is_announced():
    state, sent = _state(), []
    update = {"chat_member": {"chat": {"id": -100}, "old_chat_member": {"status": "member"},
                              "new_chat_member": {"status": "left", "user": {"id": 1, "first_name": "Ana"}}}}
    assert on_telegram_leave(update, CONFIG, state, send=lambda g, t, text: sent.append(text) or True)
    assert sent and sent[0].startswith("🚪 Ana has left the Path Wars Telegram group.")


def test_a_join_or_another_chat_is_not_a_leave():
    join = {"chat_member": {"chat": {"id": -100}, "old_chat_member": {"status": "left"},
                            "new_chat_member": {"status": "member", "user": {"id": 1}}}}
    other = {"message": {"chat": {"id": -5}, "left_chat_member": {"id": 1, "first_name": "Ana"}}}
    assert not on_telegram_leave(join, CONFIG, _state(), send=lambda *a: True)
    assert not on_telegram_leave(other, CONFIG, _state(), send=lambda *a: True)
