"""The Wishing Well (wwell12.zip) -- documented recreation.

``contract_check`` covers the framework invariants; these tests pin the
mechanics recorded/invented in ``igms/wishing_well/igm.py``'s module
docstring: the flat per-wish coin cost (spent whether or not the wish is
granted), the daily wish-count gate (with its own recorded "self-
maintaining" justification), the six-outcome wish table pinned outcome by
outcome via ``SeqRandom``, the lifetime (never-reset) ``coins_tossed``
counter shown by "Peer into the well", and the cross-IGM economy
drift-guard confirming the wish table never touches the shared
``has_fairy`` flag priced by ``sunshines_fairy_land``/``kaldors_court``.
"""

from __future__ import annotations

from igms.wishing_well.igm import (
    _WISH_OUTCOME_COUNT,
    WISH_BACKFIRE_GOLD,
    WISH_COST,
    WISH_EXP_PER_LEVEL,
    WISH_GEM_PRIZE,
    WISH_GOLD_PRIZE,
    WISH_LIMIT_PER_DAY,
    WishingWell,
)
from tests.igm_contract import contract_check
from tests.igms._harness import (
    SeqRandom,
    make_ctx,
    make_db,
    make_igm_ctx,
    make_maint_ctx,
)


async def _visit(keys, rng=None, **overrides):
    database, repo = await make_db()
    player = await repo.create("Hero", "pw", "M")
    for key, value in overrides.items():
        setattr(player, key, value)
    gctx = make_ctx(database, repo, player, keys=keys, rng=rng)
    return gctx, await make_igm_ctx(gctx, WishingWell), player, database


async def test_contract():
    await contract_check(WishingWell)


def test_ships_enabled():
    assert WishingWell.default_enabled is True
    assert WishingWell.key == "wishing_well"


# --- Wishing: cost, gate, gold floor -----------------------------------


async def test_wish_charges_coin_cost_regardless_of_outcome():
    # outcome index 4 == "nothing happens" -- no prize, no backfire, but
    # the coin is still spent.
    keys = ["W", "\r", "L"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([4]), gold=10_000)
    await WishingWell().enter(ctx)
    assert p.gold == 10_000 - WISH_COST


async def test_wish_refused_without_enough_gold():
    keys = ["W", "\r", "L"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([4]), gold=WISH_COST - 1)
    await WishingWell().enter(ctx)
    assert p.gold == WISH_COST - 1
    assert any("haven't even got" in line for line in ctx.term.output)


async def test_wish_limited_to_daily_cap():
    keys = ["W", "\r"] * (WISH_LIMIT_PER_DAY + 1) + ["L"]
    _gctx, ctx, p, _db = await _visit(
        keys, rng=SeqRandom([4] * WISH_LIMIT_PER_DAY), gold=1_000_000
    )
    await WishingWell().enter(ctx)
    assert p.gold == 1_000_000 - WISH_COST * WISH_LIMIT_PER_DAY
    assert any("heard enough from you today" in line for line in ctx.term.output)


# --- The wish table, outcome by outcome ---------------------------------


async def test_wish_outcome_0_gold_prize():
    keys = ["W", "\r", "L"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([0]), gold=10_000)
    await WishingWell().enter(ctx)
    assert p.gold == 10_000 - WISH_COST + WISH_GOLD_PRIZE


async def test_wish_outcome_1_exp_prize_is_level_scaled():
    keys = ["W", "\r", "L"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([1]), gold=10_000)
    await WishingWell().enter(ctx)
    assert p.exp == 1 + WISH_EXP_PER_LEVEL * p.level


async def test_wish_outcome_2_gem_prize():
    keys = ["W", "\r", "L"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([2]), gold=10_000)
    await WishingWell().enter(ctx)
    assert p.gems == WISH_GEM_PRIZE


async def test_wish_outcome_3_full_heal():
    keys = ["W", "\r", "L"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([3]), gold=10_000, hp=1)
    await WishingWell().enter(ctx)
    assert p.hp == p.hp_max


async def test_wish_outcome_4_nothing_happens_is_flavor_only():
    keys = ["W", "\r", "L"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([4]), gold=10_000)
    await WishingWell().enter(ctx)
    assert p.gold == 10_000 - WISH_COST
    assert any("well is silent" in line for line in ctx.term.output)


