"""Session-wide isolation of bot-sent-registry and refusal-log paths.

Imported by ``conftest.py`` at conftest-load time. The act of import is
the configuration: setting the module-level ``_STATE_PATH`` /
``_LOG_PATH`` / ``_ALERTED_PATH`` constants in
``posting.bot_sent_registry`` and ``posting.refusal_log`` to a
session-scoped tmp dir.

Why this lives in its own module:
  - Keeps ``conftest.py`` under the 200-line cap.
  - Keeps the side-effect contract explicit: importing this file
    redirects production state paths.

Why session-tmp rather than per-test:
  - ``test_telegram_*.py`` loads the *real* ``telegram.py`` via
    importlib so it can exercise the production HTTP wrappers with
    ``requests.post`` patched. Those wrappers call
    ``posting.bot_sent_registry.record_sent(mid)`` after a successful
    send. Without a session-level path override, the mocked send IDs
    (e.g. ``99``, ``77``, ``10``) leak into the real
    ``data/state/bot_sent_ids.json``.
  - ``posting.safe_delete`` has the same exposure for the refusal log.
  - Per-test fixtures that further monkeypatch these paths to their
    own ``tmp_path`` continue to work; pytest restores them to *this*
    session tmp dir at teardown, never to the production path.
"""

import tempfile
from pathlib import Path

from posting import bot_sent_registry as _bsr
from posting import refusal_log as _rl


_TEST_STATE_DIR = Path(tempfile.mkdtemp(prefix="pbpbot_test_state_"))

_bsr._STATE_PATH = _TEST_STATE_DIR / "bot_sent_ids.json"
_rl._LOG_PATH = _TEST_STATE_DIR / "refusal_log.json"
_rl._ALERTED_PATH = _TEST_STATE_DIR / "refusal_log_alerted.json"
