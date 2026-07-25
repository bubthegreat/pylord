"""Schema creation, for whichever database the realm is running on.

Replaces the old SQLite migration tests: the schema is now one SQLAlchemy
definition (pylord/schema.py) that produces DDL for SQLite and MySQL
alike, rather than hand-written SQLite DDL in a migration list.
"""

from __future__ import annotations

import pytest
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


async def test_a_new_column_reaches_a_database_that_predates_it():
    """A release that adds a field must not work everywhere except the one
    realm that matters.

    ``create_all`` only creates whole tables, so without the additive
    migration this passes on every fresh database and every test, then
    queries a column the live realm doesn't have.
    """
    from sqlalchemy import Column, Integer, String, text

    database = await data.connect(":memory:")
    hero = await database.players.create("Hero", "pw", "M")
    hero.gold = 4242
    await database.players.save(hero)

    added = [
        Column("des1", String(80), nullable=False, server_default=""),
        Column("scars", Integer, nullable=False, server_default="0"),
    ]
    for column in added:
        schema.players.append_column(column)
    try:
        await database.create_schema()

        row = await database.fetch_one(text("SELECT des1, scars FROM players"))
        # The character already there is untouched, and gets the defaults.
        assert (row.des1, row.scars) == ("", 0)
        assert (await database.players.get(hero.id)).gold == 4242

        # Starting again must not try to add them a second time.
        await database.create_schema()
    finally:
        for column in added:
            schema.players._columns.remove(column)


async def test_a_column_that_cannot_be_added_safely_says_so():
    """A NOT NULL column with no default has no value to give the rows
    already there. Fail with an explanation rather than a driver error."""
    from sqlalchemy import Column, Integer

    database = await data.connect(":memory:")
    await database.players.create("Hero", "pw", "M")

    column = Column("unsafe", Integer, nullable=False)
    schema.players.append_column(column)
    try:
        with pytest.raises(RuntimeError, match="needs a server_default"):
            await database.create_schema()
    finally:
        schema.players._columns.remove(column)
