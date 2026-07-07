"""Regression test: nothing in production may bypass the unpin guard.

Companion to ``test_no_direct_delete_bypass.py``. Unpinning has the same
danger as deletion: a bot with admin rights can unpin **any** message in
a group (Telegram has no own-messages-only flag), so a raw
``unpinChatMessage`` call reaching a non-bot ID silently clears a GM's or
player's manual pin. The 2026-07-07 fix routed all unpins through
``posting.safe_delete.perform_guarded_unpin`` (the bot-sent-registry
guard). This test makes re-introducing a bypass structurally impossible
without a deliberate code review:

    * Any new ``unpinChatMessage`` reference outside the allow-list
      below fails the test.
    * Any new direct ``api.telegram.org/bot{token}/unpinChatMessage``
      URL construction fails the test.
    * Any new caller passing ``"unpinChatMessage"`` as a positional arg
      to a function fails the test (unless it's safe_delete itself).

If you genuinely need to unpin from a new place, route it through
``telegram.unpin_message`` (which delegates to
``posting.safe_delete.perform_guarded_unpin``) and add no new
``unpinChatMessage`` references. If a new benign mention is necessary
(e.g. another docstring), update the allow-list with a comment.

The audit covers ``scripts/`` and ``tools/``.
"""

import re
from pathlib import Path


# Allow-list: files where ``unpinChatMessage`` may legitimately appear.
# When adding a new entry, include a short comment explaining why.
ALLOWED_UNPINMESSAGE_FILES = {
    # The single guarded call site.
    "scripts/posting/safe_delete.py",
    # Test that asserts the call site uses the right method name.
    "scripts/test_safe_delete.py",
    # Prose: documents that the queue poster unpins via the targeted
    # endpoint, never unpin-all. No API call.
    "scripts/test_topic_queue.py",
    # Documentation of _post's suppressed-error semantics. Mentions
    # ``unpinChatMessage`` only in prose; no API call here.
    "scripts/telegram_post_notes.py",
    # This file itself (must mention the term to test for it).
    "scripts/test_no_direct_unpin_bypass.py",
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


def test_no_unexpected_unpinmessage_references():
    """Every file mentioning ``unpinChatMessage`` must be on the allow-list.

    A new mention typically means either a new caller (which must go
    through telegram.unpin_message instead) or a new doc file (which
    should be added to the allow-list with a justification comment).
    """
    offenders = []
    for fp, rel in _all_python_files():
        try:
            content = fp.read_text(encoding="utf-8")
        except OSError:
            continue
        if "unpinChatMessage" not in content:
            continue
        if rel not in ALLOWED_UNPINMESSAGE_FILES:
            offenders.append(rel)

    assert not offenders, (
        f"New file(s) mention 'unpinChatMessage' without being on the "
        f"allow-list: {offenders}. Either route the call through "
        f"telegram.unpin_message (which goes through the safety guard) "
        f"or add the file to ALLOWED_UNPINMESSAGE_FILES with a comment "
        f"explaining why the mention is benign."
    )


def test_no_direct_api_url_for_unpin():
    """No file constructs ``api.telegram.org/.../unpinChatMessage`` URLs.

    Even a file on the allow-list (because it documents the API) must
    NOT build a URL pointing directly at the unpin endpoint — that would
    bypass the registry guard exactly as the 2026-05-08 purge script
    bypassed the delete guard.
    """
    pattern = re.compile(
        r"api\.telegram\.org[^\"'\n]*unpinChatMessage", re.IGNORECASE,
    )
    offenders = []
    for fp, rel in _all_python_files():
        # This file names the URL pattern in its own docstring — skip it.
        if rel == "scripts/test_no_direct_unpin_bypass.py":
            continue
        try:
            content = fp.read_text(encoding="utf-8")
        except OSError:
            continue
        if pattern.search(content):
            offenders.append(rel)

    assert not offenders, (
        f"File(s) construct a direct unpinChatMessage URL: {offenders}. "
        f"Use telegram.unpin_message instead - it goes through the "
        f"posting.safe_delete guard."
    )


def test_only_safe_delete_calls_post_with_unpinmessage():
    """The only place a Python call passes 'unpinChatMessage' as the first
    argument to a function is posting/safe_delete.py.

    Catches the case where someone copy-pastes the call pattern into a
    new module and forgets to delegate through the guard.
    """
    pattern = re.compile(r"""\(\s*["']unpinChatMessage["']\s*,""")
    offenders = []
    for fp, rel in _all_python_files():
        try:
            content = fp.read_text(encoding="utf-8")
        except OSError:
            continue
        if pattern.search(content):
            if rel == "scripts/posting/safe_delete.py":
                continue
            offenders.append(rel)

    assert not offenders, (
        f"File(s) call something with 'unpinChatMessage' as first arg: "
        f"{offenders}. The only file allowed to do this is "
        f"posting/safe_delete.py - that's the guarded call site. "
        f"Other callers must use telegram.unpin_message."
    )
