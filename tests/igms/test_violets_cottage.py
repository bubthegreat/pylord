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
    conn, repo = make_db()
    p = repo.create("Hero", "pw", "M")
    charm_before = p.charm
    gctx = make_ctx(conn, repo, p, keys=["I", "\r", "L"], rng=SeqRandom([0]))
    igm = VioletsCottage()
    ctx = make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.charm == charm_before + 1


async def test_impress_fail_loses_charm_floored_at_one():
    conn, repo = make_db()
    p = repo.create("Hero", "pw", "M")
    p.charm = 1
    gctx = make_ctx(conn, repo, p, keys=["I", "\r", "L"], rng=SeqRandom([1]))
    igm = VioletsCottage()
    ctx = make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.charm == 1  # PlayerView floors charm at 1, never 0


async def test_impress_blocked_second_time_same_visit():
    conn, repo = make_db()
    p = repo.create("Hero", "pw", "M")
    p.charm = 5
    gctx = make_ctx(
        conn, repo, p, keys=["I", "\r", "I", "\r", "L"], rng=SeqRandom([0])
    )
    igm = VioletsCottage()
    ctx = make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.charm == 6  # only the first attempt counted
    assert "already" in "".join(ctx.term.output)


# --- tea with grandma ------------------------------------------------------


async def test_tea_heals_within_hp_max():
    conn, repo = make_db()
    p = repo.create("Hero", "pw", "M")
    p.hp_max = 20
    p.hp = 19
    gctx = make_ctx(conn, repo, p, keys=["T", "\r", "L"], rng=SeqRandom([]))
    igm = VioletsCottage()
    ctx = make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.hp == 20  # clamped, not 21


async def test_tea_blocked_second_time_same_visit():
    conn, repo = make_db()
    p = repo.create("Hero", "pw", "M")
    p.hp_max = 30
    p.hp = 10
    gctx = make_ctx(
        conn, repo, p, keys=["T", "\r", "T", "\r", "L"], rng=SeqRandom([])
    )
    igm = VioletsCottage()
    ctx = make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.hp == 12  # only the first cup of tea healed


# --- play with the kids -----------------------------------------------


async def test_play_grants_flat_ten_exp():
    conn, repo = make_db()
    p = repo.create("Hero", "pw", "M")
    exp_before = p.exp
    gctx = make_ctx(conn, repo, p, keys=["P", "\r", "L"], rng=SeqRandom([]))
    igm = VioletsCottage()
    ctx = make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.exp == exp_before + 10


# --- daily_maint clears gates + refreshes the marriage flag ---------------


async def test_daily_maint_clears_gates():
    conn, repo = make_db()
    p = repo.create("Hero", "pw", "M")
    igm = VioletsCottage()
    mctx = make_maint_ctx(conn, {}, igm.key)
    mctx.store.set(f"impress:{p.id}", True)
    mctx.store.set(f"tea:{p.id}", True)
    mctx.store.set(f"play:{p.id}", True)
    mctx.store.flush()
    conn.commit()

    mctx2 = make_maint_ctx(conn, {}, igm.key)
    await igm.daily_maint(mctx2)
    mctx2.store.flush()
    conn.commit()

    mctx3 = make_maint_ctx(conn, {}, igm.key)
    assert mctx3.store.get(f"impress:{p.id}", False) is False
    assert mctx3.store.get(f"tea:{p.id}", False) is False
    assert mctx3.store.get(f"play:{p.id}", False) is False


async def test_daily_maint_refreshes_married_flag_from_npc_state():
    conn, repo = make_db()
    p = repo.create("Hero", "pw", "M")
    npc_state.set_married_to_violet(conn, p.id)
    igm = VioletsCottage()

    mctx = make_maint_ctx(conn, {}, igm.key)
    await igm.daily_maint(mctx)
    mctx.store.flush()
    conn.commit()

    mctx2 = make_maint_ctx(conn, {}, igm.key)
    assert mctx2.store.get(f"married_violet:{p.id}", False) is True


# --- married-to-Violet celebration branch ----------------------------------


async def test_married_celebration_grants_charm_once_ever():
    conn, repo = make_db()
    p = repo.create("Hero", "pw", "M")
    charm_before = p.charm
    igm = VioletsCottage()

    # Simulate daily_maint having already cached the marriage flag.
    gctx1 = make_ctx(conn, repo, p, keys=["\r"], rng=SeqRandom([]))
    ctx1 = make_igm_ctx(gctx1, igm)
    ctx1.store.set(f"married_violet:{p.id}", True)
    await igm.enter(ctx1)
    ctx1.store.flush()
    conn.commit()

    assert p.charm == charm_before + 1
    assert "family" in "".join(ctx1.term.output).lower()

    # A second visit, fresh context reading the flag from the DB: no
    # further charm gain -- the celebration is a once-ever event.
    gctx2 = make_ctx(conn, repo, p, keys=["\r"], rng=SeqRandom([]))
    ctx2 = make_igm_ctx(gctx2, igm)
    await igm.enter(ctx2)

    assert p.charm == charm_before + 1


async def test_not_married_shows_full_menu():
    conn, repo = make_db()
    p = repo.create("Hero", "pw", "M")
    gctx = make_ctx(conn, repo, p, keys=["L"], rng=SeqRandom([]))
    igm = VioletsCottage()
    ctx = make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    out = "".join(ctx.term.output)
    assert "mpress" in out
    assert "ea with" in out or "Grandma" in out
