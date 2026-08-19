"""The heartbeat: the local, committed evidence that a state push landed.

Split out of ``test_preflight_gate.py`` on 2026-08-19 when that file hit the
repo's 200 line limit. The seam is real rather than arbitrary: this file is
about the file on disk that records whether state is reaching the remote,
while the other is about the gate's decision-making around it.
"""

import json

class TestHeartbeat:
    def test_writes_a_record_that_changes_every_run(self, tmp_path, monkeypatch):
        from datetime import datetime, timezone

        from preflight.heartbeat import write_heartbeat
        path = tmp_path / "state" / "ci_heartbeat.json"
        monkeypatch.setenv("GITHUB_RUN_ID", "123")
        monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
        record = write_heartbeat(datetime(2026, 8, 19, tzinfo=timezone.utc),
                                 path=str(path))
        assert record["last_run_id"] == "123"
        assert record["last_run_attempt"] == "2"
        assert json.loads(path.read_text(encoding="utf-8"))["written_at"].startswith("2026-08-19")

    def test_round_trips_and_reports_its_age(self, tmp_path, monkeypatch):
        from datetime import datetime, timedelta, timezone

        from preflight.heartbeat import (heartbeat_age_hours, read_heartbeat,
                                         write_heartbeat)
        path = str(tmp_path / "ci_heartbeat.json")
        now = datetime(2026, 8, 19, 12, tzinfo=timezone.utc)
        write_heartbeat(now, path=path)
        assert heartbeat_age_hours(read_heartbeat(path),
                                   now + timedelta(hours=4)) == 4.0

    def test_a_missing_or_broken_file_reads_as_unknown(self, tmp_path):
        from preflight.heartbeat import read_heartbeat
        assert read_heartbeat(str(tmp_path / "nope.json")) is None
        broken = tmp_path / "broken.json"
        broken.write_text("{not json", encoding="utf-8")
        assert read_heartbeat(str(broken)) is None
        empty = tmp_path / "empty.json"
        empty.write_text("{}", encoding="utf-8")
        # ⚠️ A dict with no written_at is unusable, not age zero. Treating
        # it as fresh would be the silent-health failure all over again.
        assert read_heartbeat(str(empty)) is None

    def test_a_future_timestamp_is_unknown_not_fresh(self):
        from datetime import datetime, timezone

        from preflight.heartbeat import heartbeat_age_hours
        now = datetime(2026, 8, 19, 12, tzinfo=timezone.utc)
        record = {"written_at": datetime(2026, 8, 19, 20,
                                         tzinfo=timezone.utc).isoformat()}
        assert heartbeat_age_hours(record, now) is None

    def test_default_path_is_anchored_to_the_repo_not_the_cwd(self):
        # ⭐ The workflow runs this as `cd scripts && python -m preflight.gate`.
        # A cwd-relative default would write scripts/data/ci_heartbeat.json,
        # which the commit step's `git add data/` never sees - so the file
        # would exist, look correct, and never be pushed. The heartbeat's
        # whole job is to make the push happen, so that miss would be silent
        # and total.
        import os

        from preflight import heartbeat
        assert os.path.isabs(heartbeat.HEARTBEAT_PATH)
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(heartbeat.__file__))))
        assert heartbeat.HEARTBEAT_PATH == os.path.join(
            repo_root, "data", "ci_heartbeat.json")
        # And it must sit OUTSIDE data/state/, whose schema registry demands
        # an owning module and a runtime reader the heartbeat does not have.
        assert os.path.join("data", "state") not in heartbeat.HEARTBEAT_PATH

    def test_a_rerun_of_the_same_run_still_differs(self, monkeypatch):
        # ⚠️ Re-running a failed run reuses GITHUB_RUN_ID. That is exactly
        # when a human is retrying a broken push, so the file must still
        # change or there would be nothing to commit and nothing to prove.
        from datetime import datetime, timezone

        from preflight.heartbeat import build_heartbeat
        now = datetime(2026, 8, 19, tzinfo=timezone.utc)
        assert build_heartbeat("123", "1", now) != build_heartbeat("123", "2", now)
