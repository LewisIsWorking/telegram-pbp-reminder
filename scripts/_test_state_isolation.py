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

P3/9 slice 1 update: bot_sent_registry now persists through
``StateStore``. The isolation hook for it is to install a tmp-rooted
StateStore on the registry module rather than monkeypatching a
``_STATE_PATH`` constant.

P3/9 slice 2 update: refusal_log now also persists through
``StateStore``. Same pattern — install a tmp-rooted StateStore on
the module rather than monkeypatching individual file paths.
"""

import tempfile
from pathlib import Path

from posting import bot_sent_registry as _bsr
from posting import refusal_log as _rl
from posting import pin_audit as _pa
from posting import sent_log as _sl
from posting import stuck_deletes as _sd
from state_store import StateStore


_TEST_STATE_DIR = Path(tempfile.mkdtemp(prefix="pbpbot_test_state_"))
_TEST_STORE = StateStore(state_dir=_TEST_STATE_DIR)

_bsr._store = _TEST_STORE
_rl._store = _TEST_STORE
# pin_audit records every pin/unpin the bot performs; isolate it too so
# the suite never writes to the real data/state/pin_audit_log.json.
_pa._store = _TEST_STORE
# stuck_deletes, added 2026-08-16. Before that date a delete Telegram
# refused wrote nothing anywhere, so no test could leak through this path
# — the write did not exist. Making the failure real made it leakable: the
# first full-suite run after the fix deposited a fixture's
# chat_id=-1001/mid=12345 into the real data/state/stuck_deletes.json,
# which CI would then have committed.
# ⭐ Any module newly persisting through StateStore belongs on this list.
# A fix that wakes a previously-dead write path is exactly when it bites.
_sd._store = _TEST_STORE
# sent_log, added 2026-08-16. record_sent now writes a description of
# every message the bot sends, and the suite sends a great many — so this
# is the highest-volume leak path of the lot, not a marginal one.
_sl._store = _TEST_STORE
