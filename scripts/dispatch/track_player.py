"""Keeping one player's roster record up to date when they post.

Extracted from dispatch/tracking.py on 2026-09-02 at 210 lines, when
the merge-not-replace fix landed.

⛔⛔ The split is not cosmetic. This module is where the bot's OWN
observations meet a human's DECISIONS on the same dict, and conflating
those two owners is what silently deleted every /setpermanent in the
repository for months. See the comment on the merge below.
"""

import helpers
import telegram as tg


def _track_player(parsed: dict, state: dict, config: dict,
                  gm_ids: set, maps) -> None:
    """Update player roster, handle away auto-clear and rejoin notifications."""
    pid = parsed["pid"]
    user_id = parsed["user_id"]
    user_name = parsed["user_name"]
    campaign_name = parsed["campaign_name"]
    msg_time_iso = parsed["msg_time_iso"]
    text = parsed["text"]
    group_id = config["group_id"]

    # Auto-clear away when player posts (non-command)
    if not text.startswith("/"):
        away_key = f"{pid}:{user_id}"
        if away_key in state.get("away", {}):
            del state["away"][away_key]
            print(f"Auto-cleared away for {user_name} in {campaign_name} (posted)")

    player_key = f"{pid}:{user_id}"
    was_removed = player_key in state["removed_players"]
    old_player = state.get("players", {}).get(player_key, {})
    old_warn_level = old_player.get("last_warned_week", 0)

    # ⛔⛔ MERGE, NEVER REPLACE. Until 2026-09-02 this was a wholesale
    # `state["players"][key] = {...}`, which silently deleted every field
    # a GM had set, the moment that player next posted.
    #
    # `/setpermanent` was the casualty and nobody noticed for months. The
    # live state carried **zero** records with `permanent`, and the only
    # field names present across all 40-odd records were exactly the
    # eight written here. `roster_members._active_players` carries a
    # long, carefully argued docstring about the permanent rule (L20,
    # "Lewis explicitly flagged this design on 2026-05-10") describing
    # behaviour that could not survive a single post.
    #
    # ⚠️ The eight below are the bot's OWN observations and must always
    # win. Everything else on the record belongs to whoever set it:
    # `permanent`, `played_by`, and anything added later.
    record = dict(old_player)
    record.update({
        "user_id": user_id,
        "first_name": user_name,
        "last_name": parsed["user_last_name"],
        "username": parsed["username"],
        "campaign_name": campaign_name,
        "pbp_topic_id": pid,
        "last_post_time": msg_time_iso,
        "last_warned_week": 0,
    })
    state["players"][player_key] = record

    if was_removed:
        removed_data = state["removed_players"].pop(player_key)
        __import__("players.history", fromlist=["on_rejoin"]).on_rejoin(pid, user_id, user_name, parsed.get("username", ""), state, config)
        chat_tid = maps.to_chat.get(pid)
        if chat_tid:
            char = helpers.character_name(config, pid, user_id)
            uname = parsed.get("username", "") or removed_data.get("username", "")
            mention = f" @{uname}" if uname else ""
            tag = f" ({char})" if char else ""
            tg.send_message(group_id, chat_tid,
                            f"\U0001f44b{mention} {user_name}{tag} is back in {campaign_name}!")
    elif not old_player:
        # ⚠️ A brand new person, arriving the ordinary way: by posting.
        # Every other branch here assumes we have seen them before, and
        # until 2026-08-27 a first-time poster fell through ALL of them.
        # They were written into state["players"] above and nothing else
        # happened: no player_history entry and no roster post to the
        # campaign topic. on_join existed, was correct, and was only
        # ever called by /addplayer, so organic arrivals were invisible
        # in the history Lewis actually reads.
        #
        # Found when C07 read 6/6 and he asked whether that was real. It
        # was: Paul had joined by posting. So had Volf and Alastair in
        # C04. None of the three appear in player_history.
        #
        # ⚠️ The history entry is written for ANY first message, so the
        # history never disagrees with the roster: the seat above is
        # written unconditionally, so the record of it must be too.
        # The roster POST is suppressed for commands, matching every
        # other announcement in this file (the comeback check and the
        # transcript both skip `/`). Passing config=None is how on_join
        # already expresses "log it, do not announce it".
        #
        # test_checker_misc_b.py::test_pick_vote caught this: a stranger
        # typing /pick is seated by the code above, and announcing that
        # as an arrival put a roster post after the vote confirmation.
        from players.history import on_join
        on_join(pid, user_id, user_name, parsed.get("username", ""),
                state, None if text.startswith("/") else config)
    elif old_warn_level >= 2:
        print(f"Warned player {user_name} returned to {campaign_name}")  # pragma: no cover
        chat_tid = maps.to_chat.get(pid)  # pragma: no cover
        if chat_tid:  # pragma: no cover
            char = helpers.character_name(config, pid, user_id)  # pragma: no cover
            uname = parsed.get("username", "") or old_player.get("username", "")  # pragma: no cover
            mention = f" @{uname}" if uname else ""  # pragma: no cover
            tag = f" as {char}" if char else ""  # pragma: no cover
            tg.send_message(group_id, chat_tid,  # pragma: no cover
                            f"\U0001f389{mention} {user_name} is back{tag}! Good to see you.")
    elif old_player.get("last_post_time") and not text.startswith("/"):
        from dispatch.comeback import check_comeback
        check_comeback(parsed, old_player, state, config, gm_ids)
