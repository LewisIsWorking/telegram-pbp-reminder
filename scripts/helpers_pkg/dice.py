"""
Helpers: dice.
"""

import re
import random

# ------------------------------------------------------------------ #
#  Dice roller
# ------------------------------------------------------------------ #
def roll_dice(expression: str) -> dict:
    """Parse and evaluate a dice expression.

    Supports: NdX, NdX+M, NdX-M, NdXkhN (keep highest), NdXklN (keep lowest).
    Multiple dice groups separated by spaces are rolled independently.

    Returns: {"results": [{"expr": str, "rolls": [int], "kept": [int],
              "modifier": int, "total": int, "detail": str}], "label": str}
    """
    import re
    import random

    expression = expression.strip()
    if not expression:
        return {"results": [], "label": "", "error": "No dice expression given."}

    # Extract optional label (text after last dice expression)
    # Dice pattern: NdX possibly followed by kh/kl and +/-
    dice_re = re.compile(
        r"(\d*)d(\d+)"               # NdX (N optional, defaults to 1)
        r"(?:kh(\d+)|kl(\d+))?"      # optional keep highest/lowest
        r"([+\-]\d+)?",              # optional modifier
        re.IGNORECASE,
    )

    matches = list(dice_re.finditer(expression))
    if not matches:
        return {"results": [], "label": expression, "error": f"No valid dice found in: {expression}"}

    # Label is anything after the last match
    last_end = matches[-1].end()
    label = expression[last_end:].strip()

    results = []
    for m in matches:
        num_dice = int(m.group(1)) if m.group(1) else 1
        sides = int(m.group(2))
        keep_high = int(m.group(3)) if m.group(3) else None
        keep_low = int(m.group(4)) if m.group(4) else None
        modifier = int(m.group(5)) if m.group(5) else 0

        # Clamp for sanity
        num_dice = min(num_dice, 100)
        sides = max(sides, 1)
        sides = min(sides, 1000)

        rolls = [random.randint(1, sides) for _ in range(num_dice)]
        kept = rolls[:]

        if keep_high is not None:
            kept = sorted(rolls, reverse=True)[:keep_high]
        elif keep_low is not None:
            kept = sorted(rolls)[:keep_low]

        subtotal = sum(kept) + modifier

        # Build detail string
        expr_str = m.group(0)
        if len(rolls) == 1:
            detail = f"[{rolls[0]}]"
        else:
            roll_strs = []
            for r in rolls:
                if r in kept and kept.count(r) > roll_strs.count(str(r)):
                    roll_strs.append(str(r))
                else:
                    if keep_high is not None or keep_low is not None:
                        roll_strs.append(f"~~{r}~~")
                    else:
                        roll_strs.append(str(r))
            detail = "[" + ", ".join(roll_strs) + "]"

        if modifier > 0:
            detail += f" +{modifier}"
        elif modifier < 0:
            detail += f" {modifier}"

        results.append({
            "expr": expr_str,
            "rolls": rolls,
            "kept": kept,
            "modifier": modifier,
            "total": subtotal,
            "detail": detail,
        })

    return {"results": results, "label": label, "error": None}

#  DC Lookup (PF2e DC by level + difficulty adjustments)
# ------------------------------------------------------------------ #
# Standard DCs by level 0–20 (Core Rulebook Table 10-5)
