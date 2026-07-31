"""The FreeWorld II -- a once-a-day walk, a wishing well, and a Chancellor.

**This one is a port, not a recreation.** Source:
``reference/igm-sources/lordts/freeworld2/freeworld2.ts`` -- itself a
TypeScript port of the Virtual Pascal original by Chris Martino, with
thanks to Michael Preslar and Rick Parrish (2005). Line references below
are into the TypeScript. ``screens/`` holds the original ANSI art.

The chain matters when reading this: **Pascal -> TypeScript -> here**, and
the middle link already made one change of its own. The original had four
identical "the path goes on forever" no-op walk events; the TypeScript
replaced them with four distinct pieces of flavour (``:374-402``, each
marked "Replaced duplicate"). Those four are ported from the TypeScript,
so they are the one part of this module with no Pascal ancestry.

**This is the most generous IGM in the realm, by a distance.** Five walks
a day, each with a 1-in-10 chance of the wishing well, which grants a wish
1 time in 3 -- and a granted Strength wish is up to +100 in one keypress
(``:496``). The Chancellor pays 50,000 gold for guessing a number in five
tries, and the Fairy Wizard pays up to 700,000 for a fairy. Every one of
those figures is the source's, and nothing here is rebalanced -- doing so
would make this a recreation rather than a port.

Like every bundled IGM it ships **on** (``config.toml``'s ``[igms]``: the
sysop turns off what they don't want). A realm that wants a tighter economy
should turn it off rather than expect the port to invent restraint the
original never had. See ``docs/deviations.md``.
"""

from __future__ import annotations

from pylord.hooks import IGM, IgmContext, IgmMaintContext
from pylord.terminal import load_screen

#: ``freeworld2.ts:29``. Walks are counted per *visit*, and a visit is
#: once a day, so this is also the daily ceiling.
MAX_WALKS = 5
#: The Chancellor's purse and his patience (``:635-666``).
CHANCELLOR_PRIZE = 50_000
CHANCELLOR_TRIES = 5
CHANCELLOR_RANGE = 100
#: ``:528``. The TypeScript's own comment explains the cap: it sits below
#: Felicity's Temple's 750,000 fairy price so the two cannot be looped
#: against each other. Felicity is not ported here, but the cap stays.
FAIRY_GOLD_PER_LEVEL = 50_000
FAIRY_GOLD_MAX = 700_000
#: ``:582``. The pouch is a 1-in-3 win.
POUCH_GOLD_MAX = 10_000

#: The wishing well (``:494-508``): key -> (player field, label, maximum).
#: The granted amount is ``rng.randrange(maximum) + 1``.
WISHES: dict[str, tuple[str, str, int]] = {
    "A": ("strength", "Strength", 100),
    "B": ("charm", "Charm", 10),
    "C": ("defense", "Defense", 100),
    "D": ("forest_fights", "Forest Fights", 10),
    "E": ("player_fights", "Human Fights", 10),
    "F": ("hp_max", "Hit Points", 30),
    "G": ("bank", "Gold In Bank", 5000),
    "H": ("lays", "Lays", 1),
    "I": ("exp", "Experience", 5000),
    "J": ("gold", "Gold", 5000),
    "K": ("kids", "Kids", 1),
    "L": ("gems", "Gems", 10),
}
#: 'M' is handled separately: it picks one of the three skill tracks.
_SKILL_FIELDS = ("skill_dk", "skill_my", "skill_th")

_RULE = "`2-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"

_MAIN_MENU = (
    "\n  `0The `%FreeWorld `0II `$v`21`%.`20 `%Menu\n"
    f"  {_RULE}"
    "  `2(`5W`2)alk Around\n"
    "  `2(`5H`2)igh Chancellor\n"
    "  `2(`5V`2)iew Your Stats\n"
    "  `2(`5I`2)nfo On `0The `%FreeWorld `0II\n"
    "  `2(`5Q`2)uit Back To `4Lord\n\n"
)

_WELL_MENU = (
    "  `2You Stumble Upon A Wishing Well`%!!!\n"
    "  `2What Do You Want To Wish For`%?\n\n"
    "  `%A`$. Strength     `%B`$. Charm\n"
    "  `%C`$. Defense      `%D`$. Forest Fights\n"
    "  `%E`$. Human Fights `%F`$. Hit Points\n"
    "  `%G`$. Gold In Bank `%H`$. Lays\n"
    "  `%I`$. Experience   `%J`$. Gold\n"
    "  `%K`$. Kids         `%L`$. Gems\n"
    "  `%M`$. Skill Points\n\n"
)


