"""Kaldor's Court (kaldor20.zip) -- documented recreation.

``contract_check`` covers the framework invariants; these tests pin the
mechanics recorded in ``igms/kaldors_court/igm.py``'s module docstring: the
5-gem bundle size and level-scaled Gems Galore prices with the v1.3 daily
dealer-stock cap, the flat 30,000-gold horse sell price (with a level-scaled
buy price always kept above it), the Temple's six recorded instrument
reward/penalty pairs and the Chant/Scream charm deltas, each Temple action's
once-a-day gate (each with its own recorded refusal line), the Inn's
Hercules/Xena flirting escalation (with the recorded back-room charm swing),
and the shared daily flirt gate across both targets.
"""

from __future__ import annotations

from igms.kaldors_court.igm import (
    CHANT_CHARM_DELTA,
    FAIRY_BUY_PRICE,
    FAIRY_SELL_PRICE,
    FLIRT_BACKROOM_CHARM_GAIN,
    FLIRT_BACKROOM_CHARM_LOSS,
    FLIRT_EXP_PER_LEVEL,
    GEM_BUNDLE_SIZE,
    GEM_DAILY_STOCK_BUNDLES,
    HORSE_SELL_PRICE,
    INSTRUMENT_EXP_DELTA,
    INSTRUMENT_GOLD_DELTA,
    SCREAM_CHARM_PENALTY,
    SCREAM_EXP_PER_LEVEL,
    KaldorsCourt,
    _gem_buy_price,
    _gem_sell_price,
    _horse_buy_price,
    _SEED_TALK_LINE,
)
from tests.igm_contract import contract_check
from tests.igms._harness import SeqRandom, make_ctx, make_db, make_igm_ctx, make_maint_ctx


async def _visit(keys, rng=None, **overrides):
    database, repo = await make_db()
    player = await repo.create("Hero", "pw", "M")
    for key, value in overrides.items():
        setattr(player, key, value)
    gctx = make_ctx(database, repo, player, keys=keys, rng=rng)
    return gctx, await make_igm_ctx(gctx, KaldorsCourt), player, database


async def test_contract():
    await contract_check(KaldorsCourt)


def test_ships_enabled():
    assert KaldorsCourt.default_enabled is True
    assert KaldorsCourt.key == "kaldors_court"


# --- Your stats --------------------------------------------------------


async def test_stats_screen_shows_key_fields():
    _gctx, ctx, _p, _db = await _visit(["Y", "\r", "Q"])
    await KaldorsCourt().enter(ctx)
    out = "\n".join(ctx.term.output)
    assert "Experience" in out
    assert "Hitpoints" in out
    assert "Gold in Hand" in out


# --- Marketplace: Gems Galore --------------------------------------------


async def test_gems_buy_bundle_at_level_scaled_price():
    keys = ["M", "G", "B", "\r", "L", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, gold=1_000_000)
    await KaldorsCourt().enter(ctx)
    assert p.gems == GEM_BUNDLE_SIZE
    assert p.gold == 1_000_000 - _gem_buy_price(1)
    assert ctx.store.get("gem_stock") == GEM_DAILY_STOCK_BUNDLES - 1


async def test_gems_buy_insufficient_gold_refused():
    keys = ["M", "G", "B", "\r", "L", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, gold=100)
    await KaldorsCourt().enter(ctx)
    assert p.gems == 0
    assert p.gold == 100


async def test_gems_buy_refused_when_stock_exhausted():
    # Buy out the dealer's whole day's stock, then try once more.
    keys = ["M", "G"] + ["B", "\r"] * (GEM_DAILY_STOCK_BUNDLES + 1) + ["L", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, gold=100_000)
    await KaldorsCourt().enter(ctx)
    assert p.gems == GEM_DAILY_STOCK_BUNDLES * GEM_BUNDLE_SIZE
    assert p.gold == 100_000 - GEM_DAILY_STOCK_BUNDLES * _gem_buy_price(1)
    assert ctx.store.get("gem_stock") == 0
    assert any("all out of gems for the day" in line for line in ctx.term.output)


