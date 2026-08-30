"""Three ways to count the roster, and the ways each one goes wrong.

Lewis, 2026-08-30: *"Are there actually 44 active players?"*

There were 41 records, 25 people and 19 who had posted inside the window,
and the README was quoting the first of those under the word "seats".
``recruiting/roster_basis`` exists so the answer is re-run rather than
re-derived by hand, which is how it came out wrong the second time.

What is actually worth guarding
-------------------------------
Every trap here produces a **plausible number**, which is the failure
mode that survives review:

* a seat that posted moments ago measures ``0.0`` days, and ``0.0`` is
  falsy, so the terse ``if ago`` form files the most active player in the
  group under "never posted";
* ``--asof`` missing measures an old roster against today's clock and
  prints the answer to a different question under the same heading;
* one person holding five seats is five seats and one person, and which
  of those you quote decides whether recruiting looks solved.
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

_NOW = datetime.datetime(2026, 8, 30, 12, 0, tzinfo=datetime.timezone.utc)
_LIVE = "66154"
_RETIRED = "1242"


def _cfg():
    return {"topic_pairs": [{"code": "C00", "pbp_topic_ids": [int(_LIVE)]}]}


def _seat(uid, pid=_LIVE, days_ago=1, posted=True):
    record = {"user_id": str(uid), "first_name": f"P{uid}",
              "pbp_topic_id": pid}
    if posted:
        record["last_post_time"] = (
            _NOW - datetime.timedelta(days=days_ago)).isoformat()
    return record


def _players(*seats):
    return {f"r{i}": s for i, s in enumerate(seats)}


def _counts(*seats):
    from recruiting.roster_basis import counts
    return counts(_players(*seats), _cfg(), _NOW)


class TestTheThreeBases:
    def test_a_retired_campaigns_rows_are_records_but_not_seats(self):
        # ⭐ Live case: Luke and Poo still sit in C11 Dark Pockets
        # (pid 1242), retired, so 41 records are 39 seats.
        figures = _counts(_seat(1), _seat(2, pid=_RETIRED))
        assert figures["records"] == 2
        assert figures["seats"] == 1

    def test_one_person_with_three_seats_is_three_seats_and_one_person(self):
        figures = _counts(_seat(7), _seat(7), _seat(7))
        assert figures["seats"] == 3
        assert figures["seat_humans"] == 1
        assert figures["active_seats"] == 3
        assert figures["active_humans"] == 1

    def test_silence_removes_a_seat_from_active_but_not_from_seats(self):
        figures = _counts(_seat(1, days_ago=200))
        assert figures["seats"] == 1
        assert figures["active_seats"] == 0


class TestTheWindowBoundary:
    def test_a_seat_that_posted_today_is_active(self):
        # ⭐⭐ 0.0 days is falsy. `if ago` here would file the single most
        # active player in the group under "never posted".
        assert _counts(_seat(1, days_ago=0))["active_seats"] == 1

    def test_exactly_thirty_days_is_still_active(self):
        assert _counts(_seat(1, days_ago=30))["active_seats"] == 1

    def test_thirty_one_days_is_not(self):
        assert _counts(_seat(1, days_ago=31))["active_seats"] == 0

    def test_a_record_that_never_posted_is_not_active(self):
        # Distinct from "posted long ago": nothing created it by posting.
        figures = _counts(_seat(1, posted=False))
        assert figures["seats"] == 1 and figures["active_seats"] == 0

    def test_an_unparseable_timestamp_is_not_active(self):
        from recruiting.roster_basis import counts
        broken = {"r0": {"user_id": "1", "pbp_topic_id": _LIVE,
                         "last_post_time": "not a date"}}
        assert counts(broken, _cfg(), _NOW)["active_seats"] == 0


class TestConcentration:
    def test_the_top_five_are_counted_by_seats_held(self):
        seats = [_seat(1) for _ in range(5)] + [_seat(n) for n in range(2, 8)]
        figures = _counts(*seats)
        assert figures["active_seats"] == 11
        assert figures["top_five_seats"] == 9, "5 + four singles"
        assert figures["top_five_pct"] == 82

    def test_an_empty_roster_does_not_divide_by_zero(self):
        figures = _counts()
        assert figures["active_seats"] == 0 and figures["top_five_pct"] == 0


class TestAsOf:
    def test_it_defaults_to_the_supplied_now(self):
        from recruiting.roster_basis import asof_from
        assert asof_from(["prog"], _NOW) == _NOW

    def test_it_parses_the_flag(self):
        from recruiting.roster_basis import asof_from
        got = asof_from(["prog", "-", "--asof", "2026-08-20"], _NOW)
        assert got.date().isoformat() == "2026-08-20"

    def test_the_flag_changes_the_answer(self):
        # ⭐⭐ The reason the flag exists. The same roster measured ten
        # days later has fewer active seats, and without --asof an old
        # revision is silently measured against today.
        from recruiting.roster_basis import counts
        players = _players(_seat(1, days_ago=25))
        assert counts(players, _cfg(), _NOW)["active_seats"] == 1
        later = _NOW + datetime.timedelta(days=10)
        assert counts(players, _cfg(), later)["active_seats"] == 0


class TestTheCommandLine:
    def _run(self, argv, stdin_text):
        import io

        from recruiting.roster_basis import main
        printed = []
        code = main(argv, now=_NOW, stdin=io.StringIO(stdin_text),
                    out=printed.append)
        return code, "\n".join(printed)

    def test_it_reads_a_wrapped_blob_from_stdin(self):
        import json
        blob = json.dumps({"players": _players(_seat(1))})
        code, text = self._run(["prog", "-"], blob)
        assert code == 0
        assert "records (enrolment)" in text

    def test_it_reads_a_bare_mapping_too(self):
        # git show of an older revision has produced both shapes.
        import json
        code, text = self._run(["prog", "-"], json.dumps(_players(_seat(1))))
        assert code == 0 and "1 seats" in text

    def test_every_line_names_its_basis(self):
        # ⭐ The point of the tool. A number with no basis printed beside
        # it is the thing that went into the README and was misread.
        import json
        _code, text = self._run(["prog", "-"],
                                json.dumps(_players(_seat(1))))
        for basis in ("records (enrolment)", "seats in a live campaign",
                      "active (<=30d)", "top five hold"):
            assert basis in text, f"{basis!r} missing from:\n{text}"

    def test_it_reports_the_date_it_measured_against(self):
        import json
        _code, text = self._run(["prog", "-", "--asof", "2026-08-20"],
                                json.dumps(_players(_seat(1))))
        assert "as of 2026-08-20" in text, (
            "a printed measurement that does not say when it was taken is "
            "the exact defect this tool was written to stop")
