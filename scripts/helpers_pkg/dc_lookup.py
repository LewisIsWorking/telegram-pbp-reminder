"""
Helpers: DC lookup tables and functions.
"""


_STANDARD_DC = {
    0: 14, 1: 15, 2: 16, 3: 18, 4: 19, 5: 20, 6: 22, 7: 23, 8: 24,
    9: 26, 10: 27, 11: 28, 12: 30, 13: 31, 14: 32, 15: 34, 16: 35,
    17: 36, 18: 38, 19: 39, 20: 40,
}


# Difficulty adjustments (added to standard DC)
_DC_ADJUSTMENTS = {
    "incredibly easy": -10,
    "very easy": -5,
    "easy": -2,
    "standard": 0,
    "hard": +2,
    "very hard": +5,
    "incredibly hard": +10,
}


# Proficiency-based DCs (Table 10-4)
_PROF_DC = {
    "untrained": 10,
    "trained": 15,
    "expert": 20,
    "master": 30,
    "legendary": 40,
}


# Aliases for fuzzy matching
_DC_ALIASES = {
    "ie": "incredibly easy", "trivial": "incredibly easy",
    "ve": "very easy",
    "e": "easy",
    "s": "standard", "normal": "standard", "medium": "standard",
    "h": "hard",
    "vh": "very hard",
    "ih": "incredibly hard", "extreme": "incredibly hard",
    "u": "untrained", "t": "trained", "ex": "expert",
    "m": "master", "l": "legendary", "leg": "legendary",
}



def dc_lookup(query: str) -> str:
    """Look up a Pathfinder 2e DC.

    Supports:
    - "5" → standard DC for level 5
    - "5 hard" → hard DC for level 5
    - "trained" → proficiency DC
    - "hard" → just the adjustment info
    """
    query = query.strip().lower()
    if not query:
        return _dc_help()

    parts = query.split(None, 1)

    # Try pure level number
    try:
        level = int(parts[0])
        if level < 0 or level > 20:
            return "Level must be 0–20."
        difficulty = parts[1].strip() if len(parts) > 1 else None

        base_dc = _STANDARD_DC[level]

        if difficulty is None:
            # Show all difficulties for this level
            lines = [f"DCs for Level {level} (base DC {base_dc}):", ""]
            for name, adj in _DC_ADJUSTMENTS.items():
                dc = base_dc + adj
                marker = " ◄" if name == "standard" else ""
                sign = f"+{adj}" if adj > 0 else str(adj) if adj < 0 else "±0"
                lines.append(f"  {name.title():20s} DC {dc:2d}  ({sign}){marker}")
            return "\n".join(lines)
        else:
            # Specific difficulty
            diff_key = _DC_ALIASES.get(difficulty, difficulty)
            if diff_key in _DC_ADJUSTMENTS:
                adj = _DC_ADJUSTMENTS[diff_key]
                dc = base_dc + adj
                return f"Level {level} {diff_key.title()}: DC {dc}"
            else:
                return f"Unknown difficulty: {difficulty}\nTry: easy, standard, hard, very hard"

    except ValueError:
        pass

    # Try proficiency or difficulty name
    key = _DC_ALIASES.get(parts[0], parts[0])
    full_query = _DC_ALIASES.get(query, query)

    if full_query in _PROF_DC:
        return f"{full_query.title()} proficiency DC: {_PROF_DC[full_query]}"
    if key in _PROF_DC:
        return f"{key.title()} proficiency DC: {_PROF_DC[key]}"

    if full_query in _DC_ADJUSTMENTS:
        adj = _DC_ADJUSTMENTS[full_query]
        sign = f"+{adj}" if adj > 0 else str(adj) if adj < 0 else "±0"
        return f"{full_query.title()} adjustment: {sign} to standard DC\nUse '/dc <level> {full_query}' for a specific DC."
    if key in _DC_ADJUSTMENTS:
        adj = _DC_ADJUSTMENTS[key]
        sign = f"+{adj}" if adj > 0 else str(adj) if adj < 0 else "±0"
        return f"{key.title()} adjustment: {sign} to standard DC\nUse '/dc <level> {key}' for a specific DC."

    return _dc_help()



def _dc_help() -> str:
    return (
        "Usage: /dc <level> [difficulty]\n"
        "  /dc 5         → all DCs for level 5\n"
        "  /dc 5 hard    → hard DC for level 5\n"
        "  /dc trained   → proficiency DC\n\n"
        "Difficulties: incredibly easy, very easy, easy,\n"
        "standard, hard, very hard, incredibly hard\n"
        "Proficiencies: untrained, trained, expert, master, legendary"
    )
