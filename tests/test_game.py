"""Unit tests for the scene dispatcher / GameCtx (pylord/engine/game.py),
independent of any real scene content."""

from __future__ import annotations

import pytest

from pylord import db
from pylord.engine.game import SCENES, GameCtx, run_session, scene
from pylord.models import PlayerRepo
from pylord.terminal import FakeIO


def _ctx(keys=None):
    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)
    player = repo.create("Tester", "pw", "M")
    io = FakeIO(keys or [])
    return GameCtx(player=player, repo=repo, io=io, conn=conn)


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
        ctx = _ctx()
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
        ctx = _ctx()
        await run_session(ctx, start="_test_scene_c1")
        assert calls == ["c1", "c2"]
    finally:
        del SCENES["_test_scene_c1"]
        del SCENES["_test_scene_c2"]


async def test_run_session_unknown_scene_key_raises_keyerror():
    ctx = _ctx()
    with pytest.raises(KeyError):
        await run_session(ctx, start="_scene_key_that_does_not_exist")


async def test_run_session_saves_player_on_logoff():
    @scene("_test_scene_d")
    async def _d(ctx):
        ctx.player.gold = 999

    try:
        ctx = _ctx()
        await run_session(ctx, start="_test_scene_d")
        reloaded = ctx.repo.get(ctx.player.id)
        assert reloaded.gold == 999
    finally:
        del SCENES["_test_scene_d"]


def test_news_inserts_row_with_day_from_game_state():
    ctx = _ctx()
    ctx.conn.execute("INSERT INTO game_state (key, value) VALUES ('day', '7')")
    ctx.news("Something happened.")
    row = ctx.conn.execute("SELECT day, text FROM daily_news").fetchone()
    assert row["day"] == "7"
    assert row["text"] == "Something happened."


def test_news_defaults_day_to_1_when_game_state_row_missing():
    ctx = _ctx()
    ctx.news("hi")
    row = ctx.conn.execute("SELECT day FROM daily_news").fetchone()
    assert row["day"] == "1"


def test_save_persists_player_changes():
    ctx = _ctx()
    ctx.player.gold = 12345
    ctx.save()
    reloaded = ctx.repo.get(ctx.player.id)
    assert reloaded.gold == 12345


def test_ctx_defaults():
    ctx = _ctx()
    assert ctx.igms is None
    assert ctx.config == {}
    assert ctx.rng is not None
