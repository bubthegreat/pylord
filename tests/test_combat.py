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
    for seed in range(500):
        rng = random.Random(seed)
        assert combat.attack_damage(attacker, defender, rng, pfight=False) >= 0
        rng = random.Random(seed)
        assert combat.attack_damage(attacker, defender, rng, pfight=True) >= 0


def test_attack_damage_pfight_gates_defense_subtraction():
    """CRITICAL regression test: lord.js only subtracts defender.defense
    when pfight is true (do_attack:6948-6949, handle_hit:6897-6898).

    strength=10 -> half=5; random.Random(42).randrange(5) == 0, so the raw
    roll is 0 + 5 == 5 (hand-computed, matches _random()'s port of lord.js's
    random(n)). defender.defense=999 must be completely ignored when
    pfight=False, and fully subtracted (floored at 0) when pfight=True.
    """
    attacker = combat.Combatant(
        name="A", hp=10, hp_max=10, strength=10, defense=0, weapon_name="Fists"
    )
    defender = combat.Combatant(
        name="B", hp=10, hp_max=10, strength=1, defense=999, weapon_name="Fists"
    )

    dmg_pfight_false = combat.attack_damage(
        attacker, defender, random.Random(42), pfight=False
    )
    dmg_pfight_true = combat.attack_damage(
        attacker, defender, random.Random(42), pfight=True
    )

    assert dmg_pfight_false == 5
    assert dmg_pfight_true == 0  # 5 - 999, floored at 0


def test_player_attack_vs_master_ignores_defense():
    """CRITICAL regression test: an ordinary (non-PvP) fight against a
    Master never subtracts the Master's defense, no matter how high it is
    -- every trainer encounter runs as battle(trainer, false, false)
    (lord.js:15760), and do_attack only subtracts op.def `if (pfight)`
    (lord.js:6948-6949). Turgon (MASTERS[11]) has defense=150; without the
    fix this would floor player_attack's damage to 0 (a miss) every time.

    Hand-computed for strength=10 (half=5), random.Random(42):
    randrange(5) == 0 -> raw = 5; randrange(10)+1 == 1 (not > 9, no crit)
    -> final damage == 5, completely unaffected by Turgon's defense=150.
    """
    player = combat.Combatant(
        name="Hero", hp=20, hp_max=20, strength=10, defense=1, weapon_name="Fists"
    )
    turgon = combat.Combatant.from_master(data.MASTERS[11])
    assert turgon.defense == 150

    fight = combat.Fight(player, turgon, random.Random(42))  # pfight defaults False

    round_ = fight.player_attack()

    assert round_.damage == 5
    assert round_.killed is False
    assert "miss" not in round_.text.lower()


def test_player_attack_pfight_true_subtracts_defense():
    """PvP-style test: with pfight=True, the defender's defense IS
    subtracted (lord.js:6948-6949, the only caller that sets pfight=true is
    real player-vs-player combat, lord.js:7824).

    Hand-computed for strength=10 (half=5), random.Random(42): raw roll ==
    5 (as above), defender.defense=3 subtracted -> 2; crit_roll == 1 (not >
    9, no crit multiply) -> final damage == 2.
    """
    player = combat.Combatant(
        name="Hero", hp=20, hp_max=20, strength=10, defense=1, weapon_name="Fists"
    )
    rival = combat.Combatant(
        name="Rival", hp=20, hp_max=20, strength=8, defense=3, weapon_name="Dagger"
    )
    fight = combat.Fight(player, rival, random.Random(42), pfight=True)

    round_ = fight.player_attack()

    assert round_.damage == 2


def test_player_attack_round_damage_never_negative():
    player = combat.Combatant.from_player(make_player())
    enemy = combat.Combatant.from_monster(small_thief())
    for seed in range(200):
        fight = combat.Fight(player, enemy, random.Random(seed))
        round_ = fight.player_attack()
        assert round_.damage >= 0


def test_enemy_attack_exact_value_vs_small_thief():
    """Exact-value regression test for a normal monster attack.

    Small Thief strength=6 -> half=3. random.Random(0): randrange(3) == 1
    -> raw = 1 + 3 = 4; randrange(30) == 24 (!= 1, no power move); player
    defense=1 -> atk = 4 - 1 = 3 (hand-computed against enemy_attack()'s
    ported formula, lord.js:6703-6726).
    """
    player = combat.Combatant.from_player(make_player())
    enemy = combat.Combatant.from_monster(small_thief())
    fight = combat.Fight(player, enemy, random.Random(0))

    round_ = fight.enemy_attack()

    assert round_.damage == 3
    assert player.hp == 20 - 3


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

    round_ = combat.skill_attack(fight, "my", 4, mystical_choice="D", skill_rank=40)

    assert round_.damage == 0
    assert fight.ran_away is True
    assert fight.over is True


def test_mystical_mind_heal_restores_hp():
    player = combat.Combatant.from_player(make_player(hp=1, hp_max=20))
    enemy = combat.Combatant.from_monster(small_thief())
    fight = combat.Fight(player, enemy, random.Random(0))
    fight.player_side.hp = 1

    round_ = combat.skill_attack(fight, "my", 20, mystical_choice="M", skill_rank=40)

    assert round_.damage == 0
    assert fight.player_side.hp == fight.player_side.hp_max


