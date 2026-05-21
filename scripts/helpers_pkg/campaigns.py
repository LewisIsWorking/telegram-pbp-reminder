"""
Campaign configuration lookup.

Centralizes access to campaign metadata from config.json.
Eliminates repeated iteration over topic_pairs across the codebase.
"""


def get_pair(config: dict, pid: str) -> dict | None:
    """Get the full topic_pair dict for a campaign PID."""
    for pair in config.get("topic_pairs", []):
        if str(pair["pbp_topic_ids"][0]) == pid:
            return pair
    return None  # pragma: no cover


def get_code(config: dict, pid: str) -> str:
    """Get campaign code (e.g. 'C06') for a PID."""
    pair = get_pair(config, pid)
    return pair.get("code", "") if pair else ""


def get_name(config: dict, pid: str) -> str:
    """Get campaign name for a PID."""
    pair = get_pair(config, pid)
    return pair.get("name", "Unknown") if pair else "Unknown"


def try_get_name(config: dict, pid: str) -> str | None:
    """Get campaign name for a PID, or None if it can't be resolved.

    Use this at any state-write boundary where persisting the literal
    string "Unknown" would poison data — callers should treat None as
    "skip the write" or fall back to a diagnosable sentinel (e.g. the
    topic_id) rather than baking "Unknown" into players.json.
    See potw.py:_potw_run and boons/handler.py:_resolve_campaign_name."""
    pair = get_pair(config, pid)
    if not pair:
        return None
    name = pair.get("name")
    return name if name else None


def get_label(config: dict, pid: str) -> str:
    """Get formatted label (e.g. 'C06: Kibwe') for a PID."""
    code = get_code(config, pid)
    name = get_name(config, pid)
    return f"{code}: {name}" if code else name


def is_hybrid(config: dict, pid: str) -> bool:
    """Check if campaign is a hybrid live+PBP campaign."""
    pair = get_pair(config, pid)
    return bool(pair.get("hybrid_live")) if pair else False


def is_priority(config: dict, pid: str) -> bool:
    """Check if campaign is queue-priority (pinned to top)."""
    pair = get_pair(config, pid)  # pragma: no cover
    return bool(pair.get("queue_priority")) if pair else False  # pragma: no cover


def is_excluded(config: dict, pid: str) -> bool:
    """Check if campaign is excluded from the queue."""
    pair = get_pair(config, pid)
    return bool(pair.get("queue_exclude")) if pair else False


def all_pids(config: dict) -> list[str]:
    """Return all campaign PIDs in config order."""
    return [str(pair["pbp_topic_ids"][0])
            for pair in config.get("topic_pairs", [])]


def iter_campaigns(config: dict):
    """Yield (pid, code, name, pair) for each campaign."""
    for pair in config.get("topic_pairs", []):
        pid = str(pair["pbp_topic_ids"][0])
        code = pair.get("code", "")
        name = pair.get("name", "Unknown")
        yield pid, code, name, pair