async def test_gems_sell_at_level_scaled_price():
    keys = ["M", "G", "S", "5", "\r", "L", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, gems=10)
    await KaldorsCourt().enter(ctx)
    assert p.gems == 5
    assert p.gold == 500 + 5 * _gem_sell_price(1)


async def test_gems_sell_more_than_owned_refused():
    keys = ["M", "G", "S", "10", "\r", "L", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, gems=2)
    await KaldorsCourt().enter(ctx)
    assert p.gems == 2
    assert p.gold == 500


def test_gem_round_trip_always_loses_gold():
    """Economy guardrail: buying a bundle then immediately selling it back
    must always cost gold, at every level 1-12."""
    for level in range(1, 13):
        bundle_cost = _gem_buy_price(level)
        resale_value = _gem_sell_price(level) * GEM_BUNDLE_SIZE
        assert resale_value < bundle_cost


# --- Marketplace: Horse Heaven --------------------------------------------


async def test_horse_buy_at_level_scaled_price():
    keys = ["M", "H", "B", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, gold=1_000_000)
    await KaldorsCourt().enter(ctx)
    assert p.horse == 1
    assert p.gold == 1_000_000 - _horse_buy_price(1)


async def test_horse_buy_already_owned_refused():
    keys = ["M", "H", "B", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, horse=1, gold=1_000_000)
    await KaldorsCourt().enter(ctx)
    assert p.gold == 1_000_000


async def test_horse_sell_flat_price():
    keys = ["M", "H", "S", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, horse=1)
    await KaldorsCourt().enter(ctx)
    assert p.horse == 0
    assert p.gold == 500 + HORSE_SELL_PRICE


async def test_horse_sell_without_horse_refused():
    keys = ["M", "H", "S", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys)
    await KaldorsCourt().enter(ctx)
    assert p.gold == 500
    assert p.horse == 0


def test_horse_round_trip_always_loses_gold():
    for level in range(1, 13):
        assert HORSE_SELL_PRICE < _horse_buy_price(level)


# --- Marketplace: Fairies `R` Us -------------------------------------------


async def test_fairy_buy():
    keys = ["M", "F", "B", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, gold=1_000_000)
    await KaldorsCourt().enter(ctx)
    assert p.has_fairy == 1
    assert p.gold == 1_000_000 - FAIRY_BUY_PRICE


async def test_fairy_buy_already_owned_refused():
    keys = ["M", "F", "B", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, has_fairy=1, gold=1_000_000)
    await KaldorsCourt().enter(ctx)
    assert p.gold == 1_000_000


async def test_fairy_sell():
    keys = ["M", "F", "S", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, has_fairy=1)
    await KaldorsCourt().enter(ctx)
    assert p.has_fairy == 0
    assert p.gold == 500 + FAIRY_SELL_PRICE


async def test_fairy_sell_without_one_refused():
    keys = ["M", "F", "S", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys)
    await KaldorsCourt().enter(ctx)
    assert p.gold == 500
    assert p.has_fairy == 0


def test_fairy_round_trip_always_loses_gold():
    assert FAIRY_SELL_PRICE < FAIRY_BUY_PRICE


async def test_fairy_buy_limited_to_once_per_day_cross_igm_guardrail():
    """Cross-IGM guardrail: buying a fairy here is gated to once/day so a
    player can't buy cheap here, sell high at igms/sunshines_fairy_land's
    General Store (FAIRY_SELL_PRICE=500,000 there), and repeat for
    unbounded gold in a single day -- see module docstring."""
    keys = ["M", "F", "B", "\r", "F", "S", "\r", "F", "B", "\r", "Q", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, gold=1_000_000)
    await KaldorsCourt().enter(ctx)
    assert p.has_fairy == 0  # bought, then sold; second buy refused
    assert p.gold == 1_000_000 - FAIRY_BUY_PRICE + FAIRY_SELL_PRICE
    assert any("sold you all the fairies it can spare" in line for line in ctx.term.output)


# --- Temple: Chant with the monks ------------------------------------------


async def test_chant_success_gains_charm():
    keys = ["T", "C", "\r", "L", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([0]))
    await KaldorsCourt().enter(ctx)
    assert p.charm == 1 + CHANT_CHARM_DELTA


