"""Schema creation, for whichever database the realm is running on.

Replaces the old SQLite migration tests: the schema is now one SQLAlchemy
definition (pylord/schema.py) that produces DDL for SQLite and MySQL
alike, rather than hand-written SQLite DDL in a migration list.
"""

from __future__ import annotations

from sqlalchemy import inspect

from pylord import data, schema


async def test_connect_creates_every_table(tmp_path):
    database = await data.connect(str(tmp_path / "lord.db"))
    try:
        async with database.engine.connect() as conn:
            names = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
        assert {
            "players",
            "game_state",
            "daily_news",
            "mail",
            "igm_data",
            "schema_version",
        } <= names
    finally:
        await database.dispose()


async def test_connect_is_idempotent(tmp_path):
    """Starting the server twice against the same database must not
    re-create anything or stamp a second version row."""
    path = str(tmp_path / "lord.db")
    first = await data.connect(path)
    hero = await first.players.create("Hero", "pw", "M")
    await first.dispose()

    second = await data.connect(path)
    try:
        assert (await second.players.get_by_name("Hero")).id == hero.id
        rows = await second.fetch_all(
            schema.schema_version.select()
        )
        assert len(rows) == 1
        assert rows[0].applied_count == schema.CURRENT_VERSION
    finally:
        await second.dispose()


async def test_player_names_are_unique_case_insensitively():
    """The realm has always refused a duplicate name regardless of case:
    SQLite via COLLATE NOCASE, MySQL via its default collation."""
    import pytest

    database = await data.connect(":memory:")
    try:
        await database.players.create("Hero", "pw", "M")
        with pytest.raises(ValueError):
            await database.players.create("hero", "pw", "M")
    finally:
        await database.dispose()
