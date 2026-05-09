"""Tests for checker.py — root file after phase-2 partial extraction.

Most feature-area tests have moved to sibling ``test_checker_<group>``
files. The remaining tests are queued for further extraction in
follow-up commits. See ``docs/dev/REFACTOR_PROGRESS.md``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_cleanup_timestamps_prunes_old():
    now = datetime.now(timezone.utc)
    state = _make_state()
    state["post_timestamps"] = {
        "100": {
            "user1": [
                (now - timedelta(days=1)).isoformat(),   # Keep
                (now - timedelta(days=20)).isoformat(),  # Prune
            ],
            "user2": [
                (now - timedelta(days=30)).isoformat(),  # Prune (user removed entirely)
            ],
        }
    }
    checker.cleanup_timestamps(state)
    assert len(state["post_timestamps"]["100"]["user1"]) == 1
    assert "user2" not in state["post_timestamps"]["100"]

def test_cleanup_timestamps_empty_state():
    state = _make_state()
    checker.cleanup_timestamps(state)  # Should not crash

def test_validate_config_valid():
    config = _make_config()
    issues = helpers.validate_config(config)
    assert not any(i.startswith("ERROR:") for i in issues)

def test_validate_config_bad_group_id():
    config = _make_config()
    config["group_id"] = 12345
    issues = helpers.validate_config(config)
    assert any("group_id" in i for i in issues)

def test_validate_config_duplicate_pbp_ids():
    config = _make_config(pairs=[
        {"name": "A", "chat_topic_id": 1, "pbp_topic_ids": [100]},
        {"name": "B", "chat_topic_id": 2, "pbp_topic_ids": [100]},
    ])
    issues = helpers.validate_config(config)
    assert any("ERROR:" in i and "100" in i for i in issues)

def test_validate_config_unknown_feature():
    config = _make_config(pairs=[
        {"name": "A", "chat_topic_id": 1, "pbp_topic_ids": [100], "disabled_features": ["bogus"]},
    ])
    issues = helpers.validate_config(config)
    assert any("bogus" in i for i in issues)

def test_validate_config_bad_created_date():
    config = _make_config(pairs=[
        {"name": "A", "chat_topic_id": 1, "pbp_topic_ids": [100], "created": "15-01-2025"},
    ])
    issues = helpers.validate_config(config)
    assert any("YYYY-MM-DD" in i for i in issues)

def test_feature_enabled():
    config = _make_config(pairs=[
        {"name": "A", "chat_topic_id": 1, "pbp_topic_ids": [100], "disabled_features": ["roster"]},
    ])
    assert helpers.feature_enabled(config, "100", "roster") is False
    assert helpers.feature_enabled(config, "100", "alerts") is True
    assert helpers.feature_enabled(config, "999", "roster") is True

def test_parse_message_valid():
    maps = helpers.build_topic_maps({"group_id": -100, "topic_pairs": [
        {"name": "Test", "chat_topic_id": 200, "pbp_topic_ids": [100]},
    ]})
    msg = {
        "chat": {"id": -100},
        "message_thread_id": 100,
        "from": {"id": 42, "first_name": "Alice", "last_name": "B", "username": "alice"},
        "date": int(datetime.now(timezone.utc).timestamp()),
        "text": "Hello world",
    }
    result = checker._parse_message(msg, maps)
    assert result is not None
    assert result["pid"] == "100"
    assert result["user_id"] == "42"
    assert result["user_name"] == "Alice"
    assert result["text"] == "hello world"

def test_parse_message_wrong_group():
    maps = helpers.build_topic_maps({"group_id": -100, "topic_pairs": [
        {"name": "Test", "chat_topic_id": 200, "pbp_topic_ids": [100]},
    ]})
    msg = {"chat": {"id": -999}, "message_thread_id": 100, "from": {"id": 42}}
    assert checker._parse_message(msg, maps) is None

def test_parse_message_unknown_topic():
    maps = helpers.build_topic_maps({"group_id": -100, "topic_pairs": [
        {"name": "Test", "chat_topic_id": 200, "pbp_topic_ids": [100]},
    ]})
    msg = {"chat": {"id": -100}, "message_thread_id": 999, "from": {"id": 42}}
    assert checker._parse_message(msg, maps) is None

def test_parse_message_bot_skipped():
    maps = helpers.build_topic_maps({"group_id": -100, "topic_pairs": [
        {"name": "Test", "chat_topic_id": 200, "pbp_topic_ids": [100]},
    ]})
    msg = {"chat": {"id": -100}, "message_thread_id": 100, "from": {"id": 42, "is_bot": True}}
    assert checker._parse_message(msg, maps) is None

def test_expire_pending_boons():
    _reset()
    state = _make_state()
    old_time = (datetime.now(timezone.utc) - timedelta(hours=170)).isoformat()
    state["pending_potw_boons"]["100"] = {
        "message_id": 555,
        "winner_user_id": "42",
        "boons": ["Boon A", "Boon B"],
        "base_message": "Winner!",
        "campaign_name": "TestCampaign",
        "posted_at": old_time,
    }
    checker.expire_pending_boons(_make_config(), state)
    assert "100" not in state["pending_potw_boons"]
    auto_msgs = [m for m in _sent_messages if "auto-selected" in m.get("text", "")]
    assert len(auto_msgs) >= 1

def test_calc_streak_consecutive_days():
    now = datetime(2025, 3, 15, 14, 0, 0, tzinfo=timezone.utc)
    timestamps = [
        (now - timedelta(days=d, hours=h)).isoformat()
        for d, h in [(0, 2), (1, 5), (2, 3), (3, 8)]  # 4 consecutive days
    ]
    assert checker._calc_streak(timestamps, now) == 4

def test_calc_streak_gap_breaks():
    now = datetime(2025, 3, 15, 14, 0, 0, tzinfo=timezone.utc)
    timestamps = [
        (now - timedelta(days=0, hours=2)).isoformat(),
        (now - timedelta(days=1, hours=5)).isoformat(),
        # Day 2 missing
        (now - timedelta(days=3, hours=3)).isoformat(),
    ]
    assert checker._calc_streak(timestamps, now) == 2

def test_calc_streak_no_recent_posts():
    now = datetime(2025, 3, 15, 14, 0, 0, tzinfo=timezone.utc)
    timestamps = [
        (now - timedelta(days=5)).isoformat(),  # Too old
    ]
    assert checker._calc_streak(timestamps, now) == 0

def test_calc_streak_multiple_posts_same_day():
    now = datetime(2025, 3, 15, 14, 0, 0, tzinfo=timezone.utc)
    timestamps = [
        (now - timedelta(hours=1)).isoformat(),
        (now - timedelta(hours=3)).isoformat(),
        (now - timedelta(hours=5)).isoformat(),
        (now - timedelta(days=1, hours=2)).isoformat(),
    ]
    assert checker._calc_streak(timestamps, now) == 2

def test_calc_streak_empty():
    now = datetime(2025, 3, 15, 14, 0, 0, tzinfo=timezone.utc)
    assert checker._calc_streak([], now) == 0

def test_post_daily_tip_sends():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()

    checker.post_daily_tip(config, state, now=now)
    assert len(_sent_messages) == 1
    assert "💡" in _sent_messages[0].get("text", "")
    assert state.get("last_daily_tip") is not None
    assert len(state.get("used_tip_indices", [])) == 1

def test_post_daily_tip_respects_cooldown():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()
    state["last_daily_tip"] = (now - timedelta(hours=10)).isoformat()

    checker.post_daily_tip(config, state, now=now)
    assert len(_sent_messages) == 0  # Too soon

def test_post_daily_tip_rotates():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()

    # Exhaust all but one tip
    state["used_tip_indices"] = list(range(len(checker._TIPS) - 1))

    checker.post_daily_tip(config, state, now=now)
    assert len(_sent_messages) == 1
    # The only remaining index should be the one not in the used list
    last_idx = state["used_tip_indices"][-1]
    assert last_idx == len(checker._TIPS) - 1

def test_post_daily_tip_resets_cycle():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()

    # All tips used
    state["used_tip_indices"] = list(range(len(checker._TIPS)))

    checker.post_daily_tip(config, state, now=now)
    assert len(_sent_messages) == 1
    # Cycle should have reset - used_tip_indices should have exactly 1 entry
    assert len(state["used_tip_indices"]) == 1

def test_streak_milestone_fires_at_7():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()

    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": now.isoformat(),
        "last_warned_week": 0,
    }
    # 8 consecutive days of posts
    state["post_timestamps"]["100"] = {
        "42": [(now - timedelta(days=d, hours=3)).isoformat() for d in range(8)],
    }

    checker.check_streak_milestones(config, state, now=now)
    streak_msgs = [m for m in _sent_messages if "7-day" in m.get("text", "")]
    assert len(streak_msgs) == 1
    assert state["celebrated_streaks"]["100:42"] == 7

def test_streak_milestone_no_duplicate():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()

    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": now.isoformat(),
        "last_warned_week": 0,
    }
    state["post_timestamps"]["100"] = {
        "42": [(now - timedelta(days=d, hours=3)).isoformat() for d in range(8)],
    }
    state["celebrated_streaks"] = {"100:42": 7}  # Already celebrated

    checker.check_streak_milestones(config, state, now=now)
    assert len(_sent_messages) == 0

def test_streak_milestone_escalates():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()

    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": now.isoformat(),
        "last_warned_week": 0,
    }
    # 15 consecutive days
    state["post_timestamps"]["100"] = {
        "42": [(now - timedelta(days=d, hours=3)).isoformat() for d in range(15)],
    }
    state["celebrated_streaks"] = {"100:42": 7}

    checker.check_streak_milestones(config, state, now=now)
    streak_msgs = [m for m in _sent_messages if "14-day" in m.get("text", "")]
    assert len(streak_msgs) == 1
    assert state["celebrated_streaks"]["100:42"] == 14

def test_sanitize_dirname():
    assert checker._sanitize_dirname("Doomsday Funtime") == "Doomsday_Funtime"
    assert checker._sanitize_dirname("Test/Bad:Name!") == "TestBadName"
    assert checker._sanitize_dirname("  Spaces  ") == "Spaces"

def test_append_to_transcript():
    import shutil
    test_dir = checker._LOGS_DIR / "transcript_test"
    if test_dir.exists():
        shutil.rmtree(test_dir)

    parsed = {
        "campaign_name": "transcript_test",
        "user_name": "Alice", "user_last_name": "", "user_id": "42",
        "msg_time_iso": "2026-02-26T14:30:05+00:00",
        "raw_text": "Hello world!", "media_type": None, "caption": "",
    }
    checker._append_to_transcript(parsed, {"999"})

    log_dir = checker._LOGS_DIR / "transcript_test"
    assert log_dir.exists()
    log_file = log_dir / "2026-02.md"
    assert log_file.exists()
    content = log_file.read_text()
    assert "transcript_test — 2026-02" in content
    assert "**Alice**" in content
    assert "Hello world!" in content

    # Second write appends
    parsed["raw_text"] = "Second message"
    checker._append_to_transcript(parsed, {"999"})
    content = log_file.read_text()
    assert "Second message" in content
    assert content.count("transcript_test — 2026-02") == 1  # Header only once

    shutil.rmtree(test_dir)

def test_parse_message_captures_media():
    maps = helpers.build_topic_maps({"group_id": -100, "topic_pairs": [
        {"name": "Test", "chat_topic_id": 200, "pbp_topic_ids": [100]},
    ]})
    msg = {
        "chat": {"id": -100},
        "message_thread_id": 100,
        "from": {"id": 42, "first_name": "Alice"},
        "date": int(datetime.now(timezone.utc).timestamp()),
        "photo": [{"file_id": "abc"}],
        "caption": "battle map",
    }
    result = checker._parse_message(msg, maps)
    assert result["media_type"] == "image"
    assert result["caption"] == "battle map"
    assert result["text"] == "battle map"  # Falls back to caption

def test_overview_multi_campaign():
    _reset()
    now = datetime.now(timezone.utc)
    config = {
        "group_id": -100,
        "gm_user_ids": [999],
        "topic_pairs": [
            {"name": "Campaign A", "chat_topic_id": 200, "pbp_topic_ids": [100]},
            {"name": "Campaign B", "chat_topic_id": 400, "pbp_topic_ids": [300]},
        ],
    }
    state = _make_state()
    state["topics"]["100"] = {
        "last_message_time": (now - timedelta(hours=2)).isoformat(),
        "last_user": "Alice", "last_user_id": "42",
        "campaign_name": "Campaign A",
    }
    state["topics"]["300"] = {
        "last_message_time": (now - timedelta(days=3)).isoformat(),
        "last_user": "Bob", "last_user_id": "50",
        "campaign_name": "Campaign B",
    }
    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "", "campaign_name": "Campaign A",
        "pbp_topic_id": "100", "last_post_time": now.isoformat(),
        "last_warned_week": 0,
    }

    result = checker._build_overview(config, state)
    assert "Campaign A" in result
    assert "Campaign B" in result
    assert "2 campaigns" in result
    assert "1 active players" in result

def test_get_characters():
    config = {
        "topic_pairs": [
            {"name": "A", "chat_topic_id": 10, "pbp_topic_ids": [100],
             "characters": {42: "Cardigan"}},
        ],
    }
    chars = helpers.get_characters(config, "100")
    assert chars == {"42": "Cardigan"}
    assert helpers.get_characters(config, "999") == {}

def test_word_count_tracking():
    """Word counts are accumulated per-user per-campaign during message processing."""
    _reset()
    config = _make_config()
    state = _make_state()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [
        {
            "update_id": 2001,
            "message": {
                "chat": {"id": -100},
                "message_thread_id": 100,
                "from": {"id": 42, "first_name": "Alice", "last_name": "", "username": "alice"},
                "date": now_ts,
                "text": "Cardigan draws her blade and charges forward",
            },
        },
        {
            "update_id": 2002,
            "message": {
                "chat": {"id": -100},
                "message_thread_id": 100,
                "from": {"id": 42, "first_name": "Alice", "last_name": "", "username": "alice"},
                "date": now_ts + 60,
                "text": "She strikes true",
            },
        },
    ]
    checker.process_updates(updates, config, state)
    # 7 words + 3 words = 10
    assert state["word_counts"]["100"]["42"] == 10

def test_pace_drop_detected():
    _reset()
    config = _make_config()
    now = datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc)
    state = _make_state()

    # Last week had 20 posts, this week has 5 -> 75% drop
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    last_week_times = [(two_weeks_ago + timedelta(hours=i * 6)).isoformat() for i in range(20)]
    this_week_times = [(week_ago + timedelta(hours=i * 24)).isoformat() for i in range(5)]

    state["post_timestamps"]["100"] = {
        "42": last_week_times + this_week_times,
    }
    state["players"]["100"] = {
        "42": {"first_name": "Alice", "last_post": this_week_times[-1]},
    }

    checker.check_pace_drop(config, state, now=now)
    assert any("Pace check" in m.get("text", "") or "📉" in m.get("text", "") for m in _sent_messages)
    assert "last_pace_drop_check" in state

def test_pace_drop_skips_low_activity():
    _reset()
    config = _make_config()
    now = datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc)
    state = _make_state()

    # Last week had only 3 posts (below threshold of 5) — should not alert
    two_weeks_ago = now - timedelta(days=14)
    last_week_times = [(two_weeks_ago + timedelta(hours=i * 24)).isoformat() for i in range(3)]

    state["post_timestamps"]["100"] = {
        "42": last_week_times,
    }
    state["players"]["100"] = {
        "42": {"first_name": "Alice", "last_post": last_week_times[-1]},
    }

    checker.check_pace_drop(config, state, now=now)
    pace_msgs = [m for m in _sent_messages if "Pace check" in m.get("text", "") or "📉" in m.get("text", "")]
    assert len(pace_msgs) == 0

def test_pace_drop_weekly_gating():
    _reset()
    config = _make_config()
    now = datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc)
    state = _make_state()
    # Already checked recently
    state["last_pace_drop_check"] = (now - timedelta(days=1)).isoformat()

    checker.check_pace_drop(config, state, now=now)
    assert len(_sent_messages) == 0  # Should not run

def test_conversation_dying_48h():
    _reset()
    config = _make_config()
    now = datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc)
    state = _make_state()

    # Last post was 60h ago
    last_post = (now - timedelta(hours=60)).isoformat()
    state["post_timestamps"]["100"] = {
        "42": [last_post],
        "999": [(now - timedelta(hours=55)).isoformat()],
    }

    checker.check_conversation_dying(config, state, now=now)
    dying_msgs = [m for m in _sent_messages if "💤" in m.get("text", "") or "silent" in m.get("text", "")]
    assert len(dying_msgs) == 1
    assert state.get("dying_alerts_sent", {}).get("100") == "active"

def test_conversation_dying_not_repeated():
    _reset()
    config = _make_config()
    now = datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc)
    state = _make_state()

    last_post = (now - timedelta(hours=60)).isoformat()
    state["post_timestamps"]["100"] = {"42": [last_post]}
    state["dying_alerts_sent"] = {"100": "active"}

    checker.check_conversation_dying(config, state, now=now)
    # Should NOT send again — already flagged
    assert len(_sent_messages) == 0

def test_conversation_dying_resets_on_activity():
    _reset()
    config = _make_config()
    now = datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc)
    state = _make_state()

    # Recent post (1h ago) — should clear the flag
    recent = (now - timedelta(hours=1)).isoformat()
    state["post_timestamps"]["100"] = {"42": [recent]}
    state["dying_alerts_sent"] = {"100": "active"}

    checker.check_conversation_dying(config, state, now=now)
    assert "100" not in state.get("dying_alerts_sent", {})
    assert len(_sent_messages) == 0

def test_conversation_dying_skips_paused():
    _reset()
    config = _make_config()
    now = datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc)
    state = _make_state()

    last_post = (now - timedelta(hours=72)).isoformat()
    state["post_timestamps"]["100"] = {"42": [last_post]}
    state["paused"] = {"100": "on holiday"}

    checker.check_conversation_dying(config, state, now=now)
    assert len(_sent_messages) == 0

def test_note_command():
    """GM /note adds a persistent note."""
    _reset()
    config = _make_config()
    state = _make_state()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 9110,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 999, "first_name": "GM"},
            "date": now_ts,
            "text": "/note Party agreed to meet the informant at dawn",
        },
    }]

    checker.process_updates(updates, config, state)
    notes = state.get("campaign_notes", {}).get("100", [])
    assert len(notes) == 1
    assert notes[0]["text"] == "Party agreed to meet the informant at dawn"
    saved_msgs = [m for m in _sent_messages if "saved" in m.get("text", "").lower()]
    assert len(saved_msgs) >= 1

def test_note_no_text():
    """GM /note with no text shows usage."""
    _reset()
    config = _make_config()
    state = _make_state()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 9111,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 999, "first_name": "GM"},
            "date": now_ts,
            "text": "/note",
        },
    }]

    checker.process_updates(updates, config, state)
    assert len(state.get("campaign_notes", {}).get("100", [])) == 0

def test_note_max_limit():
    """Notes capped at 20 per campaign."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["campaign_notes"] = {"100": [
        {"text": f"Note {i}", "created_at": "2026-01-01T00:00:00+00:00"}
        for i in range(20)
    ]}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 9112,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 999, "first_name": "GM"},
            "date": now_ts,
            "text": "/note One too many",
        },
    }]

    checker.process_updates(updates, config, state)
    assert len(state["campaign_notes"]["100"]) == 20
    max_msgs = [m for m in _sent_messages if "Maximum" in m.get("text", "")]
    assert len(max_msgs) >= 1

