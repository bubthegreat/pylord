"""The Latrine -- exactly what it sounds like, and a wall to write on.

Wave-2 IGM. The original was a joke IGM; nothing of it survives to port, so
the outcomes, odds and every line of flavour here are invented.

The wall is the interesting half: it is a shared, persistent scrawl board in
``ctx.store``, so what one player writes the next one reads. Entries are
capped in number and length, and attributed, because an anonymous unbounded
text box in a game is an invitation.
"""

from __future__ import annotations

from pylord.hooks import IGM, IgmContext

WALL_KEY = "wall"
WALL_MAX = 15
LINE_MAXLEN = 60
FIND_ODDS = (0, 1, 2, 3)  # gold / gem / nothing / regret

_MENU = (
    "\n  `5The Latrine`2\n"
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
    "  `2(`0S`2)earch it        (`0R`2)ead the wall\n"
    "  `2(`0W`2)rite on the wall   (`0L`2)eave, obviously\n"
)


class TheLatrine(IGM):
    key = "the_latrine"
    name = "The Latrine"
    author = "pylord (recreation)"
    default_enabled = False

    async def enter(self, ctx: IgmContext) -> None:
        await ctx.term.write(
            "\n  `2A plank, a hole, and a hundred years of other people's opinions\n"
            "  carved into the wall.  You have made worse decisions today.\n"
        )
        while True:
            await ctx.term.write(_MENU)
            choice = await ctx.term.menu(
                {"S": "search", "R": "read", "W": "write", "L": "leave"},
                "  `2Your choice? [`0L`2] : `%",
            )
            if choice == "L":
                await ctx.term.write("\n  `2You leave, breathing through your mouth.\n")
                return
            if choice == "S":
                await self._search(ctx)
            elif choice == "R":
                await self._read(ctx)
            else:
                await self._write(ctx)

    async def _search(self, ctx: IgmContext) -> None:
        p = ctx.player
        outcome = ctx.rng.choice(FIND_ODDS)
        if outcome == 0:
            gold = ctx.rng.randrange(10, 200)
            p.gold += gold
            text = f"  `2Somebody's purse, and they are not coming back for it.\n  `%{gold} GOLD.`2\n"
        elif outcome == 1:
            p.gems += 1
            text = "  `2Something winks at you from the muck.  You take it anyway.\n  `%A GEM.`2\n"
        elif outcome == 2:
            text = "  `2Nothing.  Which is, on reflection, the best outcome available.\n"
        else:
            hurt = max(1, p.hp_max // 20)
            p.hp = max(1, p.hp - hurt)
            text = (
                "  `4You find something you will think about at odd moments for\n"
                f"  the rest of your life.  YOU LOSE {hurt} HITPOINTS.`2\n"
            )
        await ctx.term.write("\n" + text)
        await ctx.term.pause()

    async def _read(self, ctx: IgmContext) -> None:
        wall = ctx.store.get(WALL_KEY, [])
        await ctx.term.write("\n  `5Scrawled on the wall:`2\n\n")
        if not wall:
            await ctx.term.write("  `2Nothing but old stains.  Be the change.\n")
        for name, line in wall[-WALL_MAX:]:
            await ctx.term.write(f"  `0{name}`2: {line}\n")
        await ctx.term.pause()

    async def _write(self, ctx: IgmContext) -> None:
        line = (await ctx.term.readline("\n  `2Write what? : `%", maxlen=LINE_MAXLEN)).strip()
        if not line:
            return
        wall = list(ctx.store.get(WALL_KEY, []))
        wall.append([ctx.player.name, line])
        ctx.store.set(WALL_KEY, wall[-WALL_MAX:])
        await ctx.term.write(
            "\n  `2You carve it in with your knife.  It will outlive you.\n"
        )
        await ctx.term.pause()
