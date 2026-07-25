"""The Outlands Tavern (outs13.zip) -- script-port, hybrid provenance.

``contract_check`` covers the framework invariants; these tests pin the
mechanics recorded in ``igms/outlands_tavern/igm.py``'s module docstring:
the charm-discount room price ("If user has 100 or more charm they only
pay 33% normal prices to stay overnight."), the room flag's survival across
``daily_maint`` ("Users staying in the Tavern will never lose thier rooms
after maintence is ran now!"), the Back Room's high-spirits effect, the
Wander action ported verbatim from ``SHINY.RHP``'s ``@RANDOM@ 4`` /
``@GOLD@ 10*LEVEL`` / ``@GEMS@ 2*LEVEL``, the fairy sneak-bypass ("they can
sneak by the BarKeep with no chance of being caught, and they lose the
fairy"), the too-weak reroll-without-recatch, and the no-kill guard's
mailed exp drain / attacker hp floor.
"""

from __future__ import annotations

from igms.outlands_tavern.igm import (
    CHARM_DISCOUNT_THRESHOLD,
    DISCOUNT_PRICE_FRACTION,
    REWARD_GOLD_PER_LEVEL,
    ROOM_COST_PER_LEVEL,
    VICTIM_EXP_DRAIN_PER_LEVEL,
    WANDER_GEMS_PER_LEVEL,
    WANDER_GOLD_PER_LEVEL,
    OutlandsTavern,
)
from tests.harness import query_one
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
    return gctx, await make_igm_ctx(gctx, OutlandsTavern), player, database


async def _visit_with_target(keys, rng=None, target_overrides=None, **overrides):
    """Like ``_visit``, but also creates a second player ("Villager") --
    see ``tests/igms/test_werewolf.py``'s identical helper for why target
    overrides must be saved before the roster snapshot is taken."""
    database, repo = await make_db()
    player = await repo.create("Hero", "pw", "M")
    for key, value in overrides.items():
        setattr(player, key, value)
    target = await repo.create("Villager", "pw", "M")
    for key, value in (target_overrides or {}).items():
        setattr(target, key, value)
    if target_overrides:
        await repo.save(target)
    gctx = make_ctx(database, repo, player, keys=keys, rng=rng)
    return gctx, await make_igm_ctx(gctx, OutlandsTavern), player, target, database


async def test_contract():
    await contract_check(OutlandsTavern)


def test_ships_enabled():
    assert OutlandsTavern.default_enabled is True
    assert OutlandsTavern.key == "outlands_tavern"


# --- Room: charm discount ("100 or more charm... 33% normal prices") -------


async def test_room_charges_full_price_and_ends_the_visit():
    _gctx, ctx, p, _db = await _visit(["R", "Y"], gold=1000, charm=1)
    await OutlandsTavern().enter(ctx)
    assert p.gold == 1000 - ROOM_COST_PER_LEVEL * p.level
    assert ctx.store.get(f"room:{p.name.lower()}") is True


async def test_room_charm_discount_at_threshold():
    _gctx, ctx, p, _db = await _visit(
        ["R", "Y"], gold=1000, charm=CHARM_DISCOUNT_THRESHOLD
    )
    await OutlandsTavern().enter(ctx)
    discounted = int(ROOM_COST_PER_LEVEL * p.level * DISCOUNT_PRICE_FRACTION)
    assert p.gold == 1000 - discounted


async def test_room_declined_no_charge():
    _gctx, ctx, p, _db = await _visit(["R", "N", "L"], gold=1000)
    await OutlandsTavern().enter(ctx)
    assert p.gold == 1000
    assert ctx.store.get(f"room:{p.name.lower()}") is None


async def test_room_insufficient_gold_refused():
    _gctx, ctx, p, _db = await _visit(["R", "Y", "\r", "L"], gold=10, level=5)
    await OutlandsTavern().enter(ctx)
    assert p.gold == 10
    assert ctx.store.get(f"room:{p.name.lower()}") is None


async def test_room_flag_cleared_and_flavored_on_players_next_visit():
    database, repo = await make_db()
    player = await repo.create("Hero", "pw", "M")
    player.gold = 1000
    igm = OutlandsTavern()

    gctx1 = make_ctx(database, repo, player, keys=["R", "Y"])
    ctx1 = await make_igm_ctx(gctx1, igm)
    await igm.enter(ctx1)
    await ctx1.flush(database)

    gctx2 = make_ctx(database, repo, player, keys=["L"])
    ctx2 = await make_igm_ctx(gctx2, igm)
    await igm.enter(ctx2)

    assert ctx2.store.get(f"room:{player.name.lower()}") is None
    assert any("gather your things" in line for line in ctx2.term.output)


