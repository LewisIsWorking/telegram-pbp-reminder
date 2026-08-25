"""Permanent status is paused. Nobody holds it, and the machinery stays.

Lewis, 2026-08-25: *"I want to pause perm player status. I think it
screws up player count numbers. Can we keep the logic but unassign
current perm players from being perm players?"*

He is right about the cause. ``_active_players`` counts a permanent
player however long they have been silent, which is correct for "who is
enrolled" and is exactly what made C04 Magni Guard read as 3/6 with a
seat 56 days quiet.

## What was paused, and what was NOT

Paused: three ids moved out of ``config["permanent_user_ids"]`` into
``permanent_user_ids_paused``, and one per-record ``permanent`` flag
cleared from state (Moss, set at some point via ``/setpermanent``).

Untouched: ``players/permanence.py``, ``/setpermanent``,
``/unsetpermanent``, and every consumer. The feature works. Nobody is
currently using it.

## ⚠️ This had teeth, and Lewis chose to let them bite

``permanent`` does two jobs: it counts the player, and it blocks
auto-removal at week 4. Lifting it hands the bot weeks of silence it was
previously told to ignore. Measured before the change, the next run
would remove Ryo from Riddleport (57d), Magni Guard (57d) and Doomsday
Funtime (28d), and Moss from Doomsday Funtime (125d), announcing each in
the group. Asked directly, Lewis chose **"let the removals fire"**.

Recorded because a future reader finding four removals on 2026-08-25
should find the decision, not a mystery.

## Why this file exists rather than just the config edit

A paused feature with nothing pinning the pause drifts back on. The
tests below fail the moment anybody is permanent again, so resuming has
to be deliberate: put the ids back AND update this file.
"""

import json
import os

from players.permanence import is_permanent

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _config() -> dict:
    with open(os.path.join(_ROOT, "config.json"), encoding="utf-8") as handle:
        return json.load(handle)


def _players() -> dict:
    path = os.path.join(_ROOT, "data", "state", "players.json")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle).get("players", {})


class TestNobodyIsPermanent:
    def test_the_config_list_is_empty(self):
        assert _config().get("permanent_user_ids") == []

    def test_no_player_record_carries_the_flag(self):
        # ⚠️ The second mechanism, and the easier one to forget. Emptying
        # the config list alone would have left Moss permanent, because
        # is_permanent is an OR of the two.
        flagged = [key for key, player in _players().items()
                   if player.get("permanent")]
        assert not flagged, f"still flagged permanent in state: {flagged}"

    def test_no_actual_player_resolves_as_permanent(self):
        # ⭐⭐ The one that matters. The two tests above check the two
        # inputs; this checks the ANSWER, through the real helper, for
        # every real player. A third mechanism appearing later would slip
        # past the other two and be caught here.
        config = _config()
        perm = [key for key, player in _players().items()
                if is_permanent(player, config)]
        assert not perm, f"still resolving as permanent: {perm}"


class TestTheMachineryStillWorks:
    # ⭐ Can-fail counterparts. Without these, deleting is_permanent
    # entirely would satisfy every test above. "Paused" has to mean the
    # feature is idle, not that it was quietly removed.

    def test_the_per_record_flag_still_confers_permanence(self):
        assert is_permanent({"user_id": "1", "permanent": True}, {})

    def test_the_config_list_still_confers_permanence(self):
        config = {"permanent_user_ids": [4242]}
        assert is_permanent({"user_id": "4242"}, config)

    def test_an_ordinary_player_does_not(self):
        assert not is_permanent({"user_id": "1"}, {"permanent_user_ids": []})

    def test_the_commands_still_exist(self):
        # Pausing must not have cost the GM the ability to resume by
        # hand. A config list is not the only way back.
        path = os.path.join(_ROOT, "scripts", "dispatch", "cmd_gm.py")
        with open(path, encoding="utf-8") as handle:
            body = handle.read()
        assert "/setpermanent" in body and "/unsetpermanent" in body


class TestResumingIsPossible:
    def test_the_paused_ids_were_preserved(self):
        # Deleting them would make "pause" a one-way door and force
        # somebody to work out who was permanent from git history.
        paused = _config().get("permanent_user_ids_paused")
        assert paused, "the paused ids are gone, so this cannot be undone"
        assert len(paused) == 3

    def test_they_are_not_in_both_lists(self):
        config = _config()
        live = {str(uid) for uid in config.get("permanent_user_ids") or []}
        paused = {str(uid) for uid in config.get("permanent_user_ids_paused") or []}
        assert not (live & paused), f"listed as both live and paused: {live & paused}"

    def test_the_reason_is_written_down_next_to_the_change(self):
        # ⚠️ A config key called "..._paused" with no note reads as debris
        # to the next person and gets deleted in a tidy-up.
        note = _config().get("_permanent_user_ids_note", "")
        assert "PAUSED" in note and "2026-08-25" in note
