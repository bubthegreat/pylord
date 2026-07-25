"""Behavior tests for Violet's Cottage (Task 17).

``contract_check`` covers the framework invariants; these tests pin the
charm-check math (success/fail, floored at 1), the tea heal and kids-play
exp, once-a-day gates cleared by ``daily_maint``, and the
married-to-Violet celebration branch (``daily_maint`` bridges the global
NPC-marriage singleton -- unreachable from ``enter()``'s guardrailed
``ctx`` -- into a per-player store flag; see the module docstring for why).
"""

from __future__ import annotations

from igms.violets_cottage.igm import VioletsCottage
from pylord.engine import npc_state
from tests.igm_contract import contract_check
from tests.igms._harness import (
    SeqRandom,
    make_ctx,
    make_db,
    make_igm_ctx,
    make_maint_ctx,
)


async def test_contract():
    await contract_check(VioletsCottage)


# --- impress her parents --------------------------------------------------


async def test_impress_success_grants_charm():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    charm_before = p.charm
    gctx = make_ctx(database, repo, p, keys=["I", "\r", "L"], rng=SeqRandom([0]))
    igm = VioletsCottage()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.charm == charm_before + 1


async def test_impress_fail_loses_charm_floored_at_zero():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.charm = 0
    gctx = make_ctx(database, repo, p, keys=["I", "\r", "L"], rng=SeqRandom([1]))
    igm = VioletsCottage()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.charm == 0  # PlayerView floors charm at 0 (lord.js:16653-16654)


async def test_impress_blocked_second_time_same_visit():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.charm = 5
    gctx = make_ctx(
        database, repo, p, keys=["I", "\r", "I", "\r", "L"], rng=SeqRandom([0])
    )
    igm = VioletsCottage()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.charm == 6  # only the first attempt counted
    assert "already" in "".join(ctx.term.output)


# --- tea with grandma ------------------------------------------------------


async def test_tea_heals_within_hp_max():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.hp_max = 20
    p.hp = 19
    gctx = make_ctx(database, repo, p, keys=["T", "\r", "L"], rng=SeqRandom([]))
    igm = VioletsCottage()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.hp == 20  # clamped, not 21


async def test_tea_blocked_second_time_same_visit():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.hp_max = 30
    p.hp = 10
    gctx = make_ctx(
        database, repo, p, keys=["T", "\r", "T", "\r", "L"], rng=SeqRandom([])
    )
    igm = VioletsCottage()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.hp == 12  # only the first cup of tea healed


# --- play with the kids -----------------------------------------------


async def test_play_grants_flat_ten_exp():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    exp_before = p.exp
    gctx = make_ctx(database, repo, p, keys=["P", "\r", "L"], rng=SeqRandom([]))
    igm = VioletsCottage()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.exp == exp_before + 10


# --- daily_maint clears gates + refreshes the marriage flag ---------------


async def test_daily_maint_clears_gates():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    igm = VioletsCottage()
    mctx = await make_maint_ctx(database, {}, igm.key)
    mctx.store.set(f"impress:{p.id}", True)
    mctx.store.set(f"tea:{p.id}", True)
    mctx.store.set(f"play:{p.id}", True)
    await mctx.store.flush(database)
    mctx2 = await make_maint_ctx(database, {}, igm.key)
    await igm.daily_maint(mctx2)
    await mctx2.store.flush(database)
    mctx3 = await make_maint_ctx(database, {}, igm.key)
    assert mctx3.store.get(f"impress:{p.id}", False) is False
    assert mctx3.store.get(f"tea:{p.id}", False) is False
    assert mctx3.store.get(f"play:{p.id}", False) is False


async def test_daily_maint_refreshes_married_flag_from_npc_state():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    await npc_state.set_married_to_violet(database, p.id)
    igm = VioletsCottage()

    mctx = await make_maint_ctx(database, {}, igm.key)
    await igm.daily_maint(mctx)
    await mctx.store.flush(database)
    mctx2 = await make_maint_ctx(database, {}, igm.key)
    assert mctx2.store.get(f"married_violet:{p.id}", False) is True


# --- married-to-Violet celebration branch ----------------------------------


async def test_married_celebration_grants_charm_once_ever():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    charm_before = p.charm
    igm = VioletsCottage()

    # Simulate daily_maint having already cached the marriage flag.
    gctx1 = make_ctx(database, repo, p, keys=["\r"], rng=SeqRandom([]))
    ctx1 = await make_igm_ctx(gctx1, igm)
    ctx1.store.set(f"married_violet:{p.id}", True)
    await igm.enter(ctx1)
    await ctx1.store.flush(database)
    assert p.charm == charm_before + 1
    assert "family" in "".join(ctx1.term.output).lower()

    # A second visit, fresh context reading the flag from the DB: no
    # further charm gain -- the celebration is a once-ever event.
    gctx2 = make_ctx(database, repo, p, keys=["\r"], rng=SeqRandom([]))
    ctx2 = await make_igm_ctx(gctx2, igm)
    await igm.enter(ctx2)

    assert p.charm == charm_before + 1


async def test_not_married_shows_full_menu():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    gctx = make_ctx(database, repo, p, keys=["L"], rng=SeqRandom([]))
    igm = VioletsCottage()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    out = "".join(ctx.term.output)
    assert "mpress" in out
    assert "ea with" in out or "Grandma" in out
