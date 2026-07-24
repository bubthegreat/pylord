"""Ye Old Bank -- port of ``reference/lord.js``'s ``ye_old_bank()``
(``:15886-16161``), Withdraw/Deposit only.

**Deviations** (mirrored into ``docs/deviations.md``):

1. **No transfer (`T`)**: lord.js's transfer sends gold to *another*
   player's account (``find_player()``/``mail_to()``, lord.js
   :16019-16097) -- a PvP-adjacent, multiplayer-mail feature this task's
   brief explicitly defers ("that's PvP-adjacent, defer to Task 13").
2. **No thief "steal from the bank" (`2`)**: gated on
   ``player.clss === 3 && player.has_fairy`` (lord.js:16119-16153) -- the
   thief-class fairy-capture flag isn't modeled anywhere on this project's
   ``Player`` (see ``forest.py``'s own fairy-event deviation note); there is
   no robbery-*of-another-player* mechanic anywhere in ``ye_old_bank()`` at
   all (searched), so this is the entirety of what "robbery" means in this
   function, and it's out of scope for the reason above, not because it's
   PvP.
3. **No "leaving the bank" Amulet random event** (lord.js:16162-16220,
   after the main loop exits) -- depends on ``player.amulet``, a field with
   no equivalent in this project's ``Player`` model (``combat.py``'s module
   docstring already notes amulet handling is out of scope project-wide).

Deposit/withdraw formulas: `` `1` `` typed as the amount means "all of it"
(lord.js:15940-15942, :15986-15988); both directions cap the *destination*
pile at 2,000,000,000 by clamping the requested amount down, not by
rejecting the transaction (lord.js:15943-15945, :15989-15991).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylord.engine.game import scene

if TYPE_CHECKING:
    from pylord.engine.game import GameCtx

_CAP = 2_000_000_000
_DIGITS = "0123456789"


def _pronoun(p) -> str:
    return "sir." if p.gender == "M" else "ma'am."


@scene("bank")
async def bank(ctx: GameCtx) -> str:
    while True:
        p = ctx.player
        await ctx.io.write(
            f"\n  `2Gold In Hand: `0{p.gold}\n  `2Gold In Bank: `0{p.bank}\n"
        )
        choice = await ctx.io.menu(
            {"W": "withdraw", "D": "deposit", "R": "town"},
            "  `5The Bank `8(W,D,R)`2 : ",
        )
        if choice == "R":
            return "town"
        if choice == "W":
            await _withdraw(ctx)
        else:
            await _deposit(ctx)


async def _withdraw(ctx: GameCtx) -> None:
    """Port of the `W` case. reference/lord.js:15921-15967."""
    p = ctx.player
    await ctx.io.write(
        '\n  `2"How much gold would you like to\n  withdraw?" `0(1 for ALL of it)\n\n'
    )
    raw = await ctx.io.readline("  `0AMOUNT : ", maxlen=11, charset=_DIGITS)
    amt = int(raw) if raw else 0
    if amt == 1:
        amt = p.bank
    if p.gold + amt > _CAP:
        amt = _CAP - p.gold

    if amt == 0:
        await ctx.io.write('\n  "Okay. Maybe another time."\n')
    elif amt < 0:  # pragma: no cover -- digit-only charset can't type '-'
        await ctx.io.write('\n  "Uh...Wouldn\'t that be depositing?!"\n')
    elif amt > p.bank:
        await ctx.io.write(
            "\n  \"I'm afraid you don't have that much in your account, \n"
            f"  {_pronoun(p)}\n"
        )
    else:
        await ctx.io.write(f"\n  Done! {amt} withdrawn.\n")
        p.bank -= amt
        p.gold += amt


async def _deposit(ctx: GameCtx) -> None:
    """Port of the `D` case. reference/lord.js:15968-16018."""
    p = ctx.player
    await ctx.io.write(
        '\n  `2"How much gold would you like to\n  deposit?" `0(1 for ALL of it)\n\n'
    )
    raw = await ctx.io.readline("  `0AMOUNT: ", maxlen=11, charset=_DIGITS)
    amt = int(raw) if raw else 0
    if amt == 1:
        amt = p.gold
    if p.bank + amt > _CAP:
        amt = _CAP - p.bank

    if amt == 0:
        await ctx.io.write('\n  "Okay. Maybe another time."\n')
    elif amt < 0:  # pragma: no cover -- digit-only charset can't type '-'
        await ctx.io.write('\n  "Uh...Wouldn\'t that be withdrawing?!"\n')
    elif amt > p.gold:
        await ctx.io.write(
            f"\n  \"I'm afraid you don't have that much on you, \n  {_pronoun(p)}\n"
        )
    elif p.bank >= _CAP:  # pragma: no cover -- unreachable, see note below
        # The clamp above already forces amt == 0 (hitting the branch
        # above) whenever bank is already at the cap -- lord.js's own
        # equivalent branch (:16005-16009) is equally dead code in
        # practice. Kept for structural fidelity with the source.
        p.bank = _CAP
        await ctx.io.write(
            "\n  \"I'm sorry, but we can only keep 2,000,000,000 gold at a time. \n"
        )
    else:
        await ctx.io.write(f"\n  Done! {amt} deposited.\n")
        p.gold -= amt
        p.bank += amt