async def test_daily_maint_preserves_room_but_clears_other_daily_gates():
    database, repo = await make_db()
    await repo.create("Hero", "pw", "M")
    igm = OutlandsTavern()

    mctx = await make_maint_ctx(database, {}, igm.key)
    mctx.store.set("room:hero", True)
    mctx.store.set("drunk:hero", 3)
    mctx.store.set("backroom:hero", True)
    mctx.store.set("shiny:hero", True)
    await mctx.store.flush(database)

    mctx2 = await make_maint_ctx(database, {}, igm.key)
    await igm.daily_maint(mctx2)
    await mctx2.store.flush(database)

    mctx3 = await make_maint_ctx(database, {}, igm.key)
    assert mctx3.store.get("room:hero") is True
    assert mctx3.store.get("drunk:hero") is None
    assert mctx3.store.get("backroom:hero") is None
    assert mctx3.store.get("shiny:hero") is None


# --- Talk / Drunk Meter -----------------------------------------------------


async def test_talk_increments_the_drunk_meter():
    _gctx, ctx, p, _db = await _visit(["T", "\r", "L"])
    await OutlandsTavern().enter(ctx)
    assert ctx.store.get(f"drunk:{p.name.lower()}") == 1


async def test_talk_twice_accumulates_the_drunk_meter():
    _gctx, ctx, p, _db = await _visit(["T", "\r", "T", "\r", "L"])
    await OutlandsTavern().enter(ctx)
    assert ctx.store.get(f"drunk:{p.name.lower()}") == 2


# --- Back Room: fairies grant high spirits ----------------------------------


async def test_backroom_success_grants_high_spirits():
    _gctx, ctx, p, _db = await _visit(["B", "\r", "L"], rng=SeqRandom([0]))
    await OutlandsTavern().enter(ctx)
    assert p.high_spirits == 1


async def test_backroom_failure_no_high_spirits():
    _gctx, ctx, p, _db = await _visit(["B", "\r", "L"], rng=SeqRandom([1]))
    await OutlandsTavern().enter(ctx)
    assert p.high_spirits == 0


async def test_backroom_gated_once_per_day():
    _gctx, ctx, p, _db = await _visit(
        ["B", "\r", "B", "\r", "L"], rng=SeqRandom([0])
    )
    await OutlandsTavern().enter(ctx)
    assert p.high_spirits == 1  # only the first attempt actually rolled


# --- Wander -- SHINY.RHP ("The Strange Shiny Thing"), ported verbatim ------


async def test_wander_decline_no_effect():
    _gctx, ctx, p, _db = await _visit(["W", "N", "\r", "L"])
    await OutlandsTavern().enter(ctx)
    assert p.gold == 500  # unchanged (Player.gold default)
    assert p.gems == 0


async def test_wander_nothing_outcome():
    _gctx, ctx, p, _db = await _visit(["W", "Y", "\r", "L"], rng=SeqRandom([0]))
    await OutlandsTavern().enter(ctx)
    assert p.gold == 500
    assert p.gems == 0


async def test_wander_gold_outcome_is_10_times_level():
    _gctx, ctx, p, _db = await _visit(["W", "Y", "\r", "L"], rng=SeqRandom([2]))
    await OutlandsTavern().enter(ctx)
    assert p.gold == 500 + WANDER_GOLD_PER_LEVEL * p.level


async def test_wander_gems_outcome_is_2_times_level():
    _gctx, ctx, p, _db = await _visit(["W", "Y", "\r", "L"], rng=SeqRandom([3]))
    await OutlandsTavern().enter(ctx)
    assert p.gems == WANDER_GEMS_PER_LEVEL * p.level


async def test_wander_gated_once_per_day():
    _gctx, ctx, p, _db = await _visit(
        ["W", "Y", "\r", "W", "\r", "L"], rng=SeqRandom([2])
    )
    await OutlandsTavern().enter(ctx)
    assert p.gold == 500 + WANDER_GOLD_PER_LEVEL * p.level  # credited only once


# --- View stats --------------------------------------------------------------


async def test_view_stats_shows_level_and_gold():
    _gctx, ctx, _p, _db = await _visit(["V", "\r", "L"])
    await OutlandsTavern().enter(ctx)
    assert any("Your Stats" in line for line in ctx.term.output)


# --- Sneak upstairs: fairy bypass --------------------------------------------


