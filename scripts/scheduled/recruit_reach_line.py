"""The closing "Know someone?" line of the recruit advert.

Split out of ``recruit_focus`` (2026-10-08) when it grew a third case.

⭐ Alone in its tier is not alone overall. Kibwe sits in tier -1, so on
2026-10-08 it was the only ELIGIBLE campaign and was posted as "the only
campaign currently below target" while C10 and C08 were both short in
later tiers. The claim is now made only when every tier agrees.
"""


def reach_line(eligible: int, short_total: int) -> str:
    """eligible: short campaigns in the chosen tier; short_total: in all."""
    if eligible > 1:
        return (f"↗ Know someone? This is the biggest gap of "
                f"{eligible} campaigns currently recruiting.")
    if short_total > 1:
        return "↗ Know someone? This table is first in line for new players."
    return "↗ Know someone? This is the only campaign currently below target."
