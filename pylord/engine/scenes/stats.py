"""Your Stats screen ('V' from the Town Square).

Ported from lord.js's ``show_stats()`` (``reference/lord.js:5824-5921``) for
the field subset this task covers -- name, level, exp, HP current/max,
forest/player fights remaining, gold in hand/bank, weapon, armor, charm,
gems, strength, defense (lines 5832-5840). lord.js additionally shows
marriage/kids/horse/fairy state, per-skill-track uses, and amulet status
(lines 5842-5919); those depend on fields/systems this task doesn't own
(marriage, skills UI, horse, fairy, amulet aren't modeled on ``Player``
beyond a couple of raw counters) and are left for whichever later task
introduces them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylord.engine import data
from pylord.engine.game import scene

if TYPE_CHECKING:
    from pylord.engine.game import GameCtx


def _weapon_name(weapon_num: int) -> str:
    # weapon_num 0 = unarmed; get_weapon() in lord.js (1842-1845) returns
    # the weapon_stats[0] placeholder ("Fists") rather than a real lookup.
    return "Fists" if weapon_num == 0 else data.weapon(weapon_num).name


def _armor_name(armor_num: int) -> str:
    # armor_num 0 = unarmored; mirrors get_armour() (lord.js:1837-1840).
    return "Nothing!" if armor_num == 0 else data.armor(armor_num).name


@scene("stats")
async def stats(ctx: GameCtx) -> str:
    p = ctx.player
    lines = [
        "",
        f"`%  {p.name}`2's Stats...",
        "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-",
        f"  `2Experience   : `0{p.exp}",
        f"`2  Level        : `0{p.level:<17} `2HitPoints          : `0{p.hp}`2 of `0{p.hp_max}",
        f"`2  Forest Fights: `0{p.forest_fights:<17} `2Player Fights Left : `0{p.player_fights}",
        f"`2  Gold In Hand : `0{p.gold:<17} `2Gold In Bank       : `0{p.bank}",
        f"`2  Weapon       : `0{_weapon_name(p.weapon_num):<17} `2Attack Strength    : `0{p.strength}",
        f"`2  Armour       : `0{_armor_name(p.armor_num):<17} `2Defensive Strength : `0{p.defense}",
        f"`2  Charm        : `0{p.charm:<17} `2Gems               : `0{p.gems}",
        "",
    ]
    await ctx.io.write("\n".join(lines) + "\n")
    await ctx.io.pause()
    return "town"