async def test_chant_failure_loses_charm():
    keys = ["T", "C", "\r", "L", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([1]))
    await KaldorsCourt().enter(ctx)
    assert p.charm == max(0, 1 - CHANT_CHARM_DELTA)


async def test_chant_limited_to_once_per_day():
    keys = ["T", "C", "\r", "C", "\r", "L", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([0]))
    await KaldorsCourt().enter(ctx)
    assert p.charm == 1 + CHANT_CHARM_DELTA  # only the first chant counted
    assert any("anymore today" in line for line in ctx.term.output)


# --- Temple: Play an instrument ---------------------------------------------


async def test_instrument_gong_win_gains_gold():
    keys = ["T", "P", "G", "\r", "L", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([0]))
    await KaldorsCourt().enter(ctx)
    assert p.gold == 500 + INSTRUMENT_GOLD_DELTA


async def test_instrument_bells_lose_exp():
    keys = ["T", "P", "B", "\r", "L", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([1]))
    await KaldorsCourt().enter(ctx)
    assert p.exp == max(0, 1 - INSTRUMENT_EXP_DELTA)


async def test_instrument_none_does_not_consume_gate_or_roll():
    keys = ["T", "P", "N", "P", "G", "\r", "L", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([0]))
    await KaldorsCourt().enter(ctx)
    assert p.gold == 500 + INSTRUMENT_GOLD_DELTA


async def test_instrument_limited_to_once_per_day():
    keys = ["T", "P", "G", "\r", "P", "\r", "L", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([0]))
    await KaldorsCourt().enter(ctx)
    assert p.gold == 500 + INSTRUMENT_GOLD_DELTA  # only the first play counted
    assert any("Give it a rest" in line for line in ctx.term.output)


# --- Temple: Scream loudly ---------------------------------------------


async def test_scream_obscene_win_gains_level_scaled_exp():
    keys = ["T", "S", "O", "\r", "L", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([0]))
    await KaldorsCourt().enter(ctx)
    assert p.exp == 1 + SCREAM_EXP_PER_LEVEL * p.level


async def test_scream_obscene_loss_costs_charm():
    keys = ["T", "S", "O", "\r", "L", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([1]))
    await KaldorsCourt().enter(ctx)
    assert p.charm == max(0, 1 - SCREAM_CHARM_PENALTY)


async def test_scream_earpiercing_win_is_flavor_only():
    keys = ["T", "S", "E", "\r", "L", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([0]))
    await KaldorsCourt().enter(ctx)
    assert p.exp == 1
    assert p.charm == 1
    assert p.gold == 500


async def test_scream_earpiercing_loss_costs_charm():
    keys = ["T", "S", "E", "\r", "L", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([1]))
    await KaldorsCourt().enter(ctx)
    assert p.charm == max(0, 1 - SCREAM_CHARM_PENALTY)


async def test_scream_changemind_does_not_consume_gate_or_roll():
    keys = ["T", "S", "C", "S", "O", "\r", "L", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([0]))
    await KaldorsCourt().enter(ctx)
    assert p.exp == 1 + SCREAM_EXP_PER_LEVEL * p.level


async def test_scream_limited_to_once_per_day():
    keys = ["T", "S", "O", "\r", "S", "\r", "L", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([0]))
    await KaldorsCourt().enter(ctx)
    assert p.exp == 1 + SCREAM_EXP_PER_LEVEL * p.level  # only the first scream counted
    assert any("against screaming anymore today" in line for line in ctx.term.output)


# --- Inn: Converse with the Kaldorians --------------------------------------


async def test_converse_shows_the_seed_line():
    keys = ["I", "C", "C", "L", "Q"]
    _gctx, ctx, _p, _db = await _visit(keys, rng=SeqRandom([0]))
    await KaldorsCourt().enter(ctx)
    assert any("Hey Bartender" in line for line in ctx.term.output)


