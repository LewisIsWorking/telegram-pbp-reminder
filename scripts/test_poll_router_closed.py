"""``handle_poll_closed`` — the other fully-excluded poll path (2026-08-10).

``dispatch/poll_router.py`` carried 31 ``# pragma: no cover``, and the whole
of ``handle_poll_closed`` was inside them. The existing
``test_final_100_01_dispatch_router.py`` covers ``handle_poll_answer`` and
``build_poll_id_map`` but never this function, so its behaviour was
unverified *and* invisible to the coverage number.

It matters because it sets ``session_happened = True``, the flag that stops
poll pings for the rest of the week. If it fired on the wrong poll it would
silence a campaign that had not played; if it stopped firing, players would
be pinged after the session already happened.

Matching poll ids is the whole job, so the tests are built around getting
the *right* slot: correct campaign, not a sibling, swimming kept separate,
and unknown ids touching nothing.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

# pbp_topic_ids is required: handle_poll_answer does pair["pbp_topic_ids"][0]
# unguarded, so a pair without it raises KeyError. Real config always has it
# (validate_config enforces the shape) but it is worth knowing the access is
# not defensive.
_CFG = {"group_id": -100, "bot_topic_id": 5,
        "topic_pairs": [{"code": "C11", "name": "Dark Pockets",
                         "pbp_topic_ids": [40585], "chat_topic_id": 200}]}


def _closed(poll_id="p1", voters=4):
    return {"id": poll_id, "total_voter_count": voters, "is_closed": True}


def _texts(tg_mock):
    return " ".join(str(c.args[2]) for c in tg_mock.send_message.call_args_list)


class TestSessionPollClose:
    def test_marks_the_matching_campaign(self, tg_mock):
        from dispatch.poll_router import handle_poll_closed
        state = {"session_poll": {"C11": {"poll_id": "p1",
                                          "session_happened": False}}}
        handle_poll_closed(_closed(), _CFG, state)
        assert state["session_poll"]["C11"]["session_happened"] is True

    def test_announces_the_voter_count(self, tg_mock):
        from dispatch.poll_router import handle_poll_closed
        state = {"session_poll": {"C11": {"poll_id": "p1"}}}
        handle_poll_closed(_closed(voters=7), _CFG, state)
        text = _texts(tg_mock)
        assert "C11" in text and "7 voted" in text

    def test_does_not_touch_a_sibling_campaign(self, tg_mock):
        """The bug that would silence the wrong game."""
        from dispatch.poll_router import handle_poll_closed
        state = {"session_poll": {
            "C11": {"poll_id": "p1", "session_happened": False},
            "C06": {"poll_id": "p2", "session_happened": False}}}
        handle_poll_closed(_closed("p1"), _CFG, state)
        assert state["session_poll"]["C11"]["session_happened"] is True
        assert state["session_poll"]["C06"]["session_happened"] is False

    def test_unknown_poll_id_changes_nothing(self, tg_mock):
        from dispatch.poll_router import handle_poll_closed
        state = {"session_poll": {"C11": {"poll_id": "p1",
                                          "session_happened": False}}}
        handle_poll_closed(_closed("nope"), _CFG, state)
        assert state["session_poll"]["C11"]["session_happened"] is False
        assert not tg_mock.send_message.called

    def test_missing_poll_id_is_a_noop(self, tg_mock):
        """Guards the early return — an empty id must not match an empty slot."""
        from dispatch.poll_router import handle_poll_closed
        state = {"session_poll": {"C11": {"session_happened": False}}}
        handle_poll_closed({"id": "", "total_voter_count": 0}, _CFG, state)
        assert state["session_poll"]["C11"]["session_happened"] is False
        assert not tg_mock.send_message.called

    def test_no_bot_topic_still_marks_state(self, tg_mock):
        """The announcement is optional; the state change is not."""
        from dispatch.poll_router import handle_poll_closed
        cfg = {"group_id": -100, "topic_pairs": []}
        state = {"session_poll": {"C11": {"poll_id": "p1",
                                          "session_happened": False}}}
        handle_poll_closed(_closed(), cfg, state)
        assert state["session_poll"]["C11"]["session_happened"] is True
        assert not tg_mock.send_message.called


class TestSwimmingPollClose:
    def test_marks_swimming(self, tg_mock):
        from dispatch.poll_router import handle_poll_closed
        state = {"swimming_poll": {"poll_id": "s1",
                                   "session_happened": False}}
        handle_poll_closed(_closed("s1"), _CFG, state)
        assert state["swimming_poll"]["session_happened"] is True
        assert "Swimming poll closed" in _texts(tg_mock)

    def test_session_close_does_not_mark_swimming(self, tg_mock):
        """The two must stay independent."""
        from dispatch.poll_router import handle_poll_closed
        state = {"session_poll": {"C11": {"poll_id": "p1"}},
                 "swimming_poll": {"poll_id": "s1",
                                   "session_happened": False}}
        handle_poll_closed(_closed("p1"), _CFG, state)
        assert state["swimming_poll"]["session_happened"] is False

    def test_swimming_close_does_not_mark_a_session(self, tg_mock):
        from dispatch.poll_router import handle_poll_closed
        state = {"session_poll": {"C11": {"poll_id": "p1",
                                          "session_happened": False}},
                 "swimming_poll": {"poll_id": "s1"}}
        handle_poll_closed(_closed("s1"), _CFG, state)
        assert state["session_poll"]["C11"]["session_happened"] is False

    def test_no_swimming_poll_configured_is_a_noop(self, tg_mock):
        from dispatch.poll_router import handle_poll_closed
        state = {}
        handle_poll_closed(_closed("s1"), _CFG, state)
        assert not tg_mock.send_message.called


class TestVoteRetractionAndRevoting:
    """The revoting branches, also previously pragma-hidden.

    An empty ``option_ids`` is Telegram's signal that a user *retracted*
    their vote. If that were mishandled the voter would stay counted, and
    the poll tally the GM schedules around would be wrong.
    """

    def _answer(self, uid="9", option_ids=None, poll_id="p1"):
        return {"user": {"id": uid, "first_name": "Ann"},
                "option_ids": [] if option_ids is None else option_ids,
                "poll_id": poll_id}

    def test_retraction_removes_the_voter(self, tg_mock):
        from dispatch.poll_router import handle_poll_answer
        state = {"session_poll": {"C11": {"poll_id": "p1",
                                          "voted_uids": ["9"],
                                          "votes": {"0": ["9"]}}}}
        handle_poll_answer(self._answer(), _CFG, state)
        assert "9" not in state["session_poll"]["C11"]["voted_uids"]
        assert state["session_poll"]["C11"]["votes"]["0"] == []

    def test_retraction_by_a_non_voter_is_harmless(self, tg_mock):
        from dispatch.poll_router import handle_poll_answer
        state = {"session_poll": {"C11": {"poll_id": "p1",
                                          "voted_uids": ["other"]}}}
        handle_poll_answer(self._answer(), _CFG, state)
        assert state["session_poll"]["C11"]["voted_uids"] == ["other"]

    def test_revote_replaces_rather_than_duplicates(self, tg_mock):
        """Voting again must not leave the old option still counted."""
        from dispatch.poll_router import handle_poll_answer
        state = {"session_poll": {"C11": {
            "poll_id": "p1", "voted_uids": ["9"],
            "votes": {"0": ["9"]},
            "options": ["Mon 5pm", "Tue 5pm"]}}}
        handle_poll_answer(self._answer(option_ids=[1]), _CFG, state)
        votes = state["session_poll"]["C11"]["votes"]
        assert votes["0"] == [], "old option must be cleared"
        assert votes["1"] == ["9"]

    def test_stored_options_are_used_for_the_label(self, tg_mock):
        """Labels come from stored options, not from today's date.

        Votes can arrive days after the poll was posted, so recomputing
        the label from `now` would drift.
        """
        from dispatch.poll_router import handle_poll_answer
        state = {"session_poll": {"C11": {
            "poll_id": "p1", "options": ["Monday 5pm", "Tuesday 5pm"]}}}
        handle_poll_answer(self._answer(option_ids=[0]), _CFG, state)
        assert "Monday" in _texts(tg_mock)

    def test_out_of_range_option_index_is_ignored(self, tg_mock):
        from dispatch.poll_router import handle_poll_answer
        state = {"session_poll": {"C11": {
            "poll_id": "p1", "options": ["Monday 5pm"]}}}
        handle_poll_answer(self._answer(option_ids=[9]), _CFG, state)
        assert "?" in _texts(tg_mock)


class TestFindPairFallback:
    def test_unknown_code_returns_none(self):
        """The `return None` tail was pragma'd; it is the not-found path."""
        from dispatch.poll_router import find_pair
        assert find_pair(_CFG, "C99") is None

    def test_known_code_returns_the_pair(self):
        from dispatch.poll_router import find_pair
        assert find_pair(_CFG, "C11")["name"] == "Dark Pockets"
