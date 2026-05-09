"""Regression test: nothing in production may bypass safe_delete.

The 2026-05-08 incident happened because a maintenance script called
Telegram's deleteMessage API directly via requests.post, bypassing
tg.delete_message and therefore the bot-sent-registry guard. This
test makes that mistake structurally impossible to re-introduce
without a deliberate code review:

    * Any new ``deleteMessage`` reference outside the allow-list
      below fails the test.
    * Any new direct ``api.telegram.org/bot{token}/deleteMessage``
      URL construction fails the test.
    * Any new caller passing ``"deleteMessage"`` as a positional arg
      to a function fails the test (unless it's safe_delete itself).

If you genuinely need to add a new caller, route it through
``telegram.delete_message`` (which delegates to
``posting.safe_delete.perform_guarded_delete``) and add no new
``deleteMessage`` references at all. If for some unusual reason a
new mention is necessary (e.g. another docstring), update the
allow-list with a comment explaining why.

The audit covers ``scripts/`` and ``tools/``.
"""

import re
from pathlib import Path


# Allow-list: files where ``deleteMessage`` may legitimately appear.
# When adding a new entry, include a short comment explaining why.
ALLOWED_DELETEMESSAGE_FILES = {
    # Documentation / comments only, no API calls
    "scripts/maintenance/purge_gm_queue_history.py",
    "scripts/posting/bot_sent_registry.py",
    "scripts/posting/message_batch.py",
    # The single guarded call site
    "scripts/posting/safe_delete.py",
    # Test that asserts the call site uses the right method name
    "scripts/test_safe_delete.py",
    # This file itself (must mention the term to test for it)
    "scripts/test_no_direct_delete_bypass.py",
}


def _all_python_files():
    """Yield every .py path under scripts/ and tools/."""
    repo_root = Path(__file__).resolve().parent.parent
    for sub in ("scripts", "tools"):
        sub_path = repo_root / sub
        if not sub_path.exists():
            continue
        for fp in sub_path.rglob("*.py"):
            if "__pycache__" in fp.parts or ".venv" in fp.parts:
                continue
            yield fp, fp.relative_to(repo_root).as_posix()


def test_no_unexpected_deletemessage_references():
    """Every file mentioning ``deleteMessage`` must be on the allow-list.

    A new mention typically means either a new caller (which must go
    through telegram.delete_message instead) or a new doc file (which
    should be added to the allow-list with a justification comment).
    """
    offenders = []
    for fp, rel in _all_python_files():
        try:
            content = fp.read_text(encoding="utf-8")
        except OSError:
            continue
        if "deleteMessage" not in content:
            continue
        if rel not in ALLOWED_DELETEMESSAGE_FILES:
            offenders.append(rel)

    assert not offenders, (
        f"New file(s) mention 'deleteMessage' without being on the "
        f"allow-list: {offenders}. Either route the call through "
        f"telegram.delete_message (which goes through the safety guard) "
        f"or add the file to ALLOWED_DELETEMESSAGE_FILES with a comment "
        f"explaining why the mention is benign."
    )


def test_no_direct_api_url_for_delete():
    """No file constructs ``api.telegram.org/.../deleteMessage`` URLs.

    Even if a file is on the deleteMessage allow-list (because it
    documents the API), it must NOT build a URL that points directly
    at the deleteMessage endpoint, since that's how the original
    purge script bypassed the guard.
    """
    pattern = re.compile(
        r"api\.telegram\.org[^\"'\n]*deleteMessage", re.IGNORECASE,
    )
    offenders = []
    for fp, rel in _all_python_files():
        # The bypass-test file itself mentions the URL pattern in its
        # own docstring as documentation — skip it for this check.
        if rel == "scripts/test_no_direct_delete_bypass.py":
            continue
        try:
            content = fp.read_text(encoding="utf-8")
        except OSError:
            continue
        if pattern.search(content):
            offenders.append(rel)

    assert not offenders, (
        f"File(s) construct a direct deleteMessage URL: {offenders}. "
        f"Use telegram.delete_message instead - it goes through the "
        f"posting.safe_delete guard."
    )


def test_only_safe_delete_calls_post_with_deletemessage():
    """The only place a Python call passes 'deleteMessage' as the first
    argument to a function is posting/safe_delete.py.

    Catches the case where someone copy-pastes the call pattern into
    a new module and forgets to delegate.
    """
    pattern = re.compile(r"""\(\s*["']deleteMessage["']\s*,""")
    offenders = []
    for fp, rel in _all_python_files():
        try:
            content = fp.read_text(encoding="utf-8")
        except OSError:
            continue
        if pattern.search(content):
            if rel != "scripts/posting/safe_delete.py":
                offenders.append(rel)

    assert not offenders, (
        f"File(s) call something with 'deleteMessage' as first arg: "
        f"{offenders}. The only file allowed to do this is "
        f"posting/safe_delete.py - that's the guarded call site. "
        f"Other callers must use telegram.delete_message."
    )
