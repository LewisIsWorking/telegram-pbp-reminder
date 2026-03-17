"""Archives of Nethys search command."""

import requests

AON_URL = "https://elasticsearch.aonprd.com/aon/_search"
AON_BASE = "https://2e.aonprd.com"

_CATEGORY_ICONS = {
    "spell": "🔮",
    "feat": "⭐",
    "action": "⚡",
    "equipment": "🛡️",
    "weapon": "⚔️",
    "armor": "🛡️",
    "condition": "💫",
    "trait": "🏷️",
    "ancestry": "👤",
    "class": "📖",
    "archetype": "📜",
    "deity": "🙏",
    "domain": "✨",
    "skill": "🎯",
}


def handle_search(query: str, group_id: int, topic_id: int, tg) -> None:
    """Search Archives of Nethys and post results."""
    if not query.strip():
        tg.send_message(group_id, topic_id,
                        "Usage: /search <query>\nExample: /search fireball")
        return

    print(f"AoN search: '{query}'")
    try:
        resp = requests.post(AON_URL, json={
            "query": {
                "bool": {
                    "must": {
                        "multi_match": {
                            "query": query,
                            "fields": ["name^3", "text"],
                            "type": "best_fields",
                        }
                    },
                    "must_not": [
                        {"term": {"exclude_from_search": True}},
                        {"term": {"category": "creature"}},
                        {"term": {"category": "hazard"}},
                    ],
                }
            },
            "size": 5,
            "_source": [
                "name", "category", "url", "level", "type",
                "rarity", "summary", "actions", "tradition",
            ],
        }, timeout=10)
    except requests.RequestException as e:
        tg.send_message(group_id, topic_id, f"AoN search failed: {e}")
        return

    if resp.status_code != 200:
        tg.send_message(group_id, topic_id,
                        f"AoN search error (HTTP {resp.status_code})")
        return

    data = resp.json()
    hits = data.get("hits", {}).get("hits", [])
    total = data.get("hits", {}).get("total", {}).get("value", 0)

    if not hits:
        tg.send_message(group_id, topic_id,
                        f"No results for \"{query}\".")
        return

    lines = [f"🔍 AoN: \"{query}\" ({total} results)\n"]

    # Blocked categories (GM-only info that would spoil encounters)
    _BLOCKED = {"creature", "hazard"}
    seen = set()
    for hit in hits:
        s = hit["_source"]
        name = s.get("name", "?")
        category = s.get("category", "")

        if category in _BLOCKED:
            continue
        url = s.get("url", "")
        level = s.get("level")
        rarity = s.get("rarity", "common")
        summary = s.get("summary", "")
        actions = s.get("actions", "")

        # Skip duplicate names (e.g. remaster + legacy fireball)
        key = (name.lower(), category)
        if key in seen:
            continue
        seen.add(key)

        icon = _CATEGORY_ICONS.get(category, "📄")
        full_url = f"{AON_BASE}{url}" if url else ""

        header = f"{icon} {name}"
        if level is not None:
            header += f" (Lv {level})"
        if rarity and rarity != "common":
            header += f" [{rarity}]"
        if actions:
            header += f" {actions}"

        entry = header
        if summary:
            entry += f"\n{summary}"
        if full_url:
            entry += f"\n{full_url}"

        lines.append(entry)

    result = "\n\n".join(lines)
    print(f"AoN: {len(hits)} hits, sending {len(result)} chars")
    tg.send_message(group_id, topic_id, result)
