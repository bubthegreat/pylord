"""Unit tests for the scene dispatcher / GameCtx (pylord/engine/game.py),
independent of any real scene content."""

from __future__ import annotations

import pytest

from pylord import data
from pylord.engine.game import SCENES, GameCtx, grant_exp, run_session, scene
from pylord.terminal import FakeIO
from tests.harness import query_one, screen


async def _ctx(keys=None):
    database = await data.connect(":memory:")
    repo = database.players
    player = await repo.create("Tester", "pw", "M")
    io = FakeIO(keys or [])
    return GameCtx(player=player, db=database, io=io)


async def test_scene_decorator_registers_in_scenes_dict():
    @scene("_test_scene_a")
    async def _a(ctx):
        return None

    try:
        assert SCENES["_test_scene_a"] is _a
    finally:
        del SCENES["_test_scene_a"]


async def test_run_session_stops_when_scene_returns_none():
    calls = []

    @scene("_test_scene_b")
    async def _b(ctx):
        calls.append("b")

    try:
        ctx = await _ctx()
        await run_session(ctx, start="_test_scene_b")
        assert calls == ["b"]
    finally:
        del SCENES["_test_scene_b"]


async def test_run_session_chains_to_returned_scene_key():
    calls = []

    @scene("_test_scene_c1")
    async def _c1(ctx):
        calls.append("c1")
        return "_test_scene_c2"

    @scene("_test_scene_c2")
    async def _c2(ctx):
        calls.append("c2")

    try:
        ctx = await _ctx()
        await run_session(ctx, start="_test_scene_c1")
        assert calls == ["c1", "c2"]
    finally:
        del SCENES["_test_scene_c1"]
        del SCENES["_test_scene_c2"]


async def test_run_session_unknown_scene_key_raises_keyerror():
    ctx = await _ctx()
    with pytest.raises(KeyError):
        await run_session(ctx, start="_scene_key_that_does_not_exist")


async def test_run_session_saves_player_on_logoff():
    @scene("_test_scene_d")
    async def _d(ctx):
        ctx.player.gold = 999

    try:
        ctx = await _ctx()
        await run_session(ctx, start="_test_scene_d")
        reloaded = await ctx.repo.get(ctx.player.id)
        assert reloaded.gold == 999
    finally:
        del SCENES["_test_scene_d"]


async def test_news_inserts_row_with_day_from_game_state():
    ctx = await _ctx()
    await ctx.db.state.set("day", 7)
    await ctx.news("Something happened.")
    row = await query_one(ctx.db, "SELECT day, text FROM daily_news")
    assert row.day == "7"
    assert row.text == "Something happened."


async def test_news_defaults_day_to_1_when_game_state_row_missing():
    ctx = await _ctx()
    await ctx.news("hi")
    row = await query_one(ctx.db, "SELECT day FROM daily_news")
    assert row.day == "1"


async def test_save_persists_player_changes():
    ctx = await _ctx()
    ctx.player.gold = 12345
    await ctx.save()
    reloaded = await ctx.repo.get(ctx.player.id)
    assert reloaded.gold == 12345


async def test_ctx_defaults():
    ctx = await _ctx()
    assert ctx.igms is None
    assert ctx.config == {}
    assert ctx.rng is not None


async def test_grant_exp_credits_amount():
    ctx = await _ctx()
    ctx.player.exp = 1
    ctx.player.level = 1
    await grant_exp(ctx, 5)
    assert ctx.player.exp == 6


async def test_grant_exp_announces_when_next_level_threshold_is_crossed():
    """EXP_FOR_LEVEL[2] == 100 (pylord/engine/data/levels.py)."""
    ctx = await _ctx()
    ctx.player.exp = 95
    ctx.player.level = 1
    await grant_exp(ctx, 10)  # 95 -> 105, crosses 100
    assert ctx.player.exp == 105
    text = screen(ctx.io)
    assert "reach level 2" in text
    assert "Go see your master" in text


async def test_grant_exp_silent_when_threshold_not_crossed():
    ctx = await _ctx()
    ctx.player.exp = 10
    ctx.player.level = 1
    await grant_exp(ctx, 5)
    assert ctx.player.exp == 15
    assert screen(ctx.io) == ""


async def test_grant_exp_caps_at_two_billion():
    ctx = await _ctx()
    ctx.player.exp = 2_000_000_000
    await grant_exp(ctx, 500)
    assert ctx.player.exp == 2_000_000_000