def test_notes_command():
    """Anyone can view notes with /notes."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["campaign_notes"] = {"100": [
        {"text": "First note", "created_at": "2026-01-15T10:00:00+00:00"},
        {"text": "Second note", "created_at": "2026-01-16T10:00:00+00:00"},
    ]}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 9113,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 42, "first_name": "Player"},
            "date": now_ts,
            "text": "/notes",
        },
    }]

    checker.process_updates(updates, config, state)
    notes_msgs = [m for m in _sent_messages if "First note" in m.get("text", "")]
    assert len(notes_msgs) >= 1

def test_notes_empty():
    """/notes with no notes shows helpful message."""
    _reset()
    result = checker._build_notes("100", "TestCampaign", {})
    assert "No GM notes" in result

def test_delnote_command():
    """GM /delnote removes a note by number."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["campaign_notes"] = {"100": [
        {"text": "Keep this", "created_at": "2026-01-15T10:00:00+00:00"},
        {"text": "Delete this", "created_at": "2026-01-16T10:00:00+00:00"},
    ]}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 9114,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 999, "first_name": "GM"},
            "date": now_ts,
            "text": "/delnote 2",
        },
    }]

    checker.process_updates(updates, config, state)
    notes = state["campaign_notes"]["100"]
    assert len(notes) == 1
    assert notes[0]["text"] == "Keep this"
    del_msgs = [m for m in _sent_messages if "Deleted" in m.get("text", "")]
    assert len(del_msgs) >= 1

