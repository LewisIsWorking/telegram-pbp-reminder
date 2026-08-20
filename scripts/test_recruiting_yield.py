"""Attribution: the half that decides whether the workflow converges.

Adding venues only spreads the same effort thinner. Knowing which venues
produced players is what lets effort move, so these tests are about the
yield table telling the truth, especially about what it does NOT know.
"""

from datetime import datetime, timedelta, timezone

from recruiting import catalogue, log

NOW = datetime(2026, 8, 20, 12, tzinfo=timezone.utc)


def _venue(vid):
    return {"id": vid, "name": vid.title(), "kind": "forum",
            "status": "candidate", "cooldown_days": 7,
            "cooldown_source": "assumed", "format": {}}


class TestRecording:
    def test_a_post_is_remembered(self):
        state = {}
        log.record_post(state, "paizo", NOW)
        assert log.posts_for(state, "paizo") == [NOW.isoformat()]

    def test_posts_accumulate(self):
        state = {}
        log.record_post(state, "paizo", NOW - timedelta(days=9))
        log.record_post(state, "paizo", NOW)
        assert len(log.posts_for(state, "paizo")) == 2

    def test_last_posted_is_the_newest(self):
        state = {}
        log.record_post(state, "paizo", NOW)
        log.record_post(state, "paizo", NOW - timedelta(days=9))
        assert log.last_posted(state, "paizo") == NOW.isoformat()

    def test_never_posted_is_none(self):
        assert log.last_posted({}, "paizo") is None

    def test_a_join_is_credited(self):
        state = {}
        log.record_join(state, "paizo", "Terra", NOW)
        assert log.joins_for(state, "paizo")[0]["player"] == "Terra"

    def test_a_blank_venue_becomes_unknown_not_empty(self):
        # ⚠️ An empty string would sort and group as its own silent
        # category. UNKNOWN is a real, visible value.
        state = {}
        log.record_join(state, "", "Terra", NOW)
        assert log.joins_for(state, log.UNKNOWN_VENUE)[0]["player"] == "Terra"


class TestYieldTable:
    def _state(self):
        state = {}
        for _ in range(3):
            log.record_post(state, "good", NOW)
        for _ in range(8):
            log.record_post(state, "bad", NOW)
        for name in ("A", "B", "C", "D"):
            log.record_join(state, "good", name, NOW)
        return state

    def test_ranks_by_players_gained(self):
        rows = log.yield_table(self._state(),
                               [_venue("bad"), _venue("good")])
        assert rows[0]["id"] == "good"
        assert rows[0]["joins"] == 4

    def test_computes_players_per_post(self):
        rows = log.yield_table(self._state(), [_venue("good")])
        assert rows[0]["per_post"] == 4 / 3

    def test_a_venue_with_posts_and_no_joins_scores_zero(self):
        rows = log.yield_table(self._state(), [_venue("bad")])
        assert rows[0]["posts"] == 8
        assert rows[0]["per_post"] == 0.0

    def test_never_posted_is_none_not_zero(self):
        # ⭐⭐ The distinction that decides the next action. "Tried eight
        # times, got nobody" says stop. "Never tried" says go. Rendering
        # both as 0.00 would merge the two opposite conclusions into one
        # number and quietly bury every untried venue at the bottom.
        rows = log.yield_table({}, [_venue("untried")])
        assert rows[0]["per_post"] is None
        assert rows[0]["posts"] == 0

    def test_unattributed_joins_are_counted(self):
        state = {}
        log.record_join(state, log.UNKNOWN_VENUE, "Mystery", NOW)
        log.record_join(state, "good", "Known", NOW)
        assert log.unattributed(state) == 1


class TestItSurvivesBeingSaved:
    def test_recruitment_log_is_in_a_partition(self):
        # ⭐⭐ Without this the whole feature is a no-op that looks like it
        # works. state.save() builds each partition as
        # {k: state[k] for k in keys if k in state}, so an unlisted key is
        # dropped on every save with no error at all. Both write commands
        # would reply "recorded" and the data would be gone by the next
        # run. Same shape as the timeline_events bug already noted in
        # state_schema.py.
        from state_schema import PARTITIONS
        owners = [p for p, keys in PARTITIONS.items()
                  if log.LOG_KEY in keys]
        assert owners, (
            f"{log.LOG_KEY!r} is in no partition, so every save discards it")
        assert len(owners) == 1, f"{log.LOG_KEY!r} claimed by {owners}"

    def test_a_round_trip_keeps_posts_and_joins(self, tmp_path, monkeypatch):
        # Proves the point end to end rather than trusting the list above.
        import state as state_module
        from state_store.store import StateStore
        from state_schema import PARTITIONS

        original = {}
        log.record_post(original, "paizo", NOW)
        log.record_join(original, "paizo", "Terra", NOW)

        store = StateStore(state_dir=str(tmp_path))
        for partition, keys in PARTITIONS.items():
            store.save_partition(
                partition, {k: original[k] for k in keys if k in original})
        reloaded = {}
        for partition in PARTITIONS:
            reloaded.update(store.load_partition(partition) or {})

        assert log.posts_for(reloaded, "paizo") == [NOW.isoformat()]
        assert log.joins_for(reloaded, "paizo")[0]["player"] == "Terra"
        assert state_module  # imported to prove the module still loads


class TestCatalogueValidation:
    def _cat(self, tmp_path, venue):
        import json
        path = tmp_path / "v.json"
        path.write_text(json.dumps({"venues": [venue]}), encoding="utf-8")
        return str(path)

    def test_rejects_a_short_assumed_cooldown(self, tmp_path, monkeypatch):
        # ⭐ The guard that stops an impatient edit getting the account
        # banned from the one venue that works.
        import pytest
        bad = dict(_venue("x"), cooldown_days=1, cooldown_source="assumed")
        with pytest.raises(catalogue.CatalogueError, match="floor"):
            catalogue.load(self._cat(tmp_path, bad))

    def test_allows_a_short_cooldown_backed_by_a_stated_rule(self, tmp_path):
        # ⭐ can-fail counterpart: r/lfg's real 24h rule must be expressible.
        ok = dict(_venue("x"), cooldown_days=1, cooldown_source="rule")
        assert catalogue.load(self._cat(tmp_path, ok))

    def test_rejects_an_unknown_status(self, tmp_path):
        import pytest
        bad = dict(_venue("x"), status="maybe")
        with pytest.raises(catalogue.CatalogueError, match="status"):
            catalogue.load(self._cat(tmp_path, bad))

    def test_rejects_a_missing_field(self, tmp_path):
        import pytest
        bad = dict(_venue("x"))
        del bad["cooldown_days"]
        with pytest.raises(catalogue.CatalogueError, match="cooldown_days"):
            catalogue.load(self._cat(tmp_path, bad))

    def test_rejects_duplicate_ids(self, tmp_path):
        import json
        import pytest
        path = tmp_path / "v.json"
        path.write_text(json.dumps({"venues": [_venue("x"), _venue("x")]}),
                        encoding="utf-8")
        with pytest.raises(catalogue.CatalogueError, match="duplicate"):
            catalogue.load(str(path))
