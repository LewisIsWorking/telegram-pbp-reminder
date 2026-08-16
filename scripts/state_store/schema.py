"""Schema registry for ``data/state/`` files.

Single source of truth for which JSON files are expected to live under
``data/state/`` and what kind of file each one is. Slice 6 of P3/9
landed this module. The regression test in
``scripts/test_state_schema.py`` walks the on-disk state directory
and asserts every file matches an entry here.

Why this exists: the 2026-05-10 incident investigation found an
orphaned topic queue message from 2026-05-03 that was never deleted
because the bot had lost track of its msg_id at some earlier point.
A schema-completeness test would have caught the related class of
bug: state files getting written but nothing reading them, or
readers expecting files that no writer creates.

This module is purely declarative — no I/O, no logic. The schema
is a plain tuple of ``(name, description)`` pairs grouped by kind.
Adding a new state file must:

  1. Add an entry to one of the lists below (with a clear
     description of who reads/writes it).
  2. If it's an aux file or partition, ensure the appropriate
     ``StateStore`` method exists for it.
  3. If it's write-once (no runtime reader), document why in the
     description so a future maintainer knows it's deliberate.

The slice-6 regression test will fail if a new file is added under
``data/state/`` without a matching entry here — forcing the
integration question to the surface rather than letting orphans
quietly accumulate.
"""

# Main partitions written by ``state.py`` and read on every bot run.
# Migrated to ``StateStore.save_partition`` / ``load_partition`` in
# slices 3 and 4 of P3/9. The set of partitions is fixed by
# ``state.PARTITIONS`` (the partition\u2192keys mapping) and must stay in
# sync with this list — the slice-6 test asserts that.
PARTITIONS = (
    ("live", "Hot state — offset, gm_queue_history, last_queue_pin_id, "
              "topic timestamps."),
    ("players", "Per-player tracking, inactivity windows, permanent flags."),
    ("queue", "Legacy monolithic GM queue state. Per-campaign queues now "
              "live under queues/{pid}.json (slice 5 of P3/9); this file "
              "remains for the cross-campaign reply log and historical "
              "all-time stats."),
    ("activity", "Per-topic activity timestamps and session markers."),
    ("trackers", "Long-running trackers (poll IDs, milestone markers, "
                 "diagnostic state). Optional — absent on fresh checkout."),
)

# Auxiliary files written by their owning module, single-purpose.
# Migrated to ``StateStore.save_aux`` / ``load_aux`` in slices 1-2.
AUX_FILES = (
    ("bot_sent_ids", "Registry of message IDs the bot has sent. Used by "
                     "posting.safe_delete to refuse non-bot deletes. "
                     "Owner: posting.bot_sent_registry."),
    ("refusal_log", "Append-only log of safe_delete refusals. Owner: "
                    "posting.refusal_log. Optional — absent until first "
                    "refusal occurs."),
    ("refusal_log_alerted", "Marker for the last alerted refusal so the "
                            "alert script doesn't re-send. Owner: "
                            "posting.refusal_log. Optional."),
    ("pin_audit_log", "Bounded forensic trail of every pin/unpin/delete "
                      "the bot performs (id, chat, ok, refused, call "
                      "site). Owner: posting.pin_audit. Written by "
                      "safe_delete's guarded paths; read by humans "
                      "diagnosing a vanished pin. Optional — absent "
                      "until the first pin/unpin/delete."),
    ("stuck_deletes", "Message IDs Telegram declined to delete, with an "
                      "attempt count. Owner: posting.stuck_deletes. "
                      "Written by safe_delete on every failed delete; "
                      "read by safe_delete (to skip IDs it has given up "
                      "on) and by the retry sweep in "
                      "scheduled.topic_queue_state. An entry marked "
                      "hopeless is a message still sitting in a topic "
                      "that only a human can remove. Added 2026-08-16. "
                      "Optional — absent until the first refused delete, "
                      "which before that date could not be observed."),
)

# Files written once during a one-shot migration or by an external
# tooling step, with NO runtime reader. Their presence on disk is
# intentional — do NOT add a reader unless promoting the file to a
# partition or aux entry.
WRITE_ONCE = (
    ("manifest", "Migration manifest from migrate_gist_to_files.py "
                 "(2026-04 partition rollout). Records which keys went "
                 "into which partition file, the source gist ID, and the "
                 "migration timestamp. No runtime reader; kept as an "
                 "audit record of how the partition layout was seeded."),
)

# Queue files live under ``data/state/queues/{pid}.json``. The pid
# itself is dynamic (one file per active campaign) so we don't list
# them individually — the regression test instead asserts shape
# (filename matches a campaign pid) and that StateStore has the
# matching read/write methods (slice 5).
QUEUE_FILES_DIR = "queues"


def all_top_level_names() -> set[str]:
    """Return the set of expected bare-stem names for files directly
    under ``data/state/`` (NOT including the ``queues/`` subdir).

    Used by the slice-6 regression test to compute the diff between
    declared schema and on-disk reality.
    """
    return (
        {name for name, _ in PARTITIONS}
        | {name for name, _ in AUX_FILES}
        | {name for name, _ in WRITE_ONCE}
    )
