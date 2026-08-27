"""Lewis, standing, all repos: no em dashes.

I broke this rule three times on 2026-08-25 in files I had just written,
including inside a string that goes out over Telegram. A rule I keep
breaking by hand is a missing guard, not a missing intention.

## Why a single number and not an allowlist

There are ~1,760 of them already, across ~367 files, most in transcripts
of old design docs. Clearing that is not this session's work, and a
367-entry allowlist is a file nobody reads.

So this is a **ratchet on the count**, and it fails in BOTH directions:

* more than ``CEILING`` means new ones were added, which is the bug;
* fewer than ``CEILING`` means somebody cleaned up and did not lower the
  number, so the guard has quietly gained slack and would stop catching
  the next batch.

A ratchet that only ever fails upward is just a high-water mark with
extra steps. See ``a-ratchet-that-never-tightens``.

⚠️ When you clear some, LOWER ``CEILING`` to whatever the failure message
reports. Never raise it.
"""

import os

EM_DASH = "—"

# Measured 2026-08-25, over scripts/ and docs/, AFTER clearing the 15 I
# had just added. 367 files carry them; the bulk are old design docs.
#
# 1762 -> 1761 the same day: rewriting a comment in queue_reminder.py
# dropped one, and the slack test refused to let the ceiling stay above
# reality. That is the both-directions design earning its keep on its
# first real use.
CEILING = 1759

_ROOTS = ("scripts", "docs")
_EXTS = (".py", ".md")
_SKIP_DIRS = {"__pycache__", ".pytest_cache", "htmlcov"}
# This file necessarily contains the character it forbids.
_SELF = os.path.basename(__file__)


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _counts() -> dict:
    """{relative path: occurrences}, for every file that has any."""
    found = {}
    for root in _ROOTS:
        base = os.path.join(_repo_root(), root)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for name in filenames:
                if not name.endswith(_EXTS) or name == _SELF:
                    continue
                path = os.path.join(dirpath, name)
                with open(path, encoding="utf-8") as handle:
                    hits = handle.read().count(EM_DASH)
                if hits:
                    key = os.path.relpath(path, _repo_root())
                    found[key.replace(os.sep, "/")] = hits
    return found


class TestTheRatchet:
    def test_the_scan_finds_files_at_all(self):
        # ⭐ Without this, a walk that silently matched nothing would make
        # the ratchet below pass against zero and check nothing. The
        # backlog is real, so "found nothing" means the scanner broke,
        # not that the repo is clean.
        assert _counts(), "scanner found no files at all, so it is broken"

    def test_no_new_em_dashes(self):
        total = sum(_counts().values())
        assert total <= CEILING, (
            f"{total - CEILING} new em dash(es). Rewrite them: a comma, a "
            f"colon, or two sentences almost always reads better anyway. "
            f"Worst files: {sorted(_counts().items(), key=lambda kv: -kv[1])[:5]}")

    def test_the_ceiling_has_no_slack(self):
        total = sum(_counts().values())
        assert total >= CEILING, (
            f"only {total} em dashes remain but CEILING is {CEILING}. "
            f"Somebody cleaned up without tightening the ratchet, so it "
            f"has gained {CEILING - total} of slack and would not catch "
            f"the next batch. Set CEILING = {total}.")


class TestTheRuleAppliesToTheNewestWork:
    # The recruitment work is where the rule was broken, so it is pinned
    # exactly rather than left to float inside a four-figure total. A
    # ratchet at 1,747 cannot notice one new dash arriving as another
    # leaves; these can.
    RECENT = (
        "scripts/recruiting/readiness.py",
        "scripts/recruiting/rotation.py",
        "scripts/recruiting/catalogue.py",
        "scripts/recruiting/log.py",
        "scripts/recruiting/README.md",
        "scripts/commands/recruit_ads.py",
        "docs/recruitment-ad.md",
        "scripts/test_recruiting_readiness.py",
        "scripts/test_recruiting_fit.py",
        "scripts/test_recruiting_rotation.py",
        "scripts/test_recruiting_yield.py",
    )

    def test_the_recruitment_files_are_clean(self):
        found = _counts()
        dirty = {path: found[path] for path in self.RECENT if path in found}
        assert not dirty, f"em dashes in recently written files: {dirty}"

    def test_those_files_all_exist(self):
        # ⭐ can-fail counterpart. A path typo would make the test above
        # pass by checking nothing, which is the failure mode this whole
        # file exists to prevent.
        root = _repo_root()
        missing = [p for p in self.RECENT
                   if not os.path.exists(os.path.join(root, *p.split("/")))]
        assert not missing, f"listed but absent: {missing}"
