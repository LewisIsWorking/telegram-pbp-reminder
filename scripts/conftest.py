"""
Pytest configuration for the PathWarsNudgeBot test suite.

Installs a mock telegram module into sys.modules before any test file
is collected or imported. This ensures that:
- test_checker.py's mock is consistent across all test files
- Modules that do `import telegram as tg` at module-level get the mock
- No real Telegram API calls are ever made during tests

The mock provides all functions currently used by production code.
Any new telegram.py function must be added here to avoid AttributeError
contamination that silently breaks unrelated tests.
"""

import sys
import types

_sent_messages: list = []
_mock_tg = types.ModuleType("telegram")
_mock_tg.TELEGRAM_API = ""


def _mock_init(token: str) -> None:
    pass


def _mock_send(group_id, topic_id, text, parse_mode=None) -> bool:
    _sent_messages.append({
        "group_id": group_id, "topic_id": topic_id,
        "text": text, "type": "message",
    })
    return True


def _mock_send_buttons(group_id, topic_id, text, buttons) -> int:
    _sent_messages.append({
        "group_id": group_id, "topic_id": topic_id,
        "text": text, "buttons": buttons, "type": "buttons",
    })
    return 99999


def _mock_edit(chat_id, message_id, text,
               parse_mode=None, remove_keyboard=False) -> bool:
    _sent_messages.append({
        "chat_id": chat_id, "message_id": message_id,
        "text": text, "type": "edit",
    })
    return True


def _mock_answer(cb_id, text="") -> bool:
    _sent_messages.append({"cb_id": cb_id, "text": text, "type": "answer"})
    return True


def _mock_get_updates(offset: int) -> list:
    return []


def _mock_send_poll(chat_id, thread_id, question, options,
                    is_anonymous=False, allows_multiple_answers=False,
                    allows_adding_options=False, allows_revoting=False,
                    open_period=None, explanation=None):
    _sent_messages.append({
        "type": "poll", "chat_id": chat_id,
        "question": question, "options": options,
    })
    return (99998, "mock_poll_id_001")


def _mock_pin_message(chat_id, message_id,
                      disable_notification=True) -> bool:
    _sent_messages.append({
        "type": "pin", "chat_id": chat_id, "message_id": message_id,
    })
    return True


def _mock_message_link(group_id, topic_id, message_id,
                       group_username=None) -> str:
    return f"https://t.me/mock/{topic_id}/{message_id}"


def _mock_send_id(chat_id, thread_id, text, parse_mode=None,
                  silent=False) -> int | None:
    _sent_messages.append({
        "group_id": chat_id, "topic_id": thread_id,
        "text": text, "type": "message_id", "silent": silent,
    })
    return 99997


def _mock_unpin(chat_id, message_id) -> bool:
    _sent_messages.append({"type": "unpin", "chat_id": chat_id, "message_id": message_id})
    return True


# Install all functions
_mock_tg.init = _mock_init
_mock_tg.send_message = _mock_send
_mock_tg.send_message_id = _mock_send_id
_mock_tg.send_message_with_buttons = _mock_send_buttons
_mock_tg.edit_message = _mock_edit
_mock_tg.answer_callback = _mock_answer
_mock_tg.get_updates = _mock_get_updates
_mock_tg.send_poll = _mock_send_poll
_mock_tg.pin_message = _mock_pin_message
_mock_tg.unpin_message = _mock_unpin
_mock_tg.message_link = _mock_message_link


def _mock_delete(chat_id: int, message_id: int) -> bool:
    _sent_messages.append({"type": "delete", "chat_id": chat_id, "message_id": message_id})
    return True


_mock_tg.delete_message = _mock_delete

# Register before any test module is imported
sys.modules["telegram"] = _mock_tg


# Session-wide isolation of bot_sent_registry and refusal_log state paths.
# Importing this module sets module-level path constants to a tmp dir;
# see ``_test_state_isolation.py`` for the rationale.
import _test_state_isolation  # noqa: F401, E402


# ---------------------------------------------------------------------------
# Shared fixture: patch ``tg`` in every module the queue-posting flow
# touches, routing all calls through one MagicMock instance.
#
# Background: production code lives across several modules
#
#   scheduled.gm_queue_history
#   scheduled.topic_queue_poster
#   posting.sender
#   posting.message_batch
#
# Each does ``import telegram as tg`` and calls ``tg.foo(...)`` directly.
# ``unittest.mock.patch("<module>.tg", …)`` only replaces the binding in
# *that* module's namespace, so a single per-module patch misses the
# others. Tests that span the full posting flow need to patch all four
# locations or assertions go missed.
#
# This fixture installs the same ``MagicMock`` in every relevant module
# so a single ``tg_mock.delete_message.assert_called_once(…)`` works
# regardless of which module made the call.
# ---------------------------------------------------------------------------
import pytest
from pathlib import Path
from unittest.mock import MagicMock


_TG_MODULE_NAMES: list[str] | None = None


def tg_importing_modules() -> list[str]:
    """Every non-test module in this package that does ``import telegram as tg``.

    Not used by the fixture (see below) but kept as the documented surface
    the fixture has to cover, and asserted on by
    ``test_tg_mock_coverage.py``.
    """
    global _TG_MODULE_NAMES
    if _TG_MODULE_NAMES is None:
        root = Path(__file__).parent
        found = []
        for path in root.rglob("*.py"):
            if path.name.startswith("test_") or path.name == "conftest.py":
                continue
            if "__pycache__" in path.parts:
                continue
            try:
                src = path.read_text(encoding="utf-8")
            except OSError:  # pragma: no cover - unreadable file
                continue
            if "import telegram as tg" not in src:
                continue
            rel = path.relative_to(root).with_suffix("")
            found.append(".".join(rel.parts))
        _TG_MODULE_NAMES = sorted(found)
    return _TG_MODULE_NAMES


@pytest.fixture
def tg_mock():
    """Yield a ``MagicMock`` standing in for telegram in EVERY module.

    History — this fixture used to hand-list its patch targets, and
    drifted badly: it named 8 modules while 56 import ``telegram as tg``.
    Any test using it against one of the other 48 asserted on a mock the
    code never touched, so ``assert not tg_mock.send_message.called``
    passed no matter what the code did. Two POTW guards were exactly
    that; proven on 2026-08-10 by deleting the POTW Monday gate and
    watching the suite stay green.

    Rather than patch 56 module attributes (correct, but it tripled suite
    runtime), this swaps the callables on the **shared telegram module
    object**. Every module does ``import telegram as tg``, and nothing
    anywhere does ``from telegram import <name>`` — verified by the guard
    test — so they all hold a reference to that one object. Swapping its
    attributes therefore reaches all of them at once, covers modules
    added in future with no registration step, and is O(1).
    """
    import telegram as tg_module
    mock = MagicMock()
    saved: dict = {}
    for attr in dir(tg_module):
        if attr.startswith("_"):
            continue
        value = getattr(tg_module, attr)
        if callable(value):
            saved[attr] = value
            setattr(tg_module, attr, getattr(mock, attr))
    mock.patched_attrs = sorted(saved)
    try:
        yield mock
    finally:
        for name, value in saved.items():
            setattr(tg_module, name, value)
