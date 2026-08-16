"""Every suppressed Telegram error must be declared to mean "already achieved".

COVERS  every string literal passed to a ``suppress_errors=`` keyword
        anywhere under ``scripts/`` and ``tools/``, found by parsing the
        AST rather than by grepping, so a reformatted or multi-line
        tuple cannot slip past.
MISSES  a suppression list built at runtime from a variable this file
        cannot resolve. ``test_suppress_errors_is_always_a_literal``
        below forbids exactly that, so the miss is closed by making the
        unanalysable form illegal.
PROVEN  by ``test_the_guard_can_fail``.

────────────────────────────────────────────────────────────────────────

``telegram._post`` returns ``True`` — soft success — for any response
body matching a ``suppress_errors`` entry. That is correct **only** when
the error means the caller's goal is already achieved. It is catastrophic
when the error means the operation did not happen, because every
downstream retry, alert and audit then records a success that never
occurred.

On 2026-05-10 ``"message can't be deleted"`` was added to the delete
list. It means the message is **still there**. For three months the bot
recorded 715 deletes, 715 successes and zero failures, while 28
messages it believed it had removed sat in the group. Lewis found it by
scrolling Telegram.

The judgement is one word per entry, and it is not hard — *achieved* or
*abandoned*. This test forces someone to write that word down.
"""
import ast
from pathlib import Path

# ── The declaration ──────────────────────────────────────────────────────────
# Imported, never retyped. The registry is production code, so a string
# cannot reach a suppress_errors argument without a written reason
# attached — that is the mechanism; this file is the enforcement.
from posting.suppression_registry import (  # noqa: E402
    NEVER_SUPPRESS,
    SUPPRESSIONS_THAT_MEAN_ALREADY_ACHIEVED,
)


def _python_files():
    root = Path(__file__).resolve().parent.parent
    for sub in ("scripts", "tools"):
        base = root / sub
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if "__pycache__" in path.parts or ".venv" in path.parts:
                continue
            yield path, path.relative_to(root).as_posix()


def _suppress_nodes():
    """Yield (relpath, keyword_node) for every ``suppress_errors=`` argument."""
    for path, rel in _python_files():
        if rel == "scripts/test_suppressed_errors_are_declared.py":
            continue  # its synthetic sample would look like a call site
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if kw.arg == "suppress_errors":
                    yield rel, kw


def _literal_strings(node):
    """Return the string literals in a tuple/list node, or None if not literal."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.Tuple, ast.List)):
        out = []
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                out.append(elt.value)
            else:
                return None
        return out
    return None


def test_every_suppressed_string_is_declared():
    """No error may be treated as success without a written justification."""
    undeclared = []
    for rel, kw in _suppress_nodes():
        strings = _literal_strings(kw.value)
        if strings is None:
            continue  # covered by the literal test below
        for s in strings:
            if s not in SUPPRESSIONS_THAT_MEAN_ALREADY_ACHIEVED:
                undeclared.append((rel, kw.lineno, s))

    assert not undeclared, (
        f"Suppressed error string(s) with no declaration: {undeclared}.\n\n"
        f"Suppressing an error makes telegram._post return True, so the "
        f"caller records a SUCCESS. That is only correct when the error "
        f"means the goal is already achieved.\n"
        f"Ask: does this error mean 'already true', or 'I could not'? If "
        f"the latter, it is a failure — bound the retry (see "
        f"posting.stuck_deletes), do not suppress it. If the former, add "
        f"it to SUPPRESSIONS_THAT_MEAN_ALREADY_ACHIEVED with the reason."
    )


def test_known_bad_strings_are_never_suppressed():
    """The specific strings that mean 'it is still there' stay banned."""
    offenders = []
    for rel, kw in _suppress_nodes():
        for s in _literal_strings(kw.value) or []:
            if s in NEVER_SUPPRESS:
                offenders.append((rel, kw.lineno, s, NEVER_SUPPRESS[s]))
    assert not offenders, (
        f"Banned suppression re-introduced: {offenders}"
    )


def test_the_two_lists_cannot_overlap():
    """A string cannot be both safe and banned. Catches a careless paste
    into the wrong dict, which would silently un-ban it."""
    both = (set(SUPPRESSIONS_THAT_MEAN_ALREADY_ACHIEVED)
            & set(NEVER_SUPPRESS))
    assert not both, f"declared as both safe and banned: {sorted(both)}"


def test_suppress_errors_is_always_a_literal():
    """A computed suppression list cannot be audited, so it is forbidden.

    Without this the guard above has an obvious hole: pass a variable and
    nothing static can tell what is being suppressed. The one exemption
    is safe_delete's own named constant, which IS the declaration and is
    checked by test_the_named_constant_matches_the_declaration.
    """
    computed = []
    for rel, kw in _suppress_nodes():
        if _literal_strings(kw.value) is not None:
            continue
        if (isinstance(kw.value, ast.Name)
                and kw.value.id == "ALREADY_GONE_ERRORS"):
            continue
        computed.append((rel, kw.lineno, ast.dump(kw.value)[:60]))
    assert not computed, (
        f"suppress_errors built from a non-literal: {computed}. Use a "
        f"literal tuple, or safe_delete.ALREADY_GONE_ERRORS, so this "
        f"guard can read it."
    )


def test_the_named_constant_matches_the_declaration():
    """safe_delete.ALREADY_GONE_ERRORS must itself be fully declared.

    It is exempted from the literal check above, so without this it would
    be the one unaudited way in — the exemption would become the hole.
    """
    from posting.safe_delete import ALREADY_GONE_ERRORS
    undeclared = [s for s in ALREADY_GONE_ERRORS
                  if s not in SUPPRESSIONS_THAT_MEAN_ALREADY_ACHIEVED]
    assert not undeclared, f"undeclared in ALREADY_GONE_ERRORS: {undeclared}"
    banned = [s for s in ALREADY_GONE_ERRORS if s in NEVER_SUPPRESS]
    assert not banned, f"banned string in ALREADY_GONE_ERRORS: {banned}"


# ── PROVE the guard can fail ─────────────────────────────────────────────────

def test_the_guard_can_fail(tmp_path, monkeypatch):
    """Feed it the 2026-05-10 mistake and confirm it is caught."""
    # The method name is deliberately not the real one: the bypass guards
    # in test_no_direct_delete_bypass.py scan for it by string, and a
    # synthetic sample is not a call site. What is under test here is the
    # suppress_errors argument, which is faithful.
    bad = tmp_path / "regression.py"
    bad.write_text(
        "_post('someMethod', {}, 'd',\n"
        "      suppress_errors=('message can\\'t be deleted',))\n",
        encoding="utf-8")

    def fake_nodes():
        tree = ast.parse(bad.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg == "suppress_errors":
                        yield "regression.py", kw

    monkeypatch.setattr(
        "test_suppressed_errors_are_declared._suppress_nodes", fake_nodes)
    with __import__("pytest").raises(AssertionError, match="no declaration"):
        test_every_suppressed_string_is_declared()
