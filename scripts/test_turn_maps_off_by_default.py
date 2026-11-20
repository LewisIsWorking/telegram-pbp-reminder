"""Turn-end maps never post unless config turn_end_maps is true (2026-11-20, Lewis: "You NEED to show me the map
before you ever post it")."""
from datetime import datetime, timezone

import combat.turn_maps as turn_maps
from combat.foundry_sync import sync_foundry_encounters


def _run(monkeypatch, config):
    calls = []
    monkeypatch.setattr(turn_maps, "post_turn_maps", lambda *a, **k: calls.append(a) or 0)
    sync_foundry_encounters(config, {}, now=datetime(2026, 11, 20, tzinfo=timezone.utc), fetch=lambda: [])
    return calls


def test_off_by_default(monkeypatch):
    assert _run(monkeypatch, {"topic_pairs": []}) == []


def test_on_only_when_switched_on(monkeypatch):
    assert len(_run(monkeypatch, {"topic_pairs": [], "turn_end_maps": True})) == 1
