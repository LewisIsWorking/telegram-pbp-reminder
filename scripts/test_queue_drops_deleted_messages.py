"""A player's deleted post must leave the GM queue without a /markdone.

2026-10-07: https://t.me/Path_Wars/137075/183543 (Kibwe, C06) was deleted
by the player and stayed queued, and in the 🎯 focus message, until Lewis
cleared it by hand. Telegram sends bots no deletion event, so the queue
now asks (``commands/queue_prune.py``). Only an explicit "not found"
drops an entry; every other outcome keeps it.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
import requests

sys.path.insert(0, os.path.dirname(__file__))

from commands import queue_io, queue_prune  # noqa: E402
from commands.queue_prune import drop_deleted  # noqa: E402
from posting import message_probe  # noqa: E402

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
CONFIG = {"group_id": -1001, "topic_pairs": [
    {"pbp_topic_ids": [100, 101], "code": "C06", "name": "Kibwe"}]}


def _scanned():
    return {"100": {"campaign": "Kibwe", "code": "C06", "entries": [
        {"name": "Kibwe", "time": "2026-10-07 10:00:00", "preview": "gone",
         "message_id": "183543", "link": "l1", "thread_id": "100"},
        {"name": "Ana", "time": "2026-10-07 11:00:00", "preview": "here",
         "message_id": "183600", "link": "l2", "thread_id": "100"},
    ]}}


@pytest.fixture(autouse=True)
def _queues(tmp_path, monkeypatch):
    monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)


class _Probe:
    def __init__(self, answers):
        self.answers, self.calls = answers, []

    def __call__(self, chat, mid):
        self.calls.append((chat, mid))
        return self.answers.get(mid, True)


def test_deleted_message_is_dropped_as_markdone_would():
    probe = _Probe({"183543": False})
    out = drop_deleted(CONFIG, {}, _scanned(), NOW, probe=probe)
    assert [e["message_id"] for e in out["100"]["entries"]] == ["183600"]
    cq = queue_io.load("100")
    assert "msg:183543" in cq["replied"]
    assert cq["reply_log"][-1]["msg_id"] == "183543"
    assert all(c == -1001 for c, _ in probe.calls)


def test_campaign_with_only_deleted_entries_leaves_the_scan():
    probe = _Probe({"183543": False, "183600": False})
    assert drop_deleted(CONFIG, {}, _scanned(), NOW, probe=probe) == {}


@pytest.mark.parametrize("verdict", [True, None])
def test_existing_or_unknown_is_kept(verdict):
    probe = _Probe({"183543": verdict, "183600": verdict})
    out = drop_deleted(CONFIG, {}, _scanned(), NOW, probe=probe)
    assert len(out["100"]["entries"]) == 2
    assert "msg:183543" not in queue_io.load("100").get("replied", [])


def test_unknown_is_not_cached_so_it_is_asked_again():
    probe = _Probe({"183543": None, "183600": None})
    drop_deleted(CONFIG, {}, _scanned(), NOW, probe=probe)
    drop_deleted(CONFIG, {}, _scanned(), NOW, probe=probe)
    assert len(probe.calls) == 4


def test_cache_prevents_reprobe_until_the_interval_passes():
    probe = _Probe({})
    drop_deleted(CONFIG, {}, _scanned(), NOW, probe=probe)
    assert len(probe.calls) == 2
    drop_deleted(CONFIG, {}, _scanned(), NOW + timedelta(hours=1), probe=probe)
    assert len(probe.calls) == 2
    later = NOW + timedelta(hours=queue_prune.RECHECK_HOURS + 1)
    drop_deleted(CONFIG, {}, _scanned(), later, probe=probe)
    assert len(probe.calls) == 4


def test_probes_per_run_are_capped(monkeypatch):
    monkeypatch.setattr(queue_prune, "MAX_PROBES", 1)
    probe = _Probe({})
    drop_deleted(CONFIG, {}, _scanned(), NOW, probe=probe)
    assert probe.calls == [(-1001, "183543")]  # oldest first


def test_no_bot_token_means_no_probe(monkeypatch):
    monkeypatch.setattr(queue_prune.tg, "TELEGRAM_API", "", raising=False)
    monkeypatch.setattr(queue_prune, "message_exists",
                        lambda *a: pytest.fail("probed without a token"))
    assert len(drop_deleted(CONFIG, {}, _scanned(), NOW)["100"]["entries"]) == 2


def test_build_queue_hides_a_deleted_post(monkeypatch):
    from commands import queue
    monkeypatch.setattr(queue, "scan_transcripts", lambda c, s: _scanned())
    monkeypatch.setattr(queue_prune.tg, "TELEGRAM_API", "https://x",
                        raising=False)
    monkeypatch.setattr(queue_prune, "message_exists",
                        lambda api, chat, mid: mid != "183543")
    text = queue.build_queue(CONFIG, {})
    assert "gone" not in text and "here" in text


class _Resp:
    def __init__(self, body):
        self.body = body

    def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


@pytest.mark.parametrize("body, expected", [
    ({"ok": False, "description":
      "Bad Request: message to react not found"}, False),
    ({"ok": True, "result": True}, True),
    ({"ok": False, "description": "Bad Request: chat not found"}, True),
    ({"ok": False, "error_code": 429,
      "description": "Too Many Requests: retry after 5"}, None),
    (ValueError("not json"), None),
])
def test_probe_reads_telegram_answers(monkeypatch, body, expected):
    monkeypatch.setattr(message_probe.requests, "post",
                        lambda *a, **k: _Resp(body))
    assert message_probe.message_exists("https://x", -1, 5) is expected


def test_probe_network_error_is_unknown(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("down")
    monkeypatch.setattr(message_probe.requests, "post", boom)
    assert message_probe.message_exists("https://x", -1, 5) is None
