"""Behavior tests for Turgon's House (Task 18).

``contract_check`` covers the framework invariants; these tests pin the
IGM's own seeded gameplay: each search outcome (guard dog, gems, off-duty
Turgon exp, coupon find, nothing), the 3-searches/day gate, the coupon
"one at a time" fold-into-nothing, talking's once/day defense gate (and its
level-6 threshold), and ``daily_maint`` clearing the daily gates while
leaving a held coupon alone.
"""

from __future__ import annotations

from igms.turgons_house.igm import TurgonsHouse
from tests.igms._harness import (
    SeqRandom,
    make_ctx,
    make_db,
    make_igm_ctx,
    make_maint_ctx,
)


async def test_search_guard_dog_bites():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.hp = 10
    p.hp_max = 20
    gctx = make_ctx(database, repo, p, keys=["S", "\r", "L"], rng=SeqRandom([0, 2]))
    igm = TurgonsHouse()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.hp == 8
    assert "guard dog" in "".join(ctx.term.output)


async def test_search_guard_dog_no_kill_guard_floors_hp_to_one():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.hp = 1
    p.hp_max = 20
    gctx = make_ctx(database, repo, p, keys=["S", "\r", "L"], rng=SeqRandom([0, 3]))
    igm = TurgonsHouse()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.hp == 1  # floored, never 0 or negative


async def test_search_finds_gems_exact_amount():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    gctx = make_ctx(database, repo, p, keys=["S", "\r", "L"], rng=SeqRandom([1, 2]))
    igm = TurgonsHouse()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gems == 2


async def test_search_meets_turgon_off_duty_grants_flat_exp():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    exp_before = p.exp
    gctx = make_ctx(database, repo, p, keys=["S", "\r", "L"], rng=SeqRandom([2]))
    igm = TurgonsHouse()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.exp == exp_before + 15


async def test_search_finds_coupon_once():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    gctx = make_ctx(database, repo, p, keys=["S", "\r", "L"], rng=SeqRandom([3]))
    igm = TurgonsHouse()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert ctx.store.get(f"coupon:{p.id}") is True
    assert "coupon" in "".join(ctx.term.output)


async def test_search_second_coupon_folds_into_nothing():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    igm = TurgonsHouse()
    gctx = make_ctx(
        database, repo, p, keys=["S", "\r", "S", "\r", "L"], rng=SeqRandom([3, 3])
    )
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    out = "".join(ctx.term.output)
    assert out.count("discount coupon") == 1
    assert out.count("nothing of interest") == 1


async def test_search_blocked_after_three_per_day():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    igm = TurgonsHouse()
    gctx = make_ctx(
        database,
        repo,
        p,
        keys=["S", "\r", "S", "\r", "S", "\r", "S", "\r", "L"],
        rng=SeqRandom([9, 9, 9]),
    )
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    out = "".join(ctx.term.output)
    assert out.count("nothing of interest") == 3
    assert "already searched" in out


async def test_talk_grants_defense_once_per_day_at_level_6():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.level = 6
    defense_before = p.defense
    gctx = make_ctx(
        database, repo, p, keys=["T", "\r", "T", "\r", "L"], rng=SeqRandom([0, 0])
    )
    igm = TurgonsHouse()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.defense == defense_before + 1


async def test_talk_below_level_6_grants_no_defense():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.level = 5
    defense_before = p.defense
    gctx = make_ctx(database, repo, p, keys=["T", "\r", "L"], rng=SeqRandom([0]))
    igm = TurgonsHouse()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.defense == defense_before


async def test_daily_maint_clears_searches_and_talked_but_not_coupon():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    igm = TurgonsHouse()
    mctx = await make_maint_ctx(database, {}, igm.key)
    mctx.store.set(f"searches:{p.id}", 3)
    mctx.store.set(f"talked:{p.id}", True)
    mctx.store.set(f"coupon:{p.id}", True)
    await mctx.store.flush(database)
    mctx2 = await make_maint_ctx(database, {}, igm.key)
    await igm.daily_maint(mctx2)
    await mctx2.store.flush(database)
    mctx3 = await make_maint_ctx(database, {}, igm.key)
    assert mctx3.store.get(f"searches:{p.id}", 0) == 0
    assert mctx3.store.get(f"talked:{p.id}", False) is False
    assert mctx3.store.get(f"coupon:{p.id}", False) is True
