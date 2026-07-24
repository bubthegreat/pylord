"""The Apothecary -- potions and tonics, paid for in gems.

Wave-2 IGM. The classic LORD IGM catalogue is a list of separate DOS
executables whose source is lost; `reference/lord.js` models the base game
only and never an IGM's internals. So, exactly like the starter six, this
is a **recreation from the historical premise** (a shop that sells healing
and small blessings for gems), not a port. Everything below is invented:

* the three wares and their prices,
* the tonic granting a forest fight (which leans on this project's own
  trainable-fight system, `pylord/engine/fights.py`),
* the once-a-day limit on the tonic.

Gems are the currency because the base game gives players almost nothing to
spend them on -- Violet's dress and the Inn's elixirs -- so an apothecary is
where a gem hoard finally becomes useful.
"""

from __future__ import annotations

from pylord.engine import fights
from pylord.hooks import IGM, IgmContext, IgmMaintContext

_MENU = (
    "\n  `5The Apothecary`2\n"
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
    "  `2(`0S`2)alve of mending     `%2 gems`2   -- heal every wound\n"
    "  `2(`0T`2)onic of vigour      `%3 gems`2   -- one more forest fight today\n"
    "  `2(`0C`2)harm philtre        `%5 gems`2   -- a little more charming\n"
    "  `2(`0L`2)eave\n"
)

SALVE_COST = 2
TONIC_COST = 3
PHILTRE_COST = 5


class Apothecary(IGM):
    key = "apothecary"
    name = "The Apothecary"
    author = "pylord (recreation)"
    default_enabled = False

    async def enter(self, ctx: IgmContext) -> None:
        await ctx.term.write(
            "\n  `2Bottles line every shelf, and something green bubbles in the\n"
            "  corner.  The apothecary peers at you over her spectacles.\n"
        )
        while True:
            p = ctx.player
            await ctx.term.write(_MENU)
            await ctx.term.write(f"  `2You carry `%{p.gems}`2 gems.\n\n")
            choice = await ctx.term.menu(
                {"S": "salve", "T": "tonic", "C": "philtre", "L": "leave"},
                "  `2Your choice? [`0L`2] : `%",
            )
            if choice == "L":
                await ctx.term.write(
                    '\n  `0"Mind how you go,"`2 she says, already turning away.\n'
                )
                return
            if choice == "S":
                await self._salve(ctx)
            elif choice == "T":
                await self._tonic(ctx)
            else:
                await self._philtre(ctx)

    async def _afford(self, ctx: IgmContext, cost: int) -> bool:
        if ctx.player.gems < cost:
            await ctx.term.write(
                f'\n  `0"That will be {cost} gems, dear.  Come back when you have them."`2\n'
            )
            await ctx.term.pause()
            return False
        ctx.player.gems -= cost
        return True

    async def _salve(self, ctx: IgmContext) -> None:
        p = ctx.player
        if p.hp >= p.hp_max:
            await ctx.term.write(
                '\n  `0"You have not got a scratch on you.  Save your gems."`2\n'
            )
            await ctx.term.pause()
            return
        if not await self._afford(ctx, SALVE_COST):
            return
        p.hp = p.hp_max
        await ctx.term.write(
            "\n  `2The salve is cold and smells of pine.  Your wounds close over.\n"
            "  `%YOU ARE FULLY HEALED.`2\n"
        )
        await ctx.term.pause()

    async def _tonic(self, ctx: IgmContext) -> None:
        """One per day: the flag is cleared by ``daily_maint``."""
        p = ctx.player
        gate = f"tonic:{p.id}"
        if ctx.store.get(gate, False):
            await ctx.term.write(
                '\n  `0"Another today would do you harm.  Tomorrow."`2\n'
            )
            await ctx.term.pause()
            return
        if p.forest_fights >= fights.max_forest_fights(p):
            await ctx.term.write(
                '\n  `0"You are already fit for a full day\'s hunting."`2\n'
            )
            await ctx.term.pause()
            return
        if not await self._afford(ctx, TONIC_COST):
            return
        ctx.store.set(gate, True)
        p.forest_fights += 1
        await ctx.term.write(
            "\n  `2It burns going down, and your legs stop aching.\n"
            "  `%ONE MORE TRIP INTO THE FOREST TODAY.`2\n"
        )
        await ctx.term.pause()

    async def _philtre(self, ctx: IgmContext) -> None:
        if not await self._afford(ctx, PHILTRE_COST):
            return
        ctx.player.charm += 1
        await ctx.term.write(
            "\n  `2You dab it behind each ear.  It smells faintly of rain.\n"
            "  `%YOU FEEL MORE CHARMING.`2\n"
        )
        await ctx.term.pause()

    async def daily_maint(self, ctx: IgmMaintContext) -> None:
        for player in ctx.repo.all_players():
            ctx.store.delete(f"tonic:{player.id}")
