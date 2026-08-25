"""Keep the link to the advert, because it is only easy to get once.

2026-08-25, the first real posting: Lewis pasted the Discord permalink
into chat and ``record_post`` had nowhere to put it. Everything the
recruitment workflow wants to do afterwards needs that link, and none of
it is possible without one:

  check whether anybody replied
  bump the thread when the venue allows it
  take it down once the campaign fills

Hunting a channel by hand a fortnight later is the alternative, and in
practice the alternative is that nobody bothers.

⚠️ **The entry shape changed rather than growing a parallel structure.**
Post entries went from a bare ISO string to ``{"at": ..., "url": ...}``,
which deliberately broke every reader. Two of them turned out to be
tests asserting the old shape; the rest went through ``last_posted``,
which is where the compatibility now lives. A second dict keyed by
timestamp would have avoided the breakage and created two things to keep
in step forever. See ``change-the-signature-to-break-callers``.

Legacy entries still read correctly, because state files written before
today are not migrated on load and never will be.
"""

from datetime import datetime, timedelta, timezone

from recruiting import log

NOW = datetime(2026, 8, 25, 13, tzinfo=timezone.utc)
LINK = "https://discord.com/channels/260066959238889472/1541798442513211463"


class TestTheLinkIsKept:
    def test_a_url_survives_recording(self):
        state = {}
        log.record_post(state, "pf2e-discord-lfg", NOW, url=LINK)
        assert log.last_post_url(state, "pf2e-discord-lfg") == LINK

    def test_the_timestamp_still_works_alongside_it(self):
        # ⭐ can-fail counterpart: the cooldown maths reads the timestamp,
        # and adding a field must not cost the field the rotation needs.
        state = {}
        log.record_post(state, "paizo", NOW, url=LINK)
        assert log.last_posted(state, "paizo") == NOW.isoformat()

    def test_recording_without_a_url_is_still_valid(self):
        # A posting recorded with no link is worth far more than one not
        # recorded at all, so the url must never be required.
        state = {}
        log.record_post(state, "paizo", NOW)
        assert log.last_posted(state, "paizo") == NOW.isoformat()
        assert log.last_post_url(state, "paizo") == ""

    def test_the_newest_link_wins_not_the_first(self):
        # ⚠️ Two posts to one venue: "where is my advert" means the one
        # that is up now.
        state = {}
        log.record_post(state, "paizo", NOW - timedelta(days=30), url="old")
        log.record_post(state, "paizo", NOW, url="new")
        assert log.last_post_url(state, "paizo") == "new"

    def test_a_venue_never_posted_to_has_no_link(self):
        assert log.last_post_url({}, "paizo") == ""


class TestLegacyEntriesStillRead:
    # State written before 2026-08-25 holds bare ISO strings. It is not
    # migrated on load, so every reader has to cope forever.
    def _legacy(self):
        return {log.LOG_KEY: {"posts": {"paizo": [NOW.isoformat()]},
                              "joins": []}}

    def test_the_timestamp_is_read(self):
        assert log.last_posted(self._legacy(), "paizo") == NOW.isoformat()

    def test_the_missing_url_is_empty_not_a_crash(self):
        assert log.last_post_url(self._legacy(), "paizo") == ""

    def test_the_cooldown_still_applies_to_a_legacy_entry(self):
        # ⭐⭐ The one that would actually hurt: if a legacy entry stopped
        # parsing, its venue would read as never posted and the rotation
        # would offer it again immediately, which is how an account gets
        # muted for reposting too soon.
        from recruiting import rotation
        venue = {"id": "paizo", "name": "Paizo", "status": "candidate",
                 "cooldown_days": 14, "cooldown_source": "assumed",
                 "fit": "high", "format": {}}
        assert not rotation.is_due(venue, self._legacy(), NOW)

    def test_mixed_shapes_in_one_venue_both_count(self):
        state = self._legacy()
        log.record_post(state, "paizo", NOW + timedelta(days=20), url=LINK)
        assert len(log.posts_for(state, "paizo")) == 2
        assert log.last_post_url(state, "paizo") == LINK


class TestTheCommandAcceptsIt:
    def _ctx(self, text):
        return {"group_id": -1, "reply_topic": 9, "user_id": "GM",
                "text": text, "state": {}}

    def _run(self, text, monkeypatch):
        from dispatch import cmd_recruit
        sent = []
        monkeypatch.setattr(cmd_recruit.tg, "send_message",
                            lambda g, t, m: sent.append(m) or True)
        ctx = self._ctx(text)
        cmd_recruit.handle_recruit_write(text.split()[0], ctx, {"GM"})
        return ctx["state"], sent

    def test_a_pasted_link_is_stored(self, monkeypatch):
        state, _sent = self._run(
            f"/recruitposted pf2e-discord-lfg {LINK}", monkeypatch)
        assert log.last_post_url(state, "pf2e-discord-lfg") == LINK

    def test_without_a_link_it_says_so(self, monkeypatch):
        # ⚠️ A silently optional field never gets filled in. The reply has
        # to name the thing it did not get.
        _state, sent = self._run("/recruitposted pf2e-discord-lfg", monkeypatch)
        assert "link" in " ".join(sent).lower()

    def test_with_a_link_it_does_not_nag(self, monkeypatch):
        _state, sent = self._run(
            f"/recruitposted pf2e-discord-lfg {LINK}", monkeypatch)
        assert "Tip:" not in " ".join(sent)

    def test_an_unknown_venue_is_still_refused(self, monkeypatch):
        # can-fail counterpart: adding an argument must not weaken the
        # check that stops a typo becoming a venue.
        state, sent = self._run(f"/recruitposted nonsense {LINK}", monkeypatch)
        assert "No venue" in " ".join(sent)
        assert not log.get_log(state)["posts"]


class TestTheLinkReachesTheMessage:
    def test_the_cooling_down_line_shows_where_the_advert_is(self):
        # ⭐ Stored is not shown. The cooling-down section is where "where
        # is the thing I posted" is the live question, because it is up
        # right now and the only useful actions are reading it or
        # retiring it.
        from commands.recruit_ads import build_recruit_ads
        venue = {"id": "paizo", "name": "Paizo", "kind": "forum",
                 "status": "candidate", "cooldown_days": 14,
                 "cooldown_source": "assumed", "fit": "high", "format": {}}
        state = {}
        log.record_post(state, "paizo", NOW - timedelta(days=1), url=LINK)
        message = build_recruit_ads({}, state, NOW, [venue])
        assert "Cooling down" in message
        assert LINK in message
