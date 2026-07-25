"""Healer's Hut tests. See pylord/engine/scenes/healer.py's module
docstring for lord.js line-number citations."""

from __future__ import annotations

from pylord import data
from pylord.engine.game import GameCtx
from pylord.engine.scenes import healer as healer_mod
from pylord.terminal import FakeIO
from tests.harness import play, screen


async def _ctx(overrides=None, keys=None):
    database = await data.connect(":memory:")
    repo = database.players
    player = await repo.create("Hero", "pw", "M")
    for key, value in (overrides or {}).items():
        setattr(player, key, value)
    io = FakeIO(keys or [])
    return GameCtx(player=player, db=database, io=io)


async def test_healer_reachable_from_town():
    """A fresh player is at full HP -- "you look fine" fires immediately."""
    io, _player = await play(["h", "x", "q"])
    text = screen(io)
    assert "You look fine to us" in text


async def test_full_heal_costs_exact_gold_per_hp():
    """Cost is 5 * level per HP (level=1 -> 5/hp); healing 10 of 20 missing
    HP costs 50 gold."""
    ctx = await _ctx(
        overrides={"hp": 10, "hp_max": 20, "gold": 500, "level": 1}, keys=["h", "x"]
    )
    result = await healer_mod.healer(ctx)
    assert result == "town"
    assert ctx.player.hp == 20
    assert ctx.player.gold == 500 - 50


async def test_full_heal_partial_when_cant_afford():
    """Only 40 gold at 5/hp affords exactly 8 hp; need is 10 -- partial."""
    ctx = await _ctx(
        overrides={"hp": 10, "hp_max": 20, "gold": 40, "level": 1},
        keys=["h", "x", "r"],
    )
    await healer_mod.healer(ctx)
    text = screen(ctx.io)
    assert "8" in text
    assert ctx.player.hp == 10 + 8
    assert ctx.player.gold == 40 - 8 * 5


async def test_heal_some_exact_amount():
    ctx = await _ctx(
        overrides={"hp": 5, "hp_max": 20, "gold": 500, "level": 1},
        keys=["c", "6", "r"],
    )
    await healer_mod.healer(ctx)
    assert ctx.player.hp == 5 + 6
    assert ctx.player.gold == 500 - 6 * 5


async def test_heal_some_refused_when_over_healing():
    ctx = await _ctx(
        overrides={"hp": 18, "hp_max": 20, "gold": 500, "level": 1},
        keys=["c", "5", "r"],
    )
    await healer_mod.healer(ctx)
    text = screen(ctx.io)
    assert "deadly to over heal" in text
    assert ctx.player.hp == 18
    assert ctx.player.gold == 500


async def test_heal_some_refused_when_gold_insufficient():
    ctx = await _ctx(
        overrides={"hp": 5, "hp_max": 20, "gold": 10, "level": 1},
        keys=["c", "5", "r"],
    )
    await healer_mod.healer(ctx)
    text = screen(ctx.io)
    assert "don't have enough gold" in text
    assert ctx.player.hp == 5
    assert ctx.player.gold == 10
