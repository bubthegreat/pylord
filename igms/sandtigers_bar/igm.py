"""Sandtiger's Bar -- the very first IGM ever written per this project's
design brief, by Gerald Yuvallos (Task 16; audited against the real Turbo
Pascal source in Task 2, mirroring the just-completed Barak's House audit).

Task 16 built this as a **recreation** from the historical description in
this project's design docs/task brief, believing the original source lost.
Task 2's audit found a real, released Pascal source in
``igms_to_port/sandsrc.zip``: ``SANDBAR.PAS``/``SBARADD.PAS``, "Full Source
Code To SandBar v1.02" (1995, Sons of Salami Software Group, credited to
Joseph Masters per the archive's ``FILE_ID.DIZ``/``SANDSRC.DOC``). Its own
one-line blurb calls it "The first LORD IGM returns in a virtually bugless
state" -- i.e. this is very likely a *rewrite* reviving the original
Sandtiger's Bar concept, not Gerald Yuvallos's literal lost original binary
(which, per the historical premise this task started from, still hasn't
surfaced). Either way, this audit treats ``SANDBAR.PAS``/``SBARADD.PAS`` as
the recorded source of record for numbers/flows -- the ``author`` field is
left as the brief's "Gerald Yuvallos" pending firmer provenance, since
neither name is provably wrong for the *original* concept's authorship.

**Direct-port-verified: this real source is a vastly bigger, structurally
different program than this recreation's three simple gambling games.**
The real ``SANDBAR.EXE`` runs on its own currency, **BarCoins**: entering
the bar mandatorily converts 100% of the player's gold+bank into BarCoins
at a sysop-configured exchange rate (``opening()``, ``SANDBAR.PAS``
:443-494), and leaving converts whatever's left back to gold (``menu()``'s
``L`` case, :2604-2615) -- no gold ever touches a table directly. Once
inside, "(H)it the gambling table" rolls a *random* one of three full card
games against a fixed cast of six named NPC opponents each -- Blackjack
(``blackjack``, :1803-2246), Five Card Draw poker (``fivecard``,
``SBARADD.PAS`` :283-747), and Elimination (``elimination``, :2248-2507) --
with tiered multi-way payouts (e.g. Blackjack/poker pay ``bet*7`` back if no
NPC also "stays in" with a beating hand, down through smaller splits, to a
total loss if enough do; Elimination pays 200%/150%/100% of bet for
1st/2nd/3rd place, nothing below that). None of this -- the NPC opponents,
the card mechanics, the tiered multi-way payouts, or the BarCoin economy
itself -- has anything in common with a simple player-vs-house dice/coin/cup
pick, so none of it can be "adopted" into this recreation's numbers; see
``docs/deviations.md`` for the full disclosure of what isn't ported.

* **(S)tories** -- adopted verbatim. The real ``talksandtiger()``
  (``SBARADD.PAS`` :907-1244) is a keyword-driven free-text chat with
  Sandtiger himself (gated behind buying him a drink each exchange,
  ``drinkcheck()``) whose ``HIST``/``STOR`` branch offers exactly four
  story picks (:1065-1068). ``_STORIES`` now holds all four, transcribed
  verbatim (paragraph breaks kept; the original's mid-story
  ``moreprompt()`` pauses are collapsed into a single write + a single
  pause -- the same "stitched together without their original branching
  consequences" simplification Barak's House's ``_QUOTES`` used for its
  own verbatim lines): Halder's Story, The Barak Life, Aragorn vs.
  Olodrin, and Chance's Exile. Previously five invented one-line flavor
  quips with no source counterpart at all.

**Still invented (no portable SANDBAR.PAS/SBARADD.PAS equivalent):**

* **(D)ice High/Low**, **(C)oin Flip double-or-nothing**, and **(G)uess The
  Cup** 3x payout -- none of the real source's three games is dice-,
  coin-, or cup-based (they're Blackjack/Five Card Draw/Elimination, all
  against fixed NPC fields, see above), so there is no source formula to
  adopt for any of the three. Kept invented.
* **Max-bet cap** ``player.level * 1000`` **gold** -- the source's
  ``maxbet`` config default is a flat ``1000000`` **BarCoins**, with no
  ``L`` level-scaling token (unlike ``curse``/``mindfry``/``dwarf``/
  ``abandonment``'s ``L*L*L*L*<n>`` formulas, default config written by
  ``cfgin`` at ``SANDBAR.PAS`` :301-317), wagered in a currency exchanged
  from gold at a separately sysop-configured, *also* level-scaled rate
  (``gp``) this port doesn't model. No comparable flat-gold figure can be
  derived without inventing the sysop's exchange-rate config too; kept as
  this recreation's own invented, level-scaled cap.

**Not ported** (real SANDBAR.PAS/SBARADD.PAS content with no equivalent in
this recreation, beyond the three real gambling games and the BarCoin
economy noted above): the mandatory forest-fight cost and once-per-day
play-count gate to enter at all (``opening()``/``chktheboy``, ``epd``/
``sandbar.dat``'s ``intoday``/``ltoday`` arrays, :443-454/:2663-2696); the
Black Market (``blackmarket``, :708-1521) -- permanent HP/STR/DEF/CHA
purchases, name change, sex change, class change, forest-fight and
player-fight purchases, gem/exp purchases, a one-way "protection" purchase
that ends the session outright, and a 6-tier weapon/armor shop; the Old
Witch (``oldwitch``, :1526-1798) -- PvP curse/mind-fry/dwarf/abandonment
hexes, each mailing the victim a stat penalty and the caster's name;
Sandtiger's free-text keyword chat (LORD/VIOLET/DRAGON/SETH/GOD/HELLO/
curse-word/CHEAT easter-egg replies, ``SBARADD.PAS`` :907-1244) and its
per-exchange drink-purchase gate (``drinkcheck``, :752-875, six drink tiers
3-1000 BarCoins).

**Economy guard**: every bet is validated ``0 < bet <= gold on hand`` *and*
``bet <= player.level * 1000`` (this recreation's own invented cap, see
above) -- the house never grants free gold; a bet failing either check is
refused before any random outcome is rolled (no partial deduction).
"""

