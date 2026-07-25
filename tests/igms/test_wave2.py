"""Wave-2 IGMs: Apothecary, Gem Trader, Old Skull Inn, Abandoned Mines,
Arena of Lords, The Latrine.

All six are recreations from the historical premise rather than ports --
see each module's docstring. These tests pin the mechanics that touch a
character (gems spent, gold moved, hitpoints lost, daily gates) and check
every one against the shared IGM contract.
"""

from __future__ import annotations

import pytest

from igms.abandoned_mines.igm import AbandonedMines
from igms.apothecary.igm import Apothecary
from igms.arena_of_lords.igm import ArenaOfLords
from igms.gem_trader.igm import GemTrader
from igms.old_skull_inn.igm import OldSkullInn
from igms.the_latrine.igm import TheLatrine
from tests.harness import query_one
from tests.igm_contract import contract_check
from tests.igms._harness import (
    SeqRandom,
    make_ctx,
    make_db,
    make_igm_ctx,
    make_maint_ctx,
)

_WAVE2 = [Apothecary, GemTrader, OldSkullInn, AbandonedMines, ArenaOfLords, TheLatrine]


async def _visit(igm, keys, rng=None, **overrides):
    database, repo = await make_db()
    player = await repo.create("Hero", "pw", "M")
    for key, value in overrides.items():
        setattr(player, key, value)
    gctx = make_ctx(database, repo, player, keys=keys, rng=rng)
    return gctx, await make_igm_ctx(gctx, igm), player, database


def _screen(gctx) -> str:
    import re

    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", "".join(gctx.io.output))


@pytest.mark.parametrize("igm_cls", _WAVE2)
async def test_contract(igm_cls):
    await contract_check(igm_cls)


@pytest.mark.parametrize("igm_cls", _WAVE2)
def test_ships_disabled(igm_cls):
    """Wave 2+ is opt-in: the spec ships everything past the starter six
    disabled, so a sysop chooses what their realm has."""
    assert igm_cls.default_enabled is False
    assert igm_cls.key and igm_cls.name


# --- Apothecary ------------------------------------------------------------


async def test_salve_heals_for_gems():
    igm = Apothecary()
    _gctx, ctx, p, _ = await _visit(igm, ["S", "x", "L"], gems=5, hp=4, hp_max=40)
    await igm.enter(ctx)
    assert p.gems == 3
    assert p.hp == 40


async def test_tonic_is_once_a_day_and_grants_a_fight():
    igm = Apothecary()
    gctx, ctx, p, _conn = await _visit(igm, ["T", "x", "T", "x", "L"], gems=9, forest_fights=2)
    await igm.enter(ctx)
    assert p.forest_fights == 3  # only the first tonic counted
    assert p.gems == 6
    assert "Another today would do you harm" in _screen(gctx)


async def test_apothecary_refuses_when_you_cannot_pay():
    igm = Apothecary()
    _gctx, ctx, p, _ = await _visit(igm, ["C", "x", "L"], gems=1)
    await igm.enter(ctx)
    assert p.gems == 1
    assert p.charm == 1


# --- Gem Trader ------------------------------------------------------------


async def test_gems_sell_at_the_days_rate():
    igm = GemTrader()
    # First randrange is the daily rate.
    _gctx, ctx, p, _ = await _visit(
        igm, ["S", "4", "x", "L"], rng=SeqRandom([100]), gems=10, gold=0
    )
    await igm.enter(ctx)
    assert p.gems == 6
    assert p.gold == 400


async def test_the_rate_is_shared_and_survives_the_visit():
    igm = GemTrader()
    _gctx, ctx, _p, database = await _visit(igm, ["L"], rng=SeqRandom([175]))
    await igm.enter(ctx)
    await ctx.store.flush(database)
    assert ctx.store.get("rate") == 175


