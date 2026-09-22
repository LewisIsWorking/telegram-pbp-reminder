"""A new aux file must be in the schema BEFORE it is ever written.

⛔ 2026-09-22: ``posting.sent_by_chat`` added ``bot_sent_ids_by_chat``
and the whole suite passed, including
``test_every_top_level_state_file_is_known`` - because that test walks
``data/state/`` and the file did not exist yet. It appeared on the first
real run after the merge, the schema check then failed, two runs in a
row failed, and the bot paused itself.

So the on-disk check cannot be the only one: it can only see state that
already exists, which by definition excludes every state file a PR
introduces. This reads the aux NAMES out of the source instead, so a new
one is caught while it is still only code.
"""

import ast
from pathlib import Path

import pytest

from state_store.schema import all_top_level_names

SCRIPTS = Path(__file__).resolve().parent


def _declared_aux_names():
    """Yield (relpath, name) for every literal aux name in production code.

    Two shapes, both used in this repo: a module-level ``_AUX_NAME = "x"``
    constant, and a literal passed straight to ``load_aux``/``save_aux``.
    """
    for path in sorted(SCRIPTS.rglob("*.py")):
        rel = path.relative_to(SCRIPTS.parent).as_posix()
        if "__pycache__" in rel or path.name.startswith(("test_", "_test_")):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):  # pragma: no cover - unreadable file
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                    and any(getattr(t, "id", "").endswith("AUX_NAME")
                            for t in node.targets)):
                yield rel, node.value.value
            if (isinstance(node, ast.Call)
                    and getattr(node.func, "attr", "") in ("load_aux", "save_aux")
                    and node.args and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                yield rel, node.args[0].value


def test_the_scan_finds_the_real_aux_names():
    """A source guard over an empty set passes forever. Anchor it."""
    found = {name for _, name in _declared_aux_names()}
    assert {"bot_sent_ids", "bot_sent_ids_by_chat", "sent_messages"} <= found, found


@pytest.mark.parametrize("rel,name", sorted(set(_declared_aux_names())))
def test_every_aux_name_in_the_source_is_in_the_schema(rel, name):
    assert name in all_top_level_names(), (
        f"{rel} writes data/state/{name}.json but no schema entry declares "
        f"it. Add it to state_store/schema.py (AUX_FILES) with who reads and "
        f"writes it. Waiting for the file to appear on disk means the first "
        f"production run fails, not CI."
    )
