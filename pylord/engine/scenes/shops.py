"""King Arthur's Weapons + Abdul's Armour -- buy/sell one weapon/armor at a
time, ported from ``reference/lord.js``'s ``king_arthurs()``
(``:10016-10301``) and ``abduls_armour()`` (``:10303-10577``).

Both shops share an identical shape (list items, buy one, sell the one you
have) so the two scene functions below are written in parallel rather than
sharing a generic helper -- the flavor text (NPC names/lines) differs enough
between "the fat man" (King Arthur's) and "the girl"/Paula (Abdul's) that a
single parametrized implementation would mostly be threading string
arguments through, at a real cost to readability. The handful of pieces that
really are identical formulas (the resale-price roll, the strength/defense
prerequisite sum, and the "read a 1-2 digit item number" prompt) are shared
via the small helpers at the top of the module.

Neither shop's original lord.js asset (``ARTHUR``/``BUYWEP``/``ABDUL``/
``BUYARM``, loaded via ``lrdfile()``) is present in this repo, so -- same
convention as ``town.py``'s own module docstring -- the item list below is
shown as a reconstructed numbered table every time the shop menu redraws
(matching what lord.js shows when ``!player.expert``, which is the only
mode this project models; there's no "expert" flag on ``Player``) rather
than only on a one-off `` `L`` -- ``ook`` press.

**Deviations** (also mirrored into ``docs/deviations.md``):

1. lord.js's `` `Y` ``/`` `V` `` in-shop key re-shows the player's full
   Stats screen without leaving the shop (``show_stats()``); this project
   drops it here -- the same "(V)iew your stats" is already one keypress
   away at the Town Square, and every other scene in this codebase (see
   ``forest.py``'s own `` `V` ``) already accepts that visiting stats mid
   errand bounces you back to town rather than back to the errand.
2. Strength/defense prerequisites (``str_needed()``/``def_needed()``,
   lord.js ``:10111-10128``/``:10331-10347``) are gated on
   ``settings.shop_limit`` (lord.js default ``true``, ``:1865``) -- ported
   here as ``ctx.config["game"]["shop_limit"]``, defaulting to ``True`` to
   match. Set it ``False`` in a session's config to disable the gate
   entirely, same as the original server setting.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from pylord.engine import data
from pylord.engine.game import scene

if TYPE_CHECKING:
    from pylord.engine.game import GameCtx
    from pylord.models import Player

_GOLD_CAP = 2_000_000_000
_STR_CAP = 32000  # reference/lord.js:10220-10222
_DEF_CAP = 32000  # reference/lord.js:10426-10428 ("DIFF: used to be 3200")

_DIGITS = "0123456789"


def _roll(rng: random.Random, n: int) -> int:
    """``random(n)`` port -- see combat.py's identical helper for why
    ``n <= 0`` is special-cased to 0 rather than raising."""
    return 0 if n <= 0 else rng.randrange(n)


async def _read_item_number(ctx: GameCtx, prompt: str) -> int:
    """``dk.console.getstr({len:2, integer:true})`` -> ``parseInt(...)`` port
    (weapon: lord.js:10147-10151, armor: lord.js:10367-10371). Non-numeric
    or empty input parses to 0 (lord.js's ``isNaN(n)`` guard)."""
    raw = await ctx.io.readline(prompt, maxlen=2, charset=_DIGITS)
    return int(raw) if raw else 0


def _need_sum(n: int, base: int, field: str, ctx: GameCtx) -> int:
    """Shared shape of ``str_needed()``/``def_needed()``
    (lord.js:10111-10128 / :10331-10347): both sum
    ``LEVEL_STATS[i].<field>`` for ``i`` in ``1..min(n-2, 11)`` on top of a
    per-shop ``base`` (10 for weapons, 0 for armor), gated on
    ``settings.shop_limit``."""
    # ctx.config *is* the [game] table -- pylord/server.py passes
    # config["game"] into GameCtx. Reading ctx.config["game"] here always
    # missed, so this knob could never be turned off.
    shop_limit = ctx.config.get("shop_limit", True)
    if not shop_limit:
        return 0
    if n < 3:
        return 0
    ret = base
    for i in range(1, min(n - 1, 12)):
        ret += getattr(data.LEVEL_STATS[i], field)
    return ret


def _sell_price(
    rng: random.Random, base_price: int, level: int, charm: int, *, weapon: bool
) -> int:
    """Shared resale-price roll. Weapon: lord.js:10066-10076. Armor:
    lord.js:10458-10468. The two conditions guarding which ``random(n)`` is
    rolled differ by an off-by-one in the original source (weapon: strict
    ``mult > 0 && mult < 65530`` else ``random(65535)``; armor: inclusive
    ``mult >= 0 && mult <= 65530`` else ``random(65530)``) -- ported exactly
    as written rather than unified, since it's an authentic quirk of the
    reference implementation, not a transcription choice made here."""
    mult = level * charm * level
    if weapon:
        roll = _roll(rng, mult) if 0 < mult < 65530 else _roll(rng, 65535)
    else:
        roll = _roll(rng, mult) if 0 <= mult <= 65530 else _roll(rng, 65530)
    price = base_price // 2 + roll
    if price > base_price - price / 3:
        price = base_price - base_price // 3
    return int(price)


async def _credit_gold(ctx: GameCtx, amount: int) -> None:
    """``player.gold += amount; if (player.gold > 2000000000) { ...cap +
    flavor line... }`` -- shared by both sell paths (weapon:
    lord.js:10099-10103, armor: lord.js:10494-10498)."""
    p = ctx.player
    new_gold = p.gold + amount
    if new_gold > _GOLD_CAP:
        p.gold = _GOLD_CAP
        await ctx.io.write("Wow, you have a lot of money!\n")
    else:
        p.gold = new_gold


def _weapon_name(p: Player) -> str:
    return "Fists" if p.weapon_num == 0 else data.weapon(p.weapon_num).name


def _armor_name(p: Player) -> str:
    return "Nothing!" if p.armor_num == 0 else data.armor(p.armor_num).name


# --- King Arthur's Weapons ----------------------------------------------


def _weapon_listing() -> str:
    lines = [
        f"  {i:>2}. {item.name:.<30}{item.price}"
        for i, item in enumerate(data.WEAPONS, start=1)
    ]
    return "\n".join(lines)


@scene("weapons")
async def weapons(ctx: GameCtx) -> str:
    while True:
        p = ctx.player
        await ctx.io.write(
            "\n`0  King Arthur's Weapons\n"
            "`2-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n\n"
            f"{_weapon_listing()}\n\n"
            f"  `2Current weapon: `0{_weapon_name(p)}\n"
            f"  `2Gold: `0{p.gold}\n\n"
        )
        choice = await ctx.io.menu(
            # Q also leaves, as it does in lord.js (:10281-10284).
            {"B": "buy", "S": "sell", "R": "town", "Q": "town"},
            "  `5King Arthur's Weapons `8(B,S,R)`2 : ",
        )
        if choice in ("R", "Q"):
            return "town"
        if choice == "B":
            await _buy_weapon(ctx)
        else:
            await _sell_weapon(ctx)


async def _buy_weapon(ctx: GameCtx) -> None:
    """Port of ``buy_weapon()``. reference/lord.js:10130-10225."""
    p = ctx.player
    await ctx.io.write("\n\n`2  (`0Gold: `%" + str(p.gold) + "`2)  (`00 to exit`2)\n")
    n = await _read_item_number(ctx, "  `0Number Of Weapon `2: `%")
    if not 1 <= n <= 15:
        return

    neww = data.weapon(n)
    old_power = data.weapon(p.weapon_num).power if p.weapon_num else 0
    need = _need_sum(n, 10, "strength", ctx)

    await ctx.io.write(
        f'\n\n  `2"`0Hmmm I will sell you my FAVORITE `%{neww.name}`0 for `%{neww.price} `0gold!`2"\n\n\n'
        f"  `2Note: It takes `%{need} `2strength points to weild this weapon.\n"
        f"  `2You currently have `%{p.strength - old_power} `2strength points.\n\n"
    )
    pressed = (await ctx.io.readkey()).upper()
    ich = "Y" if pressed == "Y" else "N"
    if ich == "N":
        await ctx.io.write(
            '\n  `2"`0Fine..You will come back...`2" the man grunts.\n\n'
        )
        await ctx.io.pause()
        return
    if p.strength < need:
        await ctx.io.write(
            "\n  `2\"`0You silly fool! You aren't strong enough to carry\n"
            '  that weapon!`2"\n\n'
        )
        await ctx.io.pause()
        return
    if p.weapon_num > 0:
        await ctx.io.write(
            "\n  `2\"`0You fool!  You already have a weapon, and you can't carry\n"
            '  two!`2"  You realize he is right.\n\n'
        )
        await ctx.io.pause()
        return
    if p.gold < neww.price:
        await ctx.io.write(
            "\n  `2\"`0You stupid fool!  You don't have that much gold!\n"
            '  I knew you were up to no good the moment I saw you!`2"\n\n\n'
        )
        await ctx.io.pause()
        return

    await ctx.io.write(
        '\n  `2"`0Great!`2" The fat man takes your money, and gives you the\n'
        "  weapon.\n\n"
    )
    p.weapon_num = n
    p.gold -= neww.price
    p.strength = min(p.strength + neww.power, _STR_CAP)
    await ctx.io.pause()


async def _sell_weapon(ctx: GameCtx) -> None:
    """Port of ``sell_weapon()``. reference/lord.js:10044-10109."""
    p = ctx.player
    await ctx.io.write("\n`c  `%King Arthurs Weapons\n`2-=-=-=-=-=-=-=-=-=-=-=-=-\n\n")
    if p.weapon_num == 0:
        await ctx.io.write(
            '  `2"`0What the...?!!`2" the stout man shouts. `2"`0You don\'t have\n'
            '  a weapon to sell!`2"\n\n\n'
        )
        await ctx.io.pause()
        return

    oldw = data.weapon(p.weapon_num)
    price = _sell_price(ctx.rng, oldw.price, p.level, p.charm, weapon=True)

    await ctx.io.write(
        f'  `2"`0Hmmm I will buy your `%{oldw.name}`0 for `%{price}`0, Agreed?`2"\n\n'
    )
    pressed = (await ctx.io.readkey()).upper()
    ich = "Y" if pressed == "Y" else "N"
    if ich != "Y":
        await ctx.io.write(
            "\n  `2\"`0You don't want to sell?!  Fine!  I don't want your stinken' weapon!`2\"\n\n"
        )
        await ctx.io.pause()
        return

    await ctx.io.write(
        '\n  `2"`0Great!`2" The fat man takes your weapon, and gives you the\n'
        "  money.\n\n"
    )
    p.weapon_num = 0
    await _credit_gold(ctx, price)
    p.strength = max(p.strength - oldw.power, 5)
    await ctx.io.pause()


# --- Abdul's Armour ------------------------------------------------------


def _armor_listing() -> str:
    lines = [
        f"  {i:>2}. {item.name:.<30}{item.price}"
        for i, item in enumerate(data.ARMOR, start=1)
    ]
    return "\n".join(lines)


@scene("armor")
async def armor(ctx: GameCtx) -> str:
    while True:
        p = ctx.player
        await ctx.io.write(
            "\n`0  Abdul's Armour Shop\n"
            "`2-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n\n"
            f"{_armor_listing()}\n\n"
            f"  `2Current armour: `0{_armor_name(p)}\n"
            f"  `2Gold: `0{p.gold}\n\n"
        )
        choice = await ctx.io.menu(
            # Q also leaves, as it does in lord.js (:10557-10560).
            {"B": "buy", "S": "sell", "R": "town", "Q": "town"},
            "  `5Abduls Armour `8(B,S,R)`2 : ",
        )
        if choice in ("R", "Q"):
            return "town"
        if choice == "B":
            await _buy_armor(ctx)
        else:
            await _sell_armor(ctx)


async def _buy_armor(ctx: GameCtx) -> None:
    """Port of ``buy_armour()``. reference/lord.js:10349-10433."""
    p = ctx.player
    await ctx.io.write("\n\n`2  (`0Gold: `%" + str(p.gold) + "`2)  (`00 to Exit`2) \n")
    n = await _read_item_number(ctx, "  `0Number Of Armour `2: `%")
    if not 1 <= n <= 15:
        return

    newa = data.armor(n)
    old_power = data.armor(p.armor_num).power if p.armor_num else 0
    need = _need_sum(n, 0, "defense", ctx)

    await ctx.io.write(
        f'\n\n  "`0Hmmm I will sell you a nice `%{newa.name}`0 for `%{newa.price}`0.\n'
        '   Agreed, friend?`2"\n\n\n'
        f"  Note: It takes `%{need}`2 defense points to wear this armor.\n"
        f"  `2You currently have `%{p.defense - old_power} `2defense points.\n\n"
    )
    pressed = (await ctx.io.readkey()).upper()
    ich = "Y" if pressed == "Y" else "N"

    if ich == "N":
        await ctx.io.write('\n`2  "`0Ok!  No rush!`2" the girl smiles.\n')
    elif p.defense < need:
        await ctx.io.write(
            "\n  `2\"`0I'm sorry, but you are not strong enough to wear\n"
            '  that armor.`2"\n'
        )
    elif p.armor_num > 0:
        await ctx.io.write(
            "\n  `2\"`0You already have armour, and you can't wear\n"
            '  two!`2" You realize she is right.\n'
        )
    elif p.gold < newa.price:
        await ctx.io.write(
            "\n  `2\"`0I'm sorry, but you seem to be lacking funds at the\n"
            '  moment.`2"  the girl tells you.\n'
        )
    else:
        await ctx.io.write(
            '\n  `2"`0Wonderful!`2" The girl takes your money, and helps you\n'
            "  into your new armour.\n"
        )
        p.armor_num = n
        p.gold -= newa.price
        p.defense = min(p.defense + newa.power, _DEF_CAP)
    await ctx.io.pause()


async def _sell_armor(ctx: GameCtx) -> None:
    """Port of ``sell_armour()``. reference/lord.js:10435-10504."""
    p = ctx.player
    await ctx.io.write(
        "\n`0  Abdul's Armour Shop\n"
        "`2-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n\n"
    )
    if p.armor_num == 0:
        await ctx.io.write(
            '  `2"`0You silly kidder!!`2" Paula laughs, "`0You don\'t have\n'
            '  any armour to sell!`2"  \n\n\n'
        )
        await ctx.io.pause()
        return

    olda = data.armor(p.armor_num)
    price = _sell_price(ctx.rng, olda.price, p.level, p.charm, weapon=False)

    await ctx.io.write(
        f'  `2"`0Hmmm I will buy your `%{olda.name} `0for `%{price}`0 gold.\n'
        '  Agreed, friend?`2"\n\n'
    )
    pressed = (await ctx.io.readkey()).upper()
    ich = "Y" if pressed == "Y" else "N"
    if ich == "N":
        await ctx.io.write(
            '\n  `2"`0Thats ok.  Your armour probably has sentimental value to you.`2"\n'
        )
        return

    await ctx.io.write(
        '\n  `2"`0Good doing business with you!`2" The girl takes your armour\n'
        "  and gives you the money.\n"
    )
    p.armor_num = 0
    await _credit_gold(ctx, price)
    p.defense = max(p.defense - olda.power, 0)
    await ctx.io.pause()
