"""Moving a realm between databases.

The SQLite-to-MySQL move ran this against the live realm, so the things
worth pinning are the ones that would silently corrupt characters rather
than fail loudly: ids surviving the copy, and a refusal to write over
anyone.
"""

from __future__ import annotations

import pytest

from pylord import data
from pylord.migrate import copy_realm


async def _seeded():
    """A source realm with enough shape to notice a bad copy."""
    db = await data.connect(":memory:")
    hero = await db.players.create("Hero", "pw", "M")
    villain = await db.players.create("Villain", "pw", "F")
    hero.gold, hero.level, hero.married_to = 4242, 7, villain.id
    await db.players.save(hero)

    await db.state.set("day", 9)
    await db.news.add(9, "A dragon was sighted!")
    await db.mail.send(hero.id, "Barak", text="a gift", effect={"gold": 5})
    await db.igm_data.set_raw("mines", f"digs:{hero.id}", "3")
    return db, hero, villain


async def test_copies_every_table():
    source, _hero, _villain = await _seeded()
    dest = await data.connect(":memory:")

    counts = await copy_realm(source, dest)

    assert counts == {
        "players": 2,
        "game_state": 1,
        "daily_news": 1,
        "mail": 1,
        "igm_data": 1,
    }
    assert await dest.state.get("day") == "9"
    assert await dest.news.for_day(9) == ["A dragon was sighted!"]


async def test_characters_arrive_intact():
    source, _hero, _villain = await _seeded()
    dest = await data.connect(":memory:")

    await copy_realm(source, dest)

    copied = await dest.players.get_by_name("Hero")
    assert copied.gold == 4242
    assert copied.level == 7
    # Their password still works: the hash came across, not a re-hash.
    assert await dest.players.check_password("Hero", "pw") is not None


async def test_player_ids_are_preserved():
    """Ids are foreign keys in all but name -- mail.to_id, married_to, and
    IGM store keys like "digs:7". Renumbering would re-marry people and
    hand out someone else's daily allowance."""
    source, hero, villain = await _seeded()
    dest = await data.connect(":memory:")

    await copy_realm(source, dest)

    copied = await dest.players.get_by_name("Hero")
    assert copied.id == hero.id
    assert copied.married_to == villain.id

    unread = await dest.mail.unread_for(hero.id)
    assert [row.from_name for row in unread] == ["Barak"]
    assert await dest.igm_data.get_raw("mines", f"digs:{hero.id}") == "3"


async def test_a_new_character_after_the_move_does_not_collide():
    """The destination's id counter has to pick up after the copied rows,
    not restart at 1 on top of someone."""
    source, _hero, _villain = await _seeded()
    dest = await data.connect(":memory:")

    await copy_realm(source, dest)
    newcomer = await dest.players.create("Newcomer", "pw", "M")

    assert newcomer.id not in {1, 2}
    assert len(await dest.players.all_players()) == 3


async def test_it_refuses_to_write_over_an_inhabited_realm():
    source, _hero, _villain = await _seeded()
    dest = await data.connect(":memory:")
    await dest.players.create("Resident", "pw", "M")

    with pytest.raises(ValueError, match="already has 1 character"):
        await copy_realm(source, dest)

    assert await dest.players.get_by_name("Resident") is not None
    assert await dest.players.get_by_name("Hero") is None


async def test_overwrite_replaces_the_destination():
    source, _hero, _villain = await _seeded()
    dest = await data.connect(":memory:")
    await dest.players.create("Resident", "pw", "M")

    await copy_realm(source, dest, overwrite=True)

    assert await dest.players.get_by_name("Resident") is None
    assert await dest.players.get_by_name("Hero") is not None
