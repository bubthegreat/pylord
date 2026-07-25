"""WereWolf (ww301) -- documented recreation (Task 3).

``contract_check`` covers the framework invariants; these tests pin the
mechanics recorded in ``igms/werewolf/igm.py``'s module docstring: the
2-forest-fight + 2-player-fight cost gate ("Most choices cost 2 Forest + 2
Human"), the 10%-of-current-exp reward cap ("a maximum of 10% of their
total experience for each thing they do"), a successful attack's mail
effect on the victim and the "corpse" flag it leaves for Desecrate, a
failed attack's no-kill-guard hp floor, and ``daily_maint`` clearing any
unused corpse flag.
"""

from __future__ import annotations

from igms.werewolf.igm import WereWolf
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
    return gctx, await make_igm_ctx(gctx, WereWolf), player, database


async def _visit_with_target(keys, rng=None, target_overrides=None, **overrides):
    """Like ``_visit``, but also creates a second player ("Villager") who
    can appear in ``ctx.other_players()``. Any overrides on the target must
    be saved to the DB before the IgmContext snapshot is taken -- the
    roster is read fresh from the database, not from the in-memory
    object."""
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
    return gctx, await make_igm_ctx(gctx, WereWolf), player, target, database


async def test_contract():
    await contract_check(WereWolf)


def test_ships_disabled():
    assert WereWolf.default_enabled is False
    assert WereWolf.key == "werewolf"


# --- cost gate: "Most choices cost 2 Forest + 2 Human." --------------------


async def test_attack_refused_without_fight_budget_no_charge():
    _gctx, ctx, p, _db = await _visit(
        ["F", "\r", "L"], player_fights=1, forest_fights=15
    )
    await WereWolf().enter(ctx)
    assert p.player_fights == 1  # unchanged -- refused before any spend
    assert p.forest_fights == 15


async def test_eat_kid_refused_without_fight_budget_no_charge():
    _gctx, ctx, p, _db = await _visit(["E", "\r", "L"], player_fights=1)
    await WereWolf().enter(ctx)
    assert p.player_fights == 1
    assert p.forest_fights == 15
    assert p.exp == 1  # no reward granted


async def test_kill_horse_costs_2_forest_2_player_fights():
    _gctx, ctx, p, _db = await _visit(
        ["K", "\r", "L"], rng=SeqRandom([1]), exp=10
    )
    await WereWolf().enter(ctx)
    assert p.forest_fights == 13
    assert p.player_fights == 1


# --- reward cap: "a maximum of 10% of their total experience..." -----------


async def test_kill_horse_reward_is_capped_at_10pct_of_current_exp():
    _gctx, ctx, p, _db = await _visit(
        ["K", "\r", "L"], rng=SeqRandom([5]), exp=50
    )
    await WereWolf().enter(ctx)
    # cap = max(1, int(50 * 0.10)) == 5; the scripted roll (5) is granted
    # in full since it sits exactly at the cap.
    assert p.exp == 55


async def test_eat_kid_reward_floors_at_1_for_a_fresh_character():
    # Player.exp defaults to 1; a strict 10% cap would be 0 -- the
    # invented MIN_EXP_REWARD floor keeps the action from being a no-op.
    _gctx, ctx, p, _db = await _visit(["E", "\r", "L"], rng=SeqRandom([1]))
    await WereWolf().enter(ctx)
    assert p.exp == 2


# --- PvP attack: success ----------------------------------------------------


async def test_forest_attack_success_grants_reward_spends_budget_and_mails_victim():
    # queue order: mine (attack roll), his (target roll), reward roll.
    _gctx, ctx, p, target, database = await _visit_with_target(
        ["F", "Villager", "\r", "L"],
        rng=SeqRandom([5, 2, 3]),
        exp=50,
    )
    await WereWolf().enter(ctx)

    assert p.exp == 53  # 50 + scripted reward of 3 (<= cap of 5)
    assert p.forest_fights == 13
    assert p.player_fights == 1
    assert ctx.store.get(f"corpse:{p.id}") == "Villager"

    await ctx.flush(database)
    row = await query_one(
        database,
        "SELECT from_name, text, effect FROM mail WHERE to_id = :tid",
        tid=target.id,
    )
    assert row is not None
    assert row.from_name == "WereWolf"
    assert "YOU HAVE BEEN ATTACKED" in row.text
    # target.level defaults to 1 -- drain == 1 * VICTIM_EXP_DRAIN_PER_LEVEL (10)
    assert '"exp": -10' in row.effect


async def test_inn_attack_uses_inn_flavor_and_same_mechanics():
    _gctx, ctx, p, _target, _database = await _visit_with_target(
        ["I", "Villager", "\r", "L"],
        rng=SeqRandom([5, 2, 3]),
        exp=50,
    )
    await WereWolf().enter(ctx)
    assert p.exp == 53
    assert ctx.store.get(f"corpse:{p.id}") == "Villager"


