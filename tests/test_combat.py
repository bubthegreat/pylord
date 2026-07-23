"""Tests for pylord.engine.combat -- see the module for lord.js line-number
citations behind every formula ported here."""

import random

import pytest

from pylord.engine import combat, data
from pylord.models import Player


def make_player(**overrides) -> Player:
    defaults = {
        "id": 1,
        "name": "Hero",
        "password_hash": "x",
        "strength": 10,
        "defense": 1,
        "hp": 20,
        "hp_max": 20,
        "weapon_num": 0,
    }
    defaults.update(overrides)
    return Player(**defaults)


def small_thief() -> data.Monster:
    return data.MONSTERS[1][0]


def test_from_player_unarmed_uses_fists():
    c = combat.Combatant.from_player(make_player(weapon_num=0))
    assert c.weapon_name == "Fists"
    assert c.hp == 20 and c.hp_max == 20
    assert c.strength == 10
    assert c.defense == 1


def test_from_player_armed_looks_up_weapon_name():
    c = combat.Combatant.from_player(make_player(weapon_num=3))
    assert c.weapon_name == "Short Sword"


def test_from_monster_has_zero_defense():
    m = small_thief()
    assert m.name == "Small Thief"
    c = combat.Combatant.from_monster(m)
    assert c.defense == 0
    assert c.strength == 6
    assert c.hp == 9 and c.hp_max == 9
    assert c.weapon_name == "Small Dagger"


def test_from_master_carries_real_defense():
    master = data.MASTERS[1]
    c = combat.Combatant.from_master(master)
    assert c.defense == master.defense
    assert c.defense != 0


def test_attack_damage_is_never_negative():
    attacker = combat.Combatant(
        name="A", hp=10, hp_max=10, strength=4, defense=0, weapon_name="Fists"
    )
    defender = combat.Combatant(
        name="B", hp=10, hp_max=10, strength=1, defense=999, weapon_name="Fists"
    )
    rng = random.Random(0)
    for _ in range(500):
        dmg = combat.attack_damage(attacker, defender, rng)
        assert dmg >= 0


def test_player_attack_round_damage_never_negative():
    player = combat.Combatant.from_player(make_player())
    enemy = combat.Combatant.from_monster(small_thief())
    for seed in range(200):
        fight = combat.Fight(player, enemy, random.Random(seed))
        round_ = fight.player_attack()
        assert round_.damage >= 0


def test_enemy_attack_round_damage_never_negative():
    player = combat.Combatant.from_player(make_player())
    enemy = combat.Combatant.from_monster(small_thief())
    for seed in range(200):
        fight = combat.Fight(player, enemy, random.Random(seed))
        round_ = fight.enemy_attack()
        assert round_.damage >= 0


def test_player_can_defeat_small_thief_with_seeded_rng():
    player = combat.Combatant.from_player(make_player())
    enemy = combat.Combatant.from_monster(small_thief())
    fight = combat.Fight(player, enemy, random.Random(1234))

    for _ in range(50):
        if fight.over:
            break
        fight.player_attack()
        if not fight.over:
            fight.enemy_attack()

    assert fight.over
    assert fight.winner == "player"
    assert fight.enemy.hp <= 0


def test_kill_sets_over_and_winner_player():
    player = combat.Combatant(
        name="Hero", hp=20, hp_max=20, strength=1000, defense=1, weapon_name="Fists"
    )
    enemy = combat.Combatant(
        name="Weakling", hp=1, hp_max=1, strength=1, defense=0, weapon_name="Fists"
    )
    fight = combat.Fight(player, enemy, random.Random(0))

    round_ = fight.player_attack()

    assert round_.killed is True
    assert round_.damage > 0
    assert fight.over is True
    assert fight.winner == "player"


def test_kill_sets_over_and_winner_enemy():
    player = combat.Combatant(
        name="Hero", hp=1, hp_max=20, strength=1, defense=0, weapon_name="Fists"
    )
    enemy = combat.Combatant(
        name="Brute", hp=20, hp_max=20, strength=1000, defense=0, weapon_name="Fists"
    )
    fight = combat.Fight(player, enemy, random.Random(0))

    round_ = fight.enemy_attack()

    assert round_.killed is True
    assert fight.over is True
    assert fight.winner == "enemy"


def test_attempt_run_success_seed():
    # random.Random(0).randrange(9) == 6 (!= 1) -> run succeeds, no draw
    # from the free enemy-attack path afterward.
    player = combat.Combatant.from_player(make_player())
    enemy = combat.Combatant.from_monster(small_thief())
    fight = combat.Fight(player, enemy, random.Random(0))

    ok = fight.attempt_run()

    assert ok is True
    assert fight.ran_away is True
    assert fight.over is True
    assert player.hp == fight.player_side.hp  # no free hit landed