def test_delnote_invalid_number():
    """GM /delnote with invalid number shows error."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["campaign_notes"] = {"100": [
        {"text": "A note", "created_at": "2026-01-15T10:00:00+00:00"},
    ]}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 9115,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 999, "first_name": "GM"},
            "date": now_ts,
            "text": "/delnote 5",
        },
    }]

    checker.process_updates(updates, config, state)
    assert len(state["campaign_notes"]["100"]) == 1
    err_msgs = [m for m in _sent_messages if "not found" in m.get("text", "")]
    assert len(err_msgs) >= 1

def test_notes_show_in_campaign():
    """Notes appear in /campaign output."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["campaign_notes"] = {"100": [
        {"text": "Remember the artifact", "created_at": "2026-01-15T10:00:00+00:00"},
    ]}
    result = checker._build_campaign_report("100", config, state, {999})
    assert "Remember the artifact" in result

def test_write_scene_marker():
    """Scene marker writes correct markdown to transcript."""
    import tempfile, pathlib
    from transcript import logger as _lmod
    original_dir = _lmod._LOGS_DIR
    with tempfile.TemporaryDirectory() as tmp:
        _lmod._LOGS_DIR = pathlib.Path(tmp)
        checker._LOGS_DIR = _lmod._LOGS_DIR
        try:
            checker._write_scene_marker("Test Campaign", "The Final Battle")
            campaign_dir = pathlib.Path(tmp) / "Test_Campaign"
            assert campaign_dir.exists()
            md_files = list(campaign_dir.glob("*.md"))
            assert len(md_files) == 1
            content = md_files[0].read_text()
            assert "### 🎭 Scene: The Final Battle" in content
        finally:
            _lmod._LOGS_DIR = original_dir
            checker._LOGS_DIR = original_dir