async def test_haggling_can_backfire():
    igm = GemTrader()
    # rate, then charm too low -> the price drops.
    gctx, ctx, _p, _ = await _visit(igm, ["H", "x", "L"], rng=SeqRandom([200]), charm=1)
    await igm.enter(ctx)
    assert ctx.store.get("rate") == 180
    assert "PRICE DROPS" in _screen(gctx)


# --- Old Skull Inn ---------------------------------------------------------


async def test_arm_wrestling_pays_out_on_a_win():
    igm = OldSkullInn()
    # rumour-free path: stake accepted, then my roll beats his.
    _gctx, ctx, p, database = await _visit(
        igm, ["A", "Y", "x", "L"], rng=SeqRandom([50, 1]), gold=1000, strength=100
    )
    await igm.enter(ctx)
    assert p.gold == 1000 + 250
    row = await query_one(database, "SELECT text FROM daily_news")
    assert row is None  # buffered until the visit protocol flushes


async def test_the_bed_heals_once_a_night():
    igm = OldSkullInn()
    gctx, ctx, p, _ = await _visit(
        igm, ["B", "x", "B", "x", "L"], gold=10_000, hp=5, hp_max=50, level=1
    )
    await igm.enter(ctx)
    assert p.hp == 50
    assert p.gold == 10_000 - 60
    assert "You have had yours" in _screen(gctx)


# --- Abandoned Mines -------------------------------------------------------


async def test_shallow_digging_is_safe():
    igm = AbandonedMines()
    _gctx, ctx, p, _ = await _visit(igm, ["S", "x", "L"], rng=SeqRandom([75]), gold=0, hp=30)
    await igm.enter(ctx)
    assert p.gold == 75
    assert p.hp == 30


async def test_the_deep_shaft_pays_more_and_can_collapse():
    igm = AbandonedMines()
    # gold, gem roll (0 = found), cave-in roll (0 = yes), damage
    _gctx, ctx, p, _ = await _visit(
        igm, ["D", "x", "L"], rng=SeqRandom([500, 0, 0, 10]), gold=0, hp=40, hp_max=40
    )
    await igm.enter(ctx)
    assert p.gold == 500
    assert p.gems == 1
    assert p.hp == 30


async def test_the_deep_shaft_is_once_a_day():
    igm = AbandonedMines()
    gctx, ctx, p, _ = await _visit(
        igm, ["D", "x", "D", "x", "L"], rng=SeqRandom([300, 1, 1]), gold=0
    )
    await igm.enter(ctx)
    assert p.gold == 300
    assert "been down once today" in _screen(gctx)


# --- Arena of Lords --------------------------------------------------------


async def test_arena_win_pays_a_purse_and_starts_a_streak():
    igm = ArenaOfLords()
    _gctx, ctx, p, _ = await _visit(
        igm,
        ["1", "A", "x", "L"],
        rng=SeqRandom([0, 0, 0]),  # opening roll, then a one-shot swing
        level=1,
        strength=30_000,
        hp=500,
        hp_max=500,
        gold=5_000,
    )
    await igm.enter(ctx)
    assert p.gold == 5_000 - 200 + 400
    assert ctx.store.get("streak:1") == 1


async def test_arena_loss_costs_the_fee_and_leaves_you_standing():
    """A real RNG here: the point is the *outcome* (you never die on the
    sand, and the fee is gone), not a pinned damage roll."""
    import random

    igm = ArenaOfLords()
    _gctx, ctx, p, _ = await _visit(
        igm,
        ["3"] + ["A"] * 30 + ["x", "L"],
        rng=random.Random(7),
        level=1,
        strength=1,
        defense=0,
        hp=20,  # above the arena's own "fit to fight" gate (hp_max // 4)
        hp_max=60,
        gold=5_000,
    )
    await igm.enter(ctx)
    assert p.hp == 1  # never killed outright
    assert p.alive == 1
    assert p.gold == 4_800


async def test_arena_refuses_a_bout_you_cannot_pay_for():
    igm = ArenaOfLords()
    gctx, ctx, p, _ = await _visit(igm, ["1", "x", "L"], gold=10, level=5)
    await igm.enter(ctx)
    assert p.gold == 10
    assert "No coin, no bout" in _screen(gctx)


