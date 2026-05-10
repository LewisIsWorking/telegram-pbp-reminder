"""Central registry for state migrations.

Slice 7 of P3/9. Pure refactor of how migrations are discovered —
production call sites still invoke each migration function
explicitly. The registry exists so future maintainers can see every
schema bump in one place rather than grepping for ``migrate_legacy``
across the codebase, and so the slice-7 regression tests can assert
that known migrations remain wired up.

A migration is a (target, name, fn, description) record where:

* ``target`` identifies the data shape being migrated. Currently:
    - ``"live"`` — the live partition dict (``state.PARTITIONS["live"]``)
    - ``"queue"`` — a per-campaign queue dict from
      ``commands/queue_io.load(pid)``
* ``name`` is a short stable identifier, used by tests to assert
  presence and to disambiguate migrations targeting the same scope.
* ``fn`` is the migration callable. Signatures vary by migration
  (e.g. ``(state)`` vs ``(cq, group_id)``); the registry stores fn
  for discovery and test-introspection purposes only — it never
  invokes fn itself, so the variable signature is fine.
* ``description`` records the schema bump the migration encodes.

Migrations register themselves at module import time. ``StateStore``
does NOT auto-run them on load — that's an open question deferred
past slice 7 (see ``docs/dev/statestore-design.md``). The current
production call sites continue to invoke migrations explicitly; the
registry tracks what exists for discovery and testing only.
"""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Migration:
    """A single registered state-migration record."""

    target: str
    name: str
    fn: Callable[[Any], None]
    description: str


# Module-level registry. Populated by ``register()`` calls in the
# owning modules at import time. The order of registration is the
# order in which call sites first import the registry; tests should
# not depend on it.
_REGISTRY: list[Migration] = []


def register(migration: Migration) -> None:
    """Add a migration to the registry.

    Idempotent on (target, name) — calling twice with the same
    identity is a no-op rather than appending a duplicate. This is
    important because production modules import each other in
    various orders, and a re-import (e.g., during a test that
    reloads a module) shouldn't double-count.
    """
    for existing in _REGISTRY:
        if existing.target == migration.target and existing.name == migration.name:
            return
    _REGISTRY.append(migration)


def all_migrations() -> tuple[Migration, ...]:
    """Return every registered migration as an immutable snapshot.

    The slice-7 regression test uses this to assert known migrations
    remain registered. Production code should not iterate this for
    runtime decisions — call the migration functions directly at
    the appropriate point in their owning module.
    """
    return tuple(_REGISTRY)


def for_target(target: str) -> tuple[Migration, ...]:
    """Return migrations registered for a given target.

    Useful for the regression test's per-scope coverage check
    (e.g., ``for_target("live")`` to verify the live-partition
    migrations specifically).
    """
    return tuple(m for m in _REGISTRY if m.target == target)


def reset_for_tests() -> None:
    """Clear the registry. Intended for test-isolation use only.

    Production code never calls this. Tests that exercise the
    registration mechanism itself (rather than the registered
    migrations) can wipe state between cases. Tests that exercise
    the registered migrations should NOT call this — they need the
    production registrations intact.
    """
    _REGISTRY.clear()
