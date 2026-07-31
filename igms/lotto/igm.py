"""Seth's Tribute Lotto -- a lottery machine on a hill, dedicated to Seth.

**This one is a port, not a recreation.** Source:
``reference/igm-sources/lordts/lotto/lotto.ts``, itself ported from
``SLOTTO.PAS`` by Joseph Masters (Sons of Salami Software Group, 25 Sep
1995). Line references below are into that file.

The machine takes a four-digit code from the player, rolls four of its own,
and pays on how many of its digits appear in the player's -- position does
not matter, but a player digit already spent cannot answer a second machine
digit (``:132-145``). One play per day.

**The payout is a literal port and it is enormous.** ``:166-176`` carries
its own comment saying the formula is kept verbatim "so high-level payouts
scale exactly like the original machine", and the original machine multiplies
by ten once per two character levels. At level 12 a four-digit match pays
2,000,000,000 -- the gold ceiling in ``pylord/engine/limits.py``, in one
keypress. That is not a bug in this port; it is what the machine did, and
rebalancing it would make this a recreation rather than a port.

Like every bundled IGM it ships **on** (``config.toml``'s ``[igms]``: the
sysop turns off what they don't want). A realm that leaves it on has left
a money printer on, and should mean to. See ``docs/deviations.md``.

**Storage.** The source keeps a ``lotto.dat`` with one record per player
holding the day they last played (``:201-224``). pylord has ``ctx.store``,
so the day field becomes a per-player gate key cleared in
:meth:`daily_maint`, the same shape ``igms/baraks_house`` and
``igms/abandoned_mines`` already use.
"""

from __future__ import annotations

from pylord.hooks import IGM, IgmContext, IgmMaintContext

#: Ticket price is ``TICKET_COST_PER_LEVEL * player.level`` (``lotto.ts:66``).
TICKET_COST_PER_LEVEL = 10
CODE_LEN = 4


