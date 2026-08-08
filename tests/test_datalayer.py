"""The data layer: one place where SQL lives, one transaction boundary.

These pin what the repositories promise, on whichever database is
underneath -- the same suite runs against SQLite locally and MySQL in CI.
"""

from __future__ import annotations

import pytest
from sqlalchemy import update

from pylord import data, schema
from pylord.data import Database


async def _db() -> Database:
    return await data.connect(":memory:")


async def test_game_state_round_trips_and_upserts():
    db = await _db()
    assert await db.state.get("day") is None
    assert await db.state.get("day", "1") == "1"

    await db.state.set("day", 3)
    assert await db.state.get("day") == "3"
    assert await db.state.get_int("day", 1) == 3

    await db.state.set("day", 4)  # upsert, not a second row
    assert await db.state.get_int("day", 1) == 4

    await db.state.delete("day")
    assert await db.state.get("day") is None


async def test_game_state_int_tolerates_rubbish():
    db = await _db()
    await db.state.set("day", "not a number")
    assert await db.state.get_int("day", 7) == 7


async def test_news_is_scoped_to_its_day_and_ordered():
    db = await _db()
    await db.news.add(2, "first")
    await db.news.add(2, "second")
    await db.news.add(3, "another day")

    assert await db.news.for_day(2) == ["first", "second"]
    assert await db.news.for_day("2") == ["first", "second"]  # int or str
    assert await db.news.for_day(99) == []


async def test_mail_round_trip_with_effect():
    db = await _db()
    hero = await db.players.create("Hero", "pw", "M")
    await db.mail.send(hero.id, "Barak", text="hello", effect={"gold": 5})

    unread = await db.mail.unread_for(hero.id)
    assert len(unread) == 1
    assert unread[0].from_name == "Barak"
    assert '"gold": 5' in unread[0].effect

    await db.mail.mark_read(unread[0].id)
    assert await db.mail.unread_for(hero.id) == []


async def test_deleting_a_player_frees_their_spouse_and_mail():
    db = await _db()
    hero = await db.players.create("Hero", "pw", "M")
    spouse = await db.players.create("Spouse", "pw", "F")
    spouse.married_to = hero.id
    await db.players.save(spouse)
    await db.mail.send(hero.id, "Someone", text="hi")

    async with db.transaction() as tx:
        await tx.mail.delete_for(hero.id)
        await tx.players.delete(hero.id)

    assert await db.players.get(hero.id) is None
    assert (await db.players.get(spouse.id)).married_to is None
    assert await db.mail.unread_for(hero.id) == []


async def test_a_write_inside_a_transaction_is_undone_by_a_failure():
    """The whole point of the boundary: a turn that dies half-way leaves
    the character exactly as it found them."""
    db = await _db()
    hero = await db.players.create("Hero", "pw", "M")

    with pytest.raises(RuntimeError):
        async with db.transaction() as tx:
            hero.gold = 999_999
            await tx.players.save(hero)
            raise RuntimeError("something went wrong mid-turn")

    assert (await db.players.get(hero.id)).gold == 500


async def test_transaction_rolls_everything_back_together():
    db = await _db()
    hero = await db.players.create("Hero", "pw", "M")

    with pytest.raises(RuntimeError):
        async with db.transaction() as tx:
            hero.gold = 1
            await tx.players.save(hero)
            await tx.mail.send(hero.id, "Someone", text="hi")
            await tx.state.set("day", 5)
            raise RuntimeError("something went wrong mid-turn")

    assert await db.mail.unread_for(hero.id) == []
    assert await db.state.get("day") is None
    assert (await db.players.get(hero.id)).gold == 500


async def test_nesting_a_transaction_joins_the_outer_one():
    """A helper that wants atomicity must not quietly commit the larger
    operation it was called from -- the bug the old `with conn:` idiom had."""
    db = await _db()
    hero = await db.players.create("Hero", "pw", "M")

    with pytest.raises(RuntimeError):
        async with db.transaction() as outer:
            hero.gold = 4_242
            await outer.players.save(hero)
            async with outer.transaction() as inner:
                await inner.state.set("day", 9)
            raise RuntimeError("the outer unit of work fails")

    assert (await db.players.get(hero.id)).gold == 500
    assert await db.state.get("day") is None


