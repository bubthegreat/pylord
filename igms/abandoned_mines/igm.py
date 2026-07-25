"""The Abandoned Mines -- dig for gems, and hope the roof holds.

Wave-2 IGM, recreated from the premise; no source survives for the original
binary and `reference/lord.js` never modelled an IGM's internals. Invented:
the two shafts, their odds, the payouts and the cave-in damage.

The shallow workings are safe and stingy. The deep shaft pays better and
can hurt you, and you may only try it once a day -- the pick is the same,
what changes is how far in you are willing to go.
"""

from __future__ import annotations

from pylord.hooks import IGM, IgmContext, IgmMaintContext

SHALLOW_GOLD = (20, 120)
DEEP_GOLD = (200, 900)
#: Deep-shaft chance (1 in N) of each: a gem, and a cave-in.
DEEP_GEM_ODDS = 3
DEEP_CAVEIN_ODDS = 4
CAVEIN_DAMAGE = (5, 25)

_MENU = (
    "\n  `5The Abandoned Mines`2\n"
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
    "  `2(`0S`2)ift the shallow workings   -- safe, and poor\n"
    "  `2(`0D`2)elve the deep shaft        -- once a day, and it bites\n"
    "  `2(`0L`2)eave\n"
)


class AbandonedMines(IGM):
    key = "abandoned_mines"
    name = "The Abandoned Mines"
    author = "pylord (recreation)"
    default_enabled = False

    async def enter(self, ctx: IgmContext) -> None:
        await ctx.term.write(
            "\n  `2Rotten props, a cold draught, and somewhere below, water.\n"
            "  Somebody left a pick by the entrance.  It is not new.\n"
        )
        while True:
            await ctx.term.write(_MENU)
            choice = await ctx.term.menu(
                {"S": "shallow", "D": "deep", "L": "leave"},
                "  `2Your choice? [`0L`2] : `%",
            )
            if choice == "L":
                await ctx.term.write("\n  `2You leave the dark to itself.\n")
                return
            if choice == "S":
                await self._shallow(ctx)
            else:
                await self._deep(ctx)

    async def _shallow(self, ctx: IgmContext) -> None:
        p = ctx.player
        gold = ctx.rng.randrange(SHALLOW_GOLD[0], SHALLOW_GOLD[1] + 1)
        p.gold += gold
        await ctx.term.write(
            "\n  `2You pick over the spoil heaps by the entrance for an hour.\n"
            f"  `%YOU FIND {gold} GOLD.`2\n"
        )
        await ctx.term.pause()

    async def _deep(self, ctx: IgmContext) -> None:
        p = ctx.player
        gate = f"deep:{p.id}"
        if ctx.store.get(gate, False):
            await ctx.term.write(
                "\n  `2You have been down once today.  Your hands are shaking\n"
                "  and the props are creaking.  Not again.\n"
            )
            await ctx.term.pause()
            return
        ctx.store.set(gate, True)

        gold = ctx.rng.randrange(DEEP_GOLD[0], DEEP_GOLD[1] + 1)
        p.gold += gold
        lines = [
            "\n  `2You follow the shaft down until the daylight is a coin behind you.\n",
            f"  `%YOU FIND {gold} GOLD.`2\n",
        ]
        if ctx.rng.randrange(DEEP_GEM_ODDS) == 0:
            p.gems += 1
            lines.append("  `%AND A GEM, WINKING IN THE LAMPLIGHT.`2\n")
        if ctx.rng.randrange(DEEP_CAVEIN_ODDS) == 0:
            hurt = ctx.rng.randrange(CAVEIN_DAMAGE[0], CAVEIN_DAMAGE[1] + 1)
            p.hp = max(1, p.hp - hurt)  # the mines take a toll, never a life
            lines.append(
                "\n  `4The roof comes down behind you.  You crawl out coughing.\n"
                f"  YOU LOSE {hurt} HITPOINTS.`2\n"
            )
        await ctx.term.write("".join(lines))
        await ctx.term.pause()

    async def daily_maint(self, ctx: IgmMaintContext) -> None:
        for player in ctx.repo.all_players():
            ctx.store.delete(f"deep:{player.id}")
