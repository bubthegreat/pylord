"""SunShines' Fairy Land (sfairy26.zip) -- documented recreation.

``contract_check`` covers the framework invariants; these tests pin the
mechanics recorded in ``igms/sunshines_fairy_land/igm.py``'s module
docstring: the 5-tries-a-day fairy limit ("Now limits fairy tries to 5" /
the SFAIRY.DAT file description), the level-12 Market ban ("Players at
level 12 can not enter SunShines Market"), the General Store's 15 recorded
default prices and the half-price sell-back rule ("All selling prices
(with the exception of a fairy) are 1/2 the purchase price"), the fairy's
full (non-halved) sell price, and the Bank's deposit/withdraw "1 = all"
convention borrowed from this project's own real Ye Old Bank.
"""

from __future__ import annotations

from igms.sunshines_fairy_land.igm import (
    FAIRY_SELL_PRICE,
    FAIRY_TRY_LIMIT,
    MARKET_LEVEL_BAN,
    NUMBER_GAME_EXP_PER_LEVEL,
    NUMBER_GAME_GEM_PRIZE,
    NUMBER_GAME_GOLD_PRIZE,
    NUMBER_GAME_RANGE,
    PRICE_HIT_POINTS,
    PRICE_HORSE,
    PRICE_KIDS,
    PRICE_MASTER_FIGHT,
    PRICE_RESURRECTION,
    PRICE_SEX_CHANGE,
    PRICE_SKILL_POINT,
    PRICE_STRENGTH,
    SELL_PRICE_FRACTION,
    SunshinesFairyLand,
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
    return gctx, await make_igm_ctx(gctx, SunshinesFairyLand), player, database


async def test_contract():
    await contract_check(SunshinesFairyLand)


def test_ships_enabled():
    assert SunshinesFairyLand.default_enabled is True
    assert SunshinesFairyLand.key == "sunshines_fairy_land"


# --- Catch a fairy: 5 tries/day, resets daily -------------------------------


async def test_catch_fairy_success():
    _gctx, ctx, p, _db = await _visit(["C", "\r", "L"], rng=SeqRandom([0]))
    await SunshinesFairyLand().enter(ctx)
    assert p.has_fairy == 1


async def test_catch_fairy_failure():
    _gctx, ctx, p, _db = await _visit(["C", "\r", "L"], rng=SeqRandom([1]))
    await SunshinesFairyLand().enter(ctx)
    assert p.has_fairy == 0


async def test_catch_fairy_already_holding_one_refused_no_roll():
    _gctx, ctx, p, _db = await _visit(["C", "\r", "L"], has_fairy=1)
    await SunshinesFairyLand().enter(ctx)
    assert p.has_fairy == 1  # unchanged; SeqRandom([]) would have raised on a roll


async def test_catch_fairy_limited_to_five_tries_per_day():
    keys = ["C", "\r"] * (FAIRY_TRY_LIMIT + 1) + ["L"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([1] * FAIRY_TRY_LIMIT))
    await SunshinesFairyLand().enter(ctx)
    assert p.has_fairy == 0
    assert ctx.store.get(f"fairy_tries:{p.id}") == FAIRY_TRY_LIMIT
    assert any("enough for one day" in line for line in ctx.term.output)


async def test_daily_maint_resets_fairy_tries_and_number_game_gate():
    database, repo = await make_db()
    player = await repo.create("Hero", "pw", "M")
    igm = SunshinesFairyLand()

    mctx = await make_maint_ctx(database, {}, igm.key)
    mctx.store.set(f"fairy_tries:{player.id}", FAIRY_TRY_LIMIT)
    mctx.store.set(f"numbergame:{player.id}", True)
    await mctx.store.flush(database)

    mctx2 = await make_maint_ctx(database, {}, igm.key)
    await igm.daily_maint(mctx2)
    await mctx2.store.flush(database)

    mctx3 = await make_maint_ctx(database, {}, igm.key)
    assert mctx3.store.get(f"fairy_tries:{player.id}") is None
    assert mctx3.store.get(f"numbergame:{player.id}") is None


# --- General Store: level-12 Market ban -------------------------------------


async def test_market_refuses_level_12():
    _gctx, ctx, p, _db = await _visit(["G", "\r", "L"], level=MARKET_LEVEL_BAN, gold=1_000_000)
    await SunshinesFairyLand().enter(ctx)
    assert p.gold == 1_000_000  # nothing charged, store never opened
    assert any("outgrown my little shop" in line for line in ctx.term.output)


# --- General Store: point wares (buy/sell at the recorded prices) ----------


async def test_buy_strength_charges_price_per_unit():
    _gctx, ctx, p, _db = await _visit(
        ["G", "S", "B", "3", "\r", "L", "L"], gold=1_000_000
    )
    await SunshinesFairyLand().enter(ctx)
    assert p.strength == 10 + 3
    assert p.gold == 1_000_000 - 3 * PRICE_STRENGTH


async def test_buy_strength_insufficient_gold_refused():
    _gctx, ctx, p, _db = await _visit(["G", "S", "B", "3", "\r", "L", "L"], gold=1_000)
    await SunshinesFairyLand().enter(ctx)
    assert p.strength == 10
    assert p.gold == 1_000


async def test_sell_strength_at_half_price():
    _gctx, ctx, p, _db = await _visit(["G", "S", "S", "2", "\r", "L", "L"])
    await SunshinesFairyLand().enter(ctx)
    assert p.strength == 10 - 2
    assert p.gold == 500 + int(2 * PRICE_STRENGTH * SELL_PRICE_FRACTION)


async def test_sell_more_strength_than_owned_refused():
    _gctx, ctx, p, _db = await _visit(["G", "S", "S", "50", "\r", "L", "L"])
    await SunshinesFairyLand().enter(ctx)
    assert p.strength == 10
    assert p.gold == 500


async def test_buy_hit_points_raises_hp_max_not_current_hp():
    _gctx, ctx, p, _db = await _visit(
        ["G", "H", "B", "5", "\r", "L", "L"], gold=1_000_000
    )
    await SunshinesFairyLand().enter(ctx)
    assert p.hp_max == 20 + 5
    assert p.hp == 20  # unchanged -- a max raise, not a heal


async def test_sell_hit_points_reclamps_current_hp_down():
    _gctx, ctx, p, _db = await _visit(
        ["G", "H", "S", "15", "\r", "L", "L"], hp=20, hp_max=20
    )
    await SunshinesFairyLand().enter(ctx)
    assert p.hp_max == 5
    assert p.hp == 5  # reclamped down from 20


async def test_sell_hit_points_cannot_zero_out_hp_max():
    """A live player with hp_max == 0 is a nonsense state -- selling all 20
    units is refused outright rather than clamped/partial-filled."""
    _gctx, ctx, p, _db = await _visit(
        ["G", "H", "S", "20", "\r", "L", "L"], hp=20, hp_max=20
    )
    await SunshinesFairyLand().enter(ctx)
    assert p.hp_max == 20  # refused -- unchanged
    assert p.gold == 500  # nothing paid out


async def test_sell_hit_points_down_to_the_floor_of_one():
    """One less than the full stack is the most that can ever be sold."""
    _gctx, ctx, p, _db = await _visit(
        ["G", "H", "S", "19", "\r", "L", "L"], hp=20, hp_max=20
    )
    await SunshinesFairyLand().enter(ctx)
    assert p.hp_max == 1
    assert p.hp == 1  # reclamped down alongside hp_max
    assert p.gold == 500 + int(19 * PRICE_HIT_POINTS * SELL_PRICE_FRACTION)


async def test_buy_experience_is_scaled_by_exp_unit():
    _gctx, ctx, p, _db = await _visit(
        ["G", "E", "B", "2", "\r", "L", "L"], gold=1_000_000
    )
    await SunshinesFairyLand().enter(ctx)
    assert p.exp == 1 + 2 * 1_000  # EXP_UNIT


async def test_buy_forest_fights_credits_today_only_not_permanent_bonus():
    _gctx, ctx, p, _db = await _visit(
        ["G", "F", "B", "2", "\r", "L", "L"], gold=1_000_000
    )
    await SunshinesFairyLand().enter(ctx)
    assert p.forest_fights == 15 + 2
    assert p.fight_bonus == 0  # the permanent capacity system is untouched


async def test_forest_fights_cannot_be_sold_back():
    """Fixed post-review: selling forest_fights back would combine with the
    engine's own free real-time regen (pylord/engine/fights.py's
    apply_regen) for unbounded gold. The store's Buy/Sell submenu simply
    never offers "S" for this ware -- pressing it is an invalid key the
    menu ignores and re-prompts on."""
    _gctx, ctx, p, _db = await _visit(["G", "F", "S", "L", "L", "L"])
    await SunshinesFairyLand().enter(ctx)
    assert p.forest_fights == 15
    assert p.gold == 500


async def test_player_fights_cannot_be_sold_back():
    """Same buy-only restriction, kept consistent with forest_fights even
    though player_fights has no free regen of its own -- see module
    docstring."""
    _gctx, ctx, p, _db = await _visit(["G", "P", "S", "L", "L", "L"])
    await SunshinesFairyLand().enter(ctx)
    assert p.player_fights == 3
    assert p.gold == 500


# --- General Store: one-time wares ------------------------------------------


async def test_buy_horse():
    _gctx, ctx, p, _db = await _visit(
        ["G", "O", "Y", "\r", "L", "L"], gold=1_000_000
    )
    await SunshinesFairyLand().enter(ctx)
    assert p.horse == 1
    assert p.gold == 1_000_000 - PRICE_HORSE


async def test_buy_horse_already_owned_refused():
    _gctx, ctx, p, _db = await _visit(["G", "O", "\r", "L", "L"], horse=1, gold=1_000_000)
    await SunshinesFairyLand().enter(ctx)
    assert p.gold == 1_000_000  # nothing charged


async def test_buy_skill_point():
    _gctx, ctx, p, _db = await _visit(
        ["G", "K", "Y", "\r", "L", "L"], gold=1_000_000
    )
    await SunshinesFairyLand().enter(ctx)
    assert p.skill_uses == 1
    assert p.gold == 1_000_000 - PRICE_SKILL_POINT


async def test_buy_kid():
    _gctx, ctx, p, _db = await _visit(
        ["G", "I", "Y", "\r", "L", "L"], gold=1_000_000
    )
    await SunshinesFairyLand().enter(ctx)
    assert p.kids == 1
    assert p.gold == 1_000_000 - PRICE_KIDS


async def test_resurrection_refused_while_alive():
    _gctx, ctx, p, _db = await _visit(["G", "R", "\r", "L", "L"], gold=1_000_000)
    await SunshinesFairyLand().enter(ctx)
    assert p.gold == 1_000_000


async def test_resurrection_revives_and_fully_heals():
    _gctx, ctx, p, _db = await _visit(
        ["G", "R", "Y", "\r", "L", "L"], alive=0, hp=0, hp_max=20, gold=1_000_000
    )
    await SunshinesFairyLand().enter(ctx)
    assert p.alive == 1
    assert p.hp == 20
    assert p.gold == 1_000_000 - PRICE_RESURRECTION


async def test_sex_change_toggles_gender():
    _gctx, ctx, p, _db = await _visit(
        ["G", "X", "Y", "\r", "L", "L"], gold=1_000_000
    )
    await SunshinesFairyLand().enter(ctx)
    assert p.gender == "F"
    assert p.gold == 1_000_000 - PRICE_SEX_CHANGE


async def test_master_fight_reset_refused_without_having_seen_master():
    _gctx, ctx, p, _db = await _visit(["G", "M", "\r", "L", "L"], gold=1_000_000)
    await SunshinesFairyLand().enter(ctx)
    assert p.gold == 1_000_000


async def test_master_fight_reset():
    _gctx, ctx, p, _db = await _visit(
        ["G", "M", "Y", "\r", "L", "L"], seen_master=1, gold=1_000_000
    )
    await SunshinesFairyLand().enter(ctx)
    assert p.seen_master == 0
    assert p.gold == 1_000_000 - PRICE_MASTER_FIGHT


async def test_sell_fairy_without_one_refused():
    _gctx, ctx, p, _db = await _visit(["G", "Z", "\r", "L", "L"])
    await SunshinesFairyLand().enter(ctx)
    assert p.gold == 500


async def test_sell_fairy_pays_full_price_not_halved():
    _gctx, ctx, p, _db = await _visit(["G", "Z", "Y", "\r", "L", "L"], has_fairy=1)
    await SunshinesFairyLand().enter(ctx)
    assert p.has_fairy == 0
    assert p.gold == 500 + FAIRY_SELL_PRICE


# --- Number game: 8 prizes, one guess per day -------------------------------


async def test_number_game_correct_guess_wins_a_prize():
    _gctx, ctx, p, _db = await _visit(
        ["N", str(NUMBER_GAME_RANGE), "\r", "L"],
        rng=SeqRandom([NUMBER_GAME_RANGE, 0]),
    )
    await SunshinesFairyLand().enter(ctx)
    assert p.gold == 500 + NUMBER_GAME_GOLD_PRIZE


async def test_number_game_wrong_guess_no_prize():
    _gctx, ctx, p, _db = await _visit(
        ["N", "1", "\r", "L"], rng=SeqRandom([NUMBER_GAME_RANGE])
    )
    await SunshinesFairyLand().enter(ctx)
    assert p.gold == 500
    assert p.gems == 0


async def test_number_game_once_per_day():
    _gctx, ctx, p, _db = await _visit(
        ["N", str(NUMBER_GAME_RANGE), "\r", "N", "\r", "L"],
        rng=SeqRandom([NUMBER_GAME_RANGE, 0]),
    )
    await SunshinesFairyLand().enter(ctx)
    assert p.gold == 500 + NUMBER_GAME_GOLD_PRIZE  # only the first attempt paid out


async def test_number_game_all_eight_prizes():
    """Exercise every prize branch directly -- the count (8) is the one
    recorded number here; each branch's effect is invented (see module
    docstring), pinned so no branch silently breaks."""
    igm = SunshinesFairyLand()
    database, repo = await make_db()

    async def _prize_player(prize, **overrides):
        player = await repo.create(f"P{prize}", "pw", "M")
        for key, value in overrides.items():
            setattr(player, key, value)
        gctx = make_ctx(database, repo, player, keys=["\r"])
        ctx = await make_igm_ctx(gctx, igm)
        await igm._award_number_game_prize(ctx, prize)
        return player

    p0 = await _prize_player(0)
    assert p0.gold == 500 + NUMBER_GAME_GOLD_PRIZE

    p1 = await _prize_player(1)
    assert p1.gems == NUMBER_GAME_GEM_PRIZE

    p2 = await _prize_player(2)
    assert p2.exp == 1 + NUMBER_GAME_EXP_PER_LEVEL * p2.level

    p3 = await _prize_player(3, hp=1, hp_max=20)
    assert p3.hp == 20

    p4 = await _prize_player(4)
    assert p4.strength == 11

    p5 = await _prize_player(5)
    assert p5.defense == 4  # model default (3) + 1

    p6 = await _prize_player(6)
    assert p6.charm == 2

    p7 = await _prize_player(7)
    assert p7.forest_fights == 16


# --- Bank: deposit/withdraw, "1" means "all" --------------------------------


async def test_bank_deposit():
    _gctx, ctx, p, _db = await _visit(["B", "D", "300", "\r", "L", "L"], gold=1_000)
    await SunshinesFairyLand().enter(ctx)
    assert p.gold == 700
    assert p.bank == 300


async def test_bank_deposit_all():
    _gctx, ctx, p, _db = await _visit(["B", "D", "1", "\r", "L", "L"], gold=1_000)
    await SunshinesFairyLand().enter(ctx)
    assert p.gold == 0
    assert p.bank == 1_000


async def test_bank_withdraw():
    _gctx, ctx, p, _db = await _visit(
        ["B", "W", "150", "\r", "L", "L"], gold=500, bank=500
    )
    await SunshinesFairyLand().enter(ctx)
    assert p.gold == 650
    assert p.bank == 350


async def test_bank_withdraw_all():
    _gctx, ctx, p, _db = await _visit(
        ["B", "W", "1", "\r", "L", "L"], gold=500, bank=500
    )
    await SunshinesFairyLand().enter(ctx)
    assert p.gold == 1_000
    assert p.bank == 0


async def test_bank_deposit_clamps_at_cap():
    _gctx, ctx, p, _db = await _visit(
        ["B", "D", "100", "\r", "L", "L"], gold=1_000, bank=2_000_000_000 - 10
    )
    await SunshinesFairyLand().enter(ctx)
    assert p.bank == 2_000_000_000
    assert p.gold == 1_000 - 10
