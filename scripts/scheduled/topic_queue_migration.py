"""Central-registry registration for the per-topic-queue schema migration.

Extracted from ``scheduled/topic_queue_poster.py`` to keep that module
under the 200-line cap. The migration function itself
(``_migrate_legacy``) still lives in the poster and is invoked there at
production call sites; this module only registers it for discovery and
the slice-7 regression test (``test_migration_registry``).

The poster imports this module at the bottom of its file so the
registration runs whenever the poster is imported — preserving the
behaviour the migration-registry test relies on (it triggers
registration by importing the poster).
"""

from scheduled.topic_queue_poster import _migrate_legacy
from state_store.migration_registry import Migration, register

register(Migration(
    target="queue",
    name="topic_msg_id_to_topic_queues",
    fn=_migrate_legacy,
    description=(
        "Pre-2025 each per-campaign queue file carried a single "
        "``topic_msg_id`` plus ``topic_fingerprint`` field tracking "
        "one pinned topic queue. The schema bump introduced "
        "``topic_queues`` (a per-thread dict mapping thread_id to "
        "slot data) so multi-topic campaigns like C06 Kibwe and "
        "C09 Metal City could carry separate pins per thread. This "
        "migration deletes the stale single-pin message from "
        "Telegram (best-effort) and clears the legacy fields."
    ),
))
