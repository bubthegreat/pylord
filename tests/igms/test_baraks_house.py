"""Behavior tests for Barak's House (Task 15; audited against BARAK.PAS in
Task 2 -- see ``igms/baraks_house/igm.py``'s module docstring).

``contract_check`` covers the framework invariants (guardrails, store
round-trip); these tests pin the IGM's own seeded gameplay: gold find
amount, once-a-day gates (blocked within a visit and across visits via the
flush/fresh-context pattern), the strength-training gain, mother's two
outcomes (now pinned to BARAK.PAS's own recorded numbers -- ``hit := 1`` on
getting caught, the "Ultra Ale" over-heal clamped to ``hp_max``), and
``daily_maint`` clearing the daily gates.
"""

from __future__ import annotations

from igms.baraks_house.igm import BaraksHouse
from tests.igm_contract import contract_check
from tests.igms._harness import (
    SeqRandom,
    make_ctx,
    make_db,
    make_igm_ctx,
    make_maint_ctx,
)


async def test_contract():
    await contract_check(BaraksHouse)


async def test_talk_uses_verbatim_barak_quote():
    """(T)alk's quotes are lifted verbatim from BARAK.PAS dialogue (Task 2
    audit) -- pin one exactly by literal text, not by re-importing
    ``_QUOTES``, so a future edit can't silently drift back to invented
    flavor text without the test noticing.
    """
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    gctx = make_ctx(database, repo, p, keys=["T", "\r", "L"], rng=SeqRandom([2]))
    ctx = await make_igm_ctx(gctx, BaraksHouse())

    await BaraksHouse().enter(ctx)

    out = "".join(ctx.term.output)
    # BARAK.PAS's shoot(): sethln('  `0"Books?!  BOOKS?!  You know I can''t
    # read!" `2Barak shouts, tears').
    assert "Books?!  BOOKS?!  You know I can't read!" in out


async def test_search_finds_gold_exact_amount():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 100
    gctx = make_ctx(database, repo, p, keys=["S", "\r", "L"], rng=SeqRandom([17]))
    igm = BaraksHouse()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 117


async def test_search_blocked_second_time_same_visit():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 100
    gctx = make_ctx(
        database, repo, p, keys=["S", "\r", "S", "\r", "L"], rng=SeqRandom([10])
    )
    igm = BaraksHouse()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 110  # only the first search paid out
    assert "already checked" in "".join(ctx.term.output)


async def test_search_blocked_across_visits_via_store_flush():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 100
    igm = BaraksHouse()

    gctx = make_ctx(database, repo, p, keys=["S", "\r", "L"], rng=SeqRandom([5]))
    ctx1 = await make_igm_ctx(gctx, igm)
    await igm.enter(ctx1)
    await ctx1.store.flush(database)
    assert p.gold == 105

    # Fresh context/visit, same player -- the gate must persist through the DB.
    gctx2 = make_ctx(database, repo, p, keys=["S", "\r", "L"], rng=SeqRandom([]))
    ctx2 = await make_igm_ctx(gctx2, igm)
    await igm.enter(ctx2)

    assert p.gold == 105  # blocked -- no second payout
    assert "already checked" in "".join(ctx2.term.output)


async def test_train_grants_one_strength_once_per_day():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    strength_before = p.strength
    gctx = make_ctx(database, repo, p, keys=["A", "\r", "A", "\r", "L"], rng=SeqRandom([]))
    igm = BaraksHouse()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.strength == strength_before + 1


async def test_train_also_grants_exp_per_hair_end_formula():
    """BARAK.PAS's ``hair_end()`` (:1117-1123) grants exp *unconditionally*
    on every path that reaches it (``times_hit`` 1-5) -- including the
    ``times_hit = 5`` perfect run that already inspired the +1 strength
    reward this action adopted. An earlier audit pass wrongly claimed that
    branch grants "no exp" (Task 2 review finding); this pins the fix.

    ``_train()`` doesn't model ``fly()``'s minigame at all, so there's no
    real ``shots_left`` (tries remaining) to read -- the source formula
    needs one. It assumes the flawless case the reward already implies:
    5 hits on the first 5 of the 10 starting throws (``fly()``:1165,
    ``tries := 10``), leaving ``shots_left = 5``. Source math:
    ``num_end := (times_hit + shots_left) * (10 * level)`` then
    ``num_end := num_end * level`` -- i.e. ``(5 + 5) * 10 * level * level``.
    """
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.level = 3
    exp_before = p.exp
    gctx = make_ctx(database, repo, p, keys=["A", "\r", "L"], rng=SeqRandom([]))
    igm = BaraksHouse()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.exp == exp_before + 900  # (5 + 5) * 10 * 3 * 3


async def test_mother_chases_you_out_ends_visit():
    """BARAK.PAS sets ``pl^.hit := 1`` every time you're caught/defeated --
    beard()'s decline-the-duel branch and run()'s chase-capture both use
    this exact number. Adopted verbatim for the "broom" outcome (Task 2)."""
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.hp = 5
    p.hp_max = 20
    gctx = make_ctx(database, repo, p, keys=["M", "\r"], rng=SeqRandom([0]))
    igm = BaraksHouse()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.hp == 1  # BARAK.PAS: `pl^.hit := 1`
    assert "broom" in "".join(ctx.term.output)


async def test_mother_feeds_soup_heals_within_cap():
    """BARAK.PAS's "Ultra Ale" reward is ``pl^.hit := pl^.hit_max + (pl^.
    hit_max div 4)`` (chest()'s full-clear reward and walk_in()'s kick-and-
    win branch). That formula always exceeds ``hp_max``, so it's a
    guaranteed full heal once ``PlayerView`` clamps it -- exactly the
    "formula exceeds a cap" case flagged in this task's brief. Starting hp
    well below max (5, not 19) so the pre-audit flat ``+2`` and the
    adopted formula would visibly disagree if the adoption were wrong."""
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.hp_max = 20
    p.hp = 5
    gctx = make_ctx(database, repo, p, keys=["M", "\r", "L"], rng=SeqRandom([1]))
    igm = BaraksHouse()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.hp == 20  # 20 + 20//4 = 25, clamped to hp_max by PlayerView


async def test_daily_maint_clears_gates():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    igm = BaraksHouse()
    mctx = await make_maint_ctx(database, {}, igm.key)
    mctx.store.set(f"couch:{p.id}", True)
    mctx.store.set(f"trained:{p.id}", True)
    await mctx.store.flush(database)
    mctx2 = await make_maint_ctx(database, {}, igm.key)
    await igm.daily_maint(mctx2)
    await mctx2.store.flush(database)
    mctx3 = await make_maint_ctx(database, {}, igm.key)
    assert mctx3.store.get(f"couch:{p.id}", False) is False
    assert mctx3.store.get(f"trained:{p.id}", False) is False
