"""Wave-3 IGMs: Seth's Tribute Lotto, Pickle's, Olodrin's Orphanage and
The FreeWorld II.

Unlike waves 1 and 2, these are **ports** of the real sources vendored in
``reference/igm-sources/`` -- so these tests pin the ported formulas against
the source's own numbers, not against invented balance. Where a test asserts
something that looks wrong (row 10 paying the same as row 1; a level-12
jackpot hitting the gold ceiling; a catch mini-game that can only ever land
your first child), it is pinning a faithfully-reproduced flaw of the
original. See each IGM's module docstring.
"""

from __future__ import annotations

import pytest

from igms.freeworld2.igm import (
    CHANCELLOR_PRIZE,
    CHANCELLOR_TRIES,
    MAX_WALKS,
    FreeWorld2,
    fairy_gold,
)
from igms.lotto.igm import Lotto, count_matches, prize
from igms.oorphans.igm import (
    MAX_KIDS,
    MAX_PRICE,
    SELL_PRICE,
    Oorphans,
    adoption_price,
    horse_trade_cost,
    js_round,
)
from igms.pickle.igm import BAD_FROM, ROW_MAX, TATTOO, Pickles, row_pct
from tests.igms._harness import (
    SeqRandom,
    make_ctx,
    make_db,
    make_igm_ctx,
    make_maint_ctx,
)


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


# --- Seth's Tribute Lotto -------------------------------------------------


@pytest.mark.parametrize(
    ("player_code", "machine_code", "expected"),
    [
        ("1234", "1234", 4),
        ("4321", "1234", 4),  # position does not matter
        ("1111", "1234", 1),  # ...but one player digit answers one machine digit
        ("1234", "1111", 1),  # and symmetrically
        ("1122", "1234", 2),
        ("5678", "1234", 0),
        ("0000", "0000", 4),
    ],
)
def test_count_matches(player_code, machine_code, expected):
    """The used[] rule from lotto.ts:132-145 -- no digit counted twice."""
    assert count_matches(player_code, machine_code) == expected


@pytest.mark.parametrize(
    ("level", "matched", "expected"),
    [
        # magicnum 10 (odd level), x10 twice = 1000, then /10 three times
        (1, 1, 1),
        (1, 4, 1000),
        # magicnum 30 (even level), x10 three times = 30000
        (2, 4, 30000),
        (2, 1, 30),
        # level 12 is the one explicit override in the source: 20, not 30
        (12, 4, 2_000_000_000),
        (11, 4, 100_000_000),
        (12, 1, 2_000_000),
    ],
)
def test_prize_table(level, matched, expected):
    """Literal port of lotto.ts:168-176, including the level-12 override and
    the payout curve that makes this IGM a money printer at high level."""
    assert prize(level, matched) == expected


