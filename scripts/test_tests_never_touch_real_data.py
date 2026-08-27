"""A test run must not modify anything under ``data/``.

2026-08-27, the second half of the fixture leak. Cleaning the queue
files changed nothing, because **the GM queue is rebuilt from the
transcripts on every run**. ``scan_transcripts`` reads
``data/pbp_logs/``, so 43 imaginary "Paul: Hello all!" entries came
straight back the moment the bot ran again.

``append_to_transcript`` is called by ``track_message`` for any
non-command message, so every test that tracked a player message
appended to a real campaign transcript. 48 fixture blocks reached
Hopeful End-Times and 8 reached Kibwe.

## ⭐⭐ Why this file checks the invariant and not the symptom

I guarded the queue files first, because the queue files were what I had
looked at. That guard passed while the bug was still live, because the
queue files were never the source.

⚠️ It also *looked* isolated in a full-suite run and was not. Running the
offending test file **alone** re-added 10 blocks; something else in the
suite happened to patch ``_LOGS_DIR`` in an order that masked it.
**An accidentally-passing isolation is worse than a missing one**,
because the measurement everyone runs reports clean.

So this asserts the thing that actually matters, by doing it: exercise
every known write path and prove the real directory is byte-identical
afterwards. That holds no matter which module grows a new writer.
"""

import hashlib
import json
import os
import re

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA = os.path.join(_ROOT, "data")

# Topic ids that appear in old transcripts and no longer exist in
# config. All three are real history: 1242 is C11 Dark Pockets (retired
# in #22), 1825 and 145053 are earlier topics. Measured 2026-08-27.
# ⚠️ 100 is deliberately NOT here. It never existed; it is the fixture.
HISTORICAL_TOPIC_IDS = {"1242", "1825", "145053"}


def _fingerprint() -> dict:
    out = {}
    for root, _dirs, files in os.walk(_DATA):
        for name in files:
            path = os.path.join(root, name)
            with open(path, "rb") as handle:
                out[path] = hashlib.md5(handle.read()).hexdigest()
    return out


class TestNothingReachesTheRealDirectory:
    def test_the_fingerprint_sees_files(self):
        # ⭐ Without this, a wrong _DATA path would make every assertion
        # below compare two empty dicts and pass forever.
        assert len(_fingerprint()) > 50

    def test_appending_a_transcript_does_not_touch_it(self):
        # ⭐⭐ The exact call track_message makes. This is the one that
        # put 43 fake messages in front of the group.
        #
        # ⚠️ The campaign name is deliberately junk. The first version
        # used "Hopeful End-Times", and when I mutated the isolation
        # away to prove this guard fires, THE PROBE WROTE A REAL BLOCK
        # INTO A REAL TRANSCRIPT. The guard failed correctly and the
        # damage was already done, because restoring the source file
        # does not undo a write to data/.
        #
        # A probe that exercises a safety mechanism must be harmless
        # when that mechanism is absent, or proving the guard becomes a
        # way of triggering the bug.
        from transcript.logger import append_to_transcript
        before = _fingerprint()
        append_to_transcript({
            "campaign_name": "__probe_not_a_campaign__", "pid": "999999",
            "user_id": "PROBE", "user_name": "Probe", "first_name": "Probe",
            "user_last_name": "", "username": "probe",
            "text": "probe message", "raw_text": "probe message",
            "msg_time_iso": "2026-08-27T09:00:00+00:00",
            "message_id": 424242, "thread_id": "999999",
        }, set(), {})
        assert _fingerprint() == before

    def test_saving_a_queue_does_not_touch_it(self):
        from commands import queue_io
        before = _fingerprint()
        queue = queue_io.load("424242")
        queue["unreplied"].append({"message_id": 1, "user_name": "Probe",
                                   "preview": "probe", "time": "x"})
        queue_io.save("424242", queue)
        assert _fingerprint() == before

    def test_the_state_backup_does_not_touch_it(self):
        from scheduled import state_backup
        before = _fingerprint()
        try:
            state_backup.save_backup({"probe": True})
        except (AttributeError, TypeError):
            # Signature drift is not this test's business; the path
            # constant is checked separately below.
            pass
        assert _fingerprint() == before


class TestThePathConstantsAreRedirected:
    # Each of these is a module-level constant pointing into data/ at
    # import time. _test_state_isolation must move every WRITER off the
    # real tree. Named individually so a failure says which one.
    def _outside_repo(self, value):
        return os.path.realpath(_ROOT) not in os.path.realpath(str(value))

    def test_transcript_logger(self):
        from transcript import logger
        assert self._outside_repo(logger._LOGS_DIR), logger._LOGS_DIR

    def test_transcript_finalize(self):
        from transcript import finalize
        assert self._outside_repo(finalize._LOGS_DIR), finalize._LOGS_DIR

    def test_state_backup(self):
        from scheduled import state_backup
        assert self._outside_repo(state_backup._BACKUP_PATH)

    def test_queue_io_store(self):
        from commands import queue_io
        assert self._outside_repo(queue_io._store._state_dir)


class TestTheTranscriptsAreClean:
    def test_no_transcript_references_an_invented_topic(self):
        # ⭐⭐ The content backstop, and the check that would have caught
        # this on day one. Every message header carries its topic id, so
        # a fixture's invented id is visible without knowing anything
        # about which test wrote it.
        with open(os.path.join(_ROOT, "config.json"), encoding="utf-8") as fh:
            config = json.load(fh)
        known = {str(t) for pair in config.get("topic_pairs", [])
                 for t in pair.get("pbp_topic_ids", [])} | HISTORICAL_TOPIC_IDS
        offenders = {}
        for root, _dirs, files in os.walk(os.path.join(_DATA, "pbp_logs")):
            for name in files:
                if not name.endswith(".md"):
                    continue
                path = os.path.join(root, name)
                with open(path, encoding="utf-8") as handle:
                    found = set(re.findall(r"msg#\d+@(\d+):", handle.read()))
                bad = found - known
                if bad:
                    offenders[os.path.relpath(path, _ROOT)] = sorted(bad)
        assert not offenders, (
            f"transcripts reference topic ids that exist in no campaign: "
            f"{offenders}. Topic 100 is the test fixture; those entries get "
            f"rebuilt into the GM queue and posted to the group.")

    def test_the_scan_finds_transcripts_at_all(self):
        # ⭐ can-fail counterpart for the walk above.
        count = sum(1 for root, _d, files in os.walk(os.path.join(_DATA, "pbp_logs"))
                    for f in files if f.endswith(".md"))
        assert count > 20, f"only {count} transcripts found; the walk is wrong"
