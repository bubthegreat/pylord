"""Behavior tests for The Warrior's Graveyard (Task 19).

``contract_check`` covers the framework invariants; these tests pin the
IGM's own seeded gameplay: each dig outcome (gold cache, rare gem,
nothing, undead fight), the 5-digs/day gate, an undead fight's victory
payout, the no-kill guard (hp floored to 1, never touching ``alive``, on a
losing fight), the Old Hag's hp<->stat trade and its hp<=5 refusal and
once/day gate, the ghost's listen-for-exp option and its once/day gate,
and ``daily_maint`` clearing all three daily gates.
"""

from __future__ import annotations

from igms.warriors_graveyard.igm import WarriorsGraveyard
from tests.igm_contract import contract_check
from tests.igms._harness import (
    SeqRandom,
    make_ctx,
    make_db,
    make_igm_ctx,
    make_maint_ctx,
)


async def test_contract():
    await contract_check(WarriorsGraveyard)


async def test_dig_finds_gold_cache_exact_amount():
    conn, repo = make_db()
    p = repo.create("Hero", "pw", "M")
    p.gold = 100
    gctx = make_ctx(conn, repo, p, keys=["D", "\r", "L"], rng=SeqRandom([0, 123]))
    igm = WarriorsGraveyard()
    ctx = make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 223


async def test_dig_finds_rare_gem():
    conn, repo = make_db()
    p = repo.create("Hero", "pw", "M")
    gctx = make_ctx(conn, repo, p, keys=["D", "\r", "L"], rng=SeqRandom([4]))
    igm = WarriorsGraveyard()
    ctx = make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gems == 1


async def test_dig_finds_nothing():
    conn, repo = make_db()
    p = repo.create("Hero", "pw", "M")
    p.gold = 50
    gctx = make_ctx(conn, repo, p, keys=["D", "\r", "L"], rng=SeqRandom([5]))
    igm = WarriorsGraveyard()
    ctx = make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 50
    assert p.gems == 0
    assert "find nothing" in "".join(ctx.term.output)


async def test_digs_blocked_after_five_per_day():
    conn, repo = make_db()
    p = repo.create("Hero", "pw", "M")
    igm = WarriorsGraveyard()
    keys = ["D", "\r"] * 6 + ["L"]
    gctx = make_ctx(conn, repo, p, keys=keys, rng=SeqRandom([5, 5, 5, 5, 5]))
    ctx = make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    out = "".join(ctx.term.output)
    assert out.count("find nothing") == 5
    assert "shovel is spent" in out


async def test_undead_fight_victory_grants_exp_and_gold():
    conn, repo = make_db()
    p = repo.create("Hero", "pw", "M")
    p.level = 1
    p.gold = 100
    exp_before = p.exp
    igm = WarriorsGraveyard()
    gctx = make_ctx(
        conn,
        repo,
        p,
        keys=["D", "A", "\r", "L"],
        # dig outcome=7 (undead), name choice idx=0, attack raw=4, crit=9
        # (crit -> dmg*=3 -> 27, one-shots the 15hp monster), loot-bonus
        # roll=2 (no gem/bonus-gold effect), victory gold roll=50.
        rng=SeqRandom([7, 0, 4, 9, 2, 50]),
    )
    ctx = make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.exp == exp_before + 20
    assert p.gold == 150
    from igms.warriors_graveyard.igm import _UNDEAD_NAMES

    assert _UNDEAD_NAMES[0] in "".join(ctx.term.output)


async def test_undead_fight_loss_no_kill_guard_floors_hp_to_one():
    conn, repo = make_db()
    p = repo.create("Hero", "pw", "M")
    p.level = 1
    p.hp = 1
    p.hp_max = 20
    p.strength = 1  # half=0 -> guaranteed miss, no crit possible
    p.defense = 1
    igm = WarriorsGraveyard()
    gctx = make_ctx(
        conn,
        repo,
        p,
        keys=["D", "A", "\r"],
        # dig outcome=7 (undead), name idx=1, player crit_roll draw=5
        # (irrelevant, player misses since str=1 -> half=0), enemy raw
        # draw=3 (raw=3+4=7), enemy power-move draw=0 (no power move) ->
        # atk = 7 - defense(1) = 6, kills the 1-hp player.
        rng=SeqRandom([7, 1, 5, 3, 0]),
    )
    ctx = make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.hp == 1  # floored, never 0
    assert p.alive == 1  # IGM never touches alive
    assert "badly hurt but alive" in "".join(ctx.term.output)


async def test_hag_refuses_trade_at_low_hp():
    conn, repo = make_db()
    p = repo.create("Hero", "pw", "M")
    p.hp = 5
    p.hp_max = 20
    strength_before = p.strength
    gctx = make_ctx(conn, repo, p, keys=["O", "\r", "L"], rng=SeqRandom([]))
    igm = WarriorsGraveyard()
    ctx = make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.hp == 5
    assert p.strength == strength_before
    assert "too weak" in "".join(ctx.term.output)


async def test_hag_trades_hp_for_strength():
    conn, repo = make_db()
    p = repo.create("Hero", "pw", "M")
    p.hp = 15
    p.hp_max = 20
    strength_before = p.strength
    gctx = make_ctx(conn, repo, p, keys=["O", "S", "\r", "L"], rng=SeqRandom([]))
    igm = WarriorsGraveyard()
    ctx = make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.hp == 10
    assert p.strength == strength_before + 1


async def test_hag_trade_blocked_second_time_same_day():
    conn, repo = make_db()
    p = repo.create("Hero", "pw", "M")
    p.hp = 15
    p.hp_max = 20
    igm = WarriorsGraveyard()
    gctx = make_ctx(
        conn, repo, p, keys=["O", "D", "\r", "O", "\r", "L"], rng=SeqRandom([])
    )
    ctx = make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.hp == 10  # only the first trade applied
    assert "Come back tomorrow" in "".join(ctx.term.output)


async def test_ghost_listen_grants_flat_exp_once_per_day():
    conn, repo = make_db()
    p = repo.create("Hero", "pw", "M")
    exp_before = p.exp
    gctx = make_ctx(
        conn, repo, p, keys=["G", "L", "\r", "G", "\r", "L"], rng=SeqRandom([])
    )
    igm = WarriorsGraveyard()
    ctx = make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.exp == exp_before + 25
    assert "quiet tonight" in "".join(ctx.term.output)


async def test_ghost_flee_grants_no_exp():
    conn, repo = make_db()
    p = repo.create("Hero", "pw", "M")
    exp_before = p.exp
    gctx = make_ctx(conn, repo, p, keys=["G", "F", "\r", "L"], rng=SeqRandom([]))
    igm = WarriorsGraveyard()
    ctx = make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.exp == exp_before


async def test_daily_maint_clears_all_gates():
    conn, repo = make_db()
    p = repo.create("Hero", "pw", "M")
    igm = WarriorsGraveyard()
    mctx = make_maint_ctx(conn, {}, igm.key)
    mctx.store.set(f"digs:{p.id}", 5)
    mctx.store.set(f"hag:{p.id}", True)
    mctx.store.set(f"ghost:{p.id}", True)
    mctx.store.flush()
    conn.commit()

    mctx2 = make_maint_ctx(conn, {}, igm.key)
    await igm.daily_maint(mctx2)
    mctx2.store.flush()
    conn.commit()

    mctx3 = make_maint_ctx(conn, {}, igm.key)
    assert mctx3.store.get(f"digs:{p.id}", 0) == 0
    assert mctx3.store.get(f"hag:{p.id}", False) is False
    assert mctx3.store.get(f"ghost:{p.id}", False) is False
