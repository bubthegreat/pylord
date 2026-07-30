"""Olodrin's Orphanage -- adopt, sell, catch, or trade children for a horse.

**This one is a port, not a recreation.** Source:
``reference/igm-sources/lordts/oorphans/oorphans.ts`` (a LORD 5.00 IGM by
Underminer, 2020; the Synchronet tree carries the same module as
``oorphans.js``). Line references below are into the TypeScript. The three
tables in ``data/`` are the original ``.dat`` files, copied unchanged.

It is bleak and it is meant to be. Olodrin will sell you a child, buy one
back off you for a flat 250 gold, and swap a pile of them for a horse.

**Why it matters mechanically.** Both currencies here are live in this
port: ``kids`` and ``horse`` each add forest fights at the daily reset
(``pylord/engine/daily.py:39,180``) and both show on the stats screen.
lord.js's own forest horse-trader is unported (see ``docs/deviations.md``),
so Olodrin's trade is currently the only way to get a horse in the realm --
which makes this the one wave-3 IGM that fills a gap rather than adding a
diversion.

**The catch mini-game barely works, faithfully.** ``catchOrphans``
(``:350-422``) rolls ``random(7)``: two results are a success and five cost
you something. But a success is refused outright if you already have *any*
child (``:367-373``), so in practice catching only ever lands your first
one; every visit after that is a pure loss. The source's own comment above
the roll ("2/7 success (29%)") describes odds its code does not implement.
Reproduced as written -- see ``docs/deviations.md``.
"""

from __future__ import annotations

import math

from pylord.hooks import IGM, IgmContext

#: ``oorphans.ts:48-50``.
MAX_KIDS = 12
SELL_PRICE = 250
MAX_PRICE = 2_000_000_000

#: ``oorphans.ts:56-70`` -- who the orphan lost, and whether that guardian
#: gets a name from the boys' or the girls' table.
GUARDIANS: tuple[tuple[str, bool], ...] = (
    ("Father", False),
    ("Mother", True),
    ("Grandfather", False),
    ("Grandmother", True),
    ("Papa", False),
    ("Mama", True),
    ("Aunt", True),
    ("Uncle", False),
    ("Brother", False),
    ("Sister", True),
    ("Uncle Daddy", False),
    ("Sister Mama", True),
)

#: ``oorphans.ts:14-46``.
LOOKING_FOR_WAIF = (
    "After skulking through the grass a while, you spot your quarry!",
    "You try wandering casually down a path, lunging out as a youth passes",
    "Playing dead, you jump up when a curious youth approaches",
    "You are completely surprised as you are suddenly jumped!",
    "You charge into the fields screaming bloody murder!",
    "Thinking you're sneaking, you clatter loudly down the path",
    "'I suure hate eating this chocolate!' you scream out. Suddenly...",
    "You stand perfectly still until a wild youth looks at you, puzzled",
)
INTERMEDIATE_ACTION = (
    "You flail wildly, trying to get a hand on the quick youngster",
    "You decide your best bet is to sweep the leg",
    "A smarter individual would have brought a net...",
    "You grab a chunk of flesh and bite down hard",
    "You close your eyes and let an inner voice guide you",
)
GOOD_CATCH = (
    "Success! You vow to hug him and squeeze him and call him George",
    "Congratulations! Under that mess of hair is a little girl to win over",
    "You manage to get hold of a scamp and calm them down!",
    "Your first attempt fails, but chocolate bribery works!",
)
BAD_CATCH = (
    "You get hit with a stick behind the knee and go down hard",
    "Somehow you manage to kick YOURSELF in the face",
    "You feel teeth dig into your arm and scream out in pain!",
    "You feel an impact in the back of the head and see stars",
    "After feeling pain, you stop biting yourself and take stock",
)

_HEAD_RULE = "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=\n"

_MENU = (
    "`!Olodrin`2 stands before you, arms crossed\n"
    "`2He waits for you to make a decision\n\n"
    "`2(`0A`2)dopt an orphan\n"
    "`2(`0G`2)ive child up for adoption\n"
    "`2(`0C`2)atch a feral child\n"
    "`2(`0T`2)rade some of your children for a horse\n"
    "`2(`0Q`2)uit and go home\n\n"
)


