"""
Transcript post-link lookup for Player of the Week.

Scans a campaign's monthly transcript markdown for a winner's recent
posts and returns deep-links (or date fallbacks) to them. This is the
transcript-parsing concern, kept separate from the award logic in
``scheduled.potw``.

Extracted from ``scheduled/potw.py`` in v4.x to keep both modules under
the 200-line limit. ``scheduled.potw`` re-exports ``_find_player_post_links``
so ``player_of_the_week`` and test patch targets keep resolving. NOTE:
tests that control the transcript root patch ``scheduled.potw_links._LOGS_DIR``
(where the function reads it), not ``scheduled.potw._LOGS_DIR``.
"""

import re
from datetime import datetime, timezone
from pathlib import Path

from transcript.logger import sanitize_dirname

_LOGS_DIR = Path(__file__).parent.parent.parent / "data" / "pbp_logs"
_ENTRY_RE = re.compile(
    r'\*\*(.+?)\*\*(?:\s*\([^)]*\))?'
    r'(?:\s*\[GM\])?\s*\((\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})\)'
    r'(?:\s*msg#(\d+))?:\s*$'
)


def _find_player_post_links(campaign_name: str, player_first_name: str,
                            pid: str, since: datetime) -> list[str]:
    """Find a player's recent posts with links from transcript."""
    dirname = sanitize_dirname(campaign_name)
    month = since.strftime("%Y-%m")
    path = _LOGS_DIR / dirname / f"{month}.md"
    if not path.exists():
        return []
    links = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        m = _ENTRY_RE.match(line)
        if not m:
            continue
        author, date_str, time_str, msg_id = m.groups()
        if not author.startswith(player_first_name):
            continue  # pragma: no cover
        try:
            ts = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
            ts = ts.replace(tzinfo=timezone.utc)
            if ts < since:
                continue  # pragma: no cover
        except ValueError:  # pragma: no cover
            continue  # pragma: no cover
        if msg_id:
            links.append(f"🔗 https://t.me/Path_Wars/{pid}/{msg_id}")
        else:
            links.append(f"📝 {date_str} {time_str}")  # pragma: no cover
    return links
