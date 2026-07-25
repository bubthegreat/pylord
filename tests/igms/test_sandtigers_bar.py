"""Behavior tests for Sandtiger's Bar (Task 16; audited against
SANDBAR.PAS/SBARADD.PAS in Task 2 -- see ``igms/sandtigers_bar/igm.py``'s
module docstring).

``contract_check`` covers the framework invariants; these tests pin the
gambling math (dice win/loss/push, coin-flip double-or-nothing chain,
guess-the-cup 3x payout), the economy guard (bet validation refuses a
bet over gold-on-hand or over ``level * 1000``), and the Task 2 audit's
adoption of the four real Sandtiger tales (verbatim SANDBAR.PAS/SBARADD.PAS
text) into (S)tories. The gambling math itself stays invented -- the real
source's only games are three card games against fixed NPC casts
(Blackjack/Five Card Draw/Elimination), with no dice/coin/cup equivalent to
adopt; see the module docstring and ``docs/deviations.md``.
"""

from __future__ import annotations

from igms.sandtigers_bar.igm import SandtigersBar
from tests.igm_contract import contract_check
from tests.igms._harness import SeqRandom, make_ctx, make_db, make_igm_ctx


async def test_contract():
    await contract_check(SandtigersBar)


# --- dice high/low -----------------------------------------------------


async def test_dice_win_doubles_bet():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 100
    gctx = make_ctx(
        database, repo, p,
        keys=["D", "50", "\r", "L"],
        rng=SeqRandom([6, 1]),  # player rolls 6, house rolls 1
    )
    igm = SandtigersBar()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 150  # +bet


async def test_dice_loss_takes_bet():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 100
    gctx = make_ctx(
        database, repo, p,
        keys=["D", "50", "\r", "L"],
        rng=SeqRandom([1, 6]),  # player rolls 1, house rolls 6
    )
    igm = SandtigersBar()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 50  # -bet


async def test_dice_tie_pushes():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 100
    gctx = make_ctx(
        database, repo, p,
        keys=["D", "50", "\r", "L"],
        rng=SeqRandom([3, 3]),
    )
    igm = SandtigersBar()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 100  # unchanged


# --- bet validation ------------------------------------------------------


async def test_bet_over_gold_refused():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 20
    gctx = make_ctx(
        database, repo, p, keys=["D", "50", "\r", "L"], rng=SeqRandom([])
    )
    igm = SandtigersBar()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 20  # refused before any roll happened
    assert "don't have that much" in "".join(ctx.term.output)


async def test_bet_over_max_bet_refused():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.level = 1
    p.gold = 5000
    gctx = make_ctx(
        database, repo, p, keys=["D", "1500", "\r", "L"], rng=SeqRandom([])
    )
    igm = SandtigersBar()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 5000
    assert "refuses a bet over" in "".join(ctx.term.output)


async def test_bet_zero_declines_quietly():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 100
    gctx = make_ctx(
        database, repo, p, keys=["D", "0", "\r", "L"], rng=SeqRandom([])
    )
    igm = SandtigersBar()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 100


# --- coin flip double-or-nothing -----------------------------------------


async def test_coin_flip_win_then_cash_out():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 100
    gctx = make_ctx(
        database, repo, p,
        keys=["C", "20", "K", "\r", "L"],
        rng=SeqRandom([0]),  # one winning flip, then cash out
    )
    igm = SandtigersBar()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    # 100 - 20 (staked) + 40 (doubled pot cashed out) == 120
    assert p.gold == 120


async def test_coin_flip_chain_continues_then_loses_pot():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 100
    gctx = make_ctx(
        database, repo, p,
        keys=["C", "20", "C", "\r", "L"],
        rng=SeqRandom([0, 1]),  # win once (pot=40), continue, then lose
    )
    igm = SandtigersBar()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 80  # lost the original 20 stake, nothing recovered


async def test_coin_flip_immediate_loss():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 100
    gctx = make_ctx(
        database, repo, p,
        keys=["C", "20", "\r", "L"],
        rng=SeqRandom([1]),
    )
    igm = SandtigersBar()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 80


# --- guess the cup ---------------------------------------------------


async def test_guess_cup_correct_pays_3x():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 100
    gctx = make_ctx(
        database, repo, p,
        keys=["G", "30", "2", "\r", "L"],
        rng=SeqRandom([2]),  # correct cup is 2
    )
    igm = SandtigersBar()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 160  # 100 - 30 + 90 (3x payout)


async def test_guess_cup_wrong_loses_bet():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 100
    gctx = make_ctx(
        database, repo, p,
        keys=["G", "30", "1", "\r", "L"],
        rng=SeqRandom([2]),  # correct cup is 2, player guessed 1
    )
    igm = SandtigersBar()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    assert p.gold == 70


# --- stories -------------------------------------------------------------


async def test_stories_rotate_via_rng():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    gctx = make_ctx(database, repo, p, keys=["S", "\r", "L"], rng=SeqRandom([1]))
    igm = SandtigersBar()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    from pylord.terminal import strip

    from igms.sandtigers_bar.igm import _STORIES

    out = "".join(ctx.term.output)
    assert strip(_STORIES[1]) in strip(out)


async def test_stories_uses_verbatim_sandbar_tale():
    """(S)tories now tells one of four tales lifted verbatim from
    SBARADD.PAS's ``talksandtiger()`` ``HIST``/``STOR`` branch (Task 2
    audit) -- pin one exactly by literal text, not by re-importing
    ``_STORIES``, so a future edit can't silently drift back to invented
    flavor text without the test noticing.
    """
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    gctx = make_ctx(database, repo, p, keys=["S", "\r", "L"], rng=SeqRandom([0]))
    igm = SandtigersBar()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    out = "".join(ctx.term.output)
    # SBARADD.PAS's Halder's Story (ch = 'H').
    assert "Halder was born in Devonshire" in out
    assert "cannot kill or" in out


async def test_stories_second_tale_is_barak_life():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    gctx = make_ctx(database, repo, p, keys=["S", "\r", "L"], rng=SeqRandom([1]))
    igm = SandtigersBar()
    ctx = await make_igm_ctx(gctx, igm)

    await igm.enter(ctx)

    out = "".join(ctx.term.output)
    # SBARADD.PAS's "The Barak Life" (ch = 'T') -- the short one.
    assert "we really know little about him" in out
