"""The Gem Trader -- turn gems into gold, at whatever rate the day brings.

Wave-2 IGM, a recreation from the premise (a trader who buys gems) rather
than a port -- no gem-trading IGM appears anywhere in
`reference/igm-sources/`, and `reference/lord.js` never modelled one.
Invented here: the price band, the daily roll, the haggle and its charm
gate.

The rate is rolled once per game day and shared by everyone (an
``IgmStore`` key, not a per-player one), so the realm's traders all see the
same market and "the price is good today" means something. Haggling is the
one lever a player has, and it can go wrong.
"""

from __future__ import annotations

from pylord.hooks import IGM, IgmContext, IgmMaintContext

RATE_MIN = 80
RATE_MAX = 260
RATE_KEY = "rate"
#: Charm needed before haggling can improve the price at all.
HAGGLE_CHARM = 10
HAGGLE_BONUS = 25
HAGGLE_PENALTY = 20

_MENU = (
    "\n  `5The Gem Trader`2\n"
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
    "  `2(`0S`2)ell gems      (`0H`2)aggle over the price      (`0L`2)eave\n"
)


def _rate(ctx: IgmContext) -> int:
    """Today's price per gem, rolled once and shared by every player."""
    rate = ctx.store.get(RATE_KEY)
    if rate is None:
        rate = ctx.rng.randrange(RATE_MIN, RATE_MAX + 1)
        ctx.store.set(RATE_KEY, rate)
    return rate


class GemTrader(IGM):
    key = "gem_trader"
    name = "The Gem Trader"
    author = "pylord (recreation)"
    default_enabled = True

    async def enter(self, ctx: IgmContext) -> None:
        await ctx.term.write(
            "\n  `2A folding table, a set of brass scales, and a man who looks at\n"
            "  your pouch before he looks at your face.\n"
        )
        while True:
            p = ctx.player
            rate = _rate(ctx)
            await ctx.term.write(_MENU)
            await ctx.term.write(
                f"  `2Today he pays `%{rate}`2 gold a gem.  "
                f"You have `%{p.gems}`2.\n\n"
            )
            choice = await ctx.term.menu(
                {"S": "sell", "H": "haggle", "L": "leave"},
                "  `2Your choice? [`0L`2] : `%",
            )
            if choice == "L":
                await ctx.term.write("\n  `2He is already weighing someone else's stones.\n")
                return
            if choice == "S":
                await self._sell(ctx, rate)
            else:
                await self._haggle(ctx)

    async def _sell(self, ctx: IgmContext, rate: int) -> None:
        p = ctx.player
        if p.gems < 1:
            await ctx.term.write('\n  `0"Come back with something to sell."`2\n')
            await ctx.term.pause()
            return
        raw = await ctx.term.readline(
            f"\n  `2How many gems? (you have `%{p.gems}`2) : `%", maxlen=6
        )
        digits = "".join(c for c in raw if c.isdigit())
        count = int(digits) if digits else 0
        if count < 1:
            return
        if count > p.gems:
            await ctx.term.write('\n  `0"You have not got that many."`2\n')
            await ctx.term.pause()
            return
        paid = count * rate
        p.gems -= count
        p.gold += paid
        await ctx.term.write(
            f"\n  `2He counts out `%{paid}`2 gold and sweeps the gems into a bag.\n"
        )
        await ctx.term.pause()

    async def _haggle(self, ctx: IgmContext) -> None:
        """Charm decides whether he raises the price or ends the day's trade."""
        p = ctx.player
        if ctx.store.get(f"haggled:{p.id}", False):
            await ctx.term.write(
                '\n  `0"We have already had this conversation today."`2\n'
            )
            await ctx.term.pause()
            return
        ctx.store.set(f"haggled:{p.id}", True)

        rate = _rate(ctx)
        if p.charm >= HAGGLE_CHARM and ctx.rng.randrange(2) == 0:
            ctx.store.set(RATE_KEY, rate + HAGGLE_BONUS)
            await ctx.term.write(
                f"\n  `2He laughs, waves a hand, and writes a new number.\n"
                f"  `%THE PRICE RISES TO {rate + HAGGLE_BONUS} GOLD A GEM.`2\n"
            )
        else:
            ctx.store.set(RATE_KEY, max(RATE_MIN, rate - HAGGLE_PENALTY))
            await ctx.term.write(
                "\n  `2He does not care for your tone.\n"
                f"  `4THE PRICE DROPS TO {max(RATE_MIN, rate - HAGGLE_PENALTY)} "
                "GOLD A GEM.`2\n"
            )
        await ctx.term.pause()

    async def daily_maint(self, ctx: IgmMaintContext) -> None:
        """New day, new market -- and everyone may haggle again."""
        ctx.store.delete(RATE_KEY)
        for player in ctx.repo.all_players():
            ctx.store.delete(f"haggled:{player.id}")