async def test_clear_online_flags_reports_how_many_it_freed():
    db = await _db()
    for name in ("A", "B", "C"):
        player = await db.players.create(name, "pw", "M")
        if name != "C":
            player.online = 1
            await db.players.save(player)

    async with db.transaction() as tx:
        assert await tx.players.clear_online_flags() == 2

    assert [p.online for p in await db.players.all_players()] == [0, 0, 0]


async def test_igm_data_is_namespaced_per_igm():
    db = await _db()
    await db.igm_data.set_raw("mines", "sift:1", "3")
    await db.igm_data.set_raw("latrine", "sift:1", "9")

    assert await db.igm_data.get_raw("mines", "sift:1") == "3"
    assert await db.igm_data.get_raw("latrine", "sift:1") == "9"
    assert await db.igm_data.get_raw("mines", "missing") is None

    await db.igm_data.delete("mines", "sift:1")
    assert await db.igm_data.get_raw("mines", "sift:1") is None
    assert await db.igm_data.get_raw("latrine", "sift:1") == "9"


async def _set_version(db: Database, version: int) -> None:
    await db.execute(
        update(schema.schema_version).values(applied_count=version)
    )


async def test_v6_migration_rebases_armored_defense_by_delta():
    db = await _db()
    p = await db.players.create("Armored", "pw")
    p.armor_num = 11  # Blood Armour: old power 225, new power 560
    p.defense = 233 + 225 + 50  # base + old armor + 50 fairyland points
    await db.players.save(p)

    await _set_version(db, 5)
    await db.create_schema()

    migrated = await db.players.get(p.id)
    # Delta (+335) applied; the 50 bought points survive.
    assert migrated.defense == 233 + 560 + 50
    row = await db.fetch_one(
        schema.schema_version.select()
    )
    assert row.applied_count == schema.CURRENT_VERSION


async def test_v6_migration_skips_unarmored_and_corrupt_rows():
    db = await _db()
    bare = await db.players.create("Bare", "pw")
    bare.armor_num = 0  # sold their Coat -- Player defaults to armor_num=1
    await db.players.save(bare)
    corrupt = await db.players.create("Corrupt", "pw")
    corrupt.armor_num = 99
    corrupt.defense = 123
    await db.players.save(corrupt)

    await _set_version(db, 5)
    await db.create_schema()

    assert (await db.players.get(bare.id)).defense == 3  # model default
    assert (await db.players.get(corrupt.id)).defense == 123


async def test_v6_migration_is_idempotent_and_clamps():
    db = await _db()
    p = await db.players.create("Capped", "pw")
    p.armor_num = 15  # delta +350
    p.defense = 31_900
    await db.players.save(p)

    await _set_version(db, 5)
    await db.create_schema()
    assert (await db.players.get(p.id)).defense == 32_000  # clamped

    # Second startup: version is already current, no second delta.
    await db.create_schema()
    assert (await db.players.get(p.id)).defense == 32_000


async def test_v6_migration_is_atomic_across_a_crash(monkeypatch):
    db = await _db()
    first = await db.players.create("First", "pw")
    first.armor_num = 11  # delta +335
    first.defense = 233 + 225 + 50
    await db.players.save(first)
    second = await db.players.create("Second", "pw")
    second.armor_num = 11
    second.defense = 233 + 225 + 50
    await db.players.save(second)

    await _set_version(db, 5)

    original_save = data.PlayersRepo.save
    calls = 0

    async def flaky_save(self, player):
        nonlocal calls
        calls += 1
        if calls == 2:  # crash partway through the migration loop
            raise RuntimeError("simulated crash mid-migration")
        await original_save(self, player)

    monkeypatch.setattr(data.PlayersRepo, "save", flaky_save)

    with pytest.raises(RuntimeError, match="simulated crash mid-migration"):
        await db.create_schema()

    monkeypatch.undo()  # restore the real save before reading state back

    # Nothing committed: the first player's mid-loop save rolled back
    # along with the version bump, so a retry sees version 5 again and
    # re-migrates everyone -- not a double-applied delta on survivors.
    assert (await db.players.get(first.id)).defense == 233 + 225 + 50
    assert (await db.players.get(second.id)).defense == 233 + 225 + 50
    row = await db.fetch_one(schema.schema_version.select())
    assert row.applied_count == 5
