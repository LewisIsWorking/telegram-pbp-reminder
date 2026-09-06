"""One Python version, declared in six places, drifting in none.

Raised 3.11 -> 3.14 on 2026-09-06 at Lewis's request, after the VPS
heartbeat went on 3.14 and it turned out CI was two releases behind it.

⚠️ The version is declared at **six separate `python-version:` keys**
across four workflow files. Nothing made them agree, so a bump could
easily land in the job that runs the tests and miss the job that runs
the bot - and the suite would keep passing on a version production does
not use. That is the shape of skew that hides real incompatibilities:
green here, broken there, and the difference invisible.

⭐ The floor is asserted as a NUMBER, not a string match. `'3.4'` sorts
above `'3.14'` lexically, which is exactly the sort of comparison that
looks right and silently permits a downgrade.
"""

import pathlib
import re

import pytest

_WORKFLOWS = pathlib.Path(__file__).resolve().parent.parent / ".github" / "workflows"

# ⚠️ Hardcoded, not read from the workflows. An expectation taken from
# the thing under test cannot fail - see the network guard, where
# parametrising over the module's own constant let a mutation shrink the
# test along with the code.
MINIMUM = (3, 14)


def _declarations() -> list:
    """(file, line, version string) for every python-version: key."""
    out = []
    for path in sorted(_WORKFLOWS.glob("*.yml")):
        for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1):
            match = re.search(r"python-version:\s*['\"]?([0-9.]+)", line)
            if match:
                out.append((path.name, number, match.group(1)))
    return out


def _as_tuple(version: str) -> tuple:
    return tuple(int(part) for part in version.split("."))


class TestTheDeclaredVersion:
    def test_the_scan_finds_them_all(self):
        """⛔ A scan that matches nothing passes forever. There were six
        on 2026-09-06; fewer means the scan broke or a job lost its
        setup-python step, and both are worth knowing."""
        found = _declarations()
        assert len(found) >= 6, (
            f"only found {len(found)} python-version declarations: {found}")

    def test_they_all_agree(self):
        versions = {version for _, _, version in _declarations()}
        assert len(versions) == 1, (
            f"workflows disagree about Python: {sorted(versions)}. A bump "
            f"that lands in the test job but not the bot job leaves the "
            f"suite validating a version production never runs.\n  " +
            "\n  ".join(f"{f}:{n}: {v}" for f, n, v in _declarations()))

    @pytest.mark.parametrize("file_line_version", _declarations())
    def test_none_is_below_the_floor(self, file_line_version):
        name, number, version = file_line_version
        assert _as_tuple(version) >= MINIMUM, (
            f"{name}:{number} pins Python {version}, below the "
            f"{'.'.join(map(str, MINIMUM))} floor")

    def test_the_comparison_is_numeric_not_lexical(self):
        """⭐ Proves the check above cannot be fooled. As strings,
        '3.4' > '3.14', so a lexical comparison would wave through a
        downgrade to 3.4 and reject the correct 3.14."""
        assert _as_tuple("3.4") < _as_tuple("3.14")
        assert "3.4" > "3.14", "if this ever fails, drop this test"
