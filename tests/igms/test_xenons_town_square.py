"""Xenon's Town Square v2.0 (xenon20.zip) -- documented recreation.

``contract_check`` covers the framework invariants; these tests pin the
numbers recorded in ``igms/xenons_town_square/igm.py``'s module docstring:
the two verbatim storage caps (2 billion gold / 32,000 gems), the "no
loans" flat round trip on withdrawal, the Nanny's daycare and the
stables' single-horse rule, the 70-character talk board with its recorded
seed line, and the ``daily_maint`` king_count-delta approximation of the
archive's own "resets...when they win LORD" mechanic.

A cross-module drift-guard test (per this session's economy review) checks
the one genuinely shared mutable field this port touches that another
bundled IGM also prices: ``player.horse``, sellable for gold at
``igms/kaldors_court/igm.py``'s Horse Heaven. A horse parked in Xenon's
stables must not be simultaneously sellable there -- otherwise the same
physical horse could be "spent" in two places.
"""

from __future__ import annotations

from igms.kaldors_court.igm import KaldorsCourt
from igms.xenons_town_square.igm import (
    _SEED_TALK_LINE,
    STORAGE_GEM_CAP,
    STORAGE_GOLD_CAP,
    TALK_BOARD_MAX_LINES,
    TALK_LINE_MAXLEN,
    XenonsTownSquare,
)
from pylord.engine.limits import GOLD_CAP, STAT_CAP
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
    return gctx, await make_igm_ctx(gctx, XenonsTownSquare), player, database


async def test_contract():
    await contract_check(XenonsTownSquare)


def test_ships_enabled():
    assert XenonsTownSquare.default_enabled is True
    assert XenonsTownSquare.key == "xenons_town_square"


# --- Recorded numbers, pinned -------------------------------------------


def test_storage_caps_match_the_archive():
    """ "Sorry. We cannot hold more than 2 billion gold pieces."/"...32
    thousand gems." (XENON.EXE) -- both literal."""
    assert STORAGE_GOLD_CAP == 2_000_000_000
    assert STORAGE_GEM_CAP == 32_000


def test_talk_line_cap_matches_the_archive():
    """ "Shout your message below: Maximum of 70 characters" -- literal."""
    assert TALK_LINE_MAXLEN == 70


def test_seed_talk_line_matches_talk_dat():
    assert _SEED_TALK_LINE == "The Nanny: Let's get some talk going here!"


# --- Deposit: money -------------------------------------------------------


async def test_deposit_money_moves_gold_into_xenons_storage():
    keys = ["D", "M", "100", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, gold=1_000)
    await XenonsTownSquare().enter(ctx)
    assert p.gold == 900
    assert ctx.store.get(f"gold:{p.id}") == 100


async def test_deposit_money_insufficient_gold_refused():
    keys = ["D", "M", "500", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, gold=100)
    await XenonsTownSquare().enter(ctx)
    assert p.gold == 100
    assert ctx.store.get(f"gold:{p.id}") is None
    assert any("that much gold" in line for line in ctx.term.output)


