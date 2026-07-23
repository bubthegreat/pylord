"""Golden tests pinning game data tables against reference/lord.js values.

Every literal here is transcribed straight from reference/lord.js — see the
docstrings/comments in pylord/engine/data/*.py for exact line numbers.
"""

from pylord.engine import data


def test_weapon_table_shape_and_endpoints():
    assert len(data.WEAPONS) == 15
    first = data.WEAPONS[0]
    assert first.num == 1
    assert first.name == "Stick"
    assert first.price == 200
    assert first.power == 5

    last = data.WEAPONS[14]
    assert last.num == 15
    assert last.name == "Death Sword"
    assert last.price == 400000000
    assert last.power == 1800


def test_weapon_lookup_is_1_indexed():
    assert data.weapon(1) == data.WEAPONS[0]
    assert data.weapon(15) == data.WEAPONS[14]
    assert data.weapon(3).name == "Short Sword"


def test_armor_table_shape_and_endpoints():
    assert len(data.ARMOR) == 15
    first = data.ARMOR[0]
    assert first.num == 1
    assert first.name == "Coat"
    assert first.price == 200
    assert first.power == 1

    last = data.ARMOR[14]
    assert last.num == 15
    assert last.name == "Armour Of Lore"
    assert last.price == 400000000
    assert last.power == 1000


def test_armor_lookup_is_1_indexed():
    assert data.armor(1) == data.ARMOR[0]
    assert data.armor(15) == data.ARMOR[14]


def test_exp_curve_monotonic_and_endpoints():
    vals = [data.EXP_FOR_LEVEL[i] for i in range(2, 13)]
    assert vals == sorted(vals)
    assert len(vals) == len(set(vals))  # strictly increasing, no dupes
    assert data.EXP_FOR_LEVEL[2] == 100
    assert data.EXP_FOR_LEVEL[12] == 10000000


def test_level_stats_endpoints():
    assert len(data.LEVEL_STATS) == 11
    lvl1 = data.LEVEL_STATS[1]
    assert (lvl1.hp, lvl1.strength, lvl1.defense) == (10, 5, 2)
    lvl11 = data.LEVEL_STATS[11]
    assert (lvl11.hp, lvl11.strength, lvl11.defense) == (550, 200, 150)


def test_masters():
    assert len(data.MASTERS) == 11
    assert data.MASTERS[1].name == "Halder"
    assert data.MASTERS[1].weapon == "Short Sword"
    assert data.MASTERS[1].hp == 30
    assert data.MASTERS[1].strength == 15
    assert data.MASTERS[1].defense == 2
    assert data.MASTERS[1].exp_reward == 100

    assert data.MASTERS[11].name == "Turgon"
    assert data.MASTERS[11].weapon == "Ables Sword"
    assert data.MASTERS[11].hp == 2500
    assert data.MASTERS[11].strength == 1200
    assert data.MASTERS[11].defense == 150
    assert data.MASTERS[11].exp_reward == 10000000


def test_masters_have_quote_fields():
    halder = data.MASTERS[1]
    assert halder.swear == "Belar!!! You are truly a great warrior!"
    assert "muscles" in halder.needstr1
    assert halder.death == "  You blew your master away!"


def test_monsters_grouped_by_level():
    assert set(data.MONSTERS.keys()) == set(range(1, 13))
    for level, monsters in data.MONSTERS.items():
        assert len(monsters) == 10, f"level {level} has {len(monsters)} monsters"

    level1_first = data.MONSTERS[1][0]
    assert level1_first.name == "Small Thief"
    assert level1_first.weapon == "Small Dagger"
    assert level1_first.strength == 6
    assert level1_first.hp == 9
    assert level1_first.gold == 56
    assert level1_first.exp == 2
    assert level1_first.death_phrase == "You disembowel the little thieving menace!"

    level12_last = data.MONSTERS[12][-1]
    assert level12_last.name == "Great Ogre Of The North"
    assert level12_last.strength == 1800
    assert level12_last.hp == 2878
    assert level12_last.gold == 524838
    assert level12_last.exp == 112833


def test_monster_has_no_defense_field():
    # lord.js monster_stats records never carry a `def` key (only masters do).
    assert "defense" not in data.Monster._fields
