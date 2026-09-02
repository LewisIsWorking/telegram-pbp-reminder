"""Where the recruit advert's link points.

⛔ The **chat** topic, not the pbp topic. Lewis, 2026-09-02, on the live
C01 advert:

> *"why does this not link to DF chat? https://t.me/Path_Wars/21514 is
> the DF Chat."*

It linked to `25059`, C01's in-character thread. The link sits directly
under *"↗ Know someone?"*, so it is the one you forward to a prospective
player, and it was dropping them somewhere they cannot ask to join
without posting out of character in the middle of a scene.

⚠️ It matters most in the **mirror** copy. The advert goes to two places
(see ``recruit_focus_post.py``): the campaign's own chat topic, where a
reader is already in the right room and the link is a nicety, and the
standing "what campaign needs people most" topic in Nudge Bot
Notifications, where **this link is the only route to the campaign at
all**. There, the wrong link is the whole message.

Self-referential in the campaign's own chat topic, which is harmless:
Telegram resolves it to the topic you are already reading.

The fallback keeps a link on the post for a campaign configured without
a ``chat_topic_id``. An advert with no way to reach the campaign is
worse than one pointing at the wrong thread, and
``recruit_focus_post.recruit_destination`` already prints a warning for
that case rather than letting it pass silently.
"""


def recruit_link(pair: dict, config: dict) -> str:
    """The ``🔗`` line for the advert, or "" when the group has no username.

    Private groups have no ``t.me/<name>`` form, so there is nothing
    useful to print and the line is omitted rather than faked.
    """
    username = config.get("group_username", "")
    if not username:
        return ""
    topic = pair.get("chat_topic_id") or pair["pbp_topic_ids"][0]
    return f"\U0001f517 https://t.me/{username}/{topic}"