def test_attempt_run_failure_seed():
    # random.Random(6).randrange(9) == 1 -> caught, enemy gets a free hit.
    player = combat.Combatant.from_player(make_player())
    enemy = combat.Combatant.from_monster(small_thief())
    fight = combat.Fight(player, enemy, random.Random(6))

    ok = fight.attempt_run()

    assert ok is False
    assert fight.ran_away is False


def test_death_knight_skill_requires_points():
    player = combat.Combatant.from_player(make_player())
    enemy = combat.Combatant.from_monster(small_thief())
    fight = combat.Fight(player, enemy, random.Random(0))

    round_ = combat.skill_attack(fight, "dk", 0)

    assert round_.damage == 0
    assert enemy.hp == small_thief().hp


def test_death_knight_skill_hits_at_least_once():
    player = combat.Combatant.from_player(make_player())
    enemy = combat.Combatant.from_monster(small_thief())
    fight = combat.Fight(player, enemy, random.Random(0))

    round_ = combat.skill_attack(fight, "dk", 3)

    assert round_.damage >= 1
    assert enemy.hp == small_thief().hp - round_.damage


def test_thief_skill_hits_at_least_once():
    player = combat.Combatant.from_player(make_player())
    enemy = combat.Combatant.from_monster(small_thief())
    fight = combat.Fight(player, enemy, random.Random(0))

    round_ = combat.skill_attack(fight, "th", 3)

    assert round_.damage >= 1


def test_mystical_pinch_costs_at_least_1_point():
    player = combat.Combatant.from_player(make_player())
    enemy = combat.Combatant.from_monster(small_thief())
    fight = combat.Fight(player, enemy, random.Random(0))

    round_ = combat.skill_attack(fight, "my", 0)

    assert round_.damage == 0
    assert "power" in round_.text.lower()


def test_mystical_disappear_sets_ran_away():
    player = combat.Combatant.from_player(make_player())
    enemy = combat.Combatant.from_monster(small_thief())
    fight = combat.Fight(player, enemy, random.Random(0))

    round_ = combat.skill_attack(fight, "my", 4, mystical_choice="D")

    assert round_.damage == 0
    assert fight.ran_away is True
    assert fight.over is True


def test_mystical_mind_heal_restores_hp():
    player = combat.Combatant.from_player(make_player(hp=1, hp_max=20))
    enemy = combat.Combatant.from_monster(small_thief())
    fight = combat.Fight(player, enemy, random.Random(0))
    fight.player_side.hp = 1

    round_ = combat.skill_attack(fight, "my", 20, mystical_choice="M")

    assert round_.damage == 0
    assert fight.player_side.hp == fight.player_side.hp_max


def test_mystical_light_shield_halves_next_enemy_hit():
    player = combat.Combatant.from_player(make_player(strength=1, defense=0))
    enemy = combat.Combatant.from_monster(small_thief())
    fight = combat.Fight(player, enemy, random.Random(0))

    combat.skill_attack(fight, "my", 12, mystical_choice="L")
    assert fight.light_shield is True

    shielded_fight = fight
    unshielded = combat.Fight(
        combat.Combatant.from_player(make_player(strength=1, defense=0)),
        combat.Combatant.from_monster(small_thief()),
        random.Random(42),
    )
    shielded_rng_copy = random.Random(42)
    shielded_fight.rng = shielded_rng_copy
    r_shielded = shielded_fight.enemy_attack()
    r_unshielded = unshielded.enemy_attack()

    assert r_shielded.damage <= r_unshielded.damage


def test_mystical_auto_selects_highest_affordable_tier():
    player = combat.Combatant.from_player(make_player())
    enemy = combat.Combatant.from_monster(small_thief())
    fight = combat.Fight(player, enemy, random.Random(0))

    # 20 points affords Mind Heal (highest tier); auto-select should pick it.
    fight.player_side.hp = 1
    combat.skill_attack(fight, "my", 20)

    assert fight.player_side.hp == fight.player_side.hp_max


def test_skill_attack_unknown_kind_raises():
    player = combat.Combatant.from_player(make_player())
    enemy = combat.Combatant.from_monster(small_thief())
    fight = combat.Fight(player, enemy, random.Random(0))

    with pytest.raises(ValueError):
        combat.skill_attack(fight, "nope", 5)