async def test_wish_outcome_5_backfire_costs_extra_gold():
    keys = ["W", "\r", "L"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([5]), gold=10_000)
    await WishingWell().enter(ctx)
    assert p.gold == 10_000 - WISH_COST - WISH_BACKFIRE_GOLD


async def test_wish_backfire_never_drives_gold_negative():
    keys = ["W", "\r", "L"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([5]), gold=WISH_COST)
    await WishingWell().enter(ctx)
    assert p.gold == 0


def test_wish_table_has_six_equally_weighted_outcomes():
    assert _WISH_OUTCOME_COUNT == 6


# --- Economy guardrails ---------------------------------------------------


def test_wish_expected_value_is_negative_including_coin_cost():
    """House-edge guardrail: averaged across all six equally likely
    outcomes, a wish must not be free money -- the coin cost must exceed
    the average net gold swing from the table itself."""
    net_gold_outcomes = [
        WISH_GOLD_PRIZE,  # 0
        0,  # 1: exp, no gold
        0,  # 2: gems, no gold
        0,  # 3: heal, no gold
        0,  # 4: nothing
        -WISH_BACKFIRE_GOLD,  # 5
    ]
    average_swing = sum(net_gold_outcomes) / len(net_gold_outcomes)
    assert average_swing < WISH_COST


async def test_wish_table_never_touches_shared_fairy_flag():
    """Cross-IGM economy guardrail: player.has_fairy is priced realm-wide
    by igms/sunshines_fairy_land/igm.py (pays 500,000) and
    igms/kaldors_court/igm.py (charges 550,000). This IGM's wish table
    must never grant or take has_fairy -- a cheap chance at a shared,
    highly-priced flag would be a free-money generator against either
    shop. Exhaust every wish-table outcome via scripted RNG and confirm
    has_fairy never moves."""
    for outcome in range(_WISH_OUTCOME_COUNT):
        keys = ["W", "\r", "L"]
        _gctx, ctx, p, _db = await _visit(
            keys, rng=SeqRandom([outcome]), gold=1_000_000, has_fairy=0
        )
        await WishingWell().enter(ctx)
        assert p.has_fairy == 0


# --- Peer into the well --------------------------------------------------


async def test_peer_shows_lifetime_total_and_remaining_wishes():
    keys = ["P", "\r", "L"]
    _gctx, ctx, _p, _db = await _visit(keys, rng=SeqRandom([]))
    await WishingWell().enter(ctx)
    out = "\n".join(ctx.term.output)
    assert "coins have vanished" in out
    assert f"{WISH_LIMIT_PER_DAY} wishes left today" in out


async def test_peer_reflects_coins_already_tossed_and_wishes_used():
    keys = ["W", "\r", "P", "\r", "L"]
    _gctx, ctx, _p, _db = await _visit(keys, rng=SeqRandom([4]), gold=10_000)
    await WishingWell().enter(ctx)
    out = "\n".join(ctx.term.output)
    assert f"{WISH_COST} coins have vanished" in out
    assert f"{WISH_LIMIT_PER_DAY - 1} wishes left today" in out


async def test_peer_costs_nothing_and_does_not_consume_a_wish():
    keys = ["P", "\r", "W", "\r", "L"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([4]), gold=10_000)
    await WishingWell().enter(ctx)
    assert p.gold == 10_000 - WISH_COST  # only the one real wish charged


# --- daily_maint -------------------------------------------------------


async def test_daily_maint_resets_wish_gates_but_not_lifetime_total():
    database, repo = await make_db()
    player = await repo.create("Hero", "pw", "M")
    igm = WishingWell()

    mctx = await make_maint_ctx(database, {}, igm.key)
    mctx.store.set(f"wishes:{player.id}", WISH_LIMIT_PER_DAY)
    mctx.store.set("coins_tossed", WISH_COST * 3)
    await mctx.store.flush(database)

    mctx2 = await make_maint_ctx(database, {}, igm.key)
    await igm.daily_maint(mctx2)
    await mctx2.store.flush(database)

    mctx3 = await make_maint_ctx(database, {}, igm.key)
    assert mctx3.store.get(f"wishes:{player.id}") is None
    assert mctx3.store.get("coins_tossed") == WISH_COST * 3