async def test_attack_is_case_insensitive_on_target_name():
    _gctx, ctx, p, _target, _database = await _visit_with_target(
        ["F", "VILLAGER", "\r", "L"],
        rng=SeqRandom([5, 2, 3]),
        exp=50,
    )
    await WereWolf().enter(ctx)
    assert p.exp == 53


# --- PvP attack: failure / no-kill guard ------------------------------------


async def test_failed_attack_floors_attackers_own_hp_never_kills():
    # mine < his -> attacker loses; no reward, no mail, no corpse flag.
    _gctx, ctx, p, target, database = await _visit_with_target(
        ["F", "Villager", "\r", "L"],
        rng=SeqRandom([1, 5, 200]),
        exp=50,
        hp=20,
        hp_max=20,
    )
    await WereWolf().enter(ctx)

    assert p.exp == 50  # no reward on a loss
    assert p.hp == max(1, 20 - 200)  # damage clamped by PlayerView -> floors at 1
    assert p.hp >= 1
    assert p.forest_fights == 13  # budget still spent on a failed attempt
    assert p.player_fights == 1
    assert ctx.store.get(f"corpse:{p.id}") is None

    await ctx.flush(database)
    row = await query_one(
        database, "SELECT 1 FROM mail WHERE to_id = :tid", tid=target.id
    )
    assert row is None


# --- attack eligibility gates (checked before any resource is spent) -------


async def test_attack_with_no_other_players_costs_nothing():
    _gctx, ctx, p, _db = await _visit(["F", "\r", "L"])
    await WereWolf().enter(ctx)
    assert p.forest_fights == 15
    assert p.player_fights == 3


async def test_attack_blank_name_loses_the_scent_no_charge():
    # menu(F) + readline(blank "\r") + pause-dismiss + menu(L)
    _gctx, ctx, p, _target, _db = await _visit_with_target(
        ["F", "\r", "\r", "L"]
    )
    await WereWolf().enter(ctx)
    assert p.forest_fights == 15
    assert p.player_fights == 3


async def test_attack_unknown_name_refused_no_charge():
    _gctx, ctx, p, _target, _db = await _visit_with_target(
        ["F", "Nobody", "\r", "L"]
    )
    await WereWolf().enter(ctx)
    assert p.forest_fights == 15
    assert p.player_fights == 3


async def test_attack_dead_target_refused_no_charge():
    _gctx, ctx, p, _target, _db = await _visit_with_target(
        ["F", "Villager", "\r", "L"], target_overrides={"alive": 0}
    )
    await WereWolf().enter(ctx)
    assert p.forest_fights == 15
    assert p.player_fights == 3


# --- Desecrate ---------------------------------------------------------------


async def test_desecrate_with_no_corpse_is_refused():
    _gctx, ctx, p, _db = await _visit(["D", "\r", "L"])
    await WereWolf().enter(ctx)
    assert p.exp == 1  # unchanged


async def test_desecrate_after_a_kill_grants_reward_and_clears_flag():
    _gctx, ctx, p, _target, _database = await _visit_with_target(
        ["F", "Villager", "\r", "D", "\r", "L"],
        rng=SeqRandom([5, 2, 3, 4]),  # attack: mine, his, reward; desecrate: reward
        exp=50,
    )
    await WereWolf().enter(ctx)
    # attack grants 3 (50 -> 53); desecrate grants 4 more off the *new* exp
    # (53 -> cap max(1, int(53*0.10)) == 5, scripted 4 is within cap)
    assert p.exp == 57
    assert ctx.store.get(f"corpse:{p.id}") is None


async def test_desecrate_is_one_shot_per_kill():
    _gctx, ctx, p, _target, _database = await _visit_with_target(
        ["F", "Villager", "\r", "D", "\r", "D", "\r", "L"],
        rng=SeqRandom([5, 2, 3, 4]),
        exp=50,
    )
    await WereWolf().enter(ctx)
    # Second D finds no corpse flag left -- no further reward.
    assert p.exp == 57


# --- daily_maint -------------------------------------------------------------


async def test_daily_maint_clears_unused_corpse_flag():
    database, repo = await make_db()
    p = await repo.create("Hero", "pw", "M")
    igm = WereWolf()
    mctx = await make_maint_ctx(database, {}, igm.key)
    mctx.store.set(f"corpse:{p.id}", "Someone")
    await mctx.store.flush(database)

    mctx2 = await make_maint_ctx(database, {}, igm.key)
    await igm.daily_maint(mctx2)
    await mctx2.store.flush(database)

    mctx3 = await make_maint_ctx(database, {}, igm.key)
    assert mctx3.store.get(f"corpse:{p.id}") is None
