"""test_import_history.py — bin 3.

  - misc (part c)
"""
#!/usr/bin/env python3
"""Tests for import_history.py"""

import json
import shutil
import tempfile
from pathlib import Path

import import_history



def _make_export(messages):
    """Create a minimal Telegram export dict."""
    return {"messages": messages}

def _make_msg(msg_id, thread_id, text="Hello", from_name="Alice",
              from_id="user42", date="2025-06-15T14:30:05", **extra):
    msg = {
        "id": msg_id,
        "type": "message",
        "message_thread_id": thread_id,
        "text": text,
        "from": from_name,
        "from_id": from_id,
        "date": date,
    }
    msg.update(extra)
    return msg

def _make_desktop_msg(msg_id, reply_to, text_entities=None, from_name="Alice",
                      from_id="user42", date="2025-06-15T14:30:05", **extra):
    """Create a message in Telegram Desktop export format."""
    msg = {
        "id": msg_id,
        "type": "message",
        "reply_to_message_id": reply_to,
        "from": from_name,
        "from_id": from_id,
        "date": date,
    }
    if text_entities:
        msg["text_entities"] = text_entities
    msg.update(extra)
    return msg

def test_import_desktop_export_format():
    """Test import with Telegram Desktop export format (reply_to_message_id, text_entities)."""
    tmp = tempfile.mkdtemp()
    old_logs = import_history.LOGS_DIR
    old_config = import_history.CONFIG_PATH

    try:
        config = {
            "gm_user_ids": [999],
            "topic_pairs": [
                {"name": "TestCampaign", "chat_topic_id": 10, "pbp_topic_ids": [100]},
            ],
        }
        config_path = Path(tmp) / "config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        import_history.CONFIG_PATH = config_path
        import_history.LOGS_DIR = Path(tmp) / "logs"

        export = _make_export([
            _make_desktop_msg(1, 100,
                text_entities=[{"type": "plain", "text": "Amar attacks!"}],
                date="2025-06-15T10:00:00"),
            _make_desktop_msg(2, 100,
                text_entities=[{"type": "mention", "text": "@player"}, {"type": "plain", "text": " The goblin snarls."}],
                from_name="Lewis", from_id="user999",
                date="2025-06-15T10:05:00"),
            _make_desktop_msg(3, 999,
                text_entities=[{"type": "plain", "text": "Wrong topic"}],
                date="2025-06-15T10:10:00"),
        ])
        export_path = Path(tmp) / "export.json"
        export_path.write_text(json.dumps(export), encoding="utf-8")

        results = import_history.import_messages(str(export_path))
        assert results["TestCampaign"] == 2

        campaign_dir = Path(tmp) / "logs" / "TestCampaign"
        content = (campaign_dir / "2025-06.md").read_text(encoding="utf-8")
        assert "Amar attacks!" in content
        assert "[GM]" in content
        assert "@player The goblin snarls." in content

    finally:
        import_history.LOGS_DIR = old_logs
        import_history.CONFIG_PATH = old_config
        shutil.rmtree(tmp)
