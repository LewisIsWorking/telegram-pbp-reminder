"""
Helpers: topic_maps.
"""

import re

# ------------------------------------------------------------------ #
#  Topic mapping (multi-topic campaign support)
# ------------------------------------------------------------------ #
class TopicMaps:
    """Lookup container for campaign topic ID mappings."""
    __slots__ = ("to_canonical", "to_chat", "to_name", "all_pbp_ids",
                 "name_to_pid", "to_group")

    def __init__(self, to_canonical, to_chat, to_name, all_pbp_ids,
                 name_to_pid, to_group):
        self.to_canonical = to_canonical  # any pbp_topic_id (str) -> canonical pid
        self.to_chat = to_chat            # canonical pid -> chat_topic_id
        self.to_name = to_name            # canonical pid -> campaign name
        self.all_pbp_ids = all_pbp_ids    # set of all pbp topic id strings
        self.name_to_pid = name_to_pid    # lowercased name -> canonical pid
        self.to_group = to_group          # canonical pid -> group_id



_topic_maps_cache = (None, None)  # (config_id, TopicMaps)



def build_topic_maps(config: dict) -> TopicMaps:
    """Build lookup dicts from config's topic_pairs. Cached per config object."""
    global _topic_maps_cache
    if _topic_maps_cache[0] == id(config):
        return _topic_maps_cache[1]

    to_canonical = {}
    to_chat = {}
    to_name = {}
    to_group = {}
    all_pbp_ids = set()
    name_to_pid = {}
    global_gid = config.get("group_id", 0)
    for pair in config["topic_pairs"]:
        ids = pair["pbp_topic_ids"]
        canonical = str(ids[0])
        name = pair["name"]
        gid = pair.get("group_id", global_gid)
        to_chat[canonical] = pair["chat_topic_id"]
        to_name[canonical] = name
        to_group[canonical] = gid
        # Map full name and individual words for flexible matching
        name_to_pid[name.lower()] = canonical
        for word in name.lower().split():
            if len(word) >= 3 and word not in name_to_pid:
                name_to_pid[word] = canonical
        for tid in ids:
            tid_str = str(tid)
            to_canonical[tid_str] = canonical
            all_pbp_ids.add(tid_str)
    result = TopicMaps(to_canonical, to_chat, to_name, all_pbp_ids,
                       name_to_pid, to_group)
    _topic_maps_cache = (id(config), result)
    return result



def get_characters(config: dict, pid: str, state: dict | None = None) -> dict:
    """Return {user_id_str: character_name} for a campaign.

    Checks state['characters'] first (set via /setchar), then config.
    """
    result = {}
    # Config characters (base)
    for pair in config.get("topic_pairs", []):
        all_ids = [str(pair.get("chat_topic_id", ""))] + [str(x) for x in pair.get("pbp_topic_ids", [])]
        if pid in all_ids:
            chars = pair.get("characters", {})
            result = {str(k): v for k, v in chars.items()}
            break
    # State overrides (from /setchar)
    if state:
        state_chars = state.get("characters", {}).get(pid, {})
        result.update(state_chars)
    return result


def character_name(config: dict, pid: str, user_id: str,
                   state: dict | None = None) -> str | None:
    """Look up a user's character name for a campaign, or None."""
    return get_characters(config, pid, state).get(str(user_id))



def players_by_campaign(state: dict) -> dict:
    """Group active players by canonical topic ID. Returns {pid: [player_dict, ...]}."""
    campaigns = {}
    for player_key, player in state.get("players", {}).items():
        pid = player["pbp_topic_id"]
        campaigns.setdefault(pid, []).append(player)
    return campaigns



def get_topic_timestamps(state: dict, pid: str) -> dict:
    """Get per-user timestamp dict for a campaign. Returns {uid: [iso_str, ...]}."""
    return state.get("post_timestamps", {}).get(pid, {})



def get_player(state: dict, pid: str, uid: str) -> dict:
    """Look up a player dict by campaign and user ID. Returns {} if not found."""
    return state.get("players", {}).get(f"{pid}:{uid}", {})



def campaign_dir_name(campaign_name: str) -> str:
    """Sanitise a campaign name for use as a directory name."""
    return campaign_name.replace(" ", "_").replace("/", "_")