# --- The Latrine -----------------------------------------------------------


async def test_the_wall_remembers_what_you_wrote():
    igm = TheLatrine()
    gctx, ctx, _p, _ = await _visit(igm, ["W", "Turgon smells", "x", "R", "x", "L"])
    await igm.enter(ctx)
    text = _screen(gctx)
    assert "Turgon smells" in text
    assert ctx.store.get("wall")[-1] == ["Hero", "Turgon smells"]


async def test_searching_can_find_gold_or_regret():
    igm = TheLatrine()
    _gctx, ctx, p, _ = await _visit(
        igm, ["S", "x", "L"], rng=SeqRandom([0, 150]), gold=0
    )
    await igm.enter(ctx)
    assert p.gold == 150

    igm = TheLatrine()
    _gctx, ctx, p, _ = await _visit(igm, ["S", "x", "L"], rng=SeqRandom([3]), hp=100, hp_max=100)
    await igm.enter(ctx)
    assert p.hp == 95


# --- Daily allowances: none of these may print money ------------------------


async def test_shallow_digging_is_rationed():
    """Unlimited small payouts are unlimited payouts: sifting used to be an
    endless gold faucet."""
    from igms.abandoned_mines.igm import SHALLOW_PER_DAY

    igm = AbandonedMines()
    keys = []
    for _ in range(SHALLOW_PER_DAY + 2):
        keys += ["S", "x"]
    keys.append("L")
    gctx, ctx, p, _ = await _visit(
        igm, keys, rng=SeqRandom([50] * SHALLOW_PER_DAY), gold=0
    )
    await igm.enter(ctx)

    assert p.gold == 50 * SHALLOW_PER_DAY  # the extra attempts paid nothing
    assert "every heap worth turning today" in _screen(gctx)


async def test_latrine_searching_is_rationed():
    from igms.the_latrine.igm import SEARCH_PER_DAY

    igm = TheLatrine()
    keys = []
    for _ in range(SEARCH_PER_DAY + 1):
        keys += ["S", "x"]
    keys.append("L")
    gctx, ctx, _p, _ = await _visit(igm, keys, rng=SeqRandom([2] * SEARCH_PER_DAY), gold=0)
    await igm.enter(ctx)

    assert "enough for one day" in _screen(gctx)


async def test_arena_bouts_are_rationed():
    """A strong warrior nets purse-minus-fee every win, so an uncapped
    arena prints gold."""
    import random

    from igms.arena_of_lords.igm import BOUTS_PER_DAY

    igm = ArenaOfLords()
    keys = []
    for _ in range(BOUTS_PER_DAY + 1):
        keys += ["1", "A", "x"]
    keys.append("L")
    gctx, ctx, _p, _ = await _visit(
        igm, keys, rng=random.Random(3),
        level=1, strength=30_000, hp=900, hp_max=900, gold=10_000,
    )
    await igm.enter(ctx)

    assert ctx.store.get("bouts:1") == BOUTS_PER_DAY
    assert "day's work" in _screen(gctx)


@pytest.mark.parametrize(
    "igm_cls,keys",
    [
        (AbandonedMines, ["sift:1", "deep:1"]),
        (TheLatrine, ["search:1"]),
        (ArenaOfLords, ["bouts:1", "streak:1"]),
    ],
)
async def test_daily_maint_clears_the_allowances(igm_cls, keys):
    database, repo = await make_db()
    await repo.create("Hero", "pw", "M")
    igm = igm_cls()

    mctx = await make_maint_ctx(database, {}, igm.key)
    for key in keys:
        mctx.store.set(key, 3)
    await mctx.store.flush(database)

    fresh = await make_maint_ctx(database, {}, igm.key)
    await igm.daily_maint(fresh)
    await fresh.store.flush(database)

    after = await make_maint_ctx(database, {}, igm.key)
    assert [after.store.get(k) for k in keys] == [None] * len(keys)
