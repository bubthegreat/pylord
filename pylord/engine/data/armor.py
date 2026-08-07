"""Armor shop table.

Transcribed from reference/lord.js:1397-1414 (`armour_stats`), then
**deliberately rebalanced** -- the powers and the tier 12-15 prices below
diverge from lord.js on purpose (DIFF), per
docs/superpowers/specs/2026-08-07-armor-rebalance-design.md:

* The original powers (1, 3, 10, 15, 25, 35, 50, 75, 100, 150, 225, 300,
  400, 600, 1000) left a player in level-appropriate armor near-certain to
  die to same-level forest monsters (a level-10 player in Full Body Armour
  faced ~26% death odds per fight), and made armor a worse deal per
  defense point than SunShines' Fairy Land's flat 35,000-gold price from
  tier 11 up. Powers are rescaled ~x2.5, with tiers 13-15 compressed so
  endgame armor blocks the Red Dragon's claws but never blunts its
  Flaming Breath.
* The original tier 12-15 prices (10M, 40M, 100M, 400M) are cut so every
  upgrade's net cost (price minus a half-price trade-in) stays under
  35,000 gold per defense point; tests/test_data.py locks that invariant.

`armour_stats[0]` ("Nothing!", price 0) is the unarmored placeholder
returned by `get_armour()` (lord.js:1837-1840) when `player.arm_num === 0`;
excluded from `ARMOR` for the same reason `weapon_stats[0]` is excluded
from `WEAPONS` (see weapons.py).

Semantics of the `num` field mirror weapons but apply to defense instead of
strength -- lord.js adds it directly onto `player.def`:

    player.def += newa.num;   // buy armor, lord.js:10424
    player.def -= olda.num;   // sell armor, lord.js:10499

We name that field `power` on `Item`, consistent with weapons.py.

The pre-rebalance powers also live, frozen, in pylord/data.py's
`_ARMOR_POWERS_V5`, which migrates old realms onto this curve. Rescaling
this table again means adding a new migration constant + version bump
there -- never editing the frozen one.
"""

from pylord.engine.data.weapons import Item

ARMOR: list[Item] = [
    Item(1, "Coat", 200, 3),
    Item(2, "Heavy Coat", 1000, 8),
    Item(3, "Leather Vest", 3000, 25),
    Item(4, "Bronze Armour", 10000, 38),
    Item(5, "Iron Armour", 30000, 63),
    Item(6, "Graphite Armour", 100000, 88),
    Item(7, "Erdricks Armour", 150000, 125),
    Item(8, "Armour Of Death", 200000, 188),
    Item(9, "Able's Armour", 400000, 250),
    Item(10, "Full Body Armour", 1000000, 375),
    Item(11, "Blood Armour", 4000000, 560),
    Item(12, "Magic Protection", 7000000, 750),
    Item(13, "Belars's Mail", 10000000, 950),
    Item(14, "Golden Armour", 11000000, 1150),
    Item(15, "Armour Of Lore", 12000000, 1350),
]


def armor(num: int) -> Item:
    """1-based lookup into ARMOR (num 1..15)."""
    if not 1 <= num <= len(ARMOR):
        raise ValueError(f"armor num out of range 1..{len(ARMOR)}: {num}")
    return ARMOR[num - 1]
