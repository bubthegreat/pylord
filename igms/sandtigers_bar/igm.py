"""Sandtiger's Bar -- the very first IGM ever written, by Gerald Yuvallos
(Task 16).

Like Barak's House, the original ``SANDTIGR.EXE`` binary's source is lost --
there is no surviving screen transcript of its dice/coin/cup games to port
line-for-line, and ``reference/lord.js`` never modeled any IGM's internals
(IGMs were always separate binaries reached through the ``3RDPARTY.DAT``
handshake, never part of the core game). This is a **recreation** built
from the historical description in this project's design docs/task brief.

**Reconstruction notes (invented filler):**

* Exact odds/payout math is invented where the brief only names the game:
  dice high/low is a fair player-die-vs-house-die roll (1-6 each), a tie is
  a push (bet fully refunded, i.e. no change) -- the brief doesn't specify
  tie handling, and "the house never grants free gold" (economy guard) rules
  out treating a tie as a win, so push was the only economy-neutral choice.
* Coin flip's payout curve (pot doubles on each win, forfeited entirely on
  a loss, cash out any time) is the standard double-or-nothing shape; no
  historical record of the exact original odds/prompts survives.
* "Guess the cup" 3x payout is implemented as: correct guess nets
  ``2 * bet`` profit (i.e. the player's total return is 3x the bet,
  matching the brief's "3x payout" literally), wrong guess loses the bet.
* The five Sandtiger tavern tales (``_STORIES``) are invented flavor text.
* The brief's *generic* six-IGM overview also mentions a "drink" option
  (gold -> temporary flavor); this task's specific spec for Sandtiger's Bar
  (given directly) enumerates exactly (D)ice/(C)oin/(G)uess/(S)tories/
  (L)eave with no drink option. Omitted deliberately, not a gap.

**Economy guard**: every bet is validated ``0 < bet <= gold on hand`` *and*
``bet <= player.level * 1000`` (the level-scaled max-bet cap from the
design spec, also used by the later LORD Gambling Casino IGM) -- the house
never grants free gold; a bet failing either check is refused before any
random outcome is rolled (no partial deduction).
"""

from __future__ import annotations

from pylord.hooks import IGM, IgmContext

_MENU = (
    "\n  `5Sandtiger's Bar   `8(? for menu)\n"
    "  `2(`0D`2)ice High/Low   (`0C`2)oin Flip   (`0G`2)uess The Cup\n"
    "  `2(`0S`2)tories   (`0L`2)eave\n"
)

_DIGITS = "0123456789"

# Invented flavor text -- see module docstring's Reconstruction notes.
_STORIES = (
    "`0\"Once I arm-wrestled a troll for his own arm.  I won.  He needed a hand.\"",
    "`0\"They say I once drank an ogre under the table.  The table didn't survive either.\"",
    "`0\"I've seen warriors come in green as spring grass and leave twice as broke.\"",
    "`0\"This bar's been robbed forty times.  Forty-one thieves left without their fingers.\"",
    "`0\"The dragon?  Personally?  No.  But I've heard it snore.  Terrifying stuff.\"",
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
        await ctx.term.write(f"\n  `2Sandtiger swirls his mug and tells you:\n  {tale}\n")
        await ctx.term.pause()
