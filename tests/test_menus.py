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

    from pylord import db
    from pylord.engine import data
    from pylord.engine.game import GameCtx
    from pylord.engine.scenes import forest as forest_mod
    from pylord.models import PlayerRepo
    from pylord.terminal import FakeIO

    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)
    player = repo.create("Hero", "pw", "M")
    player.strength, player.hp, player.hp_max = 30_000, 3_000, 3_000
    # Enter to swing, then whatever pauses the victory text asks for.
    io = FakeIO(["\r", "x", "x", "x"])
    ctx = GameCtx(player=player, repo=repo, io=io, conn=conn, rng=random.Random(0))

    await forest_mod._run_fight(ctx, data.MONSTERS[1][0])

    text = screen(io)
    assert "You hit" in text or "You miss" in text, text[-400:]
