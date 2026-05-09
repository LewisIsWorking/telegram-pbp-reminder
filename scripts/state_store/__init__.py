"""StateStore — single typed abstraction over ``data/state/``.

See ``docs/dev/statestore-design.md`` for the full design and the
slice-by-slice rollout plan. This package is the implementation home
for that design.

Slice 1 (this commit) delivers the package shell and aux-file API
only. Production code that needs to read/write auxiliary state files
(``bot_sent_ids.json``, ``refusal_log.json``,
``refusal_log_alerted.json``) goes through ``StateStore.load_aux`` /
``StateStore.save_aux`` from this slice forward.

Later slices will add ``load_partition`` / ``save_partition``
(slice 3-4), ``load_queue`` / ``save_queue`` (slice 5), the schema-
completeness test (slice 6), the migration registry (slice 7), and
the locking primitives needed by ROADMAP P3/10 (slice 8).

Public re-exports:

    StateStore — the abstraction class.
"""

from .store import StateStore  # noqa: F401
