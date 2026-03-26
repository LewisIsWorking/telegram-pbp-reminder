"""Session poll vote handler — processes callback button presses."""


def handle_poll_vote(callback_query: dict, state: dict, config: dict) -> str | None:
    """Handle a poll button press. Returns response text or None."""
    data = callback_query.get("data", "")
    if not data.startswith("poll:"):
        return None

    choice = data.split(":")[1]
    if choice not in ("friday", "saturday"):
        return None

    user = callback_query.get("from", {})
    uid = str(user.get("id", ""))
    name = user.get("first_name", "?")

    poll = state.get("session_poll", {})

    # Remove previous vote if changing
    for day in ("friday", "saturday"):
        poll.setdefault(day, {}).pop(uid, None)

    # Record new vote
    poll.setdefault(choice, {})[uid] = name

    choice_label = choice.capitalize()
    return f"✅ {name} voted {choice_label}!"
