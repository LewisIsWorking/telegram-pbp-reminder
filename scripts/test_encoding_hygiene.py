"""Guard: every text-mode file open must declare encoding="utf-8".

Background (4.51.x): the bot writes UTF-8 transcripts, but `open()`,
`Path.read_text()` and `Path.write_text()` without an explicit
`encoding=` use the platform default — utf-8 on the Linux CI runner,
but cp1252 on a Windows dev box. That mismatch silently corrupted
em-dashes and broke ~7 tests only on Windows, and is a latent
transcript-corruption risk if the bot ever runs on a non-utf-8 host.

This test walks the whole source tree with the `ast` module (so it
ignores matches inside strings/comments) and fails if any text-mode
open/read_text/write_text omits an encoding. Binary modes ("rb"/"wb"
/…) are correctly exempt — encoding is invalid there.

If this fails: add `encoding="utf-8"` to the flagged call. Don't rely
on the platform default.
"""

import ast
import pathlib

_SCRIPTS_DIR = pathlib.Path(__file__).parent


def _mode_is_binary(call: ast.Call) -> bool:
    if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant) \
            and isinstance(call.args[1].value, str) and "b" in call.args[1].value:
        return True
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant) \
                and isinstance(kw.value.value, str) and "b" in kw.value.value:
            return True
    return False


def _has_encoding(call: ast.Call) -> bool:
    return any(kw.arg == "encoding" for kw in call.keywords)


def _needs_encoding(call: ast.Call) -> bool:
    """True if call is a text open()/read_text()/write_text() lacking encoding."""
    func = call.func
    if isinstance(func, ast.Name) and func.id == "open":
        return not (_mode_is_binary(call) or _has_encoding(call))
    if isinstance(func, ast.Attribute) and func.attr in ("read_text", "write_text"):
        return not _has_encoding(call)
    return False


def _violations_in(path: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    rel = path.relative_to(_SCRIPTS_DIR)
    return [
        f"{rel}:{node.lineno}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _needs_encoding(node)
    ]


def test_no_unqualified_text_file_io():
    violations: list[str] = []
    for py in sorted(_SCRIPTS_DIR.rglob("*.py")):
        violations.extend(_violations_in(py))
    assert not violations, (
        "Text file I/O without encoding=\"utf-8\" found "
        "(platform-default encoding is non-deterministic — see this file's "
        f"docstring):\n  " + "\n  ".join(violations)
    )