async def test_sneak_fairy_bypasses_the_barkeep_and_is_consumed():
    _gctx, ctx, p, target, database = await _visit_with_target(
        ["S", "Villager", "Y", "\r", "L"],
        rng=SeqRandom([6, 2, 15]),
        has_fairy=1,
        level=5,
        target_overrides={"level": 5},
    )
    ctx.store.set(f"room:{target.name.lower()}", True)
    await OutlandsTavern().enter(ctx)

    assert p.has_fairy == 0
    assert p.gold == 500 + REWARD_GOLD_PER_LEVEL * target.level
    assert p.exp == 1 + 15
    assert ctx.store.get(f"room:{target.name.lower()}") is None

    await ctx.flush(database)
    row = await query_one(
        database,
        "SELECT from_name, text, effect FROM mail WHERE to_id = :tid",
        tid=target.id,
    )
    assert row is not None
    assert row.from_name == "The Outlands Tavern"
    assert "ATTACKED IN YOUR ROOM" in row.text
    assert f'"exp": -{target.level * VICTIM_EXP_DRAIN_PER_LEVEL}' in row.effect


# --- Sneak upstairs: caught without a fairy ----------------------------------


async def test_sneak_caught_entering_no_attack_no_fairy_lost():
    _gctx, ctx, p, _db = await _visit(
        ["S", "\r", "L"], rng=SeqRandom([0]), has_fairy=0
    )
    await OutlandsTavern().enter(ctx)
    assert p.has_fairy == 0
    assert p.gold == 500
    assert p.exp == 1


async def test_sneak_no_sleepers_available():
    _gctx, ctx, p, _db = await _visit(
        ["S", "\r", "L"], rng=SeqRandom([1, 1]), has_fairy=0
    )
    await OutlandsTavern().enter(ctx)
    assert p.gold == 500
    assert p.exp == 1


async def test_sneak_blank_name_loses_nerve():
    _gctx, ctx, p, target, _db = await _visit_with_target(
        ["S", "\r", "\r", "L"], rng=SeqRandom([1, 1])
    )
    ctx.store.set(f"room:{target.name.lower()}", True)
    await OutlandsTavern().enter(ctx)
    assert p.gold == 500
    assert p.exp == 1


async def test_sneak_unknown_name_lets_retry_without_recatch():
    _gctx, ctx, p, target, _database = await _visit_with_target(
        ["S", "Bogus", "Villager", "Y", "\r", "L"],
        rng=SeqRandom([1, 6, 1, 10]),
    )
    ctx.store.set(f"room:{target.name.lower()}", True)
    await OutlandsTavern().enter(ctx)
    assert p.exp == 1 + 10
    assert p.gold == 500 + REWARD_GOLD_PER_LEVEL * target.level


async def test_sneak_too_weak_target_lets_pick_another_without_recatch():
    database, repo = await make_db()
    player = await repo.create("Hero", "pw", "M")
    player.level = 10
    weakling = await repo.create("Villager", "pw", "M")
    weakling.level = 1
    await repo.save(weakling)
    champ = await repo.create("Champion", "pw", "M")
    champ.level = 10
    await repo.save(champ)

    gctx = make_ctx(
        database,
        repo,
        player,
        keys=["S", "Villager", "Champion", "Y", "\r", "L"],
        rng=SeqRandom([1, 6, 1, 10]),
    )
    ctx = await make_igm_ctx(gctx, OutlandsTavern)
    ctx.store.set("room:villager", True)
    ctx.store.set("room:champion", True)
    await OutlandsTavern().enter(ctx)

    assert player.exp == 1 + 10
    assert player.gold == 500 + REWARD_GOLD_PER_LEVEL * champ.level
    # the weakling was never touched
    assert ctx.store.get("room:villager") is True


# --- Sneak upstairs: no-kill guard on a failed attack ------------------------


async def test_sneak_attack_failure_floors_attackers_hp_never_kills():
    _gctx, ctx, p, target, database = await _visit_with_target(
        ["S", "Villager", "Y", "\r", "L"],
        rng=SeqRandom([1, 1, 6]),
        hp=20,
        hp_max=20,
    )
    ctx.store.set(f"room:{target.name.lower()}", True)
    await OutlandsTavern().enter(ctx)

    assert p.exp == 1  # no reward on a loss
    assert p.hp == max(1, 20 - 20 // 3)
    assert p.hp >= 1

    await ctx.flush(database)
    row = await query_one(
        database, "SELECT 1 FROM mail WHERE to_id = :tid", tid=target.id
    )
    assert row is None
