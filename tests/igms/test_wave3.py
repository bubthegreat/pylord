"""Wave-3 IGMs: Seth's Tribute Lotto and Pickle's.

Unlike waves 1 and 2, these are **ports** of the real sources vendored in
``reference/igm-sources/`` -- so these tests pin the ported formulas against
the source's own numbers, not against invented balance. Where a test asserts
something that looks wrong (row 10 paying the same as row 1; a level-12
jackpot hitting the gold ceiling), it is pinning a faithfully-reproduced
flaw of the original. See each IGM's module docstring.
"""

from __future__ import annotations

import pytest

from igms.lotto.igm import Lotto, count_matches, prize
from igms.pickle.igm import BAD_FROM, ROW_MAX, TATTOO, Pickles, row_pct
from tests.igm_contract import contract_check
from tests.igms._harness import (
    SeqRandom,
    make_ctx,
    make_db,
    make_igm_ctx,
    make_maint_ctx,
)

_WAVE3 = [Lotto, Pickles]


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


@pytest.mark.parametrize("igm_cls", _WAVE3)
async def test_contract(igm_cls):
    await contract_check(igm_cls)


@pytest.mark.parametrize("igm_cls", _WAVE3)
def test_ships_disabled(igm_cls):
    """Both carry original behaviour a live realm should opt into knowingly
    -- the lotto's payout curve, Pickle's missing daily limit."""
    assert igm_cls.default_enabled is False
    assert igm_cls.key and igm_cls.name


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