def test_activity_tracking():
    """Messages record hour and day counters in state."""
    _reset()
    config = _make_config()
    state = _make_state()
    # Use a known time: Wednesday (weekday=2) at 14:30 UTC
    from datetime import datetime as dt
    wed_14 = int(dt(2026, 2, 25, 14, 30, tzinfo=timezone.utc).timestamp())

    updates = [{
        "update_id": 9200,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 42, "first_name": "Alice"},
            "date": wed_14,
            "text": "I search the room carefully.",
        },
    }]

    checker.process_updates(updates, config, state)
    hours = state.get("activity_hours", {}).get("100", {}).get("42", {})
    days = state.get("activity_days", {}).get("100", {}).get("42", {})
    assert hours.get("14", 0) == 1
    assert days.get("2", 0) == 1  # Wednesday = 2

def test_activity_command():
    """/activity shows pattern report when data exists."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["activity_hours"] = {"100": {
        "42": {"14": 10, "15": 5, "20": 3},
        "999": {"10": 8, "14": 4},
    }}
    state["activity_days"] = {"100": {
        "42": {"0": 5, "2": 8, "4": 5},
        "999": {"1": 4, "3": 8},
    }}

    result = checker._build_activity("100", "TestCampaign", state, {999})
    assert "Activity Patterns" in result
    assert "Busiest days" in result
    assert "Busiest times" in result
    assert "Peak hour" in result

def test_activity_empty():
    """/activity with no data shows helpful message."""
    _reset()
    result = checker._build_activity("100", "TestCampaign", {}, {999})
    assert "No activity data" in result

def test_activity_command_via_message():
    """/activity sent as a message produces a response."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["activity_hours"] = {"100": {"42": {"14": 5}}}
    state["activity_days"] = {"100": {"42": {"2": 5}}}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 9201,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 42, "first_name": "Alice"},
            "date": now_ts,
            "text": "/activity",
        },
    }]

    checker.process_updates(updates, config, state)
    activity_msgs = [m for m in _sent_messages if "Activity" in m.get("text", "")]
    assert len(activity_msgs) >= 1

