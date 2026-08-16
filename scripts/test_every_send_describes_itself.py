"""Every send must describe what it sent, and no new sender may skip it.

COVERS  the capture wiring in ``bot_sent_registry.record_sent``, and a
        source scan of every ``record_sent`` call in production code.
MISSES  whether the preview is a *good* description. A human judges that.
PROVEN  by ``test_the_source_guard_can_fail``.

────────────────────────────────────────────────────────────────────────

Lewis, 2026-08-16: *"You should capture the message's contents and sender
so you know if it is an issue."*

Capture lives in ``record_sent`` rather than at each send site precisely
so it cannot be forgotten — every successful send already calls it. But
"cannot be forgotten" is a claim about code that does not exist yet, and
a claim like that needs a guard rather than a comment. A future
``send_photo`` that calls ``record_sent(mid)`` with no text would compile,
pass every other test, and quietly restore the bare-ID reports.

⚠️ The description is **best-effort by design**: ``sent_log.record``
swallows its own exceptions. A diagnostic must never be able to break a
send that has already happened. That is deliberate, and it is why the
wiring needs a test — a silent writer with no test is a writer that can
stop working unnoticed.
"""
import ast
from pathlib import Path

import pytest

from posting import bot_sent_registry as reg
from posting import sent_log


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    from state_store import StateStore
    store = StateStore(state_dir=tmp_path)
    monkeypatch.setattr(sent_log, "_store", store)
    monkeypatch.setattr(reg, "_store", store)
    sent_log.reset_for_test()
    reg.reset_for_test()
    return store


# ── The wiring ───────────────────────────────────────────────────────────────

def test_recording_a_send_captures_its_text(isolated):
    reg.record_sent(4242, "Unreplied: 2", 40585, "message")
    facts = sent_log.describe(4242)
    assert facts["preview"] == "Unreplied: 2"
    assert facts["thread_id"] == 40585
    assert facts["kind"] == "message"
    assert facts["at"]


def test_the_id_still_reaches_the_safety_registry(isolated):
    """The description must not displace the thing that guards deletes."""
    reg.record_sent(4242, "hello", 40585, "message")
    assert reg.is_bot_sent(4242) is True


def test_a_send_with_no_text_still_records_the_id(isolated):
    """Missing prose is a worse report, never a lost safety record."""
    reg.record_sent(4243)
    assert reg.is_bot_sent(4243) is True
    assert sent_log.describe(4243) is not None


def test_whitespace_is_collapsed_and_text_truncated(isolated):
    reg.record_sent(4244, "a\n\n  multi   line\nmessage " + "x" * 200)
    preview = sent_log.describe(4244)["preview"]
    assert preview.startswith("a multi line message")
    assert len(preview) <= sent_log.PREVIEW_CHARS


def test_a_broken_description_never_breaks_the_send(isolated, monkeypatch):
    """The swallow is deliberate; assert it rather than trusting it."""
    monkeypatch.setattr(sent_log, "_load",
                        lambda: (_ for _ in ()).throw(RuntimeError("disk")))
    reg.record_sent(4245, "hello")          # must not raise
    assert reg.is_bot_sent(4245) is True


def test_the_log_is_bounded(isolated, monkeypatch):
    """Unbounded growth would put a fat file in every CI checkout."""
    monkeypatch.setattr(sent_log, "MAX_ENTRIES", 5)
    for i in range(12):
        sent_log.record(1000 + i, text=f"msg {i}")
    assert len(sent_log._load()) <= 5
    assert sent_log.describe(1011) is not None, "newest must survive"


# ── No future sender may skip it ─────────────────────────────────────────────

def _production_record_sent_calls():
    """Yield (relpath, lineno, n_args) for record_sent calls in production."""
    root = Path(__file__).resolve().parent
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root.parent).as_posix()
        if "__pycache__" in rel or "/test_" in rel or "test_" in path.name:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "record_sent"):
                yield rel, node.lineno, len(node.args) + len(node.keywords)


def test_every_production_send_passes_a_description():
    """A send that records only the ID puts a bare mid back in the alerts.

    ``record_many`` is exempt by construction — it takes IDs the bot is
    reconciling from state, not messages it just sent, so there is no
    text to capture.
    """
    bare = [(rel, line) for rel, line, n in _production_record_sent_calls()
            if n < 2]
    assert not bare, (
        f"record_sent called with only an ID at {bare}. Pass the message "
        f"text (and thread_id / kind) so a later delete failure can name "
        f"what it is about. A bare message_id cannot be triaged — that is "
        f"the whole reason this capture exists."
    )


def test_the_scan_actually_finds_the_real_call_sites():
    """A source guard over an empty set passes forever. Anchor it."""
    found = list(_production_record_sent_calls())
    files = {rel for rel, _, _ in found}
    assert "scripts/telegram.py" in files, (
        f"expected telegram.py among record_sent callers, saw {files}")
    assert len(found) >= 3, f"expected the three send helpers, saw {found}"


# ── PROVE the guard can fail ─────────────────────────────────────────────────

def test_the_source_guard_can_fail(tmp_path):
    """Feed the scanner a bare call and confirm it is flagged."""
    sample = tmp_path / "sender.py"
    sample.write_text("record_sent(mid)\n", encoding="utf-8")
    tree = ast.parse(sample.read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "record_sent"]
    assert calls, "the scanner's own pattern must match a bare call"
    assert len(calls[0].args) + len(calls[0].keywords) < 2, (
        "if this fails the arity check in the guard above is meaningless")
