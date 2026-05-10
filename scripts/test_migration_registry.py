"""Slice 7 of P3/9 — migration registry regression tests.

Asserts that every production migration is registered in the central
state_store.migration_registry, and that the registry's mechanics
(idempotent registration, target filtering, test reset hook) behave
as documented.

Catches the failure mode where someone deletes a migration call
site without realising other modules still depend on it, or where
a refactor accidentally orphans a registration.
"""

import importlib

import pytest


# ---------------------------------------------------------------------------
# Production-migration coverage
# ---------------------------------------------------------------------------


# Stable identity tuples for every migration the bot relies on. New
# migrations must be added here when they're added to a production
# module's bottom-of-file ``register(...)`` call. Test failures here
# point straight at either a missing registration or an
# accidentally-renamed one.
_KNOWN_MIGRATIONS = {
    ("live", "last_queue_pin_id_to_gm_queue_history"),
    ("queue", "topic_msg_id_to_topic_queues"),
}


def _load_production_modules():
    """Import every module that registers a migration.

    Registrations happen at import time, so to test that they're
    present we have to ensure the modules have been loaded. Pytest's
    collection order isn't guaranteed to import these first, so we
    do it explicitly.
    """
    importlib.import_module("scheduled.gm_queue_history")
    importlib.import_module("scheduled.topic_queue_poster")


def test_known_production_migrations_are_registered() -> None:
    """Every known production migration appears in the registry.

    Catches the slip where a ``register(...)`` call is removed (e.g.
    during a refactor that splits the owning module) but the call
    site keeps invoking the migration function. The migration would
    silently disappear from discovery without this guard.
    """
    _load_production_modules()
    from state_store.migration_registry import all_migrations

    registered = {(m.target, m.name) for m in all_migrations()}
    missing = _KNOWN_MIGRATIONS - registered
    assert not missing, (
        f"Production migrations missing from registry: {sorted(missing)}. "
        f"The owning module's bottom-of-file ``register(Migration(...))`` "
        f"call has been removed or renamed. Restore it or update "
        f"_KNOWN_MIGRATIONS in this test if the rename is intentional."
    )


def test_no_unexpected_migrations_registered() -> None:
    """Registry contains only the known migrations — no orphans.

    Catches the inverse: someone adds a registration but forgets to
    update the test's _KNOWN_MIGRATIONS set. Forces the test to be
    explicit about every migration the production code relies on.
    """
    _load_production_modules()
    from state_store.migration_registry import all_migrations

    registered = {(m.target, m.name) for m in all_migrations()}
    unexpected = registered - _KNOWN_MIGRATIONS
    assert not unexpected, (
        f"Unexpected migrations in registry: {sorted(unexpected)}. "
        f"Add them to _KNOWN_MIGRATIONS in this test to acknowledge "
        f"them, or remove the stray ``register(...)`` call if the "
        f"registration was accidental."
    )


def test_every_migration_has_callable_fn_and_description() -> None:
    """Each registered migration has a callable fn and non-empty
    description. Catches misconfigured registrations early."""
    _load_production_modules()
    from state_store.migration_registry import all_migrations

    for migration in all_migrations():
        assert callable(migration.fn), (
            f"Migration {migration.target}/{migration.name} has "
            f"non-callable fn: {migration.fn!r}"
        )
        assert migration.description.strip(), (
            f"Migration {migration.target}/{migration.name} has empty "
            f"description — future maintainers won't know what schema "
            f"bump it encodes. Add one."
        )


# ---------------------------------------------------------------------------
# Registry mechanics (using a clean registry per test)
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_registry():
    """Wipe the registry for tests that exercise registration mechanics.

    These tests register synthetic migrations and would interfere
    with the production registrations otherwise. ``reset_for_tests``
    clears the registry; the fixture re-imports the production
    modules afterward so the rest of the test suite isn't affected.
    """
    from state_store.migration_registry import reset_for_tests
    reset_for_tests()
    yield
    # Re-register production migrations so subsequent tests see them.
    reset_for_tests()
    _load_production_modules()


def test_register_is_idempotent_on_target_and_name(clean_registry) -> None:
    """Re-registering the same (target, name) is a no-op."""
    from state_store.migration_registry import (
        Migration, all_migrations, register,
    )

    fn = lambda _state: None  # noqa: E731
    register(Migration(target="t", name="n", fn=fn, description="d1"))
    register(Migration(target="t", name="n", fn=fn, description="d2"))

    assert len(all_migrations()) == 1, (
        "Duplicate registration should be a no-op, not append a second "
        "entry. The first registration's description must win so "
        "import order doesn't matter."
    )
    assert all_migrations()[0].description == "d1"


def test_for_target_filters_correctly(clean_registry) -> None:
    """``for_target`` returns only migrations matching the given target."""
    from state_store.migration_registry import (
        Migration, for_target, register,
    )

    fn = lambda _: None  # noqa: E731
    register(Migration(target="live", name="a", fn=fn, description="."))
    register(Migration(target="live", name="b", fn=fn, description="."))
    register(Migration(target="queue", name="c", fn=fn, description="."))

    live = for_target("live")
    queue = for_target("queue")

    assert {m.name for m in live} == {"a", "b"}
    assert {m.name for m in queue} == {"c"}
    assert for_target("nonexistent") == ()


def test_all_migrations_returns_immutable_snapshot(clean_registry) -> None:
    """The returned tuple shouldn't be mutable (catches accidental
    list-return that callers could append to)."""
    from state_store.migration_registry import (
        Migration, all_migrations, register,
    )

    register(Migration(target="t", name="n", fn=lambda _: None,
                       description="."))
    snapshot = all_migrations()
    assert isinstance(snapshot, tuple), (
        "all_migrations should return a tuple to prevent callers "
        "from accidentally mutating registry state."
    )