def test_parse_away_duration_days():
    """Parse '3 days reason'."""
    now = datetime(2026, 2, 27, 12, 0, tzinfo=timezone.utc)
    until, reason = helpers.parse_away_duration("3 days vacation", now)
    assert until is not None
    assert (until - now).days == 3
    assert reason == "vacation"

def test_parse_away_duration_weeks():
    """Parse '2 weeks'."""
    now = datetime(2026, 2, 27, 12, 0, tzinfo=timezone.utc)
    until, reason = helpers.parse_away_duration("2 weeks", now)
    assert until is not None
    assert (until - now).days == 14
    assert reason == "Away"

def test_parse_away_duration_indefinite():
    """Parse plain text as indefinite."""
    now = datetime(2026, 2, 27, 12, 0, tzinfo=timezone.utc)
    until, reason = helpers.parse_away_duration("busy with real life stuff", now)
    assert until is None
    assert reason == "busy with real life stuff"

def test_parse_away_duration_empty():
    """Empty text gives indefinite with default reason."""
    now = datetime(2026, 2, 27, 12, 0, tzinfo=timezone.utc)
    until, reason = helpers.parse_away_duration("", now)
    assert until is None
    assert reason == "No reason given"

def test_quest_add():
    """/quest adds a quest to the campaign."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/quest Find the missing merchant", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    quests = state.get("quests", {}).get("100", [])
    assert len(quests) == 1
    assert quests[0]["text"] == "Find the missing merchant"
    assert quests[0]["status"] == "active"
    assert "📋" in _sent_messages[-1]["text"]

def test_quest_non_gm():
    """/quest from non-GM should be ignored."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/quest Hack the system", user_id=42, first_name="Player")]
    checker.process_updates(updates, config, state)

    quests = state.get("quests", {}).get("100", [])
    assert len(quests) == 0

