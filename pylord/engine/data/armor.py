"""Armor shop table, transcribed from reference/lord.js:1397-1414.

lord.js source (`armour_stats`)::

    var armour_stats = [
        {name:'Nothing!', price:0, num:0},
        {name:'Coat', price:200, num:1},
        {name:'Heavy Coat', price:1000, num:3},
        ...
        {name:'Armour Of Lore', price:400000000, num:1000}
    ];

`armour_stats[0]` ("Nothing!", price 0) is the unarmored placeholder
returned by `get_armour()` (lord.js:1837-1840) when `player.arm_num === 0`;
excluded from `ARMOR` for the same reason `weapon_stats[0]` is excluded
from `WEAPONS` (see weapons.py).

Semantics of the `num` field mirror weapons but apply to defense instead of
strength — lord.js adds it directly onto `player.def`:

    player.def += newa.num;   // buy armor, lord.js:10424
    player.def -= olda.num;   // sell armor, lord.js:10499

We name that field `power` on `Item`, consistent with weapons.py.
"""

from pylord.engine.data.weapons import Item

ARMOR: list[Item] = [
    Item(1, "Coat", 200, 1),
    Item(2, "Heavy Coat", 1000, 3),
    Item(3, "Leather Vest", 3000, 10),
    Item(4, "Bronze Armour", 10000, 15),
    Item(5, "Iron Armour", 30000, 25),
    Item(6, "Graphite Armour", 100000, 35),
    Item(7, "Erdricks Armour", 150000, 50),
    Item(8, "Armour Of Death", 200000, 75),
    Item(9, "Able's Armour", 400000, 100),
    Item(10, "Full Body Armour", 1000000, 150),
    Item(11, "Blood Armour", 4000000, 225),
    Item(12, "Magic Protection", 10000000, 300),
    Item(13, "Belars's Mail", 40000000, 400),
    Item(14, "Golden Armour", 100000000, 600),
    Item(15, "Armour Of Lore", 400000000, 1000),
]


def armor(num: int) -> Item:
    """1-based lookup into ARMOR (num 1..15)."""
    if not 1 <= num <= len(ARMOR):
        raise ValueError(f"armor num out of range 1..{len(ARMOR)}: {num}")
    return ARMOR[num - 1]