def js_round(value: float) -> int:
    """JavaScript's ``Math.round``, which is not Python's ``round``.

    ``Math.round`` breaks ties upward (``0.5`` -> ``1``); Python's ``round``
    breaks them to even (``0.5`` -> ``0``). Every loss in ``catchOrphans``
    is a rounded percentage, so the difference is real money.
    """
    return math.floor(value + 0.5)


def adoption_price(level: int, kids: int) -> int:
    """``oorphans.ts:115-124``: level squared thousands, doubled per child.

    Note the ceiling check runs *before* each doubling and returns the cap
    outright, so the price jumps from just under half the cap straight to
    the cap. Ported as written.
    """
    price = max(1000, js_round(level * level * 1000))
    for _ in range(kids):
        if price >= MAX_PRICE // 2:
            return MAX_PRICE
        price *= 2
    return price


def horse_trade_cost(level: int) -> int:
    """``oorphans.ts:126-128``: ``min(level * level, MAX_KIDS)`` children.

    Which means from level 4 upward the price is a full house of twelve.
    """
    return min(level * level, MAX_KIDS)


def _commas(n: int) -> str:
    """The source formats its losses with thousands separators (``:390``)."""
    return f"{n:,}"


class Oorphans(IGM):
    key = "oorphans"
    name = "Olodrin's Orphanage"
    author = "Underminer"
    default_enabled = True

    # --- data tables ---------------------------------------------------

    def _table(self, filename: str) -> list[str]:
        """Read one of the ``data/*.dat`` tables shipped beside this module.

        The originals have trailing spaces on most lines, so entries are
        stripped and blanks dropped. A missing file yields an empty list,
        which :meth:`_orphan_description` handles -- a broken install
        should not roll back a player's visit.
        """
        if self.dir is None:
            return []
        try:
            text = (self.dir / "data" / filename).read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            return []
        return [line.strip() for line in text.splitlines() if line.strip()]

    @property
    def boy_names(self) -> list[str]:
        return self._table("boynames.dat")

    @property
    def girl_names(self) -> list[str]:
        return self._table("girlnames.dat")

    @property
    def how_they_died(self) -> list[str]:
        return self._table("howdied.dat")

    # --- entry ---------------------------------------------------------

    async def enter(self, ctx: IgmContext) -> None:
        await ctx.term.write(
            "\n  `2You travel for what feels like ages down a beaten dirt path.\n"
            "  `2Finally, up ahead you see a dilapidated sign lit dimly by "
            "`$two torches.`2\n"
            "  `2It would seem you have arrived at `4Olodrin's Orphanage`2\n"
            "\n  `!Olodrin's Orphanage\n"
            "  `2A `4LoRD`2 5.00 `2IGM by `$Underminer `2in the year `$2020.`2\n"
        )
        while True:
            await self._head(ctx, "Olodrin's Orphanage")
            await ctx.term.write(_MENU)
            choice = await ctx.term.menu(
                {"A": "adopt", "G": "give", "C": "catch", "T": "trade", "Q": "quit"},
                "  `2You decide to... [`0Q`2] :`%",
            )
            if choice == "Q":
                await ctx.term.write(
                    '\n\n  `2Olodrin asks "`4Leaving already?`2" as you turn back '
                    "to town.\n\n"
                    "  `2You have had a `$uneventful `2visit to Olodrin's Orphans "
                    "today.\n"
                )
                await ctx.term.pause()
                return
            if choice == "A":
                await self._adopt(ctx)
            elif choice == "G":
                await self._give_up(ctx)
            elif choice == "C":
                await self._catch(ctx)
            else:
                await self._trade_for_horse(ctx)

    async def _head(self, ctx: IgmContext, title: str) -> None:
        await ctx.term.write(f"\n  `%{title}\n{_HEAD_RULE}\n")

    async def _confirm(self, ctx: IgmContext) -> bool:
        """The source's ``[y/N]`` prompt -- Enter means no (``:246-251``)."""
        return (
            await ctx.term.menu({"Y": "yes", "N": "no"}, "  Do it? [y/`0N`2]:`%") == "Y"
        )

    # --- (A)dopt -------------------------------------------------------

    async def _adopt(self, ctx: IgmContext) -> None:
        p = ctx.player
        price = adoption_price(p.level, p.kids)
        await self._head(ctx, "Get yourself a waif!")
        if p.kids >= MAX_KIDS:
            await self._too_many(ctx)
            return

        name = await self._orphan_description(ctx)
        await ctx.term.write(
            f"\n  It will cost you `${_commas(price)} gold `2 to adopt this child.\n\n"
        )
        if not await self._confirm(ctx):
            return
        if p.gold < price:
            await ctx.term.write("\n  `!You fool! `2You don't have enough gold!\n")
            await ctx.term.pause()
            return
        p.gold -= price
        p.kids += 1
        await ctx.term.write(f"\n  `2Take good care of `!{name}!`2\n")
        await ctx.term.pause()

    async def _too_many(self, ctx: IgmContext) -> None:
        await ctx.term.write(
            "\n  `!Olodrin `2glares at the parade of rugrats behind you.\n"
            f'  `0"No more, nit! `2You already have `${_commas(ctx.player.kids)} '
            '`2children to feed."\n'
        )
        await ctx.term.pause()

    async def _orphan_description(self, ctx: IgmContext) -> str:
        """``oorphans.ts:188-230``. Returns the orphan's name.

        Falls back to a plain description if the data tables are missing,
        rather than raising and rolling the visit back.
        """
        boys, girls, deaths = self.boy_names, self.girl_names, self.how_they_died
        if not (boys and girls and deaths):
            await ctx.term.write("\n  `2This is one of Olodrin's foundlings.\n")
            return "the child"

        male = ctx.rng.randrange(2) == 1
        own_pool = boys if male else girls
        name = own_pool[ctx.rng.randrange(len(own_pool))]
        title, guardian_female = GUARDIANS[ctx.rng.randrange(len(GUARDIANS))]
        died_by = deaths[ctx.rng.randrange(len(deaths))]
        guardian_pool = girls if guardian_female else boys
        guardian = guardian_pool[ctx.rng.randrange(len(guardian_pool))]

        possessive, pronoun = ("his", "he") if male else ("her", "she")
        await ctx.term.write(
            f"\n  `2This is `!{name}\n"
            f"  `2{possessive.capitalize()} last guardian was {possessive} "
            f"`!{title}, `${guardian}, `2who... \n"
            f"  `4{died_by}\n"
            f"  `2Needless to say, {pronoun} ended up in our care\n"
        )
        return name

    # --- (G)ive up -----------------------------------------------------

    async def _give_up(self, ctx: IgmContext) -> None:
        p = ctx.player
        if p.kids < 1:
            await ctx.term.write(
                "\n\n  `!You fool! You don't have any children!\n"
                "  `3Did you get hit in the head one too many times?\n"
            )
            await ctx.term.pause()
            return

        await self._head(ctx, "Sell your rugrats")
        await ctx.term.write(
            "  `2'Hmmm...' says `!Olodrin, `2looking over the youngster you "
            "push forward.\n"
            f"  `2I will give you `${_commas(SELL_PRICE)}`2 for this child.\n"
        )
        if not await self._confirm(ctx):
            await ctx.term.write("\n  `2Suit yourself!`2\n")
            await ctx.term.pause()
            return
        p.gold += SELL_PRICE
        p.kids -= 1
        boys = self.boy_names
        farewell = boys[ctx.rng.randrange(len(boys))] if boys else "the child"
        await ctx.term.write(
            f"\n  `2Don't worry, we'll take good care of `!{farewell}!`2\n"
        )
        await ctx.term.pause()

    # --- (T)rade for a horse -------------------------------------------

    async def _trade_for_horse(self, ctx: IgmContext) -> None:
        p = ctx.player
        if p.horse:
            await ctx.term.write("\n\n  `!You stupid nit! You already have a horse!\n")
            await ctx.term.pause()
            return

        cost = horse_trade_cost(p.level)
        await self._head(ctx, "Trade ragamuffins for a Steed!")
        await ctx.term.write(
            "  `!Olodrin `2opens his mouth to speak:\n"
            f"  For you, I will give you a horse in exchange for `${cost} "
            "`2children.\n"
        )
        if not await self._confirm(ctx):
            await ctx.term.write("\n  `2Suit yourself!`2\n")
            await ctx.term.pause()
            return
        if p.kids < cost:
            await ctx.term.write(
                f"\n\n  `!You stupid nit! You only have `${p.kids} `2children!\n"
            )
            await ctx.term.pause()
            return
        p.kids -= cost
        p.horse = 1
        await ctx.term.write(
            "\n  `2Don't worry, we'll take good care of `!THESE `2children...\n"
        )
        await ctx.term.pause()

    # --- (C)atch -------------------------------------------------------

    async def _catch(self, ctx: IgmContext) -> None:
        """``oorphans.ts:350-422``.

        The ``random(7)`` branches map: 1 and 6 succeed, 0 and 3 cost gold,
        2 costs charm, 4 costs experience, 5 costs gems. That covers all
        seven values, so the source's trailing ``else`` (``:418``) is dead
        code and is not ported.
        """
        p = ctx.player
        await self._head(ctx, "Trying to catch a wild child")
        await ctx.term.write(
            f"  {LOOKING_FOR_WAIF[ctx.rng.randrange(len(LOOKING_FOR_WAIF))]}\n"
            f"  {INTERMEDIATE_ACTION[ctx.rng.randrange(len(INTERMEDIATE_ACTION))]}\n"
        )
        result = ctx.rng.randrange(7)

        if result in (1, 6):
            await self._catch_success(ctx)
            return

        await ctx.term.write(f"  `2{BAD_CATCH[ctx.rng.randrange(len(BAD_CATCH))]}\n")
        if result == 2:
            lost = ctx.rng.randrange(5)
            p.charm -= lost
            await ctx.term.write(f"  `2You Lose `${lost}`2 charm due to injuries\n")
        elif result in (0, 3):
            lost = js_round(ctx.rng.randrange(20) / 100 * p.gold)
            p.gold -= lost
            await ctx.term.write(
                f"  `2That scamp made off with `${_commas(lost)}`2 of your gold!\n"
            )
        elif result == 4:
            lost = js_round(ctx.rng.randrange(10) / 100 * p.exp)
            p.exp -= lost
            await ctx.term.write(
                "  `2You get hit so hard you forget your own birthday...\n"
                f"  `2You lose `${_commas(lost)}`2 experience!\n"
            )
        else:  # result == 5
            # 50-74% of the player's gems, in one roll.
            lost = js_round((ctx.rng.randrange(25) + 50) / 100 * p.gems)
            p.gems -= lost
            await ctx.term.write(
                f"  `2Those little guttersnipes make off with `${_commas(lost)}"
                "`2 of your Gems!\n"
            )
        await ctx.term.pause()

    async def _catch_success(self, ctx: IgmContext) -> None:
        """The two winning rolls, and the two gates that usually eat them.

        ``:367-373`` refuses a catch to anyone already holding a child, so
        this only ever lands a player's *first* orphan. Faithful.
        """
        p = ctx.player
        if p.kids >= MAX_KIDS:
            await ctx.term.write(
                "  `2You lunge forward, but the little brat takes one look at "
                "your brood and bolts!\n"
                '  `!Olodrin `2howls with laughter. `0"No more, nit! `2Your '
                'house is full already!"\n'
            )
            await ctx.term.pause()
            return
        if p.kids > 0:
            await ctx.term.write(
                "  `2You nearly snatch the little guttersnipe by the collar...\n"
                "  `2but the brat spots the child already hanging on you and "
                "tears off laughing!\n"
                '  `!Olodrin `2cackles. `0"One at a time, nit! `2Take that one '
                'home first."\n'
            )
            await ctx.term.pause()
            return
        await ctx.term.write(f"  `2{GOOD_CATCH[ctx.rng.randrange(len(GOOD_CATCH))]}\n")
        p.kids += 1
        await ctx.term.pause()
