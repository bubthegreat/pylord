"""Trainable forest-fight capacity and real-time regeneration.

Neither mechanic is in lord.js -- see pylord/engine/fights.py's module
docstring and docs/deviations.md for what they replace.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pylord import db
from pylord.engine import daily, fights
from pylord.engine.game import GameCtx
from pylord.engine.scenes import training as training_mod
from pylord.models import PlayerRepo
from pylord.terminal import FakeIO
from tests.harness import play, screen

_NOW = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)


def _repo():
    conn = db.connect(":memory:")
    db.migrate(conn)
    return conn, PlayerRepo(conn)


# --- capacity --------------------------------------------------------------


def test_max_is_the_configured_allowance_plus_trained_bonus():
    _conn, repo = _repo()
    p = repo.create("Hero", "pw", "M")
    assert fights.max_forest_fights(p, {}) == 15
    p.fight_bonus = 4
    assert fights.max_forest_fights(p, {}) == 19
    assert fights.max_forest_fights(p, {"forest_fights_per_day": 20}) == 24


def test_endurance_price_rises_only_with_purchases():
    """You pay for what you have trained. Neither the free point a master
    grants nor the level that came with it moves the price."""
    _conn, repo = _repo()
    p = repo.create("Hero", "pw", "M")
    assert fights.endurance_cost(p, {}) == 1_000
    p.endurance_bought = 2
    assert fights.endurance_cost(p, {}) == 3_000

    p.level = 5
    assert fights.endurance_cost(p, {}) == 3_000  # levelling changes nothing

    fights.grant_bonus(p)  # a master's free forest fight
    assert fights.endurance_cost(p, {}) == 3_000


# --- regeneration ----------------------------------------------------------


def test_one_fight_returns_per_interval_up_to_the_ceiling():
    _conn, repo = _repo()
    p = repo.create("Hero", "pw", "M")
    p.forest_fights = 0
    p.fights_regen_at = (_NOW - timedelta(minutes=47)).isoformat()

    gained = fights.apply_regen(p, {}, now=_NOW)

    assert gained == 3  # 47 // 15
    assert p.forest_fights == 3
    # The leftover 2 minutes carry forward rather than being rounded away.
    assert fights._parse(p.fights_regen_at) == _NOW - timedelta(minutes=2)


def test_regen_stops_at_the_players_ceiling():
    _conn, repo = _repo()
    p = repo.create("Hero", "pw", "M")
    p.forest_fights = 14
    p.fight_bonus = 0  # ceiling 15
    p.fights_regen_at = (_NOW - timedelta(hours=8)).isoformat()

    gained = fights.apply_regen(p, {}, now=_NOW)

    assert gained == 1
    assert p.forest_fights == 15
    # Topped up: the clock restarts, so nothing is banked for later.
    assert fights._parse(p.fights_regen_at) == _NOW


def test_a_trained_player_regenerates_past_the_base_allowance():
    _conn, repo = _repo()
    p = repo.create("Hero", "pw", "M")
    p.fight_bonus = 5  # ceiling 20
    p.forest_fights = 15
    p.fights_regen_at = (_NOW - timedelta(hours=3)).isoformat()

    fights.apply_regen(p, {}, now=_NOW)

    assert p.forest_fights == 20


def test_nothing_accrues_before_a_full_interval():
    _conn, repo = _repo()
    p = repo.create("Hero", "pw", "M")
    p.forest_fights = 0
    started = (_NOW - timedelta(minutes=14)).isoformat()
    p.fights_regen_at = started

    assert fights.apply_regen(p, {}, now=_NOW) == 0
    assert p.forest_fights == 0
    assert p.fights_regen_at == started  # clock untouched


def test_regen_can_be_switched_off():
    _conn, repo = _repo()
    p = repo.create("Hero", "pw", "M")
    p.forest_fights = 0
    p.fights_regen_at = (_NOW - timedelta(days=1)).isoformat()

    assert fights.apply_regen(p, {"fight_regen_minutes": 0}, now=_NOW) == 0
    assert p.forest_fights == 0


def test_regen_interval_is_configurable():
    _conn, repo = _repo()
    p = repo.create("Hero", "pw", "M")
    p.forest_fights = 0
    p.fights_regen_at = (_NOW - timedelta(minutes=30)).isoformat()

    assert fights.apply_regen(p, {"fight_regen_minutes": 5}, now=_NOW) == 6


# --- the daily reset fills to the trained ceiling ---------------------------


def test_daily_reset_fills_to_the_trained_maximum():
    conn, repo = _repo()
    p = repo.create("Hero", "pw", "M")
    p.fight_bonus = 7
    p.forest_fights = 0
    repo.save(p)

    daily.maintenance(conn, {"game": {}}, "2026-07-24")

    assert repo.get(p.id).forest_fights == 22


# --- Turgon's endurance training -------------------------------------------


async def _training_ctx(keys, **overrides):
    conn, repo = _repo()
    player = repo.create("Hero", "pw", "M")
    for key, value in overrides.items():
        setattr(player, key, value)
    return GameCtx(player=player, repo=repo, io=FakeIO(keys), conn=conn)


async def test_endurance_training_buys_a_permanent_fight():
    ctx = await _training_ctx(["y", "x"], gold=5_000)

    await training_mod._endurance(ctx)

    p = ctx.player
    assert p.gold == 4_000
    assert p.fight_bonus == 1
    assert p.endurance_bought == 1
    assert p.forest_fights == 16  # the new capacity is usable immediately
    assert "16 FOREST FIGHTS A DAY" in screen(ctx.io)


async def test_endurance_training_refused_without_the_gold():
    ctx = await _training_ctx(["y", "x"], gold=10)

    await training_mod._endurance(ctx)

    assert ctx.player.fight_bonus == 0
    assert ctx.player.gold == 10
    assert "pay for it" in screen(ctx.io)


async def test_declining_endurance_training_costs_nothing():
    ctx = await _training_ctx(["n", "x"], gold=5_000)

    await training_mod._endurance(ctx)

    assert ctx.player.gold == 5_000
    assert ctx.player.fight_bonus == 0


async def test_beating_a_master_also_raises_the_ceiling():
    from pylord.engine import data

    class _SeqRNG:
        def __init__(self, values):
            self._values = list(values)

        def randrange(self, _n):
            return self._values.pop(0)

    trainer = data.MASTERS[1]
    ctx = await _training_ctx(
        ["a"],
        exp=trainer.exp_reward + 1,
        strength=1000,
        hp=200,
        hp_max=200,
    )
    ctx.rng = _SeqRNG([0, 0, 0])

    await training_mod._attack_master(ctx, trainer)

    assert ctx.player.fight_bonus == 1
    assert "one more forest fight" in screen(ctx.io)


# --- end to end through the real menus -------------------------------------


async def test_forest_status_line_shows_the_ceiling():
    io, _player = await play(
        ["f", "r", "q", "y"], overrides={"fight_bonus": 5, "forest_fights": 3}
    )
    assert "Fights: 3 of 20" in screen(io)


async def test_forest_credits_regen_while_you_stand_around():
    io, player = await play(
        ["f", "r", "q", "y"],
        overrides={
            "forest_fights": 0,
            "fights_regen_at": (
                datetime.now(UTC) - timedelta(minutes=32)
            ).isoformat(),
        },
    )
    assert "2 forest fights recovered" in screen(io)
    assert player.forest_fights == 2
