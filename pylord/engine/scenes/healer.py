"""The Healers -- port of ``reference/lord.js``'s ``healers()``
(``:10797-10974``).

Cost formula: 5 gold per hitpoint, scaled by level (``5 * player.level`` per
HP, lord.js:10820, 10863, 10933). `` `H` `` (heal all) heals fully if you can
afford it, otherwise heals as many points as you *can* afford (a partial
heal, still costing the same per-HP rate) -- lord.js:10801-10848. `` `C` ``
(heal some) lets you name an exact amount, refusing an over-heal or a
purchase you can't afford -- lord.js:10850-10889.

**Deviation** (mirrored into ``docs/deviations.md``): reachable from both
the Town Square (`H`) and the Forest (`H`); this scene always returns
``"town"`` regardless of which one sent the player here, the same
simplification already established by ``stats.py`` (see
``forest.py``'s own module docstring / ``docs/deviations.md`` row on
`` `V`iew your stats`` from the Forest). lord.js's real ``healers()`` has no
such ambiguity -- it's simply a function call that returns to whichever
screen called it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylord.engine.game import scene

if TYPE_CHECKING:
    from pylord.engine.game import GameCtx

_DIGITS = "0123456789"

_HEADER = "\n\n  `%Healers`#\n`2-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n\n"


def _cost_per_hp(p) -> int:
    return 5 * p.level  # reference/lord.js:10863 etc.


@scene("healer")
async def healer(ctx: GameCtx) -> str:
    p = ctx.player
    if p.hp < 0:  # reference/lord.js:10891-10894
        p.hp = 1

    if p.hp >= p.hp_max:  # reference/lord.js:10903 ("DIFF: was just ===")
        await ctx.io.write(
            _HEADER + '  `4`0"You look fine to us!"`2 the healers tell you.\n\n'
        )
        await ctx.io.pause()
        return "town"

    while True:
        await ctx.io.write(
            f"\n  `3`2HitPoints: (`0{p.hp} `2of`0 {p.hp_max}`2)\n"
            f"  `2Gold: `0{p.gold}\n"
            f"  `2(it costs `%{_cost_per_hp(p)}`2 to heal 1 hitpoint)\n\n"
        )
        choice = await ctx.io.menu(
            {"H": "heal_all", "C": "heal_some", "R": "town"},
            "  `5The Healers`2   (H,C,R)`2 : ",
        )
        if choice == "R":
            return "town"
        if choice == "H":
            if await _heal_all(ctx):
                return "town"
        else:
            await _heal_some(ctx)


async def _heal_all(ctx: GameCtx) -> bool:
    """Port of ``heal_all()``. reference/lord.js:10801-10848.

    Returns ``True`` only when the *full* heal-at-full-price branch fires
    (matching lord.js's ``ret`` -- the caller then leaves the Healers
    entirely, same as ``if (heal_all()) { return; }``); a partial heal (or
    "you look fine") leaves the loop running.
    """
    p = ctx.player
    if p.hp >= p.hp_max:
        await ctx.io.write('\n  `0"You look fine to us!"\n\n')
        await ctx.io.pause()
        return False

    per_hp = _cost_per_hp(p)
    need = p.hp_max - p.hp
    afford = p.gold // per_hp  # parseInt(player.gold / 5 / player.level, 10)

    if p.gold >= need * per_hp:
        p.hp += need
        await ctx.io.write(
            f"\n   `0{need}`2 hit points are healed and you feel much better.\n\n"
        )
        p.gold -= need * per_hp
        ret = True
    elif afford < need:
        p.hp += afford
        await ctx.io.write(
            f"\n  `0{afford}`2 hit points are healed and you feel much better.\n\n"
        )
        p.gold -= afford * per_hp
        ret = False
    else:  # pragma: no cover -- unreachable, see _sell_price-style note below
        # afford >= need implies gold >= need*per_hp (floor division), so
        # this branch mirrors lord.js's own (equally unreachable) implicit
        # "neither condition" fallthrough -- kept for structural fidelity.
        ret = False

    await ctx.io.pause()
    return ret


async def _heal_some(ctx: GameCtx) -> None:
    """Port of ``heal_some()``. reference/lord.js:10850-10889."""
    p = ctx.player
    await ctx.io.write('  "How many hit points would you like healed?"\n')
    raw = await ctx.io.readline("  `0AMOUNT : `%", maxlen=5, charset=_DIGITS)
    amt = int(raw) if raw else 0

    if amt == 0:
        await ctx.io.write('\n  "Maybe some other time.."\n')
        return
    if amt < 0:  # pragma: no cover -- digit-only charset can't type '-'
        await ctx.io.write('\n  "Uh...Wouldn\'t that be hurting yourself?!"\n')
        return

    per_hp = _cost_per_hp(p)
    if amt * per_hp > p.gold:
        await ctx.io.write(
            "\n  \"I'm afraid you don't have enough gold to cover that.\"\n"
        )
    elif amt > (p.hp_max - p.hp):
        await ctx.io.write('\n  "It would be deadly to over heal yourself!!"\n')
    else:
        await ctx.io.write("\n  Done!\n")
        p.gold -= amt * per_hp
        p.hp += amt
