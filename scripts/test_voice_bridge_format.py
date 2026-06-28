"""Unit tests for the Discord voice bridge's pure helpers.

The bridge lives in ``discord_bridge/`` and is a standalone always-on process,
but ``format_event`` / ``telegram_chat_id`` are dependency-free pure functions
(``discord`` is imported lazily inside ``main()``), so they run in the normal
pytest suite without Discord installed or any token configured.
"""
import os
import sys
from types import SimpleNamespace

# Make the discord_bridge package importable (it sits beside scripts/).
_BRIDGE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "discord_bridge")
sys.path.insert(0, _BRIDGE)

import voice_bridge as vb  # noqa: E402


def _ch(cid, name):
    return SimpleNamespace(id=cid, name=name)


def test_join():
    assert vb.format_event("Alice", None, _ch(1, "Public")) == \
        "🔊 Alice joined the voice channel Public."


def test_leave():
    assert vb.format_event("Alice", _ch(1, "Public"), None) == \
        "🔇 Alice has left the voice channel Public."


def test_switch():
    assert vb.format_event("Alice", _ch(1, "Public"), _ch(2, "AFK")) == \
        "🔀 Alice switched voice channel: Public → AFK."


def test_same_channel_is_ignored():
    # mute/deafen/stream toggle fires the event with an unchanged channel.
    assert vb.format_event("Alice", _ch(1, "Public"), _ch(1, "Public")) is None


def test_no_channels_is_ignored():
    assert vb.format_event("Alice", None, None) is None


def test_telegram_chat_id_prefers_env(monkeypatch):
    monkeypatch.setenv("TG_GROUP_ID", "-1009999")
    assert vb.telegram_chat_id() == -1009999
