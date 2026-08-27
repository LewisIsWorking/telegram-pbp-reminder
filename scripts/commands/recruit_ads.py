"""The /recruitads and /recruityield messages.

``/recruitads``    which venues are due today, and what each one demands.
``/recruityield``  which venues have actually produced players.

The campaign being advertised is not chosen here. It comes from
``scheduled.recruit_focus``, which already answers "who needs players
most" for the in-group advert, so there is one source of truth and the
external ads can never disagree with the internal one.
"""

from datetime import datetime, timezone

from recruiting import catalogue, log, readiness, rotation


def _format_line(venue: dict) -> list:
    """The venue's own demands, only the parts that are actually set."""
    # ⚠️ The id is shown because the very next instruction is
    # "/recruitposted <venue-id>". Naming an argument the reader cannot
    # see makes the command unusable without opening the JSON file.
    lines = [f"\n• {venue['name']}", f"  id: {venue['id']}"]
    if venue.get("url"):
        lines.append(f"  {venue['url']}")
    source = venue.get("cooldown_source")
    # ⚠️ Say which cooldowns are guesses. An operator who believes an
    # assumed 7 days is a real rule will shorten it when impatient.
    qualifier = "stated rule" if source == "rule" else "ASSUMED, unverified"
    lines.append(f"  cooldown: {venue['cooldown_days']:g}d ({qualifier})")
    fmt = venue.get("format") or {}
    if fmt.get("title"):
        lines.append(f"  title: {fmt['title']}")
    if fmt.get("needs_flair"):
        lines.append("  needs a flair set")
    if fmt.get("max_chars"):
        lines.append(f"  max {fmt['max_chars']} chars")
    if venue.get("rules_note"):
        lines.append(f"  ⚠️ {venue['rules_note']}")
    return lines


def build_recruit_ads(config: dict, state: dict,
                      now: datetime | None = None,
                      venues: list | None = None) -> str:
    """Where to post today."""
    now = now or datetime.now(timezone.utc)
    try:
        venues = venues if venues is not None else catalogue.load()
    except (OSError, ValueError) as error:
        # Loud, because a silently empty rotation looks exactly like
        # "nothing due today" and would never be investigated.
        return f"⚠️ Could not read the venue catalogue: {error}"

    due = rotation.due_venues(state, now, venues)
    waiting = rotation.waiting_venues(state, now, venues)

    lines = ["\U0001f4e2 Recruitment: where to post"]

    pair = _focus_pair(config, state)
    if pair:
        label = _label(pair)
        if label:
            lines.append(f"\nAdvertising: {label}")
        # ⚠️ Before the venue list, not after. A warning printed under
        # three venues and a "post now" instruction is read second, if
        # at all. It is also NOT conditional on the label rendering:
        # the risk is the point, the name is decoration.
        quiet = readiness.warning(pair, state, now)
        if quiet:
            lines.append(quiet)

    if due:
        lines.append(f"\n── Due now ({len(due)}) ──")
        for venue in due:
            lines.extend(_format_line(venue))
        lines.append("\n✅ After posting: /recruitposted <venue-id>")
    else:
        lines.append("\n✅ Nothing due. Everything is cooling down.")

    if waiting:
        lines.append(f"\n── Cooling down ({len(waiting)}) ──")
        for venue, remaining in waiting[:6]:
            lines.append(f"• {venue['name']}: {remaining:.1f}d left")
            # The live advert, when its link was recorded. This is the
            # section where "where is the thing I posted" is the actual
            # question: it is up right now, and checking it for replies
            # or retiring it are the only two useful actions.
            posted_at = log.last_post_url(state, venue["id"])
            if posted_at:
                lines.append(f"  ↗ live: {posted_at}")

    lines.append("\n\U0001f4a1 When someone joins: /recruitjoined <venue-id> <name>")
    return "\n".join(lines)


def _focus_pair(config: dict, state: dict) -> dict | None:
    """The campaign recruit_focus would advertise, or None.

    Returns the pair rather than a label because the readiness check
    needs its topic ids. Failing softly: a missing campaign makes the
    message less useful, not wrong, and should not cost the operator the
    venue list they asked for.
    """
    try:
        from scheduled.recruit_focus import build_recruit_message
        _text, pair = build_recruit_message(config, state)
    except Exception:  # noqa: BLE001 - never fail the whole command for this
        return None
    return pair or None


def _label(pair: dict) -> str:
    code = pair.get("code", "")
    name = pair.get("name") or pair.get("campaign_name") or ""
    return f"{code}: {name}".strip(": ")


def build_recruit_yield(state: dict, venues: list | None = None) -> str:
    """Which venues have actually produced players."""
    try:
        venues = venues if venues is not None else catalogue.load()
    except (OSError, ValueError) as error:
        return f"⚠️ Could not read the venue catalogue: {error}"

    # creditable, not postable: a player who arrived through somebody's
    # personal network is a real result and belongs in the comparison,
    # even though there is nowhere to post an advert.
    rows = log.yield_table(state, catalogue.creditable(venues))
    lines = ["\U0001f4ca Recruitment yield\n"]
    for row in rows:
        if not row["rotates"]:
            # ⚠️ "never posted" is meaningless for a source you cannot
            # post to, and worse, it HID the players who came from it.
            # Paul rendered as "never posted" while being the only
            # arrival credited there.
            lines.append(f"• {row['name']}: {row['joins']} player(s), "
                         f"no advert involved")
            continue
        if not row["posts"]:
            lines.append(f"• {row['name']}: never posted")
            continue
        # ⚠️ per_post is None only when posts==0, handled above.
        lines.append(
            f"• {row['name']}: {row['joins']} from {row['posts']} "
            f"post(s) ({row['per_post']:.2f}/post)")

    missing = log.unattributed(state)
    if missing:
        lines.append(f"\n⚠️ {missing} join(s) with no venue recorded. "
                     f"Those cannot be credited to anything.")
    if not any(r["posts"] for r in rows):
        lines.append("\nNothing posted yet, so there is nothing to compare. "
                     "Run /recruitads.")
    return "\n".join(lines)
