"""
Multi-group campaign helpers.

Campaigns that run in a separate Telegram group (e.g. C11 Dark Pockets)
carry a ``group_id`` override in their topic_pair. These helpers provide
a consistent way to resolve the correct group and discover linked polls.
"""


def group_id_for_campaign(config: dict, pid: str) -> int:
    """Return the Telegram group_id for a campaign.

    Falls back to the global group_id if the campaign has no override.
    """
    for pair in config.get("topic_pairs", []):
        if str(pair["pbp_topic_ids"][0]) == pid:
            return pair.get("group_id", config["group_id"])
    return config["group_id"]


def linked_poll_codes(config: dict, pid: str) -> list[str]:
    """Return codes of campaigns whose polls are linked to this one.

    Used for cross-campaign vote notifications (e.g. C01 ↔ C11).
    """
    for pair in config.get("topic_pairs", []):
        if str(pair["pbp_topic_ids"][0]) == pid:
            return pair.get("linked_polls", [])
    return []


def all_group_ids(config: dict) -> set[int]:
    """Return the set of all Telegram group IDs the bot operates in."""
    ids = {config["group_id"]}
    for pair in config.get("topic_pairs", []):
        if "group_id" in pair:
            ids.add(pair["group_id"])
    return ids


def pid_for_code(config: dict, code: str) -> str | None:
    """Return the canonical PID for a campaign code, or None."""
    for pair in config.get("topic_pairs", []):
        if pair.get("code") == code:
            return str(pair["pbp_topic_ids"][0])
    return None
