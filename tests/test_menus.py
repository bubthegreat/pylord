"""Every menu shows what you can press, and every confirm asks its question.

lord.js draws several of these screens from external ``lrdfile()`` assets
(MAIN, HEAL, ARTHUR, ...) that aren't in this repo, so the option lines are
reconstructed in each scene. They were missing from the healer, the bank and
Turgon's, and the shops' buy/sell confirms had no visible prompt at all --
the player saw a cursor and nothing else. These tests pin the reconstruction
so a screen can't silently lose its options again.
"""

from __future__ import annotations

import re

import pytest

from tests.harness import play, screen

# Scene key -> (keys that reach it, the letters its menu must advertise).
_MENUS = [
    ("Healer's Hut", ["h"], ["H", "C", "R"]),
    ("Ye Old Bank", ["y"], ["D", "W", "R"]),
    ("Turgon's", ["t"], ["Q", "A", "E", "V", "R"]),
    ("King Arthur's", ["k"], ["B", "S", "R"]),
    ("Abdul's Armour", ["a"], ["B", "S", "R"]),
    ("Slaughter", ["s"], ["S", "L", "V", "R"]),
    ("The Forest", ["f"], ["L", "H", "R", "V"]),
    ("Town Square", [], ["F", "S", "K", "A", "H", "V", "I", "T", "Y", "L", "W", "D", "C", "O", "X", "Q"]),
]


@pytest.mark.parametrize("name,keys,letters", _MENUS)
async def test_menu_advertises_every_key(name, keys, letters):
    # A wounded player, so the healer shows its menu rather than turning
    # them away at the door.
    io, _player = await play(
        [*keys, "r", "q", "y"], overrides={"hp": 5, "hp_max": 20}
    )
    text = screen(io)
    missing = [k for k in letters if f"({k})" not in text]
    assert not missing, f"{name} menu never showed: {missing}\n{text[-700:]}"


async def test_shop_buy_and_sell_ask_before_taking_your_gold():
    """reference/lord.js:10173 ("Buy it? [N]") and :10079 ("Sell it? [N]").
    Both prompts were missing: the game waited on a keypress it never asked
    for."""
    io, _player = await play(
        ["k", "b", "1", "n", "x", "s", "n", "x", "r", "q", "y"],
        overrides={"weapon_num": 0},
    )
    text = screen(io)
    assert re.search(r"Buy it\?\s+\[N\]", text), text[-500:]

    io, _player = await play(
        ["k", "s", "n", "x", "r", "q", "y"], overrides={"weapon_num": 5}
    )
    assert re.search(r"Sell it\?\s+\[N\]", screen(io))


async def test_enter_at_a_shop_confirm_declines():
    """The prompts advertise [N], so Enter must decline rather than buy."""
    io, player = await play(
        ["k", "b", "1", "\r", "x", "r", "q", "y"], overrides={"weapon_num": 0}
    )
    assert player.weapon_num == 0
    assert player.gold == 500
    assert "Fine..You will come back" in screen(io)


async def test_enter_in_a_battle_takes_the_default_attack():
    """The battle prompt advertises [A]; Enter should swing.

    Driven through ``_run_fight`` directly rather than the forest menu,
    because whether a given (L)ook produces a fight or one of the random
    forest events depends on the seed."""
    import random

    from pylord import data as storage
    from pylord.engine import data
    from pylord.engine.game import GameCtx
    from pylord.engine.scenes import forest as forest_mod
    from pylord.terminal import FakeIO

    database = await storage.connect(":memory:")
    repo = database.players
    player = await repo.create("Hero", "pw", "M")
    player.strength, player.hp, player.hp_max = 30_000, 3_000, 3_000
    # Enter to swing, then whatever pauses the victory text asks for.
    io = FakeIO(["\r", "x", "x", "x"])
    ctx = GameCtx(player=player, db=database, io=io, rng=random.Random(0))

    await forest_mod._run_fight(ctx, data.MONSTERS[1][0])

    text = screen(io)
    assert "You hit" in text or "You miss" in text, text[-400:]


async def test_enter_in_the_forest_hunts_rather_than_leaving():
    """The owner's call: holding Enter should keep the fights coming.
    lord.js leaves the forest on Enter (:15274-15277)."""
    io, player = await play(
        ["f", "\r", "x", "x", "x", "r", "q", "y"],
        overrides={"forest_fights": 5, "hp": 3000, "hp_max": 3000},
    )
    text = screen(io)
    assert "[L]" in text  # the default is advertised
    # Something happened in the forest: a fight, or one of its events.
    assert player.forest_fights < 5 or "Event In The Forest" in text or "NOTICED" in text


async def test_the_bartender_shows_what_you_can_ask_him():
    """The Inn's (T)alk to barkeep built its options dynamically and printed
    none of them -- lord.js draws that screen from lrdfile('BT'), which
    isn't in this repo (reference/lord.js:8127-8133)."""
    io, _player = await play(
        ["i", "t", "r", "r", "q", "y"],
        overrides={"level": 5, "gender": "M"},
    )
    text = screen(io)
    assert "(V)iolet" in text, text[-500:]
    assert "(B)ribe" in text
    assert "(R)eturn to the bar" in text


async def test_the_bartender_offers_the_dragon_hint_at_level_twelve():
    io, _player = await play(
        ["i", "t", "d", "x", "r", "r", "q", "y"],
        overrides={"level": 12, "gender": "F"},
    )
    text = screen(io)
    assert "(D)ragon" in text
    assert "(S)eth Able" in text  # gender-specific gossip