def fairy_gold(level: int) -> int:
    """The Fairy Wizard's offer (``freeworld2.ts:528``)."""
    return min(FAIRY_GOLD_MAX, level * FAIRY_GOLD_PER_LEVEL)


class FreeWorld2(IGM):
    key = "freeworld2"
    name = "The FreeWorld II"
    author = "Chris Martino and Mike Preslar"
    default_enabled = True

    async def enter(self, ctx: IgmContext) -> None:
        gate = f"day:{ctx.player.id}"
        if ctx.store.get(gate, False):
            await ctx.term.write(
                "\n  `0You Can't Seem To Find The Path To Take You To "
                "`0The `%FreeWorld `0II`%.\n\n"
                "  `2Try Again Tomorrow`%...\n"
            )
            await ctx.term.pause()
            return
        # Burned up front, exactly as the source does (:94-97) -- the visit
        # is the resource, and it is spent on arrival.
        ctx.store.set(gate, True)

        await self._intro(ctx)

        # Session-only counters. The source keeps these in memory too
        # (:56-59): the once-a-day record is the only thing persisted.
        walks = 0
        saw_chancellor = False

        while True:
            await ctx.term.write(_MAIN_MENU)
            choice = await ctx.term.menu(
                {
                    "W": "walk",
                    "H": "chancellor",
                    "V": "stats",
                    "I": "info",
                    "Q": "quit",
                },
                "  `2Enter Option: ",
                default="Q",
            )
            if choice == "Q":
                await ctx.term.write(
                    "\n  `$Returning To `2Legend Of The `4Red `2Dragon.....\n"
                )
                return
            if choice == "W":
                walks += 1
                if walks > MAX_WALKS:
                    await ctx.term.write(
                        "\n  `2You Used All Your Turns For Today Please Play "
                        "Again Tomorrow`%!\n\n"
                        "  `$Returning To `2Legend Of The `4Red `2Dragon.....\n"
                    )
                    return
                await self._walk(ctx)
            elif choice == "H":
                if saw_chancellor:
                    await ctx.term.write(
                        "\n  `2You Can Only See The Chancellor Once A Day`%!\n"
                    )
                    await ctx.term.pause()
                else:
                    saw_chancellor = True
                    await self._chancellor(ctx)
            elif choice == "V":
                await self._stats(ctx)
            else:
                await self._ole_man(ctx)

    # --- screens -------------------------------------------------------

    async def _screen(self, ctx: IgmContext, filename: str) -> None:
        """Draw one of the original ``.ANS`` files, if it is readable.

        Missing art is cosmetic; raising here would roll the visit back.
        """
        if self.dir is None:
            return
        try:
            await ctx.term.write_screen(load_screen(self.dir / "screens" / filename))
        except OSError:
            return

    async def _intro(self, ctx: IgmContext) -> None:
        await self._screen(ctx, "INTRO1.ANS")
        await ctx.term.write(
            "\n  `@LORD IGM`%: `0The `%FreeWorld `0II `$v`21`%.`20\n"
            "  `$-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
            "  `@- `$AUTHOR`%:  `0Chris Martino\n"
            "  `@- `$LANGUAGE`%: `!VIRTUAL PASCAL `%v2.1\n"
            "  `@- `$SPECIAL THANKS`%: `!Michael Preslar And Rick Parrish\n"
            "  `@- `$IGM INFO`%: `!This Is A Remake Of The FreeWorld IGM\n"
            "               `!Full Rewrite. Color Scheme From ANGEL Door Kit.\n"
            "               `!IGM Can Only Be Played Once A Day\n"
        )
        await ctx.term.pause()

    async def _stats(self, ctx: IgmContext) -> None:
        """The IGM's own stats screen (``:182-282``).

        Trimmed to what this port models. Dropped, with reasons: the
        weapon/armour *names* (an IGM sees only ``weapon_num``/``armor_num``
        through the guardrails), the per-class daily use counters (this port
        has one shared ``skill_uses`` -- see ``docs/deviations.md``), the
        NPC-marriage lines (global state an ``IgmContext`` deliberately
        cannot reach) and the local date/time header (no clock is exposed
        to a plugin).
        """
        p = ctx.player
        lines = [
            f"\n  `2{p.name}'`%`2s Stats...\n",
            "  `2-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n",
            f"  `2Experience   `%: `0{p.exp}\n",
            f"  `2Games Won    `%: `0{p.king_count}\n",
            f"  `2Game Level   `%: `0{p.level}\n",
            f"  `2Hit Points   `%: `0{p.hp} `2of `0{p.hp_max}\n",
            f"  `2Forest Fights`%: `0{p.forest_fights}\n",
            f"  `2Player Fights`%: `0{p.player_fights}\n",
            f"  `2Gold on Hand `%: `0{p.gold}\n",
            f"  `2Gold in Bank `%: `0{p.bank}\n",
            f"  `2Weapon  [`0{p.weapon_num}`%]   `%: `0#{p.weapon_num}\n",
            f"  `2Strength     `%: `0{p.strength}\n",
            f"  `2Armour  [`0{p.armor_num}`%]   `%: `0#{p.armor_num}\n",
            f"  `2Defense      `%: `0{p.defense}\n",
            f"  `2Charm        `%: `0{p.charm}\n",
            f"  `2Gems         `%: `0{p.gems}\n",
            f"  `2Kills        `%: `0{p.pvp_kills}\n",
            f"  `2Lays         `%: `0{p.lays}\n",
            f"  `2Children     `%: `0{p.kids if p.kids > 0 else 'None.'}\n\n",
        ]
        for label, field in (
            ("`%Death Knight Skills", "skill_dk"),
            ("`%    Mystical Skills", "skill_my"),
            ("`%    Thieving Skills", "skill_th"),
        ):
            rank = getattr(p, field)
            mastered = " `0(`%MASTERED`0)" if rank >= 40 else ""
            shown = f"`${rank}{mastered}" if rank > 0 else "`0None."
            lines.append(f"  {label}`%: {shown}\n")
        lines.append(f"\n  `%Uses Today`%: `${p.skill_uses}\n")
        if p.horse:
            lines.append("  `0Your `$Horse `0is tied up outside, to a tree.\n")
        if p.has_fairy:
            lines.append("  `$You have a `2Fairy `$in your pocket.\n")
        await ctx.term.write("".join(lines))
        await ctx.term.pause()

    async def _ole_man(self, ctx: IgmContext) -> None:
        """``:676-727``. Pure flavour -- nothing here touches a stat."""
        while True:
            await ctx.term.write(
                "\n  `2As you get closer to read the carvings you notice "
                "something`%...\n"
                "  `2Someone else is here`%.\n"
                "  `2It is OLE MAN\n"
                "  `2You cautiously approach the OLE MAN\n"
                "  `2He seems to not notice you`%.....\n\n"
                "  `%[`2A`%]`2ttack\n  `%[`2Q`%]`2uestion\n  `%[`2L`%]`2eave\n\n"
            )
            choice = await ctx.term.menu(
                {"A": "attack", "Q": "question", "L": "leave"},
                "  `2OTHER WORLDS `%(`2A`%,`2Q`%,`2L`%): ",
                default="L",
            )
            if choice == "L":
                return
            if choice == "A":
                await ctx.term.write(
                    "\n  `2You jump on the OLE MAN`%.....\n\n"
                    "  `2In an instant the OLE MAN has you pinned to the ground\n"
                    "  `2HE SAYS : Don't mess with me KID`%.... `2I`%'`2ll feed "
                    "you to the DRAGON`%!\n\n"
                    "  `2The OLE MAN then lets you up and asks if you're OK`%?\n"
                    "  `2You shake your head and quickly run off`%!\n"
                    "  `2You wonder who the HELL was that`%?\n"
                )
            else:
                await ctx.term.write(
                    "\n  `2He calmly replies `%:\n\n"
                    "  `2This is my `%FreeWorld `0II`%.............\n"
                    "  `2I can make many things happen when I use this dang "
                    "MAGIC LAMP right`%.\n"
                    "  `2I see you are a MIGHTY WARRIOR from the Legend of "
                    "`4Red `2Dragon\n"
                    "  `2I will tell you more`%!\n"
                )
            await ctx.term.pause()

    # --- walking -------------------------------------------------------

    async def _walk(self, ctx: IgmContext) -> None:
        """``:355-407``: ``random(10) + 1`` over ten outcomes."""
        walk = ctx.rng.randrange(10) + 1
        if walk == 1:
            await self._pit(ctx)
        elif walk == 2:
            await self._fairy_heal(ctx)
        elif walk == 3:
            await self._nap(ctx)
        elif walk == 4:
            await self._wishing_well(ctx)
        elif walk == 6:
            await self._fairy_wizard(ctx)
        elif walk == 10:
            await self._leather_pouch(ctx)
        else:
            await self._flavour(ctx, walk)

    async def _flavour(self, ctx: IgmContext, walk: int) -> None:
        """Walks 5, 7, 8 and 9 -- the TypeScript's replacements for the
        Pascal's four identical no-ops (``:374-402``)."""
        text = {
            5: (
                "  `2The Path You Follow Fades Into Thick Undergrowth`%.\n"
                "  `2After Some Struggling, You Find Your Way Back`%.\n"
            ),
            7: (
                "  `2You Spot Ancient Ruins Carved Into The Hillside`%...\n"
                "  `2But They Crumble And Collapse As You Approach`%.\n"
                "  `2You Back Away Slowly`%.\n"
            ),
            8: (
                "  `2A Warm Campfire Still Smolders Nearby`%.\n"
                "  `2Someone Was Here Recently`%...\n"
                "  `2You Listen Carefully`%... `%But Hear Nothing`%.\n"
            ),
            9: (
                "  `2A Figure In A Dark Cloak Passes You On The Trail`%.\n"
                "  `2They Say Nothing`%... `2And Vanish Into The Mist`%.\n"
                "  `2You Wonder Who That Could Have Been`%.\n"
            ),
        }[walk]
        await ctx.term.write("\n" + text)
        await ctx.term.pause()

    async def _pit(self, ctx: IgmContext) -> None:
        """``:409-417``. The damage roll is drawn from current hp, so it can
        take almost everything -- but never the last point."""
        p = ctx.player
        hurt = ctx.rng.randrange(max(1, p.hp)) + 1
        p.hp = max(1, p.hp - hurt)
        await ctx.term.write(
            "\n  `2Your Walking Along And Trip And Fall Into A `4Pit`%!!!\n"
            "  `2After Climbing Out You Notice Your Hurt`%.\n"
            f"  `2You Lost `4{hurt} Hit Points`%!\n"
        )
        await ctx.term.pause()

    async def _fairy_heal(self, ctx: IgmContext) -> None:
        ctx.player.hp = ctx.player.hp_max
        await ctx.term.write(
            "\n  `2You Wander Into Some Thick Brush And Tree's`%.\n"
            "  `2A Bright `%White `2Light Start's To Come Towards You`%.\n"
            "  `2As It Gets Closer You Notice It's A Fairy`%!\n"
            "  `2She Looks You Over And Says A Few Words That You Dont "
            "Understand`%.\n"
            "  `2All Your `%Hitpoints `2Are Fully Restored`%!\n"
        )
        await ctx.term.pause()

    async def _nap(self, ctx: IgmContext) -> None:
        """``:430-443``. The source paces this with ``mswait``; there is no
        timed-output primitive in ``TermIO``, so the ellipses just print."""
        await ctx.term.write(
            "\n  `2You Wander Into Some Thick Brush And Tree's`%.\n"
            "  `2Your Starting To Get Tired`%.\n"
            "  `2You Find A Nice Tree And Settle In For A Nap`%...`%...`%...`%...\n"
            "  `2You Wake Up Fully Refreshed`%!\n"
        )
        await ctx.term.pause()

    async def _leather_pouch(self, ctx: IgmContext) -> None:
        """``:567-596``. One chance in three of gold; otherwise a scorpion
        takes a slice of experience drawn from the whole total."""
        p = ctx.player
        await ctx.term.write("\n  `2You See A Leather Pouch On The Ground`%!!!\n")
        if (
            await ctx.term.menu(
                {"Y": "take", "N": "leave"},
                "  `2Pick It Up`%[`2Y`%/`2N`%]`2: ",
                default="N",
            )
            != "Y"
        ):
            await ctx.term.write("\n  `2You Continue Your Journey`%.\n")
            await ctx.term.pause()
            return
        if ctx.rng.randrange(3) + 1 == 3:
            gold = ctx.rng.randrange(POUCH_GOLD_MAX) + 1
            p.gold += gold
            await ctx.term.write(f"\n  `2You Find `$${gold} `2Gold Coins Inside`%!\n")
        else:
            lost = ctx.rng.randrange(max(1, p.exp)) + 1
            p.exp = max(0, p.exp - lost)
            await ctx.term.write(
                f"\n  `2You Get Stung By A Scorpion You Lose {lost} "
                "Experience Points`%!\n"
            )
        await ctx.term.pause()

    async def _fairy_wizard(self, ctx: IgmContext) -> None:
        """``:525-563``. Sells the fairy caught in the forest for real money."""
        p = ctx.player
        offer = fairy_gold(p.level)
        await ctx.term.write(
            "\n  `2Your Journey Brings You To A Dark Area Of The Forest`%.\n"
            "  `2You Begin To Examine The Area`%...`%...`%...\n"
            "  `5POOOOOOFFFF!\n"
            "  `2You See A Cloud Of Smoke..As It Begins To Clear You Notice "
            "A Dark Figure.\n"
            f"  `%I'm The Great Fairy Wizard`%! `2I Offer You `2$`0{offer:,} "
            "`2Reward For A `%Fairy!\n"
        )
        if (
            await ctx.term.menu(
                {"Y": "yes", "N": "no"},
                "  `2Accept Offer`%[`2Y`%/`2N`%]`2: ",
                default="N",
            )
            != "Y"
        ):
            await ctx.term.pause()
            return
        if not p.has_fairy:
            await ctx.term.write("\n  `2You Don't Have A Fairy`%!!!!!\n")
        else:
            p.has_fairy = 0
            p.gold += offer
            await ctx.term.write(
                "\n  `2You Give Him Your Fairy In Exchange For The Cash\n"
            )
        await ctx.term.pause()

    # --- the wishing well ----------------------------------------------

    async def _wishing_well(self, ctx: IgmContext) -> None:
        """``:447-521``. One wish in three is granted."""
        await ctx.term.write("\n" + _WELL_MENU)
        choice = await ctx.term.menu(
            {k: k for k in "ABCDEFGHIJKLM"}, "  `2Enter Choice: "
        )
        granted = ctx.rng.randrange(3) + 1 == 3

        if not granted:
            # The source rolls the grant *before* branching on the wish, so
            # a refused wish consumes exactly one roll whichever key it was.
            await ctx.term.write("\n  `2Not Your Lucky Day`%!!\n")
            await ctx.term.pause()
            return

        if choice == "M":
            # ``random(1) + 1`` is always 1 (:482-484) -- one rank, never two.
            field = _SKILL_FIELDS[ctx.rng.randrange(3)]
            setattr(ctx.player, field, getattr(ctx.player, field) + 1)
        else:
            field, _label, maximum = WISHES[choice]
            amount = ctx.rng.randrange(maximum) + 1
            setattr(ctx.player, field, getattr(ctx.player, field) + amount)
        await ctx.term.write("\n  `2Wish Granted`%!!\n")
        await ctx.term.pause()

    # --- the High Chancellor -------------------------------------------

    async def _chancellor(self, ctx: IgmContext) -> None:
        """``:600-672``: guess 1-100 in five tries for 50,000 gold.

        A malformed guess still burns a try. The source's comment at
        ``:651`` says that is deliberate, matching the Pascal.
        """
        await self._screen(ctx, "CHANCE.ANS")
        await ctx.term.write(
            "\n  `0The Chancellor Is Very Busy`%.\n"
            "  `2But, He Will Pay You `$Gold `2If You Can Pass A Test`%!\n\n"
        )
        if (
            await ctx.term.menu(
                {"Y": "yes", "N": "no"},
                "  `2Accept Offer`%[`2Y`%/`2N`%]`2: ",
                default="N",
            )
            != "Y"
        ):
            await ctx.term.write("\n  `4Don't Waste My Time\n")
            await ctx.term.pause()
            return

        target = ctx.rng.randrange(CHANCELLOR_RANGE) + 1
        await ctx.term.write(
            "\n  `%Very Well`2, Here Is A Test`%.\n\n"
            f"  `2Guess A Number Between `%1 `2And `%{CHANCELLOR_RANGE} `2In "
            f"Less Than `%{CHANCELLOR_TRIES} Tries`%.\n"
        )
        for _ in range(CHANCELLOR_TRIES):
            entered = (
                await ctx.term.readline("\n  `%Your Answer: `2", maxlen=3)
            ).strip()
            if not (entered.isascii() and entered.isdigit()):
                await ctx.term.write(
                    f"\n  `%Please enter a number between 1 and {CHANCELLOR_RANGE}.\n"
                )
                continue
            guess = int(entered)
            if not 1 <= guess <= CHANCELLOR_RANGE:
                await ctx.term.write(
                    f"\n  `%Please enter a number between 1 and {CHANCELLOR_RANGE}.\n"
                )
                continue
            if guess == target:
                ctx.player.gold += CHANCELLOR_PRIZE
                await ctx.term.write(
                    f"\n  `2You Got It! The Chancellor Pays You `${CHANCELLOR_PRIZE} "
                    "`2Gold Coins\n"
                )
                await ctx.term.pause()
                return
            await ctx.term.write(
                "\n  `%Too Low!\n" if guess < target else "\n  `%Too High!\n"
            )

        await ctx.term.write("\n  `2You Didn't Get The Correct Number`%!\n")
        await ctx.term.pause()

    async def daily_maint(self, ctx: IgmMaintContext) -> None:
        for player in ctx.repo.all_players():
            ctx.store.delete(f"day:{player.id}")
