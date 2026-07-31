"""Behavior tests for the LORD Gambling Casino (Task 20).

The shared IGM contract is checked once, for every bundled IGM, in
``tests/igms/test_conformance.py``; these tests pin the
IGM's own seeded gameplay. Blackjack's card math is unit-tested directly
via its pure helpers (``_hand_value``/``_is_natural``) for exact soft-ace
handling, then exercised end-to-end through ``enter()`` for natural/push/
normal-win/bust outcomes using a scripted deck shuffle (see
``tests.igms._harness.SeqRandom.shuffle``'s docstring for how the deck
order is pinned). Slots and Roulette are driven end-to-end for their exact
payouts (triple Seven, a matching-pair push, a number-bet hit) plus bet
validation (insufficient gold, over the level-scaled max bet).
"""

from __future__ import annotations

from igms.lord_casino.igm import (
    _RANKS,
    _SUITS,
    LordCasino,
    _hand_value,
    _is_natural,
)
from tests.igms._harness import SeqRandom, make_ctx, make_db, make_igm_ctx


def _card_index(rank: str, suit: str) -> int:
    return _RANKS.index(rank) * 4 + _SUITS.index(suit)


def _shuffle_offsets(deck_len: int, placements: dict[int, tuple[str, str]]) -> list[int]:
    """A scripted-shuffle offset list (see ``SeqRandom.shuffle``'s
    docstring) that pins only the given ``{deal_position: (rank, suit)}``
    cards, leaving every other position an identity no-op."""
    offsets = [0] * deck_len
    for pos, (rank, suit) in placements.items():
        offsets[pos] = _card_index(rank, suit) - pos
    return offsets


# -- pure card-math helpers ---------------------------------------------


def test_hand_value_soft_ace_counts_as_eleven():
    assert _hand_value([("A", "S"), ("6", "H")]) == 17


def test_hand_value_soft_ace_downgrades_to_avoid_bust():
    assert _hand_value([("A", "S"), ("6", "H"), ("10", "D")]) == 17


def test_hand_value_two_aces():
    assert _hand_value([("A", "S"), ("A", "H")]) == 12


def test_is_natural_ace_and_ten_value():
    assert _is_natural([("A", "S"), ("K", "H")]) is True
    assert _is_natural([("9", "S"), ("9", "H")]) is False
    assert _is_natural([("A", "S"), ("6", "H"), ("4", "D")]) is False  # 3 cards


# -- blackjack --------------------------------------------------------------


async def test_blackjack_player_natural_pays_three_to_two():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 1000
    offsets = _shuffle_offsets(52, {0: ("A", "S"), 2: ("K", "H")})
    igm = LordCasino()
    gctx = make_ctx(
        database, repo, p, keys=["B", "100", "\r", "L"], rng=SeqRandom(offsets)
    )
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    # bet 100 -> deducted, then 100 + 100*3//2 = 250 returned: net +150.
    assert p.gold == 1150


async def test_blackjack_dealer_natural_only_player_loses():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 1000
    offsets = _shuffle_offsets(52, {1: ("A", "S"), 3: ("K", "H")})
    igm = LordCasino()
    gctx = make_ctx(
        database, repo, p, keys=["B", "100", "\r", "L"], rng=SeqRandom(offsets)
    )
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 900


async def test_blackjack_both_natural_is_push():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 1000
    offsets = _shuffle_offsets(
        52,
        {
            0: ("A", "S"),
            2: ("K", "H"),
            1: ("A", "D"),
            3: ("K", "C"),
        },
    )
    igm = LordCasino()
    gctx = make_ctx(
        database, repo, p, keys=["B", "100", "\r", "L"], rng=SeqRandom(offsets)
    )
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 1000  # push -- unchanged


async def test_blackjack_normal_win_after_standing():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 1000
    # Player: 10S + 9H = 19, stands. Dealer: 2H + 2C = 4 (default identity),
    # then hits 9D (13) then 5D (18) and stops (>= 17). Player 19 beats 18.
    offsets = _shuffle_offsets(
        52,
        {
            0: ("10", "S"),
            2: ("9", "H"),
            4: ("9", "D"),
            5: ("5", "D"),
        },
    )
    igm = LordCasino()
    gctx = make_ctx(
        database, repo, p, keys=["B", "100", "S", "\r", "L"], rng=SeqRandom(offsets)
    )
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 1100  # bet returned doubled: net +100


async def test_blackjack_bust_on_hit_loses_bet():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 1000
    # Player: 10S + 9H = 19, hits 5D -> 24, busts.
    offsets = _shuffle_offsets(
        52,
        {
            0: ("10", "S"),
            2: ("9", "H"),
            4: ("5", "D"),
        },
    )
    igm = LordCasino()
    gctx = make_ctx(
        database, repo, p, keys=["B", "100", "H", "\r", "L"], rng=SeqRandom(offsets)
    )
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 900


