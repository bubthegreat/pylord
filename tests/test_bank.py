"""Ye Old Bank tests. See pylord/engine/scenes/bank.py's module docstring
for lord.js line-number citations."""

from __future__ import annotations

from pylord import db
from pylord.engine.game import GameCtx
from pylord.engine.scenes import bank as bank_mod
from pylord.models import PlayerRepo
from pylord.terminal import FakeIO
from tests.harness import play, screen


def _ctx(overrides=None, keys=None):
    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)
    player = repo.create("Hero", "pw", "M")
    for key, value in (overrides or {}).items():
        setattr(player, key, value)
    io = FakeIO(keys or [])
    return GameCtx(player=player, repo=repo, io=io, conn=conn)


async def test_bank_reachable_from_town():
    io, _player = await play(["y", "r", "q"])
    text = screen(io)
    assert "The Bank" in text
    assert "Gold In Hand" in text


async def test_deposit_and_withdraw_roundtrip():
    ctx = _ctx(overrides={"gold": 500, "bank": 0}, keys=["d", "300", "w", "300", "r"])
    result = await bank_mod.bank(ctx)
    assert result == "town"
    assert ctx.player.gold == 500
    assert ctx.player.bank == 0


async def test_deposit_all_shortcut():
    ctx = _ctx(overrides={"gold": 500, "bank": 0}, keys=["d", "1", "r"])
    await bank_mod.bank(ctx)
    assert ctx.player.gold == 0
    assert ctx.player.bank == 500


async def test_withdraw_all_shortcut():
    ctx = _ctx(overrides={"gold": 0, "bank": 500}, keys=["w", "1", "r"])
    await bank_mod.bank(ctx)
    assert ctx.player.gold == 500
    assert ctx.player.bank == 0


async def test_cannot_withdraw_more_than_in_bank():
    ctx = _ctx(overrides={"gold": 0, "bank": 100}, keys=["w", "200", "r"])
    await bank_mod.bank(ctx)
    text = screen(ctx.io)
    assert "don't have that much in your account" in text
    assert ctx.player.gold == 0
    assert ctx.player.bank == 100


async def test_cannot_deposit_more_than_on_hand():
    ctx = _ctx(overrides={"gold": 100, "bank": 0}, keys=["d", "200", "r"])
    await bank_mod.bank(ctx)
    text = screen(ctx.io)
    assert "don't have that much on you" in text
    assert ctx.player.gold == 100
    assert ctx.player.bank == 0


async def test_deposit_clamped_to_gold_cap():
    ctx = _ctx(
        overrides={"gold": 2_000_000_000, "bank": 1_999_999_999},
        keys=["d", "5", "r"],
    )
    await bank_mod.bank(ctx)
    assert ctx.player.bank == 2_000_000_000
    assert ctx.player.gold == 1_999_999_999
