"""The Old Skull Inn -- the rough house on the edge of town.

Wave-2 IGM, recreated from the premise (a second, seedier inn) rather than
ported: no source survives for the original binary. Invented here: the
rumours, the arm-wrestling odds and stake, and the cheap bed.

The bed deliberately does *not* set ``at_inn`` -- that flag is the base
game's "asleep at the Red Dragon Inn, and therefore attackable" state
(``pylord/engine/scenes/pvp.py``). Sleeping here is just a cheap heal; a
player who wants the real inn's protection can go and pay for it.
"""

from __future__ import annotations

from pylord.hooks import IGM, IgmContext, IgmMaintContext

BED_COST_PER_LEVEL = 60
#: Stake for a round of arm wrestling, and what you win if you take it.
WRESTLE_STAKE = 250
#: The house arm is this much stronger than an even match.
WRESTLE_EDGE = 5

_MENU = (
    "\n  `5The Old Skull Inn`2\n"
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
    "  `2(`0T`2)alk to the regulars   (`0A`2)rm wrestle the barman\n"
    "  `2(`0B`2)ed for the night      (`0L`2)eave\n"
)

# Invented flavour -- no transcript survives.
_RUMOURS = (
    '`0"The dragon? Killed him twice myself. Third time he got clever."',
    '`0"Turgon charges for lessons. The forest teaches free, if you live."',
    '`0"Violet is out of your league, friend. She is out of everyone\'s."',
    '`0"Man came through with a sack of gems. Left with a sack of nothing."',
    '`0"Sleep here if you like. Nobody looks for you at the Old Skull."',
)


class OldSkullInn(IGM):
    key = "old_skull_inn"
    name = "The Old Skull Inn"
    author = "pylord (recreation)"
    default_enabled = False

    async def enter(self, ctx: IgmContext) -> None:
        await ctx.term.write(
            "\n  `2Low ceiling, low company.  A skull over the bar holds a candle,\n"
            "  and the barman does not stop cleaning the same glass.\n"
        )
        while True:
            await ctx.term.write(_MENU)
            choice = await ctx.term.menu(
                {"T": "talk", "A": "wrestle", "B": "bed", "L": "leave"},
                "  `2Your choice? [`0L`2] : `%",
            )
            if choice == "L":
                await ctx.term.write("\n  `2You duck back out into cleaner air.\n")
                return
            if choice == "T":
                await ctx.term.write(
                    f"\n  {_RUMOURS[ctx.rng.randrange(len(_RUMOURS))]}`2\n"
                )
                await ctx.term.pause()
            elif choice == "A":
                await self._wrestle(ctx)
            else:
                await self._bed(ctx)

    async def _wrestle(self, ctx: IgmContext) -> None:
        p = ctx.player
        if p.gold < WRESTLE_STAKE:
            await ctx.term.write(
                f'\n  `0"Stake is {WRESTLE_STAKE} gold. Come back richer."`2\n'
            )
            await ctx.term.pause()
            return
        await ctx.term.write(
            f"\n  `2The barman sets his elbow on the bar.  `%{WRESTLE_STAKE}`2 gold "
            "a round.\n"
        )
        if await ctx.term.menu(
            {"Y": "yes", "N": "no"}, "  `2Take him on? [`0N`2] : `%"
        ) == "N":
            return

        p.gold -= WRESTLE_STAKE
        # Strength decides it, but the house arm gets an edge and the roll
        # can still surprise either of them.
        mine = ctx.rng.randrange(max(1, p.strength))
        his = ctx.rng.randrange(max(1, p.strength + WRESTLE_EDGE))
        if mine >= his:
            p.gold += WRESTLE_STAKE * 2
            await ctx.term.write(
                "\n  `2His knuckles crack against the bar.  The room goes quiet,\n"
                f"  then roars.  `%YOU WIN {WRESTLE_STAKE} GOLD.`2\n"
            )
            ctx.news(f"`0{p.name} `2out-wrestled the barman at the Old Skull Inn!")
        else:
            await ctx.term.write(
                "\n  `2Your arm goes down slowly, which is somehow worse.\n"
                f"  `4YOU LOSE {WRESTLE_STAKE} GOLD.`2\n"
            )
        await ctx.term.pause()

    async def _bed(self, ctx: IgmContext) -> None:
        """A cheap heal. Once a night, and it does not make you attackable."""
        p = ctx.player
        gate = f"bed:{p.id}"
        if ctx.store.get(gate, False):
            await ctx.term.write(
                '\n  `0"One night, one bed. You have had yours."`2\n'
            )
            await ctx.term.pause()
            return
        cost = BED_COST_PER_LEVEL * p.level
        if p.gold < cost:
            await ctx.term.write(f'\n  `0"Bed is {cost} gold."`2 You count again.\n')
            await ctx.term.pause()
            return
        if p.hp >= p.hp_max:
            await ctx.term.write(
                '\n  `0"You do not look like a man who needs a rest."`2\n'
            )
            await ctx.term.pause()
            return
        p.gold -= cost
        ctx.store.set(gate, True)
        p.hp = p.hp_max
        await ctx.term.write(
            "\n  `2The mattress is straw and the blanket has a history, but you\n"
            "  wake without pain.  `%YOU ARE FULLY HEALED.`2\n"
        )
        await ctx.term.pause()

    async def daily_maint(self, ctx: IgmMaintContext) -> None:
        for player in ctx.repo.all_players():
            ctx.store.delete(f"bed:{player.id}")
