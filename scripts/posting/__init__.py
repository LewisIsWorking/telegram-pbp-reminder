"""
Pinned-post primitives shared across queue-posting scheduled modules.

This package extracts the common patterns previously duplicated between
``scheduled/gm_queue_history.py`` (rolling history) and
``scheduled/topic_queue_poster.py`` (single-slot replace).

Layers, smallest-to-largest:

* ``message_batch`` — A logical post (one or more chunks) that share a
  lifecycle. Knows how to delete itself from Telegram, returning any
  message IDs whose deletion failed so callers can retry.

* ``sender`` — Sends a list of chunks as one batch and pins the first
  successfully-delivered chunk.

* ``queue_history`` — Rolling window of N most-recent batches. Older
  batches are evicted on overflow; failed deletes block further
  eviction so messages cannot be silently orphaned.

* ``single_pin`` — Replace-only slot (no history, just current). Posts
  a new batch and deletes the previous one.

Public API is re-exported here for short import paths::

    from posting import MessageBatch, post_batch, QueueHistory, SinglePin
"""

from posting.message_batch import MessageBatch
from posting.sender import post_batch
from posting.queue_history import QueueHistory
from posting.single_pin import SinglePin

__all__ = ["MessageBatch", "post_batch", "QueueHistory", "SinglePin"]