def test_mystical_light_shield_halves_next_enemy_hit():
    player = combat.Combatant.from_player(make_player(strength=1, defense=0))
    enemy = combat.Combatant.from_monster(small_thief())
    fight = combat.Fight(player, enemy, random.Random(0))

    combat.skill_attack(fight, "my", 12, mystical_choice="L", skill_rank=40)
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
    combat.skill_attack(fight, "my", 20, skill_rank=40)

    assert fight.player_side.hp == fight.player_side.hp_max


def test_skill_attack_unknown_kind_raises():
    player = combat.Combatant.from_player(make_player())
    enemy = combat.Combatant.from_monster(small_thief())
    fight = combat.Fight(player, enemy, random.Random(0))

    with pytest.raises(ValueError):
        combat.skill_attack(fight, "nope", 5)


# -- Rank gating, arena rules, dragon breath, opening round ----------------


def test_mystical_tier_needs_permanent_rank_not_just_uses():
    """reference/lord.js:7247-7268 gates each tier on levelm AND skillm --
    20 use points with rank 0 can't reach Mind Heal (or anything above
    Pinch, which every mystic knows)."""
    fight = combat.Fight(
        combat.Combatant.from_player(make_player(hp=1, hp_max=20)),
        combat.Combatant.from_monster(small_thief()),
        random.Random(0),
    )

    round_ = combat.skill_attack(fight, "my", 20, mystical_choice="M", skill_rank=0)

    assert round_.damage == 0
    assert fight.player_side.hp == 1  # no heal happened
    assert round_.counter is False  # a refused cast costs no counter-attack


def test_running_from_a_master_is_refused():
    """Every trainer is an arena opponent (reference/lord.js:7001-7006)."""
    fight = combat.Fight(
        combat.Combatant.from_player(make_player()),
        combat.Combatant.from_master(data.MASTERS[1]),
        random.Random(0),
    )

    assert fight.can_run is False
    assert fight.attempt_run() is False
    assert fight.ran_away is False


def test_skill_attacks_are_refused_against_a_master():
    """reference/lord.js:7045-7051, 7118-7124, 7211-7217."""
    for kind in ("dk", "th", "my"):
        fight = combat.Fight(
            combat.Combatant.from_player(make_player()),
            combat.Combatant.from_master(data.MASTERS[1]),
            random.Random(0),
        )
        hp_before = fight.enemy.hp

        round_ = combat.skill_attack(fight, kind, 20, skill_rank=40)

        assert round_.damage == 0
        assert fight.enemy.hp == hp_before
        assert "honor" in round_.text
        assert round_.counter is False


def test_dragon_flaming_breath_doubles_the_roll():
    """reference/lord.js:6704-6720 -- weapon pick 2 doubles the damage."""

    class _PickedRNG:
        """random(str//2) -> 0, then the dragon weapon pick, then the
        power-move roll (never 1)."""

        def __init__(self, weapon_pick):
            self._weapon_pick = weapon_pick
            self._calls = 0

        def randrange(self, n):
            self._calls += 1
            if self._calls == 1:
                return 0  # base roll addend
            if self._calls == 2:
                return self._weapon_pick
            return 0  # power-move roll: not 1, so no power move

    dragon = data.Monster(
        name="Red Dragon", weapon="Claw", strength=20, hp=100, gold=0, exp=0,
        death_phrase="",
    )
    breath = combat.Fight(
        combat.Combatant.from_player(make_player(defense=0)),
        combat.Combatant.from_monster(dragon, is_dragon=True),
        _PickedRNG(2),
    ).enemy_attack()
    claw = combat.Fight(
        combat.Combatant.from_player(make_player(defense=0)),
        combat.Combatant.from_monster(dragon, is_dragon=True),
        _PickedRNG(0),
    ).enemy_attack()

    assert breath.damage == claw.damage * 2
    assert "Flaming Breath" in breath.text


def test_opening_round_surprises_on_a_high_roll():
    """reference/lord.js:7375-7389 -- tmp = random(99) + 1 > 90."""

    class _FixedRNG:
        def __init__(self, first):
            self._first = first
            self._used = False

        def randrange(self, n):
            if not self._used:
                self._used = True
                return self._first
            return 0

    surprised = combat.Fight(
        combat.Combatant.from_player(make_player()),
        combat.Combatant.from_monster(small_thief()),
        _FixedRNG(94),  # -> tmp 95
    )
    result = surprised.opening()
    assert "surprises you" in result.text
    assert result.counter is False

    first_strike = combat.Fight(
        combat.Combatant.from_player(make_player()),
        combat.Combatant.from_monster(small_thief()),
        _FixedRNG(0),  # -> tmp 1
    )
    assert "first strike" in first_strike.opening().text
    assert first_strike.player_side.hp == first_strike.player_side.hp_max


def test_opening_round_always_surprises_a_higher_level_pvp_target():
    """reference/lord.js:7377-7383 -- any roll over 60 becomes 95."""

    class _FixedRNG:
        def __init__(self, first):
            self._first = first
            self._used = False

        def randrange(self, n):
            if not self._used:
                self._used = True
                return self._first
            return 0

    fight = combat.Fight(
        combat.Combatant.from_player(make_player()),
        combat.Combatant.from_player(make_player(name="Bigger")),
        _FixedRNG(70),  # -> tmp 71, harmless outside PvP
        pfight=True,
    )
    result = fight.opening(player_level=1, enemy_level=5)
    assert "surprises you" in result.text
