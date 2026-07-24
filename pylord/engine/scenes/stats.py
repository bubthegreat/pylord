"""Your Stats screen ('V' from the Town Square).

Full port of lord.js's ``show_stats()`` (``reference/lord.js:5824-5921``):
the stat block (lines 5832-5840), then marriage (to Violet, to Seth Able,
or to another player -- :5843-5857), children (:5858-5866), horseback
(:5867-5869), the fairy in your pocket (:5870-5872), the per-class skill
rank and uses-today lines (:5873-5903), the class-interest line
(:5904-5915) and the Amulet of Accuracy (:5916-5919).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylord.engine import data, npc_state
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


# reference/lord.js:5873-5903 -- rank field, mastery threshold display,
# and the label lord.js prints for each track.
_SKILL_TRACKS = (
    ("skill_dk", "Death Knight Skills"),
    ("skill_my", "The Mystical Skills"),
    ("skill_th", "The Thieving Skills"),
)

# reference/lord.js:5904-5915.
_CLASS_INTEREST = {
    1: "`%Death Knight`0",
    2: "`%The Mystical`0",
    3: "`%The Thieving`0",
}


def _skill_lines(p) -> list[str]:
    """The per-track "rank / Uses Today" block. A track appears once the
    player has rank in it or uses left for it (reference/lord.js:5873,
    5884, 5895); rank 40+ reads MASTERED rather than a number.

    lord.js has one daily counter per track; this project has a single
    shared ``skill_uses`` (see ``pylord/engine/scenes/forest.py``'s module
    docstring), which belongs to whichever class the player currently
    is -- the other tracks show 0 uses today.
    """
    out = []
    for index, (field, label) in enumerate(_SKILL_TRACKS, start=1):
        rank = getattr(p, field)
        uses = p.skill_uses if index == p.class_type else 0
        if rank <= 0 and uses <= 0:
            continue
        if rank >= 40:
            shown = "MASTERED   "
        elif rank > 0:
            shown = f"{rank:<11}"
        else:
            shown = "NONE       "
        out.append(f"`2  {label}: `0{shown}`2 Uses Today: (`0{uses}`2)")
    return out


def _marriage_lines(ctx: GameCtx) -> list[str]:
    """reference/lord.js:5843-5857 -- the NPC marriages live in shared
    game state, a player-to-player one on the player's own record."""
    p = ctx.player
    out = []
    if npc_state.married_to_violet(ctx.conn) == p.id:
        out.append("  `2You are married to `#Violet`2.")
    if npc_state.married_to_seth(ctx.conn) == p.id:
        out.append("  `2You are married to `%Seth Able`2.")
    if p.married_to is not None and p.married_to > -1:
        spouse = ctx.repo.get(p.married_to)
        if spouse is not None:
            out.append(f"  `2You are married to `%{spouse.name}`2.")
    return out


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
    lines.extend(_marriage_lines(ctx))
    if p.kids == 1:  # reference/lord.js:5858-5861
        lines.append("  `2You have `01`2 child.")
    elif p.kids > 1:  # reference/lord.js:5862-5866
        lines.append(f"  `2You have `0{p.kids}`2 children.")
    if p.horse:  # reference/lord.js:5867-5869
        lines.append("  `2You are on `%horseback`2.")
    if p.has_fairy:  # reference/lord.js:5870-5872
        lines.append("  `2You have a `#fairy`2 in your pocket.")
    lines.extend(_skill_lines(p))
    interest = _CLASS_INTEREST.get(p.class_type)
    if interest is not None:  # reference/lord.js:5904-5915
        lines.append(f"  `0You are currently interested in {interest} skills.")
    if p.amulet:  # reference/lord.js:5916-5919
        lines.append("  `2You are wearing an `%Amulet of Accuracy`2.")
    lines.append("")
    await ctx.io.write("\n".join(lines) + "\n")
    await ctx.io.pause()
    return "town"