async def test_converse_add_line_appends_to_the_board():
    keys = ["I", "C", "A", "Hello there", "\r", "L", "Q"]
    _gctx, ctx, _p, _db = await _visit(keys, rng=SeqRandom([0]))
    await KaldorsCourt().enter(ctx)
    assert ctx.store.get("talk_board") == [_SEED_TALK_LINE, "Hero: Hello there"]


# --- Inn: Flirt with Hercules / Xena ----------------------------------------


async def test_flirt_wink_win_gains_level_scaled_exp():
    keys = ["I", "H", "W", "\r", "L", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([0]))
    await KaldorsCourt().enter(ctx)
    assert p.exp == 1 + FLIRT_EXP_PER_LEVEL["W"] * p.level


async def test_flirt_wink_loss_costs_exp():
    keys = ["I", "H", "W", "\r", "L", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([99]))
    await KaldorsCourt().enter(ctx)
    assert p.exp == max(0, 1 - FLIRT_EXP_PER_LEVEL["W"] * p.level)


async def test_flirt_backroom_win_gains_exp_and_charm():
    keys = ["I", "H", "T", "\r", "L", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([0]))
    await KaldorsCourt().enter(ctx)
    assert p.exp == 1 + FLIRT_EXP_PER_LEVEL["T"] * p.level
    assert p.charm == 1 + FLIRT_BACKROOM_CHARM_GAIN


async def test_flirt_backroom_loss_costs_exp_and_charm():
    keys = ["I", "H", "T", "\r", "L", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([99]))
    await KaldorsCourt().enter(ctx)
    assert p.exp == max(0, 1 - FLIRT_EXP_PER_LEVEL["T"] * p.level)
    assert p.charm == max(0, 1 - FLIRT_BACKROOM_CHARM_LOSS)


async def test_flirt_nevermind_does_not_consume_gate_or_roll():
    keys = ["I", "H", "N", "H", "W", "\r", "L", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([0]))
    await KaldorsCourt().enter(ctx)
    assert p.exp == 1 + FLIRT_EXP_PER_LEVEL["W"] * p.level


async def test_flirt_gate_is_shared_across_hercules_and_xena():
    """"Better not flirt anymore right now" is a single daily cap, not one
    per NPC -- flirting with Hercules blocks Xena the same day, and
    vice versa."""
    keys = ["I", "H", "W", "\r", "X", "\r", "L", "Q"]
    _gctx, ctx, p, _db = await _visit(keys, rng=SeqRandom([0]))
    await KaldorsCourt().enter(ctx)
    assert p.exp == 1 + FLIRT_EXP_PER_LEVEL["W"] * p.level  # only Hercules counted
    assert any("Better not flirt anymore" in line for line in ctx.term.output)


# --- daily_maint -------------------------------------------------------


async def test_daily_maint_resets_gates_and_gem_stock_but_not_talk_board():
    database, repo = await make_db()
    player = await repo.create("Hero", "pw", "M")
    igm = KaldorsCourt()

    mctx = await make_maint_ctx(database, {}, igm.key)
    mctx.store.set("gem_stock", 0)
    mctx.store.set(f"chant:{player.id}", True)
    mctx.store.set(f"instrument:{player.id}", True)
    mctx.store.set(f"scream:{player.id}", True)
    mctx.store.set(f"flirt:{player.id}", True)
    mctx.store.set(f"fairy_buy:{player.id}", True)
    mctx.store.set("talk_board", [_SEED_TALK_LINE, "Hero: hi"])
    await mctx.store.flush(database)

    mctx2 = await make_maint_ctx(database, {}, igm.key)
    await igm.daily_maint(mctx2)
    await mctx2.store.flush(database)

    mctx3 = await make_maint_ctx(database, {}, igm.key)
    assert mctx3.store.get("gem_stock") is None
    assert mctx3.store.get(f"chant:{player.id}") is None
    assert mctx3.store.get(f"instrument:{player.id}") is None
    assert mctx3.store.get(f"scream:{player.id}") is None
    assert mctx3.store.get(f"fairy_buy:{player.id}") is None
    assert mctx3.store.get(f"flirt:{player.id}") is None
    assert mctx3.store.get("talk_board") == [_SEED_TALK_LINE, "Hero: hi"]