def test_prize_level_12_is_not_the_even_level_rule():
    """Level 12 uses 20, so it pays *less* than the 30-based even-level rule
    would -- the source's one hand-tuned exception, easy to lose in a port."""
    magicnum_30_rule = 30 * 10 ** (12 // 2 + 2)
    assert prize(12, 4) < magicnum_30_rule


async def test_lotto_charges_and_pays_a_full_match():
    """Ticket is 10 * level; a 4-digit match pays the table above."""
    gctx, ctx, player, _db = await _visit(
        Lotto(),
        keys=["Y", "1234", "\r"],
        rng=SeqRandom([1, 2, 3, 4]),
        level=1,
        gold=500,
    )
    await Lotto().enter(ctx)
    assert player.gold == 500 - 10 + prize(1, 4)
    assert "You matched 4 numbers!" in _screen(gctx)
    assert "You hit the jackpot!" in _screen(gctx)


async def test_lotto_refuses_a_player_who_cannot_afford_a_ticket():
    gctx, ctx, player, _db = await _visit(Lotto(), keys=["\r"], level=10, gold=99)
    await Lotto().enter(ctx)
    assert player.gold == 99
    assert "don't seem to have the kind of money" in _screen(gctx)


async def test_lotto_is_once_a_day_and_the_gate_clears_in_maintenance():
    _gctx, ctx, player, database = await _visit(
        Lotto(),
        keys=["Y", "1234", "\r"],
        rng=SeqRandom([9, 9, 9, 9]),
        level=1,
        gold=500,
    )
    igm = Lotto()
    await igm.enter(ctx)
    await ctx.store.flush(database)
    gold_after_first = player.gold

    # Same day, second visit: refused, and nothing is charged.
    gctx2 = make_ctx(database, database.players, player, keys=["\r"])
    ctx2 = await make_igm_ctx(gctx2, igm)
    await igm.enter(ctx2)
    assert player.gold == gold_after_first
    assert "already tried your luck today" in _screen(gctx2)

    # Daily maintenance clears the gate.
    maint = await make_maint_ctx(database, {}, igm.key)
    await igm.daily_maint(maint)
    await maint.store.flush(database)

    gctx3 = make_ctx(database, database.players, player, keys=["\r"])
    ctx3 = await make_igm_ctx(gctx3, igm)
    assert ctx3.store.get(f"day:{player.id}", False) is False


async def test_lotto_blank_code_charges_nothing():
    """Our one deliberate divergence: the source marks the day and takes the
    gold before prompting (lotto.ts:90-92), so its blank-entry escape bills
    for a ticket that was never played."""
    _gctx, ctx, player, _db = await _visit(Lotto(), keys=["Y", ""], level=5, gold=500)
    igm = Lotto()
    await igm.enter(ctx)
    assert player.gold == 500
    assert ctx.store.get(f"day:{player.id}", False) is False


async def test_lotto_rejects_bad_codes_then_accepts_a_good_one():
    gctx, ctx, _player, _db = await _visit(
        Lotto(),
        keys=["Y", "12", "ab12", "1234", "\r"],
        rng=SeqRandom([5, 5, 5, 5]),
        level=1,
        gold=500,
    )
    await Lotto().enter(ctx)
    screen = _screen(gctx)
    assert "Too short!" in screen
    assert "Not a number!" in screen
    assert "didn't match any numbers" in screen


# --- Pickle's -------------------------------------------------------------


@pytest.mark.parametrize(
    ("row", "expected"),
    [(1, 0.01), (2, 0.02), (5, 0.05), (9, 0.09), (10, 0.01)],
)
def test_row_pct_including_the_row_10_collision(row, expected):
    """pickle.js:33 builds the percentage by string concatenation, so
    '.0' + '10' is '.010' -- row 10 is row 1 wearing a bigger number."""
    assert row_pct(row) == pytest.approx(expected)


def test_row_10_is_accepted_even_though_the_prompt_says_1_to_9():
    """The message says 1-9 (pickle.js:19); the loop accepts 1-10 (:23)."""
    assert ROW_MAX == 10


async def test_pickle_good_roll_raises_the_chosen_attribute():
    # rng: good/bad roll (1..100, <49 is good), then the attribute (1..10).
    # SeqRandom returns randrange()'s raw value, so queue 0 for "1".
    gctx, ctx, player, _db = await _visit(
        Pickles(),
        keys=["\r", "9", "\r"],
        rng=SeqRandom([0, 6]),  # good; attribute 7 == strength
        strength=200,
    )
    await Pickles().enter(ctx)
    assert player.strength == 200 + int(200 * 0.09)
    assert "increased by 18" in _screen(gctx)


async def test_pickle_bad_roll_lowers_it():
    gctx, ctx, player, _db = await _visit(
        Pickles(),
        keys=["\r", "9", "\r"],
        rng=SeqRandom([BAD_FROM - 1, 6]),  # randrange+1 == BAD_FROM -> bad
        strength=200,
    )
    await Pickles().enter(ctx)
    assert player.strength == 200 - int(200 * 0.09)
    assert "taste like poo" in _screen(gctx)


async def test_pickle_zero_delta_takes_the_not_enough_branch():
    """int(stat * 0.01) is 0 for anything under 100, and the source has a
    dedicated message for it (pickle.js:130-139)."""
    gctx, ctx, player, _db = await _visit(
        Pickles(),
        keys=["\r", "1", "\r"],
        rng=SeqRandom([0, 8]),  # good; attribute 9 == gems
        gems=5,
    )
    await Pickles().enter(ctx)
    assert player.gems == 5
    assert "you do not have enough gems!" in _screen(gctx)


async def test_pickle_tattoo_overwrites_the_dark_cloak_description():
    """Faithful and destructive: outcome 10 replaces whatever the player
    wrote about themselves at the Dark Cloak Tavern (pickle.js:127)."""
    gctx, ctx, player, _db = await _visit(
        Pickles(),
        keys=["\r", "5", "\r"],
        rng=SeqRandom([0, 9]),  # attribute roll 10 == the tattoo
        description1="a quiet sort, mostly",
    )
    await Pickles().enter(ctx)
    assert player.description1 == TATTOO
    assert "marked by tattoo" in _screen(gctx)


async def test_pickle_reprompts_on_a_row_outside_the_range():
    gctx, ctx, player, _db = await _visit(
        Pickles(),
        keys=["\r", "77", "0", "9", "\r"],
        rng=SeqRandom([0, 6]),
        strength=200,
    )
    await Pickles().enter(ctx)
    assert _screen(gctx).count("Must be a choice from 1-9!") == 2
    assert player.strength == 200 + int(200 * 0.09)


async def test_pickle_blank_row_leaves_without_eating_anything():
    """The source loops forever on bad input with no escape; a blank line
    leaves here rather than trapping the player in the garden."""
    gctx, ctx, player, _db = await _visit(Pickles(), keys=["\r", ""], strength=200)
    await Pickles().enter(ctx)
    assert player.strength == 200
    assert "You leave the garden unpicked." in _screen(gctx)


# --- Olodrin's Orphanage --------------------------------------------------


def test_js_round_breaks_ties_upward_unlike_python():
    """Math.round(0.5) is 1; Python's round(0.5) is 0. Every loss in the
    catch mini-game is a rounded percentage, so the difference is money."""
    assert js_round(0.5) == 1
    assert js_round(1.5) == 2
    assert js_round(2.5) == 3
    assert round(0.5) == 0  # the trap this helper exists to avoid


@pytest.mark.parametrize(
    ("level", "kids", "expected"),
    [
        (1, 0, 1000),  # max(1000, 1*1*1000)
        (1, 1, 2000),  # doubled once per child already at home
        (1, 3, 8000),
        (5, 0, 25_000),
        (10, 2, 400_000),
    ],
)
def test_adoption_price(level, kids, expected):
    """oorphans.ts:115-124 -- level squared thousands, doubled per child."""
    assert adoption_price(level, kids) == expected


def test_adoption_price_jumps_straight_to_the_cap():
    """The ceiling check runs before each doubling and returns the cap
    outright, so there is no gradual approach to it."""
    assert adoption_price(50, 20) == MAX_PRICE


@pytest.mark.parametrize(
    ("level", "expected"), [(1, 1), (2, 4), (3, 9), (4, 12), (12, 12)]
)
def test_horse_trade_cost_caps_at_a_full_house(level, expected):
    """min(level^2, 12): from level 4 up, the horse costs every child you
    are allowed to have."""
    assert horse_trade_cost(level) == expected


async def test_orphanage_adopt_charges_and_adds_a_child():
    _gctx, ctx, player, _db = await _visit(
        Oorphans(),
        keys=["A", "Y", "\r", "Q", "\r"],
        rng=SeqRandom([1, 0, 0, 0]),  # male orphan, first guardian/death/name
        level=1,
        gold=5000,
        kids=0,
    )
    await Oorphans().enter(ctx)
    assert player.gold == 5000 - 1000
    assert player.kids == 1


async def test_orphanage_refuses_adoption_without_the_gold():
    gctx, ctx, player, _db = await _visit(
        Oorphans(),
        keys=["A", "Y", "\r", "Q", "\r"],
        rng=SeqRandom([1, 0, 0, 0]),
        level=5,
        gold=100,
        kids=0,
    )
    await Oorphans().enter(ctx)
    assert player.gold == 100
    assert player.kids == 0
    assert "don't have enough gold" in _screen(gctx)


async def test_orphanage_will_not_adopt_past_the_cap():
    gctx, ctx, player, _db = await _visit(
        Oorphans(), keys=["A", "\r", "Q", "\r"], gold=10**9, kids=MAX_KIDS
    )
    await Oorphans().enter(ctx)
    assert player.kids == MAX_KIDS
    assert "No more, nit!" in _screen(gctx)


async def test_orphanage_sells_a_child_for_the_flat_price():
    _gctx, ctx, player, _db = await _visit(
        Oorphans(),
        keys=["G", "Y", "\r", "Q", "\r"],
        rng=SeqRandom([0]),  # the farewell name
        gold=0,
        kids=2,
    )
    await Oorphans().enter(ctx)
    assert player.gold == SELL_PRICE
    assert player.kids == 1


async def test_orphanage_trades_children_for_a_horse():
    """The horse is live in this port -- daily.py grants a forest fight for
    it -- and lord.js's own horse trader is unported, so this is the only
    way to get one."""
    _gctx, ctx, player, _db = await _visit(
        Oorphans(), keys=["T", "Y", "\r", "Q", "\r"], level=2, kids=6, horse=0
    )
    await Oorphans().enter(ctx)
    assert player.horse == 1
    assert player.kids == 6 - horse_trade_cost(2)


async def test_orphanage_refuses_a_horse_without_enough_children():
    gctx, ctx, player, _db = await _visit(
        Oorphans(), keys=["T", "Y", "\r", "Q", "\r"], level=3, kids=2, horse=0
    )
    await Oorphans().enter(ctx)
    assert player.horse == 0
    assert player.kids == 2
    assert "You only have" in _screen(gctx)


async def test_orphanage_catch_only_ever_lands_your_first_child():
    """oorphans.ts:367-373 refuses a successful catch to anyone already
    holding a child, so the mini-game is a one-shot however lucky you get."""
    gctx, ctx, player, _db = await _visit(
        Oorphans(),
        keys=["C", "\r", "Q", "\r"],
        rng=SeqRandom([0, 0, 1]),  # flavour, flavour, then a winning roll
        kids=3,
    )
    await Oorphans().enter(ctx)
    assert player.kids == 3
    assert "One at a time, nit!" in _screen(gctx)


async def test_orphanage_catch_succeeds_from_zero():
    _gctx, ctx, player, _db = await _visit(
        Oorphans(),
        keys=["C", "\r", "Q", "\r"],
        rng=SeqRandom([0, 0, 1, 0]),
        kids=0,
    )
    await Oorphans().enter(ctx)
    assert player.kids == 1


async def test_orphanage_catch_can_take_most_of_your_gems():
    """Roll 5 costs 50-74% of the player's gems in one go (oorphans.ts:407-416)."""
    gctx, ctx, player, _db = await _visit(
        Oorphans(),
        keys=["C", "\r", "Q", "\r"],
        rng=SeqRandom([0, 0, 5, 0, 0]),  # flavour, flavour, roll 5, badcatch, +0%
        gems=100,
    )
    await Oorphans().enter(ctx)
    assert player.gems == 50  # 50% of 100
    assert "make off with" in _screen(gctx)


def test_orphanage_data_tables_load():
    """The three .dat tables ship beside the module and are read via IGM.dir."""
    from pathlib import Path

    igm = Oorphans()
    igm.dir = Path("igms/oorphans")
    assert len(igm.boy_names) == 1000
    assert len(igm.girl_names) == 1000
    assert len(igm.how_they_died) == 63
    assert "Liam" in igm.boy_names  # stripped of the file's trailing spaces


def test_orphanage_survives_missing_data_tables():
    """A hand-built instance has no dir; enter() must not explode."""
    igm = Oorphans()
    assert igm.dir is None
    assert igm.boy_names == []


# --- The FreeWorld II -----------------------------------------------------


@pytest.mark.parametrize(
    ("level", "expected"), [(1, 50_000), (5, 250_000), (14, 700_000), (99, 700_000)]
)
def test_fairy_gold_caps_below_felicitys_price(level, expected):
    """freeworld2.ts:528 caps at 700,000 so a fairy cannot be flipped
    against Felicity's Temple's 750,000 buy price."""
    assert fairy_gold(level) == expected


async def test_freeworld_is_once_a_day_and_the_gate_clears_in_maintenance():
    _gctx, ctx, player, database = await _visit(
        FreeWorld2(), keys=["\r", "Q"], gold=100
    )
    igm = FreeWorld2()
    await igm.enter(ctx)
    await ctx.store.flush(database)

    gctx2 = make_ctx(database, database.players, player, keys=["\r"])
    ctx2 = await make_igm_ctx(gctx2, igm)
    await igm.enter(ctx2)
    assert "Try Again Tomorrow" in _screen(gctx2)

    maint = await make_maint_ctx(database, {}, igm.key)
    await igm.daily_maint(maint)
    await maint.store.flush(database)
    gctx3 = make_ctx(database, database.players, player, keys=["\r"])
    ctx3 = await make_igm_ctx(gctx3, igm)
    assert ctx3.store.get(f"day:{player.id}", False) is False


async def test_freeworld_ends_the_visit_after_five_walks():
    # Six W presses; walks 1-5 all land on outcome 5 (a flavour no-op,
    # one pause key each), and the sixth ends the visit.
    keys = ["\r"] + ["W", "\r"] * MAX_WALKS + ["W"]
    gctx, ctx, _player, _db = await _visit(
        FreeWorld2(), keys=keys, rng=SeqRandom([4] * MAX_WALKS)
    )
    await FreeWorld2().enter(ctx)
    assert "You Used All Your Turns For Today" in _screen(gctx)


async def test_freeworld_wishing_well_grants_one_wish_in_three():
    gctx, ctx, player, _db = await _visit(
        FreeWorld2(),
        keys=["\r", "W", "A", "\r", "Q"],
        rng=SeqRandom([3, 2, 99]),  # walk 4 (well), granted, +100 strength
        strength=10,
    )
    await FreeWorld2().enter(ctx)
    assert player.strength == 110
    assert "Wish Granted" in _screen(gctx)


async def test_freeworld_wishing_well_usually_refuses():
    gctx, ctx, player, _db = await _visit(
        FreeWorld2(),
        keys=["\r", "W", "A", "\r", "Q"],
        rng=SeqRandom([3, 0]),  # walk 4 (well), not granted
        strength=10,
    )
    await FreeWorld2().enter(ctx)
    assert player.strength == 10
    assert "Not Your Lucky Day" in _screen(gctx)


async def test_freeworld_chancellor_pays_out_on_a_correct_guess():
    gctx, ctx, player, _db = await _visit(
        FreeWorld2(),
        keys=["\r", "H", "Y", "42", "\r", "Q"],
        rng=SeqRandom([41]),  # target = 41 + 1
        gold=0,
    )
    await FreeWorld2().enter(ctx)
    assert player.gold == CHANCELLOR_PRIZE
    assert "You Got It!" in _screen(gctx)


async def test_freeworld_chancellor_gives_five_tries_and_no_more():
    gctx, ctx, player, _db = await _visit(
        FreeWorld2(),
        keys=["\r", "H", "Y", "1", "2", "3", "4", "5", "\r", "Q"],
        rng=SeqRandom([98]),  # target = 99, never guessed
        gold=0,
    )
    await FreeWorld2().enter(ctx)
    assert player.gold == 0
    assert "You Didn't Get The Correct Number" in _screen(gctx)
    assert _screen(gctx).count("Too Low!") == CHANCELLOR_TRIES


async def test_freeworld_chancellor_is_once_per_visit():
    gctx, ctx, _player, _db = await _visit(
        FreeWorld2(),
        keys=["\r", "H", "N", "\r", "H", "\r", "Q"],
        gold=0,
    )
    await FreeWorld2().enter(ctx)
    assert "You Can Only See The Chancellor Once A Day" in _screen(gctx)


async def test_freeworld_fairy_wizard_buys_a_fairy():
    _gctx, ctx, player, _db = await _visit(
        FreeWorld2(),
        keys=["\r", "W", "Y", "\r", "Q"],
        rng=SeqRandom([5]),  # walk 6 == the fairy wizard
        level=3,
        gold=0,
        has_fairy=1,
    )
    await FreeWorld2().enter(ctx)
    assert player.has_fairy == 0
    assert player.gold == fairy_gold(3)


async def test_freeworld_fairy_wizard_refuses_a_player_without_one():
    gctx, ctx, player, _db = await _visit(
        FreeWorld2(),
        keys=["\r", "W", "Y", "\r", "Q"],
        rng=SeqRandom([5]),
        level=3,
        gold=0,
        has_fairy=0,
    )
    await FreeWorld2().enter(ctx)
    assert player.gold == 0
    assert "You Don't Have A Fairy" in _screen(gctx)


async def test_freeworld_pit_never_takes_the_last_hitpoint():
    _gctx, ctx, player, _db = await _visit(
        FreeWorld2(),
        keys=["\r", "W", "\r", "Q"],
        rng=SeqRandom([0, 19]),  # walk 1 (pit), then a 20-point hit
        hp=20,
        hp_max=20,
    )
    await FreeWorld2().enter(ctx)
    assert player.hp == 1