from __future__ import annotations

from pylord.hooks import IGM, IgmContext

_MENU = (
    "\n  `5Sandtiger's Bar   `8(? for menu)\n"
    "  `2(`0D`2)ice High/Low   (`0C`2)oin Flip   (`0G`2)uess The Cup\n"
    "  `2(`0S`2)tories   (`0L`2)eave\n"
)

_DIGITS = "0123456789"

# Verbatim tales lifted from SBARADD.PAS's talksandtiger()/HIST branch (the
# only four stories Sandtiger tells, SBARADD.PAS :1065-1223) -- see module
# docstring. Paragraph breaks kept; the original's mid-story moreprompt()
# pauses are collapsed into this recreation's single write + single pause.

_HALDERS_STORY = """`2Halder was born in Devonshire.  His parents were both
quite wealthy, and gave him everything he ever needed.
However, this is not the way to raise a budding young
warrior, and Halder was spoiled rotten.  He began to
visit the nightclubs daily, not do his work, and got
very lazy.

Indeed, his parents got quite worried about him.  His
younger sister, Yundra, wandered off one day into the woods
-- near the dragon's den.  Halder was sent off in search
her, and when he returned, he said he had searched the cave
and found nothing inside it.

However, Halder was lying.  He had, in fact, gone back
to the Fox's Den bar immediately after setting off.  And
thus caused the death of his poor sister.

Turgon found out about this incident, and became enraged
that a warrior under his training had done such a thing.
The first moment Turgon got, he found Halder, and backed
him into a corner, a Death Sword at his neck.  As Turgon
was to make the killing blow, Barak, then the level one
master, came up to them.

`0"Whatcha doin'?"`2 he asked, innocently snapping
the sassafras gum in his mouth.

Turgon turned to him, and then back to Halder.

`0"No,"`2 he said, `0"I will not kill you.  Instead,
you will be ranked underneath Barak, and must take orders
from him."`2

And that is why Halder, the rich child, cannot kill or
or hurt the gentle Barak."""

_BARAK_LIFE_STORY = """`2My child, you seem interested in Barak.  Well, everyone
is, but we really know little about him.  Perhaps some of the
sages in another town might know.  But no one really knows
where he comes from.  And we're not quite sure if he does,
either."""

