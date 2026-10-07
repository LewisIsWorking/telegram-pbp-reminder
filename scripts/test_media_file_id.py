"""Posted images keep their Telegram file_id in the transcript.

The file_id rides in a hidden HTML comment after the media marker, so the
GM tooling can fetch the picture later while the wiki shows nothing extra.
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from parsing.message import _media_file_id
from transcript.formatting import (
    FILE_TAG_RE, format_log_entry, strip_file_tags,
)

_FID = "AgACAgQAAxkBAAIBc2Zz-big_ONE_9"


def _parsed(**kw):
    base = {"user_name": "Alice", "user_last_name": "", "user_id": "42",
            "msg_time_iso": "2026-10-08T14:30:05+00:00", "message_id": 77,
            "thread_id": 100, "raw_text": "", "media_type": "image",
            "caption": "", "media_file_id": None}
    base.update(kw)
    return base


def test_photo_takes_the_largest_size():
    msg = {"photo": [{"file_id": "small"}, {"file_id": "mid"},
                     {"file_id": "big"}]}
    assert _media_file_id(msg) == "big"


def test_image_document_keeps_its_file_id():
    msg = {"document": {"file_id": "docimg", "mime_type": "image/png",
                        "file_name": "roll.png"}}
    assert _media_file_id(msg) == "docimg"


def test_non_image_document_and_text_have_no_file_id():
    assert _media_file_id({"document": {"file_id": "x",
                                        "mime_type": "application/pdf"}}) is None
    assert _media_file_id({"text": "hello"}) is None
    assert _media_file_id({"sticker": {"file_id": "s", "emoji": "x"}}) is None


def test_log_entry_writes_hidden_file_tag_after_marker():
    out = format_log_entry(_parsed(media_file_id=_FID, caption="rolled a 17"),
                           set())
    body = out.split("\n")[1]
    assert body.startswith(f"*[image]*<!-- file:{_FID} -->")
    assert "rolled a 17" in body
    assert FILE_TAG_RE.search(out).group(1) == _FID
    # The header line, which every reader keys on, is untouched.
    assert out.split("\n")[0].endswith(" msg#77@100:")


def test_log_entry_without_file_id_is_unchanged():
    out = format_log_entry(_parsed(caption="map"), set())
    assert out.split("\n")[1] == "*[image]* map"
    assert "<!--" not in out


def test_log_entry_refuses_a_file_id_that_could_break_the_comment():
    out = format_log_entry(_parsed(media_file_id="bad --> <b>x</b>"), set())
    assert "<!--" not in out
    assert "*[image]*" in out


def test_strip_file_tags_hides_the_tag_from_players():
    line = f"*[image]*<!-- file:{_FID} --> rolled a 17"
    assert strip_file_tags(line) == "*[image]* rolled a 17"


def test_catchup_does_not_show_the_file_tag(tmp_path, monkeypatch):
    import helpers
    from commands import catchup
    monkeypatch.setattr(catchup, "_LOGS_DIR", tmp_path)
    camp = tmp_path / helpers.campaign_dir_name("Kibwe")
    camp.mkdir()
    (camp / "2026-10.md").write_text(
        "**Alice** (2026-10-08 14:30:05):\n"
        f"*[image]*<!-- file:{_FID} --> rolled a 17\n", encoding="utf-8")
    since = datetime(2026, 10, 1, tzinfo=timezone.utc)
    posts = catchup._get_recent_transcript_posts("Kibwe", since)
    assert posts and posts[0][2] == "*[image]* rolled a 17"


def test_recap_does_not_show_the_file_tag(tmp_path, monkeypatch):
    import helpers
    from commands import recap
    monkeypatch.setattr(recap, "_LOGS_DIR", tmp_path)
    camp = tmp_path / helpers.campaign_dir_name("Kibwe")
    camp.mkdir()
    (camp / "2026-10.md").write_text(
        "**Alice** (2026-10-08 14:30:05):\n"
        f"*[image]*<!-- file:{_FID} --> rolled a 17\n", encoding="utf-8")
    out = recap.build_recap("100", "Kibwe", {"gm_user_ids": []}, 5)
    assert "rolled a 17" in out
    assert "file:" not in out and "<!--" not in out
