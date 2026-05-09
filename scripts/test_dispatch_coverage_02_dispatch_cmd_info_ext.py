"""Coverage tests extracted from test_dispatch_coverage.py — bin 2.

Sections in this file:
  - dispatch/cmd_info_ext.py (part a)
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


def _qs_config():
    return {
        "group_id": -1001, "gm_user_ids": [999],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
             "gm_user_ids": [999]}
        ]
    }


@patch("commands.queue_scan.helpers")
def test_scan_empty_no_logs(mock_helpers, tmp_path):
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
    mock_helpers.is_excluded.return_value = False
    mock_helpers.gm_ids_for_campaign.return_value = {999}
    with patch("commands.queue_scan._LOGS_DIR", tmp_path), \
         patch("commands.queue_io.all_pids", return_value=[]):
        result = scan_transcripts(_qs_config(), {})
    assert result == {}


@patch("commands.queue_scan.helpers")
def test_scan_excluded_campaign(mock_helpers, tmp_path):
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
    mock_helpers.is_excluded.return_value = True
    with patch("commands.queue_scan._LOGS_DIR", tmp_path), \
         patch("commands.queue_io.all_pids", return_value=[]):
        result = scan_transcripts(_qs_config(), {})
    assert result == {}


@patch("commands.queue_scan.helpers")
def test_scan_parses_transcript(mock_helpers, tmp_path):
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
    mock_helpers.is_excluded.return_value = False
    mock_helpers.gm_ids_for_campaign.return_value = {"999"}

    from datetime import datetime
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    log_dir = tmp_path / "Kibwe"
    log_dir.mkdir()
    (log_dir / f"{month}.md").write_text(
        "**Alice** (2026-03-01 10:00:00):\nHello world\n\n"
        "**GM** [GM] (2026-03-01 11:00:00):\nGot it\n",
        encoding="utf-8"
    )
    with patch("commands.queue_scan._LOGS_DIR", tmp_path), \
         patch("commands.queue_scan._IDS_FILE", tmp_path / "ids.json"), \
         patch("commands.queue_io.all_pids", return_value=[]):
        result = scan_transcripts(_qs_config(), {})
    assert "100" in result
    assert result["100"]["entries"][0]["name"] == "Alice"


@patch("commands.queue_scan.helpers")
def test_scan_floor_filters_old(mock_helpers, tmp_path):
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
    mock_helpers.is_excluded.return_value = False
    mock_helpers.gm_ids_for_campaign.return_value = {"999"}

    from datetime import datetime
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    log_dir = tmp_path / "Kibwe"
    log_dir.mkdir()
    (log_dir / f"{month}.md").write_text(
        "**Alice** (2020-01-01 10:00:00):\nOld message\n",
        encoding="utf-8"
    )
    state = {"queue_scan_floor": "2026-01-01"}
    with patch("commands.queue_scan._LOGS_DIR", tmp_path), \
         patch("commands.queue_scan._IDS_FILE", tmp_path / "ids.json"), \
         patch("commands.queue_io.all_pids", return_value=[]):
        result = scan_transcripts(_qs_config(), state)
    assert result == {}


@patch("commands.queue_scan.helpers")
def test_scan_msg_id_in_transcript(mock_helpers, tmp_path):
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
    mock_helpers.is_excluded.return_value = False
    mock_helpers.gm_ids_for_campaign.return_value = {"999"}

    from datetime import datetime
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    log_dir = tmp_path / "Kibwe"
    log_dir.mkdir()
    (log_dir / f"{month}.md").write_text(
        "**Alice** (2026-03-01 10:00:00) msg#12345:\nHello\n",
        encoding="utf-8"
    )
    with patch("commands.queue_scan._LOGS_DIR", tmp_path), \
         patch("commands.queue_scan._IDS_FILE", tmp_path / "ids.json"), \
         patch("commands.queue_io.all_pids", return_value=[]):
        result = scan_transcripts(_qs_config(), {})
    assert result["100"]["entries"][0]["message_id"] == "12345"
    assert "12345" in result["100"]["entries"][0]["link"]


@patch("commands.queue_scan.helpers")
def test_scan_replied_filtered(mock_helpers, tmp_path, monkeypatch):
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
    mock_helpers.is_excluded.return_value = False
    mock_helpers.gm_ids_for_campaign.return_value = {"999"}

    from datetime import datetime
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    log_dir = tmp_path / "Kibwe"
    log_dir.mkdir()
    (log_dir / f"{month}.md").write_text(
        "**Alice** (2026-03-01 10:00:00) msg#42:\nHello\n",
        encoding="utf-8"
    )
    from commands import queue_io
    monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path / "queues")
    (tmp_path / "queues").mkdir()
    (tmp_path / "queues" / "100.json").write_text(
        json.dumps({"replied": ["msg:42"], "unreplied": [], "reply_log": []})
    )
    with patch("commands.queue_scan._LOGS_DIR", tmp_path), \
         patch("commands.queue_scan._IDS_FILE", tmp_path / "ids.json"):
        result = scan_transcripts(_qs_config(), {})
    assert result == {}


@patch("commands.queue_scan.helpers")
def test_scan_id_lookup_file(mock_helpers, tmp_path):
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
    mock_helpers.is_excluded.return_value = False
    mock_helpers.gm_ids_for_campaign.return_value = {"999"}

    from datetime import datetime
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    log_dir = tmp_path / "Kibwe"
    log_dir.mkdir()
    (log_dir / f"{month}.md").write_text(
        "**Alice** (2026-03-01 10:00:00):\nHello\n",
        encoding="utf-8"
    )
    ids_file = tmp_path / "ids.json"
    ids_file.write_text(json.dumps({"100:2026-03-01 10:00:00": 99999}))
    with patch("commands.queue_scan._LOGS_DIR", tmp_path), \
         patch("commands.queue_scan._IDS_FILE", ids_file), \
         patch("commands.queue_io.all_pids", return_value=[]):
        result = scan_transcripts(_qs_config(), {})
    assert result["100"]["entries"][0]["message_id"] == "99999"