_ARAGORN_VS_OLODRIN_STORY = """`0It all really started on a warm summer day.  But it's
been very cold ever since.

`2It was the big day at school.  Aragorn's girlfriend,
Tybet, had taken up with Olodrin.  And Aragorn had challenged
the thief to a fight.  It was time.

Aragorn circled 'round his opponent as Olodrin followed
with his eyes.  The first punch was thrown, and Aragorn's
fist met Olodrin's forehead.  Olodrin tried to throw a
haymaker, but was stopped in mid-stride by Aragorn, who
kicked him in the stomach.  With an "OOF!", Olodrin stumbled
backward.  Aragorn followed with a swift kick to the head
and Olodrin crumpled to the ground.  Aragorn knelt down next
to him, and slowly withdrew his dagger, a present of his
father's.

But before Aragorn could slice, a great THUD! was heard.
A scream in unison, THE DRAGON!!! was next.  Aragorn
started heading in the direction of the crowd, but Olodrin
was oblivious.  Tybet tripped and fell on her way down the
hill to outrun the Dragon.

Aragorn saw her crumpled body, and ran back to go get her,
but as he reached her body, the Dragon was upon them.

Suddenly, the oddest sound came from the Dragon's fire-
breathing mouth.  A...  cry of pain?  It did an about-face,
and tore back towards its cave, blood dripping from its tail.

Olodrin slumped back onto the grass.  The dagger that was
meant to end his life had saved the life of his would-be
murderer.

`0"Damn, that thing can sure run with half its tail
draggin' on the ground behind it."`2 he said weakly.

Aragorn just sat down next to him, and held out his hand.
Olodrin placed his in Aragorn's.

`0Now, of course, they're both grown up, but they're as
close as that, still.  Oh, and Tybet?  She's married to Prince
Caspian now.  But that's another story."""

_CHANCES_EXILE_STORY = """`2Chance.  Now there's a fine man.  And an even finer
daughter, if I do say so myself.  But his story is sad, it
makes one wonder how he can stay so happy.

It dates back to the time of Replogle, the former leader
-- or rather, level 12 leader -- of the realm.  Before he
got eaten by the Dragon, that is.

You see, Replogle had two sons, Jeffrey and Chance.  Both
studied to be warriors.  But Jeffrey, oh, Jeffrey was a ladies'
man, and he loved the women.  He also began a small gambling
group in his father's temple every Sunday.  And when Replogle
heard of this, he kicked his son out of the house.  And his son
ended up on the Innkeeper's door.

Chance, being the good son, forgot about his scandalous brother,
and worked his way to being an excellent fighter, and reached level
nine in no time at all.

Meanwhile, Jeffrey worked for the Innkeeper, and decided that what
needed to be added to the Inn was a bar.  And since his father, the
most honorable warrior in all the land, did not come to the Inn, he
felt he would be safe running it.  And the bar flourished.  The
Innkeeper earned more money than he would ever need, and in this
manner, he helped his son, a young man called Turgon, through
warrior training.  Now Turgon was the best fighter the realm
had ever seen, better than Replogle.  And Replogle knew he had to
prove his worth -- by going after the dragon.

And he did... and so he perished.

Now Turgon owed a lot to Jeffrey, now called The Bartender, for
helping him become the youngest level 12 warrior ever, and the
youngest master ever.  So he granted Jeffrey one wish.  And Jeffrey,
who's hate for his brother was ever so strong, ordered Chance banned
from the realm.

Chance, with no other choice, packed up for the forest.  And
even though he lived on berries and twigs for 3 years, he eventually
came upon a wide clearing -- invisible from all angles, but something
a horse might find quite easily.  And he began building, with whole
trees, and using sap for cement.  But it has worked, and even though
he cannot offer the same delicacies as Jeffrey's place, Chance has
a nice bar.... and a nice daughter!"""

_STORIES = (
    _HALDERS_STORY,
    _BARAK_LIFE_STORY,
    _ARAGORN_VS_OLODRIN_STORY,
    _CHANCES_EXILE_STORY,
)


