"""Lewis, standing, all repos: no em dashes. Zero, not fewer.

History: this started on 2026-08-25 as a ratchet on the count (1,762 across
scripts/ and docs/), meant to fall as files were touched. It only ever fell
by one or two at a time. On 2026-09-21 a PR tripped the ratchet and the
failure reached Lewis's Telegram, and he answered: "There should be NO em
dashes across any repo!" Every one outside data/ was removed that day
(2,301 of them), and this is now a zero check over the whole repository.

What it covers: every tracked text file, whatever its extension, except:

* ``data/`` and ``docs/data/``: verbatim transcripts and archives of what
  people actually posted. Rewriting those would falsify the record.
* This file, which names the character by code point only anyway.

Code that must still RECOGNISE an em dash (players' phones turn "--" into
one, and old transcripts keep theirs) writes it as the escape ``\\u2014``,
which is six ASCII characters in the source and an em dash at runtime.
"""

import os
import sys
import subprocess

EM_DASH = chr(0x2014)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_EXEMPT_PREFIXES = ("data/", "docs/data/")


def _tracked_files() -> list[str]:
    # -z and quotepath off (2026-09-21). Plain ls-files quotes and escapes
    # non-ASCII paths as quoted octal escapes, open() then raises FileNotFoundError,
    # and the catch below used to skip the file without a word.
    out = subprocess.run(["git", "-c", "core.quotepath=off", "ls-files", "-z"], cwd=_ROOT,
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    return [f for f in out.split("\0") if f and not f.startswith(_EXEMPT_PREFIXES)]


def _offenders() -> list[str]:
    found = []
    for rel in _tracked_files():
        try:
            with open(os.path.join(_ROOT, rel), encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    if EM_DASH in line:
                        found.append(f"{rel}:{n}: {line.strip()[:100]}")
        except UnicodeDecodeError:
            continue  # binary files
    return found


def test_there_are_no_em_dashes_anywhere():
    found = _offenders()
    assert not found, (
        f"{len(found)} line(s) with an em dash. Lewis: \"There should be NO em "
        f"dashes across any repo!\" Use a hyphen, comma, colon or full stop. "
        f"Code that must match one writes the escape \\u2014.\n  "
        + "\n  ".join(found[:30]))


def test_the_guard_can_fail(monkeypatch):
    """A zero check that cannot fail is decoration. Plant one and look."""
    probe = os.path.join(_ROOT, "scripts", "_em_dash_probe.md")
    with open(probe, "w", encoding="utf-8") as f:
        f.write("a " + EM_DASH + " b\n")
    try:
        monkeypatch.setitem(globals(), "_tracked_files",
                            lambda: ["scripts/_em_dash_probe.md"])
        assert _offenders() == ["scripts/_em_dash_probe.md:1: a " + EM_DASH + " b"]
    finally:
        os.remove(probe)


# The only places allowed to spell an em dash as an escape: parsers that must
# RECOGNISE one, in players' input or old verbatim transcripts. Before
# 2026-09-21 the old guard counted the literal character only, and 35 escapes
# had crept in to get past it while still PRINTING em dashes (the roster,
# refusal alerts, the transcript silence marker). An escape is the character.
_ESCAPES = ("\\u2014", "\\N{EM DASH}", "&mdash;")
_ESCAPE_ALLOWED = {
    "scripts/commands/queue_scan.py": 1,          # old transcripts' silence line
    "scripts/dispatch/cmd_conditions_hp.py": 2,    # /condition, phones type one
    "scripts/dispatch/cmd_trackers_items.py": 2,   # /npc, same
}


def _escape_counts() -> dict:
    found = {}
    for rel in _tracked_files():
        if rel == "scripts/test_no_em_dashes.py":
            continue  # names the escapes in order to forbid them
        try:
            with open(os.path.join(_ROOT, rel), encoding="utf-8") as f:
                text = f.read()
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        n = sum(text.count(e) for e in _ESCAPES)
        if n:
            found[rel] = n
    return found


def test_no_em_dash_hidden_in_an_escape():
    found = _escape_counts()
    extra = {f: n for f, n in found.items() if n > _ESCAPE_ALLOWED.get(f, 0)}
    assert not extra, (
        f"em dashes spelled as escapes, which still print as em dashes: {extra}. "
        f"Only a parser that must recognise one in input or old transcripts may "
        f"use the escape; add it to _ESCAPE_ALLOWED with a reason if so.")


def test_verbatim_transcripts_are_exempt():
    assert not any(f.startswith("data/") for f in _tracked_files())



def test_accented_filenames_are_read_not_skipped(tmp_path, monkeypatch):
    """Plain `git ls-files` returns a quoted, octal-escaped name for a file like
    Bayakan-with-an-accent.md, open() fails, and the old catch skipped it
    silently. The listing must give the real name, and the file must be read."""
    import subprocess as sp
    repo = tmp_path / "r"
    repo.mkdir()
    sp.run(["git", "init", "-q"], cwd=repo, check=True)
    name = "B" + chr(0xE1) + "yakan.md"
    (repo / name).write_text("x " + EM_DASH + " y\n", encoding="utf-8")
    sp.run(["git", "add", "."], cwd=repo, check=True)
    monkeypatch.setattr(sys.modules[__name__], "_ROOT", str(repo))
    assert name in _tracked_files()
    assert _offenders() == [name + ":1: x " + EM_DASH + " y"]