def test_quests_list():
    """/quests shows active and completed quests."""
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc).isoformat()
    state["quests"] = {
        "100": [
            {"text": "Find the gem", "status": "active", "created_at": now, "completed_at": None},
            {"text": "Save the prince", "status": "completed", "created_at": now, "completed_at": now},
        ]
    }

    result = checker._build_quests("100", "TestCampaign", state)
    assert "Find the gem" in result
    assert "Save the prince" in result
    assert "1 active" in result
    assert "1 completed" in result

def test_quest_done():
    """/done marks a quest as completed."""
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc).isoformat()
    state["quests"] = {
        "100": [{"text": "Find the gem", "status": "active", "created_at": now, "completed_at": None}]
    }

    updates = [_make_msg(1, 100, "/done 1", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert state["quests"]["100"][0]["status"] == "completed"
    assert state["quests"]["100"][0]["completed_at"] is not None
    assert "✅" in _sent_messages[-1]["text"]

def test_quest_delete():
    """/delquest removes a quest entirely."""
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc).isoformat()
    state["quests"] = {
        "100": [{"text": "Find the gem", "status": "active", "created_at": now, "completed_at": None}]
    }

    updates = [_make_msg(1, 100, "/delquest 1", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert len(state["quests"]["100"]) == 0
    assert "🗑️" in _sent_messages[-1]["text"]

def test_quests_empty():
    """/quests with no quests shows helpful message."""
    result = checker._build_quests("100", "TestCampaign", {"quests": {}})
    assert "No quests" in result

def test_gm_dashboard():
    """/gm shows all campaigns with health info."""
    _reset()
    config = _make_config(pairs=[
        {"name": "Campaign A", "chat_topic_id": 200, "pbp_topic_ids": [100]},
        {"name": "Campaign B", "chat_topic_id": 400, "pbp_topic_ids": [300]},
    ])
    state = _make_state()
    now = datetime.now(timezone.utc)
    state["players"] = {
        "100:42": {
            "user_id": "42", "first_name": "Alice", "last_name": "",
            "username": "", "campaign_name": "Campaign A",
            "pbp_topic_id": "100", "last_post_time": now.isoformat(),
            "last_warned_week": 0,
        },
    }
    state["topics"]["100"] = {
        "last_message_time": now.isoformat(),
        "last_user": "Alice", "last_user_id": "42",
        "campaign_name": "Campaign A",
    }

    result = checker._build_gm_dashboard(config, state)
    assert "📊 GM Dashboard" in result
    assert "Campaign A" in result
    assert "Campaign B" in result

def test_gm_command_requires_gm():
    """/gm only works for GMs."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/gm", user_id=42, first_name="Player")]
    checker.process_updates(updates, config, state)

    gm_msgs = [m for m in _sent_messages if "GM Dashboard" in m.get("text", "")]
    assert len(gm_msgs) == 0, "Non-GM should not see dashboard"

def test_gm_command_works_for_gm():
    """/gm works for GMs."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/gm", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    gm_msgs = [m for m in _sent_messages if "GM Dashboard" in m.get("text", "")]
    assert len(gm_msgs) >= 1

def test_pin_add():
    """/pin adds a bookmark."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/pin The dragon revealed its weakness", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    pins = state.get("pins", {}).get("100", [])
    assert len(pins) == 1
    assert pins[0]["text"] == "The dragon revealed its weakness"
    assert pins[0]["author"] == "GM"
    assert "📌" in _sent_messages[-1]["text"]

def test_pin_non_gm():
    """/pin from non-GM is ignored."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/pin some note", user_id=42, first_name="Player")]
    checker.process_updates(updates, config, state)

    pins = state.get("pins", {}).get("100", [])
    assert len(pins) == 0

def test_pins_list():
    """/pins shows all bookmarks."""
    state = {"pins": {"100": [
        {"text": "Found the key", "created_at": "2026-02-27T10:00:00+00:00", "author": "GM"},
        {"text": "Met the dragon", "created_at": "2026-02-28T10:00:00+00:00", "author": "GM"},
    ]}}
    result = checker._build_pins("100", "TestCampaign", state)
    assert "Found the key" in result
    assert "Met the dragon" in result
    assert "2/30 pins" in result

def test_delpin():
    """/delpin removes a pin."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["pins"] = {"100": [
        {"text": "Pin one", "created_at": "2026-02-27T10:00:00+00:00", "author": "GM"},
    ]}

    updates = [_make_msg(1, 100, "/delpin 1", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert len(state["pins"]["100"]) == 0
    assert "🗑️" in _sent_messages[-1]["text"]

def test_loot_add():
    """/loot adds an item."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/loot +1 striking longsword", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    loot = state.get("loot", {}).get("100", [])
    assert len(loot) == 1
    assert loot[0]["text"] == "+1 striking longsword"
    assert "💰" in _sent_messages[-1]["text"]

def test_loot_non_gm():
    """/loot from non-GM is ignored."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/loot stolen gem", user_id=42, first_name="Player")]
    checker.process_updates(updates, config, state)

    loot = state.get("loot", {}).get("100", [])
    assert len(loot) == 0

def test_lootlist():
    """/lootlist shows all items."""
    state = {"loot": {"100": [
        {"text": "+1 longsword", "added_at": "2026-02-27T10:00:00+00:00"},
        {"text": "500 gp", "added_at": "2026-02-28T10:00:00+00:00"},
    ]}}
    result = checker._build_lootlist("100", "TestCampaign", state)
    assert "+1 longsword" in result
    assert "500 gp" in result
    assert "2/50 items" in result

def test_delloot():
    """/delloot removes an item."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["loot"] = {"100": [
        {"text": "+1 longsword", "added_at": "2026-02-27T10:00:00+00:00"},
    ]}

    updates = [_make_msg(1, 100, "/delloot 1", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert len(state["loot"]["100"]) == 0
    assert "🗑️" in _sent_messages[-1]["text"]

def test_next_players_to_enemies():
    """/next advances from players to enemies phase."""
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc)
    state["combat"]["100"] = {
        "active": True, "round": 1, "current_phase": "players",
        "players_acted": {}, "last_ping_at": None, "enemies": [],
        "combat_log": [], "campaign_name": "TestCampaign",
        "phase_started_at": now.isoformat(), "started_at": now.isoformat(),
        "all_players_notified": False,
    }

    updates = [_make_msg(1, 100, "/next", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert state["combat"]["100"]["current_phase"] == "enemies"
    assert "Enemies" in _sent_messages[-1]["text"]

def test_next_enemies_to_new_round():
    """/next advances from enemies to next round players."""
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc)
    state["combat"]["100"] = {
        "active": True, "round": 1, "current_phase": "enemies",
        "players_acted": {}, "last_ping_at": None, "enemies": [],
        "combat_log": [], "campaign_name": "TestCampaign",
        "phase_started_at": now.isoformat(), "started_at": now.isoformat(),
        "all_players_notified": False,
    }

    updates = [_make_msg(1, 100, "/next", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert state["combat"]["100"]["round"] == 2
    assert state["combat"]["100"]["current_phase"] == "players"
    assert state["combat"]["100"]["players_acted"] == {}
    assert "Round 2" in _sent_messages[-1]["text"]

def test_clog():
    """/clog adds a combat log entry."""
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc)
    state["combat"]["100"] = {
        "active": True, "round": 2, "current_phase": "players",
        "players_acted": {}, "last_ping_at": None, "enemies": [],
        "combat_log": [], "campaign_name": "TestCampaign",
        "phase_started_at": now.isoformat(), "started_at": now.isoformat(),
        "all_players_notified": False,
    }

    updates = [_make_msg(1, 100, "/clog The ogre crits Cardigan for 28!", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    log = state["combat"]["100"]["combat_log"]
    assert len(log) == 1
    assert log[0]["round"] == 2
    assert "ogre crits" in log[0]["text"]

def test_clock_create():
    """/clock creates a progress clock."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/clock Investigation 6", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    clocks = state.get("clocks", {}).get("100", {})
    assert "Investigation" in clocks
    assert clocks["Investigation"]["segments"] == 6
    assert clocks["Investigation"]["filled"] == 0
    assert "○" in _sent_messages[-1]["text"]

def test_delclock():
    """/delclock removes a clock."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["clocks"] = {"100": {"Investigation": {"filled": 3, "segments": 6}}}

    updates = [_make_msg(1, 100, "/delclock Investigation", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert "Investigation" not in state["clocks"]["100"]

def test_clocks_list():
    """/clocks shows all clocks."""
    state = {"clocks": {"100": {
        "Investigation": {"filled": 3, "segments": 6},
        "Ritual": {"filled": 4, "segments": 4},
    }}}
    result = checker._build_clocks("100", "TestCampaign", state)
    assert "Investigation" in result
    assert "Ritual" in result
    assert "◉" in result
    assert "✅" in result  # Ritual is complete

def test_clock_non_gm():
    """/clock from non-GM is ignored."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/clock Cheat 6", user_id=42, first_name="Player")]
    checker.process_updates(updates, config, state)

    assert len(state.get("clocks", {}).get("100", {})) == 0

def test_clock_display():
    """Clock display renders correctly."""
    import helpers
    result = helpers.clock_display(3, 6)
    assert "◉◉◉○○○" in result
    assert "3/6" in result

def test_clock_display_full():
    """Full clock is all filled."""
    import helpers
    result = helpers.clock_display(6, 6)
    assert "◉◉◉◉◉◉" in result
    assert "○" not in result

def test_vote_start():
    """/vote creates a vote with options."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/vote Where next? | North | South | Stay", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    vote = state.get("votes", {}).get("100")
    assert vote is not None
    assert vote["question"] == "Where next?"
    assert vote["options"] == ["North", "South", "Stay"]
    assert not vote["closed"]
    assert "🗳️" in _sent_messages[-1]["text"]

def test_vote_too_few_options():
    """/vote with only 1 option rejected."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/vote Bad vote | Only one", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert "100" not in state.get("votes", {})

def test_pick_vote():
    """/pick casts a vote."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["votes"] = {"100": {
        "question": "Left or right?",
        "options": ["Left", "Right"],
        "results": {"1": [], "2": []},
        "closed": False,
        "created_at": "2026-02-28T10:00:00+00:00",
    }}

    updates = [_make_msg(1, 100, "/pick 2", user_id=42, first_name="Alice")]
    checker.process_updates(updates, config, state)

    assert "Alice" in state["votes"]["100"]["results"]["2"]
    assert "✅" in _sent_messages[-1]["text"]

def test_pick_changes_vote():
    """/pick changes previous vote."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["votes"] = {"100": {
        "question": "A or B?",
        "options": ["A", "B"],
        "results": {"1": ["Alice"], "2": []},
        "closed": False,
        "created_at": "2026-02-28T10:00:00+00:00",
    }}

    updates = [_make_msg(1, 100, "/pick 2", user_id=42, first_name="Alice")]
    checker.process_updates(updates, config, state)

    assert "Alice" not in state["votes"]["100"]["results"]["1"]
    assert "Alice" in state["votes"]["100"]["results"]["2"]

def test_endvote():
    """/endvote closes and shows results."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["votes"] = {"100": {
        "question": "A or B?",
        "options": ["A", "B"],
        "results": {"1": ["Alice", "Bob"], "2": ["Charlie"]},
        "closed": False,
        "created_at": "2026-02-28T10:00:00+00:00",
    }}

    updates = [_make_msg(1, 100, "/endvote", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert state["votes"]["100"]["closed"]
    last = _sent_messages[-1]["text"]
    assert "Winner" in last or "Tied" in last
    assert "A" in last

def test_showvote():
    """/showvote displays current vote."""
    state = {"votes": {"100": {
        "question": "Go where?",
        "options": ["Left", "Right"],
        "results": {"1": ["Alice"], "2": []},
        "closed": False,
    }}}
    result = checker._build_vote("100", "TestCampaign", state)
    assert "Go where?" in result
    assert "Left" in result
    assert "Alice" in result

def test_vote_non_gm():
    """/vote from non-GM is ignored."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/vote Cheat? | Yes | No", user_id=42, first_name="Player")]
    checker.process_updates(updates, config, state)

    assert "100" not in state.get("votes", {})

def test_timer_set():
    """/timer sets a deadline."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/timer 24h Post your actions", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    timer = state.get("timers", {}).get("100")
    assert timer is not None
    assert timer["reason"] == "Post your actions"
    assert "⏳" in _sent_messages[-1]["text"]

def test_timer_bad_duration():
    """/timer with bad duration gives error."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/timer blah", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert "100" not in state.get("timers", {})
    assert "parse" in _sent_messages[-1]["text"].lower() or "Nh" in _sent_messages[-1]["text"]

def test_showtimer():
    """/showtimer displays timer."""
    from datetime import timezone
    state = {"timers": {"100": {
        "deadline": (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat(),
        "reason": "Act now!",
        "set_at": datetime.now(timezone.utc).isoformat(),
    }}}
    result = checker._build_timer("100", "TestCampaign", state)
    assert "remaining" in result
    assert "Act now!" in result

def test_canceltimer():
    """/canceltimer removes the timer."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["timers"] = {"100": {
        "deadline": (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat(),
        "reason": "test",
        "set_at": datetime.now(timezone.utc).isoformat(),
    }}

    updates = [_make_msg(1, 100, "/canceltimer", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert "100" not in state.get("timers", {})

def test_timer_expiry_notification():
    """check_expired_timers posts notification."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["timers"] = {"100": {
        "deadline": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "reason": "Time's up!",
        "set_at": datetime.now(timezone.utc).isoformat(),
    }}

    checker.check_expired_timers(config, state)

    expired_msgs = [m for m in _sent_messages if "expired" in m.get("text", "").lower()]
    assert len(expired_msgs) >= 1
    assert state["timers"]["100"].get("notified")

def test_timer_non_gm():
    """/timer from non-GM is ignored."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/timer 24h hack", user_id=42, first_name="Player")]
    checker.process_updates(updates, config, state)

    assert "100" not in state.get("timers", {})

def test_parse_timer_hours():
    """Parse '24h' duration."""
    now = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)
    deadline, reason = helpers.parse_timer_duration("24h", now)
    assert deadline == datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert reason == ""

def test_parse_timer_minutes():
    """Parse '30m' duration."""
    now = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)
    deadline, reason = helpers.parse_timer_duration("30m", now)
    assert deadline == datetime(2026, 2, 28, 12, 30, 0, tzinfo=timezone.utc)

def test_parse_timer_days():
    """Parse '2d' duration."""
    now = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)
    deadline, reason = helpers.parse_timer_duration("2d", now)
    assert deadline == datetime(2026, 3, 2, 12, 0, 0, tzinfo=timezone.utc)

def test_parse_timer_with_reason():
    """Parse '24h Post your actions'."""
    now = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)
    deadline, reason = helpers.parse_timer_duration("24h Post your actions", now)
    assert deadline is not None
    assert reason == "Post your actions"

def test_parse_timer_invalid():
    """Invalid duration returns None."""
    now = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)
    deadline, reason = helpers.parse_timer_duration("blah", now)
    assert deadline is None