async def test_blackjack_dealer_stands_on_soft_seventeen():
    """Dealer's hit condition is a bare ``< 17`` (see igm.py's module
    docstring), so an Ace+6 (soft 17) must stop drawing without a special
    case. Pin it by asserting the dealer's *final* displayed hand is
    exactly the two dealt cards at value 17 -- if the dealer wrongly hit
    on soft 17 it would draw a third card and the value/hand text would
    no longer read "AD 6C ... (17)"."""
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 1000
    # Player: KS + QH = 20, stands. Dealer: AD + 6C = soft 17, must stand.
    offsets = _shuffle_offsets(
        52,
        {
            0: ("K", "S"),
            2: ("Q", "H"),
            1: ("A", "D"),
            3: ("6", "C"),
        },
    )
    igm = LordCasino()
    gctx = make_ctx(
        database, repo, p, keys=["B", "100", "S", "\r", "L"], rng=SeqRandom(offsets)
    )
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    out = "".join(ctx.term.output)
    # The dealer-hand line's card list must read exactly "AD 6C" right up
    # to the opening paren of its value -- a third card (a wrongly-hit
    # "3S", the next card in this scripted deck) would insert itself
    # between "6C" and " (", breaking this literal match.
    assert "AD 6C (" in out
    assert "3S" not in out
    # Strongest signal: if the dealer wrongly hit to 20, a 20-vs-20 finish
    # is a push (gold unchanged at 1000), not the win a stood-at-17 dealer
    # gives the player's 20.
    assert p.gold == 1100


# -- bet validation (shared _prompt_bet, exercised via Slots) --------------


async def test_bet_over_gold_on_hand_refused():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 50
    igm = LordCasino()
    gctx = make_ctx(database, repo, p, keys=["S", "500", "\r", "L"], rng=SeqRandom([]))
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 50
    assert "don't have that much" in "".join(ctx.term.output)


async def test_bet_over_level_scaled_max_refused():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.level = 1
    p.gold = 100_000
    igm = LordCasino()
    gctx = make_ctx(database, repo, p, keys=["S", "5000", "\r", "L"], rng=SeqRandom([]))
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 100_000
    assert "refuses a bet over" in "".join(ctx.term.output)


# -- slots ------------------------------------------------------------------


async def test_slots_triple_seven_pays_ten_x():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 1000
    igm = LordCasino()
    # _SLOT_SYMBOLS = (Cherry, Lemon, Bell, Bar, Seven); index 4 = Seven.
    gctx = make_ctx(
        database, repo, p, keys=["S", "100", "\r", "L"], rng=SeqRandom([4, 4, 4])
    )
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    # bet 100 -> deducted, 100*10 = 1000 returned: net +900.
    assert p.gold == 1900


async def test_slots_two_matching_is_a_push():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 1000
    igm = LordCasino()
    # Cherry, Cherry, Lemon -- two match, not three.
    gctx = make_ctx(
        database, repo, p, keys=["S", "100", "\r", "L"], rng=SeqRandom([0, 0, 1])
    )
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 1000


async def test_slots_no_match_loses_bet():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 1000
    igm = LordCasino()
    # Cherry, Lemon, Bell -- no match at all.
    gctx = make_ctx(
        database, repo, p, keys=["S", "100", "\r", "L"], rng=SeqRandom([0, 1, 2])
    )
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 900


async def test_slots_triple_lemon_has_no_jackpot_tier_pushes_instead():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 1000
    igm = LordCasino()
    gctx = make_ctx(
        database, repo, p, keys=["S", "100", "\r", "L"], rng=SeqRandom([1, 1, 1])
    )
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 1000  # push, not a jackpot and not a loss


# -- roulette -----------------------------------------------------------


async def test_roulette_number_bet_hit_pays_35x():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 1000
    igm = LordCasino()
    gctx = make_ctx(
        database,
        repo,
        p,
        keys=["R", "100", "N", "17", "\r", "L"],
        rng=SeqRandom([17]),
    )
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    # bet 100 -> deducted, 100*35 = 3500 returned: net +3400.
    assert p.gold == 4400


async def test_roulette_number_bet_miss_loses_bet():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 1000
    igm = LordCasino()
    gctx = make_ctx(
        database,
        repo,
        p,
        keys=["R", "100", "N", "17", "\r", "L"],
        rng=SeqRandom([18]),
    )
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 900


async def test_roulette_color_bet_hit_pays_2x():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 1000
    igm = LordCasino()
    # 1 is a red number.
    gctx = make_ctx(
        database,
        repo,
        p,
        keys=["R", "100", "C", "R", "\r", "L"],
        rng=SeqRandom([1]),
    )
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 1100


async def test_roulette_color_bet_miss_on_green_zero():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 1000
    igm = LordCasino()
    gctx = make_ctx(
        database,
        repo,
        p,
        keys=["R", "100", "C", "R", "\r", "L"],
        rng=SeqRandom([0]),
    )
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 900
