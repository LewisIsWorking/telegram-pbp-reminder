"""``VERSION`` and the newest changelog entry must agree (2026-08-29).

Found while shipping the recruit-advert roster line: ``VERSION`` still read
``4.58.1`` while the changelog was on ``4.59.0``. It had not moved since
PR #41.

Why that is not merely untidy
-----------------------------
``scheduled/state_backup._read_version`` stamps this file into every state
backup. A stale ``VERSION`` does not fail anything, it writes a wrong
answer into the artefact you would reach for when reconstructing what the
bot was running at the time. A measurement written into a file has no
expiry: it was true when written and quietly false afterwards.

Both directions, deliberately
-----------------------------
* ``VERSION`` behind the changelog is the bug that happened.
* ``VERSION`` ahead of it means a release was cut with nothing describing
  it, which is the same drift facing the other way.

Neither is an opinion about which one should have been updated. The guard
says only that the two disagree, and the person merging decides.
"""

import os
import pathlib
import re

_ROOT = pathlib.Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_VERSION = _ROOT / "VERSION"
_CHANGELOG = _ROOT / "CHANGELOG.md"

# "## [4.60.0] - 2026-08-29". The date is deliberately not captured: it is
# a separate claim, and pinning it here would fail every entry written on
# a day other than the one it describes.
_ENTRY = re.compile(r"^##\s*\[(\d+\.\d+\.\d+)\]", re.MULTILINE)


def _declared() -> str:
    return _VERSION.read_text(encoding="utf-8").strip()


def _released() -> list[str]:
    return _ENTRY.findall(_CHANGELOG.read_text(encoding="utf-8"))


class TestTheScanWorks:
    def test_the_changelog_yields_entries(self):
        # ⭐ Without this, a heading format change would empty the list and
        # make every assertion below vacuous rather than failing.
        found = _released()
        assert len(found) > 20, (
            f"only parsed {len(found)} changelog entries, so the heading "
            f"pattern has probably drifted and this guard is checking "
            f"nothing")

    def test_the_version_file_is_a_version(self):
        assert re.fullmatch(r"\d+\.\d+\.\d+", _declared()), (
            f"VERSION reads {_declared()!r}, which is not a semver string")


class TestTheyAgree:
    def test_version_is_the_newest_changelog_entry(self):
        newest = _released()[0]
        assert _declared() == newest, (
            f"VERSION says {_declared()} and the newest changelog entry is "
            f"{newest}. scheduled/state_backup stamps VERSION into every "
            f"backup, so the two drifting apart puts a wrong version into "
            f"a file nobody re-reads until they need it. Update whichever "
            f"of the two is behind.")

    def test_the_changelog_is_newest_first(self):
        # The test above trusts entry [0] to be the newest. If the file
        # were ever reordered oldest-first it would compare against 1.0.0
        # and fail for a reason that has nothing to do with the drift.
        found = _released()
        as_tuples = [tuple(int(n) for n in v.split(".")) for v in found]
        assert as_tuples == sorted(as_tuples, reverse=True), (
            "changelog entries are not in descending version order, so "
            "'the newest entry' is not the first one")

    def test_no_version_is_listed_twice(self):
        found = _released()
        dupes = sorted({v for v in found if found.count(v) > 1})
        assert not dupes, f"changelog lists these versions more than once: {dupes}"