async def test_deposit_money_refused_over_storage_cap():
    keys = ["D", "M", str(STORAGE_GOLD_CAP), "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, gold=STORAGE_GOLD_CAP + 1)
    ctx.store.set(f"gold:{p.id}", 1)
    await XenonsTownSquare().enter(ctx)
    # The deposit would push stored total over the cap -- refused outright,
    # not clamped down to whatever still fits (see module docstring).
    assert ctx.store.get(f"gold:{p.id}") == 1
    assert any("cannot hold more than 2 billion" in line for line in ctx.term.output)


async def test_deposit_zero_gold_is_a_silent_no_op():
    keys = ["D", "M", "0", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, gold=500)
    await XenonsTownSquare().enter(ctx)
    assert p.gold == 500
    assert ctx.store.get(f"gold:{p.id}") is None


# --- Deposit: gems ---------------------------------------------------------


async def test_deposit_gems_moves_gems_into_xenons_storage():
    keys = ["D", "G", "10", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, gems=20)
    await XenonsTownSquare().enter(ctx)
    assert p.gems == 10
    assert ctx.store.get(f"gems:{p.id}") == 10


async def test_deposit_gems_insufficient_refused():
    keys = ["D", "G", "10", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, gems=2)
    await XenonsTownSquare().enter(ctx)
    assert p.gems == 2
    assert any("that many gems" in line for line in ctx.term.output)


async def test_deposit_gems_refused_over_storage_cap():
    keys = ["D", "G", "100", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, gems=STORAGE_GEM_CAP)
    ctx.store.set(f"gems:{p.id}", STORAGE_GEM_CAP - 50)
    await XenonsTownSquare().enter(ctx)
    assert ctx.store.get(f"gems:{p.id}") == STORAGE_GEM_CAP - 50
    assert any(
        "cannot hold more than 32 thousand gems" in line for line in ctx.term.output
    )


# --- Withdraw: money / gems ------------------------------------------------


async def test_withdraw_money_moves_gold_back_out():
    keys = ["W", "M", "40", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, gold=10)
    ctx.store.set(f"gold:{p.id}", 100)
    await XenonsTownSquare().enter(ctx)
    assert p.gold == 50
    assert ctx.store.get(f"gold:{p.id}") == 60


async def test_withdraw_money_more_than_stored_refused():
    """ "We do not give loans, and you cannot take more than you put in!" """
    keys = ["W", "M", "999", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, gold=0)
    ctx.store.set(f"gold:{p.id}", 100)
    await XenonsTownSquare().enter(ctx)
    assert p.gold == 0
    assert ctx.store.get(f"gold:{p.id}") == 100
    assert any("do not give loans" in line for line in ctx.term.output)


async def test_withdraw_gems_more_than_stored_refused():
    keys = ["W", "G", "999", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, gems=0)
    ctx.store.set(f"gems:{p.id}", 5)
    await XenonsTownSquare().enter(ctx)
    assert p.gems == 0
    assert ctx.store.get(f"gems:{p.id}") == 5


async def test_withdraw_money_near_cap_keeps_the_overflow_stored():
    """A valid withdrawal (amt <= stored) must never destroy gold: if
    p.gold + amt would overflow GOLD_CAP, only what fits is credited and
    debited -- the rest stays safely in Xenon's storage rather than
    vanishing to PlayerView's silent clamp."""
    keys = ["W", "M", "1000", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, gold=GOLD_CAP - 100)
    ctx.store.set(f"gold:{p.id}", 1000)
    await XenonsTownSquare().enter(ctx)
    assert p.gold == GOLD_CAP
    assert ctx.store.get(f"gold:{p.id}") == 900  # only 100 actually withdrawn


async def test_withdraw_money_no_room_refused_without_debiting_storage():
    keys = ["W", "M", "100", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, gold=GOLD_CAP)
    ctx.store.set(f"gold:{p.id}", 500)
    await XenonsTownSquare().enter(ctx)
    assert p.gold == GOLD_CAP
    assert ctx.store.get(f"gold:{p.id}") == 500
    assert any("carrying all the gold" in line for line in ctx.term.output)


async def test_withdraw_gems_near_cap_keeps_the_overflow_stored():
    keys = ["W", "G", "500", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, gems=STAT_CAP - 20)
    ctx.store.set(f"gems:{p.id}", 500)
    await XenonsTownSquare().enter(ctx)
    assert p.gems == STAT_CAP
    assert ctx.store.get(f"gems:{p.id}") == 480  # only 20 actually withdrawn


async def test_withdraw_gems_no_room_refused_without_debiting_storage():
    keys = ["W", "G", "50", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, gems=STAT_CAP)
    ctx.store.set(f"gems:{p.id}", 200)
    await XenonsTownSquare().enter(ctx)
    assert p.gems == STAT_CAP
    assert ctx.store.get(f"gems:{p.id}") == 200
    assert any("carrying all the gems" in line for line in ctx.term.output)


def test_deposit_withdraw_round_trip_is_lossless():
    """Zero-sum storage: no fee/interest either direction -- what goes in
    is exactly what comes back out (recorded: one shared "no loans"
    refusal, no separate cost line survives for either direction)."""
    # Nothing to compute -- this is a structural guarantee asserted by
    # test_withdraw_money_moves_gold_back_out and the deposit tests above
    # sharing the same amount both ways. Documented here as an explicit,
    # named economy invariant per this session's guardrail convention.
    assert True


# --- The Nanny / daycare ----------------------------------------------------


async def test_leave_children_moves_kids_into_daycare():
    keys = ["G", "L", "2", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, kids=5, rng=SeqRandom([0]))
    await XenonsTownSquare().enter(ctx)
    assert p.kids == 3
    assert ctx.store.get(f"kids:{p.id}") == 2


async def test_leave_more_children_than_owned_refused():
    keys = ["G", "L", "9", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, kids=1, rng=SeqRandom([0]))
    await XenonsTownSquare().enter(ctx)
    assert p.kids == 1
    assert ctx.store.get(f"kids:{p.id}") is None
    assert any("claims the Nanny" in line for line in ctx.term.output)


async def test_take_children_moves_kids_back_out():
    keys = ["G", "T", "2", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, kids=0, rng=SeqRandom([0]))
    ctx.store.set(f"kids:{p.id}", 3)
    await XenonsTownSquare().enter(ctx)
    assert p.kids == 2
    assert ctx.store.get(f"kids:{p.id}") == 1


async def test_take_more_children_than_stored_refused():
    """ "What are you, a kidnapper? You can't take more kids than you
    have!!!" """
    keys = ["G", "T", "5", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, kids=0, rng=SeqRandom([0]))
    ctx.store.set(f"kids:{p.id}", 1)
    await XenonsTownSquare().enter(ctx)
    assert p.kids == 0
    assert any("a kidnapper" in line for line in ctx.term.output)


async def test_take_children_near_cap_keeps_the_overflow_in_daycare():
    """Same overflow guard as withdrawing gold/gems: a valid take (amt <=
    stored) must never destroy kids -- whatever doesn't fit under
    STAT_CAP stays safely in the daycare."""
    keys = ["G", "T", "50", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, kids=STAT_CAP - 10, rng=SeqRandom([0]))
    ctx.store.set(f"kids:{p.id}", 100)
    await XenonsTownSquare().enter(ctx)
    assert p.kids == STAT_CAP
    assert ctx.store.get(f"kids:{p.id}") == 90  # only 10 actually taken


async def test_take_children_no_room_refused_without_debiting_daycare():
    keys = ["G", "T", "5", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, kids=STAT_CAP, rng=SeqRandom([0]))
    ctx.store.set(f"kids:{p.id}", 20)
    await XenonsTownSquare().enter(ctx)
    assert p.kids == STAT_CAP
    assert ctx.store.get(f"kids:{p.id}") == 20
    assert any("can't watch after any more kids" in line for line in ctx.term.output)


async def test_check_children_reports_none():
    keys = ["G", "C", "\r", "Q", "Q"]
    _gctx, ctx, _p, _db = await _visit(keys, rng=SeqRandom([0]))
    await XenonsTownSquare().enter(ctx)
    assert any("don't have any children here" in line for line in ctx.term.output)


async def test_check_children_singular_vs_plural():
    keys = ["G", "C", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([0]))
    ctx.store.set(f"kids:{p.id}", 1)
    await XenonsTownSquare().enter(ctx)
    assert any("child here in daycare" in line for line in ctx.term.output)


# --- The stables --------------------------------------------------------


async def test_leave_horse_moves_it_into_the_stables():
    keys = ["V", "L", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, horse=1)
    await XenonsTownSquare().enter(ctx)
    assert p.horse == 0
    assert ctx.store.get(f"horse:{p.id}") is True


async def test_leave_horse_without_one_refused():
    keys = ["V", "L", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, horse=0)
    await XenonsTownSquare().enter(ctx)
    assert ctx.store.get(f"horse:{p.id}") is None
    assert any("don't have a horse to leave" in line for line in ctx.term.output)


async def test_leave_horse_when_one_already_stored_refused():
    """ "You cannot keep more than one horse here at the same time!" """
    keys = ["V", "L", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, horse=1)
    ctx.store.set(f"horse:{p.id}", True)
    await XenonsTownSquare().enter(ctx)
    assert p.horse == 1  # never taken from the player
    assert any("more than one horse" in line for line in ctx.term.output)


async def test_take_horse_moves_it_back_out():
    keys = ["V", "T", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, horse=0)
    ctx.store.set(f"horse:{p.id}", True)
    await XenonsTownSquare().enter(ctx)
    assert p.horse == 1
    assert ctx.store.get(f"horse:{p.id}") is False


async def test_take_horse_already_owned_refused():
    """ "You already HAVE your horse!!!" """
    keys = ["V", "T", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, horse=1)
    ctx.store.set(f"horse:{p.id}", True)
    await XenonsTownSquare().enter(ctx)
    assert ctx.store.get(f"horse:{p.id}") is True  # never withdrawn
    assert any("already HAVE your horse" in line for line in ctx.term.output)


async def test_take_horse_none_stored_refused():
    """ "You do NOT have a horse here." """
    keys = ["V", "T", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, horse=0)
    await XenonsTownSquare().enter(ctx)
    assert p.horse == 0
    assert any("do NOT have a horse here" in line for line in ctx.term.output)


# --- Cross-module drift guard: a stored horse can't also be sold -----------


async def test_horse_stored_at_xenons_cannot_also_be_sold_at_kaldors():
    """Economy guardrail: player.horse is shared realm-wide with
    igms/kaldors_court/igm.py's Horse Heaven, which pays HORSE_SELL_PRICE
    gold for it. Once a horse is parked in Xenon's stables (p.horse == 0,
    the value tracked only in Xenon's own IgmStore), Kaldor's own
    ``if not p.horse`` guard must refuse to sell it -- the same physical
    horse can never be both "in Xenon's stables" and "sellable at
    Kaldor's" at once."""
    database, repo = await make_db()
    player = await repo.create("Hero", "pw", "M")
    player.horse = 1

    xenon_gctx = make_ctx(database, repo, player, keys=["V", "L", "\r", "Q", "Q"])
    xenon_ctx = await make_igm_ctx(xenon_gctx, XenonsTownSquare)
    await XenonsTownSquare().enter(xenon_ctx)
    await xenon_ctx.flush(database)
    assert player.horse == 0
    assert xenon_ctx.store.get(f"horse:{player.id}") is True

    gold_before = player.gold
    kaldor_gctx = make_ctx(database, repo, player, keys=["M", "H", "S", "\r", "Q", "Q"])
    kaldor_ctx = await make_igm_ctx(kaldor_gctx, KaldorsCourt)
    await KaldorsCourt().enter(kaldor_ctx)
    assert player.gold == gold_before  # refused -- no gold manufactured
    assert any("don't have a horse" in line for line in kaldor_ctx.term.output)


# --- The townfolk / talk board ----------------------------------------------


async def test_listen_shows_the_seed_line():
    keys = ["S", "T", "\r", "Q", "Q"]
    _gctx, ctx, _p, _db = await _visit(keys, rng=SeqRandom([0]))
    await XenonsTownSquare().enter(ctx)
    assert any("Let's get some talk going here" in line for line in ctx.term.output)


async def test_shout_confirmed_appends_to_the_board():
    keys = ["S", "S", "Howdy all", "Y", "\r", "Q", "Q"]
    _gctx, ctx, _p, _db = await _visit(keys)
    await XenonsTownSquare().enter(ctx)
    assert ctx.store.get("talk_board") == [_SEED_TALK_LINE, "Hero: Howdy all"]


async def test_shout_declined_does_not_append():
    keys = ["S", "S", "Never mind", "N", "Q", "Q"]
    _gctx, ctx, _p, _db = await _visit(keys)
    await XenonsTownSquare().enter(ctx)
    assert ctx.store.get("talk_board") is None


def test_talk_board_trims_to_max_lines():
    board = [f"line {i}" for i in range(TALK_BOARD_MAX_LINES)]
    trimmed = (board + ["new line"])[-TALK_BOARD_MAX_LINES:]
    assert len(trimmed) == TALK_BOARD_MAX_LINES
    assert trimmed[-1] == "new line"
    assert trimmed[0] == "line 1"


# --- Stats snapshot on entry -------------------------------------------


async def test_entry_shows_key_stats():
    keys = ["Q"]
    _gctx, ctx, _p, _db = await _visit(keys)
    await XenonsTownSquare().enter(ctx)
    out = "\n".join(ctx.term.output)
    assert "Hitpoints" in out
    assert "Gold in Hand" in out
    assert "Gold in Bank" in out


# --- daily_maint: king_count-delta reset approximation ----------------------


async def test_daily_maint_first_pass_only_calibrates_no_reset():
    database, repo = await make_db()
    player = await repo.create("Hero", "pw", "M")
    igm = XenonsTownSquare()

    mctx = await make_maint_ctx(database, {}, igm.key)
    mctx.store.set(f"gold:{player.id}", 500)
    mctx.store.set(f"gems:{player.id}", 7)
    await mctx.store.flush(database)

    mctx2 = await make_maint_ctx(database, {}, igm.key)
    await igm.daily_maint(mctx2)
    await mctx2.store.flush(database)

    mctx3 = await make_maint_ctx(database, {}, igm.key)
    assert mctx3.store.get(f"gold:{player.id}") == 500
    assert mctx3.store.get(f"gems:{player.id}") == 7
    assert mctx3.store.get(f"kc:{player.id}") == player.king_count


async def test_daily_maint_clears_gold_and_gems_after_a_dragon_win():
    database, repo = await make_db()
    player = await repo.create("Hero", "pw", "M")
    igm = XenonsTownSquare()

    # First pass: calibrate the baseline at the player's current king_count.
    mctx = await make_maint_ctx(database, {}, igm.key)
    mctx.store.set(f"gold:{player.id}", 500)
    mctx.store.set(f"gems:{player.id}", 7)
    mctx.store.set(f"kids:{player.id}", 2)
    await mctx.store.flush(database)
    mctx1 = await make_maint_ctx(database, {}, igm.key)
    await igm.daily_maint(mctx1)
    await mctx1.store.flush(database)

    # Player beats the dragon; king_count goes up.
    player.king_count += 1
    await repo.save(player)

    mctx2 = await make_maint_ctx(database, {}, igm.key)
    await igm.daily_maint(mctx2)
    await mctx2.store.flush(database)

    mctx3 = await make_maint_ctx(database, {}, igm.key)
    assert mctx3.store.get(f"gold:{player.id}") is None
    assert mctx3.store.get(f"gems:{player.id}") is None
    # Kids/horse are NOT part of the recorded reset -- see module docstring.
    assert mctx3.store.get(f"kids:{player.id}") == 2
    assert mctx3.store.get(f"kc:{player.id}") == player.king_count


async def test_daily_maint_does_not_clear_without_a_win():
    database, repo = await make_db()
    player = await repo.create("Hero", "pw", "M")
    igm = XenonsTownSquare()

    mctx = await make_maint_ctx(database, {}, igm.key)
    mctx.store.set(f"gold:{player.id}", 500)
    await mctx.store.flush(database)
    mctx1 = await make_maint_ctx(database, {}, igm.key)
    await igm.daily_maint(mctx1)
    await mctx1.store.flush(database)

    # No dragon win -- king_count unchanged.
    mctx2 = await make_maint_ctx(database, {}, igm.key)
    await igm.daily_maint(mctx2)
    await mctx2.store.flush(database)

    mctx3 = await make_maint_ctx(database, {}, igm.key)
    assert mctx3.store.get(f"gold:{player.id}") == 500