def prize(level: int, matched: int) -> int:
    """The original machine's payout, ported literally from ``lotto.ts:168-176``.

    ``magicnum`` opens at 10 on an odd level and 30 on an even one, with
    level 12 overridden to 20; it is multiplied by ten ``level // 2 + 2``
    times (the TS comment records the Pascal original as
    ``for num := -1 to (level DIV 2)``), then divided by ten once for each
    match the player did *not* get.

    Kept as a free function so the payout table can be tested directly
    without driving a terminal.
    """
    magicnum = 10 if level % 2 != 0 else 30
    if level == 12:
        magicnum = 20
    for _ in range(level // 2 + 2):
        magicnum *= 10
    if matched < 4:
        magicnum //= 10
    if matched < 3:
        magicnum //= 10
    if matched < 2:
        magicnum //= 10
    return magicnum


def count_matches(player_code: str, machine_code: str) -> int:
    """How many machine digits the player's code answers (``lotto.ts:132-145``).

    Position-independent, but each player digit is consumed at most once --
    a player who enters ``1111`` against a machine ``1234`` scores one, not
    four. The source tracks this with a ``used[]`` array; this is the same
    loop.
    """
    used = [False] * CODE_LEN
    matched = 0
    for machine_digit in machine_code:
        for w in range(CODE_LEN):
            if machine_digit == player_code[w] and not used[w]:
                used[w] = True
                matched += 1
                break
    return matched


class Lotto(IGM):
    key = "lotto"
    name = "Seth's Tribute Lotto"
    author = "Joseph Masters"
    default_enabled = True

    async def enter(self, ctx: IgmContext) -> None:
        p = ctx.player
        gate = f"day:{p.id}"

        await ctx.term.write(
            "\n  `2Following a path instinctively, you come to a large hill.\n"
            "  It appears insurmountable, but you feel a warmth come over you,\n"
            "  and a pulling force brings you to the top of the hill.\n"
            "\n"
            "  `2At the top is an oddly-shaped box with buttons next to the\n"
            "  numbers 1 through 9.  A plaque sits below it.\n"
            "\n"
            '  `0"`2This Lottery is placed in Honor of Seth Able Robinson for\n'
            '  his great wisdom and advice.`0"\n'
            "            `0- `2Dedicated by Joseph Masters, 9/25/95\n"
            "\n"
            "  `2This appears to be some kind of Lottery Machine...\n"
        )

        if ctx.store.get(gate, False):
            await ctx.term.write(
                "\n  `2You already tried your luck today!\n  Come back tomorrow.\n"
            )
            await ctx.term.pause()
            return

        cost = TICKET_COST_PER_LEVEL * p.level
        if p.gold < cost:
            await ctx.term.write(
                "\n  `2However, you don't seem to have the kind of money you\n"
                "  need to use the machine!\n"
            )
            await ctx.term.pause()
            return

        if (
            await ctx.term.menu(
                {"Y": "yes", "N": "no"}, "\n  `2Try it out? [`5Y`2]:`% "
            )
            == "N"
        ):
            await ctx.term.write(
                "\n  `2You trudge home, unaware of what you've missed.\n"
            )
            await ctx.term.pause()
            return

        player_code = await self._read_code(ctx)
        if player_code is None:  # blank entry walks away, lotto.ts:108-111
            return

        # Charge and burn the day only once the code is in -- the source
        # marks the record before prompting (:90-92), but its blank-entry
        # escape then leaves the player charged for a ticket they never
        # played. Ours charges what it collects.
        ctx.store.set(gate, True)
        p.gold -= cost
        await ctx.term.write(f"\n  `2You deposit `${cost}`2 gold into the box.\n")

        machine_code = "".join(str(ctx.rng.randrange(10)) for _ in range(CODE_LEN))
        matched = count_matches(player_code, machine_code)
        await ctx.term.write(f"\n  `2Machine's Code :`% {machine_code}\n")

        if matched < 1:
            await ctx.term.write(
                "\n  `2You didn't match any numbers!\n\n  Try again tomorrow!\n"
            )
            await ctx.term.pause()
            return

        won = prize(p.level, matched)
        p.gold += won
        await ctx.term.write(
            f"\n  `2You matched {matched} numbers!\n\n"
            f"  `2{'You hit the jackpot!' if matched > 3 else 'You almost hit the jackpot!'}\n"
            f"\n  `2  You win `${won} `2gold!\n"
        )
        if matched >= CODE_LEN:
            # Not in the source -- a payout this size should be public.
            ctx.news(f"`0{p.name} `2hit the jackpot at Seth's Tribute Lotto!")
        await ctx.term.pause()

    async def _read_code(self, ctx: IgmContext) -> str | None:
        """Prompt until the player enters four digits, or blanks out.

        The three rejection messages are the source's own (``:112-121``).
        "Too long!" is unreachable while the field is capped at
        ``CODE_LEN`` -- it is unreachable in the source too, for the same
        reason (``getstr({len: 4})``) -- and is kept so the ported prompt
        loop matches line for line.
        """
        await ctx.term.write(
            '\n  `0"`2Press four numbers to come up with your code.  Then, wait\n'
            "  for the machine to come up with its.  If you match one or more\n"
            '  numbers, you will win some gold back!`0"\n'
        )
        while True:
            entered = (
                await ctx.term.readline("\n  `2Enter Your Code:`% ", maxlen=CODE_LEN)
            ).strip()
            if entered == "":
                return None
            if len(entered) < CODE_LEN:
                await ctx.term.write("\n  `2  Too short!\n")
            elif len(entered) > CODE_LEN:
                await ctx.term.write("\n  `2  Too long!\n")
            # isascii() as well as isdigit(): str.isdigit() alone accepts
            # non-ASCII digits, where the source's /^\d+$/ does not.
            elif not (entered.isascii() and entered.isdigit()):
                await ctx.term.write("\n  `2  Not a number!\n")
            else:
                return entered

    async def daily_maint(self, ctx: IgmMaintContext) -> None:
        for player in ctx.repo.all_players():
            ctx.store.delete(f"day:{player.id}")
