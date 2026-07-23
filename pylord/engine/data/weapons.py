"""Weapon shop table, transcribed from reference/lord.js:1416-1433.

lord.js source (`weapon_stats`)::

    var weapon_stats = [
        {name:'Fists', price:0, num:0},
        {name:'Stick', price:200, num:5},
        {name:'Dagger', price:1000, num:10},
        ...
        {name:'Death Sword', price:400000000, num:1800}
    ];

`weapon_stats[0]` ("Fists", price 0) is the unarmed placeholder returned by
`get_weapon()` (lord.js:1842-1845, via `get_armourweap()` at 1783-1808) when
a player has no weapon equipped (`player.weapon_num === 0`). It is not one
of the 15 purchasable items, so it is intentionally excluded from `WEAPONS`.

Semantics of the `num` field: it is *not* a display index. lord.js adds it
directly onto `player.str` when the weapon is equipped/unequipped:

    player.str += neww.num;   // buy_weapon, lord.js:10219
    player.str -= oldw.num;   // sell_weapon, lord.js:10104

i.e. it's a flat strength bonus granted while wielding the weapon. We name
that field `power` on `Item`.
"""

from collections import namedtuple

Item = namedtuple("Item", "num name price power")

WEAPONS: list[Item] = [
    Item(1, "Stick", 200, 5),
    Item(2, "Dagger", 1000, 10),
    Item(3, "Short Sword", 3000, 20),
    Item(4, "Long Sword", 10000, 30),
    Item(5, "Huge Axe", 30000, 40),
    Item(6, "Bone Cruncher", 100000, 60),
    Item(7, "Twin Swords", 150000, 80),
    Item(8, "Power Axe", 200000, 120),
    Item(9, "Able's Sword", 400000, 180),
    Item(10, "Wans' Weapon", 1000000, 250),
    Item(11, "Spear of Gold", 4000000, 350),
    Item(12, "Crystal Shard", 10000000, 500),
    Item(13, "Nira's Teeth", 40000000, 800),
    Item(14, "Blood Sword", 100000000, 1200),
    Item(15, "Death Sword", 400000000, 1800),
]


def weapon(num: int) -> Item:
    """1-based lookup into WEAPONS (num 1..15)."""
    if not 1 <= num <= len(WEAPONS):
        raise ValueError(f"weapon num out of range 1..{len(WEAPONS)}: {num}")
    return WEAPONS[num - 1]