class SandtigersBar(IGM):
    key = "sandtigers_bar"
    name = "Sandtiger's Bar"
    author = "Gerald Yuvallos"
    default_enabled = True

    async def enter(self, ctx: IgmContext) -> None:
        while True:
            await ctx.term.write(_MENU)
            choice = await ctx.term.menu(
                {"D": "dice", "C": "coin", "G": "cup", "S": "stories", "L": "leave"},
                "  `2Your choice? : ",
            )
            if choice == "L":
                await ctx.term.write("\n  `2Sandtiger nods as you head for the door.\n")
                return
            if choice == "D":
                await self._dice(ctx)
            elif choice == "C":
                await self._coin_flip(ctx)
            elif choice == "G":
                await self._guess_cup(ctx)
            elif choice == "S":
                await self._stories(ctx)

    async def _prompt_bet(self, ctx: IgmContext) -> int | None:
        p = ctx.player
        max_bet = p.level * 1000
        await ctx.term.write(
            f"\n  `2You have `0{p.gold} `2gold on hand.  (Max bet: `0{max_bet}`2)\n"
        )
        raw = await ctx.term.readline(
            "  `0How much gold will you wager? : ", maxlen=10, charset=_DIGITS
        )
        bet = int(raw) if raw else 0
        if bet <= 0:
            await ctx.term.write("\n  `2You decide not to bet after all.\n")
            return None
        if bet > p.gold:
            await ctx.term.write("\n  `4You don't have that much gold on you!\n")
            return None
        if bet > max_bet:
            await ctx.term.write(
                f"\n  `4Sandtiger refuses a bet over `0{max_bet} `4gold!\n"
            )
            return None
        return bet

    async def _dice(self, ctx: IgmContext) -> None:
        p = ctx.player
        bet = await self._prompt_bet(ctx)
        if bet is None:
            return
        player_roll = ctx.rng.randint(1, 6)
        house_roll = ctx.rng.randint(1, 6)
        await ctx.term.write(
            f"\n  `2You roll a `0{player_roll}`2.  Sandtiger rolls a `0{house_roll}`2.\n"
        )
        if player_roll > house_roll:
            p.gold += bet
            await ctx.term.write(f"  `0YOU WIN `2{bet} `0GOLD!\n")
        elif player_roll < house_roll:
            p.gold -= bet
            await ctx.term.write(f"  `4YOU LOSE `0{bet} `4GOLD!\n")
        else:
            await ctx.term.write("  `2A tie!  Sandtiger slides your bet back to you.\n")
        await ctx.term.pause()

    async def _coin_flip(self, ctx: IgmContext) -> None:
        p = ctx.player
        bet = await self._prompt_bet(ctx)
        if bet is None:
            return
        p.gold -= bet
        pot = bet
        while True:
            flip = ctx.rng.randrange(2)
            if flip != 0:
                await ctx.term.write(
                    f"\n  `4The coin comes up against you!  You lose your `0{pot} `4gold pot!\n"
                )
                await ctx.term.pause()
                return
            pot *= 2
            choice = await ctx.term.menu(
                {"C": "continue", "K": "cashout"},
                f"\n  `0The coin favors you!  Your pot is now `2{pot} `0gold.\n"
                "  `2(`0C`2)ontinue flipping   (`0K`2)eep your winnings : ",
            )
            if choice == "K":
                p.gold += pot
                await ctx.term.write(f"\n  `0You walk away with `2{pot} `0gold!\n")
                await ctx.term.pause()
                return

    async def _guess_cup(self, ctx: IgmContext) -> None:
        p = ctx.player
        bet = await self._prompt_bet(ctx)
        if bet is None:
            return
        await ctx.term.write(
            "\n  `2Sandtiger shuffles three cups on the bar top...\n"
        )
        choice = await ctx.term.menu(
            {"1": "1", "2": "2", "3": "3"}, "  `0Which cup hides the coin? [1-3] : "
        )
        correct = ctx.rng.randint(1, 3)
        if int(choice) == correct:
            winnings = bet * 2
            p.gold += winnings
            await ctx.term.write(
                f"\n  `0You guessed right!  YOU WIN `2{winnings} `0GOLD!\n"
            )
        else:
            p.gold -= bet
            await ctx.term.write(
                f"\n  `4Wrong cup!  It was cup `0{correct}`4.  You lose `0{bet} `4gold.\n"
            )
        await ctx.term.pause()

    async def _stories(self, ctx: IgmContext) -> None:
        tale = ctx.rng.choice(_STORIES)
        await ctx.term.write(f"\n  `2Sandtiger settles in and tells you the tale:\n\n{tale}\n")
        await ctx.term.pause()
