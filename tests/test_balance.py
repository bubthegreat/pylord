"""Balance regression guards for the armor rebalance.

Locks in the spec's survivability window
(docs/superpowers/specs/2026-08-07-armor-rebalance-design.md): a level-10
player in tier-10 gear survives level-10 forest monsters except on
genuinely unlucky rolls, while monsters still land a meaningful share of
their swings. Seeded rng -- deterministic. Simulates production forest
encounters via Fight.opening() for initiative (no pfight/levels args needed —
defaults correct for forest). If a future data edit (armor, monsters, level
grants) breaks either bound, this test is the tripwire.
"""

import random

from pylord.engine.combat import Combatant, Fight
from pylord.engine.data.armor import armor
from pylord.engine.data.levels import LEVEL_STATS
from pylord.engine.data.monsters import MONSTERS
from pylord.engine.data.weapons import WEAPONS


def _level10_player() -> Combatant:
    """Fresh level-10 build: starting stats (20 hp / 10 str / 1 def) plus
    every level-up grant through level 9, tier-10 weapon and armor."""
    hp = 20 + sum(LEVEL_STATS[i].hp for i in range(1, 10))
    strength = (
        10
        + sum(LEVEL_STATS[i].strength for i in range(1, 10))
        + WEAPONS[9].power
    )
    defense = (
        1
        + sum(LEVEL_STATS[i].defense for i in range(1, 10))
        + armor(10).power
    )
    return Combatant(
        name="Hero",
        hp=hp,
        hp_max=hp,
        strength=strength,
        defense=defense,
        weapon_name="Wans' Weapon",
    )


def test_level10_in_full_body_survives_level10_forest():
    rng = random.Random(1234)
    trials = 2000
    deaths = 0
    blocked = 0
    swings = 0

    for _ in range(trials):
        monster = MONSTERS[10][rng.randrange(10)]
        fight = Fight(_level10_player(), Combatant.from_monster(monster), rng)
        fight.opening()  # Initiative roll (~9% chance monster lands unanswered swing)
        while not fight.over:
            fight.player_attack()
            if fight.over:
                break
            round_ = fight.enemy_attack()
            swings += 1
            # blocked-rate excludes opening swing; counting main-loop swings only
            if round_.damage == 0:
                blocked += 1
        if fight.winner == "enemy":
            deaths += 1

    death_rate = deaths / trials
    blocked_rate = blocked / swings
    # Survivable: dying to a same-level monster takes real bad luck.
    assert death_rate < 0.05, f"death rate {death_rate:.1%}"
    # ... but not nullified: monsters still land a meaningful share.
    assert 0.50 < blocked_rate < 0.90, f"blocked rate {blocked_rate:.1%}"
