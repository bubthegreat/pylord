"""Pickle's -- the Pickle Goddess's magic garden, and a stacked deck.

**This one is a port, not a recreation.** Source:
``reference/igm-sources/synchronet/pickle/pickle.js`` ("Other Places
Pickles" for LORD 5.00 JS, by The Lizard Master). Line references below are
into that file. Its two screens are the originals, copied to ``screens/``.

Pick a row of the garden, eat what grows there, and gain or lose a
percentage of one randomly chosen attribute. The author's own README
describes the odds as stacked "in a Las Vegas slot machine way" -- and they
are: 52 outcomes in 100 are bad, 48 good (``:35-38``).

**Three faithfully-ported flaws, all of them the original's.**

1. *No daily limit.* The source runs one pickle and exits (``:141``); there
   is no per-day record and nothing stops a player walking straight back
   in. The house edge only wins on a player who keeps eating -- one who
   re-enters until a favourable roll lands on the attribute they care
   about, then stops, ratchets it upward for free. This port does not add
   a gate, because adding one would be inventing balance the original
   never had. Like every bundled IGM it ships **on**, so a realm that
   wants that gate should turn the IGM off in ``config.toml`` rather than
   expect the port to invent one.
2. *Row 10 is a lie.* The prompt offers rows 1-9 (``:19``) but the
   validation loop accepts 1-10 (``:23``), and the percentage is built by
   string concatenation -- ``'.0' + row`` (``:33``) -- so row 10 reads
   ``.010``, i.e. 1%, identical to row 1. "The higher you go, the more
   potent the pickle" holds for 1-9 and then silently resets. See
   :data:`ROW_MAX` and :func:`row_pct`.
3. *The tattoo eats your description.* Outcome 10 overwrites the player's
   Dark Cloak Tavern self-description (``:127``, ``des1``, which is
   ``Player.description1`` here) with a fixed line. The original does the
   same; the text a player wrote about themselves is simply gone.

All three are recorded in ``docs/deviations.md``.
"""

from __future__ import annotations

from pylord.hooks import IGM, IgmContext
from pylord.terminal import load_screen

#: The validation loop's real bound (``pickle.js:23``) -- not the 1-9 the
#: prompt advertises.
ROW_MAX = 10
#: ``random(100) + 1 >= 49`` is a bad pickle (``pickle.js:35-38``): 52 of
#: 100 outcomes, the house edge the author's README describes.
BAD_FROM = 49
#: The line the Goddess tattoos over ``description1`` (``pickle.js:127``).
TATTOO = "I have been tagged pwned by the Pickle Goddess!"
#: ``schema.py`` gives ``description1`` 255 characters.
DESCRIPTION_MAXLEN = 255

#: ``random(10) + 1`` picks the attribute (``pickle.js:39-115``). Index 10
#: is the tattoo and has no attribute, so it is absent here.
_ATTRIBUTES: dict[int, tuple[str, str]] = {
    1: ("hp", "hit points"),
    2: ("hp_max", "max hitpoints"),
    3: ("forest_fights", "forest fights"),
    4: ("gold", "gold"),
    5: ("bank", "bank gold"),
    6: ("defense", "defense"),
    7: ("strength", "strength"),
    8: ("charm", "charm"),
    9: ("gems", "gems"),
}
_TATTOO_ROLL = 10


def row_pct(row: int) -> float:
    """The fraction of an attribute a row's pickle moves.

    A literal port of ``pickle.js:33`` -- ``pctGainLost = '.0' + tempnum``
    -- string concatenation, not arithmetic. Rows 1-9 give 0.01 through
    0.09; **row 10 gives 0.01 again**, because ``'.0' + '10'`` is
    ``'.010'``. Reproduced deliberately; see this module's docstring.
    """
    return float(".0" + str(row))


class Pickles(IGM):
    key = "pickle"
    name = "Pickle's"
    author = "The Lizard Master"
    default_enabled = True

    async def enter(self, ctx: IgmContext) -> None:
        await ctx.term.write(
            "\n\n  `5Welcome Other Places Pickles's!\n"
            "  `2Home of the Pickle Goddess!\n\n"
        )
        await self._screen(ctx, "pickle.ans")
        await ctx.term.pause()

        await self._screen(ctx, "garden.ans")
        await ctx.term.write(
            "\n  `5The Pickle Goddess has decided to allow you to\n"
            "  `5pick a Pickle from her garden! But choose wisely,\n"
            "  `5Not all are great choices!  The higher you go,\n"
            "  `5The more potent the pickle!\n"
        )
        row = await self._read_row(ctx)
        if row is None:
            await ctx.term.write("\n  `2You leave the garden unpicked.\n")
            return

        pct = row_pct(row)
        good = ctx.rng.randrange(100) + 1 < BAD_FROM
        roll = ctx.rng.randrange(10) + 1

        if roll == _TATTOO_ROLL:
            ctx.player.description1 = TATTOO[:DESCRIPTION_MAXLEN]
            await ctx.term.write(
                "\n  `5You have been marked by tattoo from the Pickle Goddess!\n"
            )
            await ctx.term.pause()
            return

        field, label = _ATTRIBUTES[roll]
        current = getattr(ctx.player, field)
        delta = int(current * pct)

        if delta == 0:
            await ctx.term.write(
                "\n  `5You were about to... \n"
                f"  `5{'gain' if good else 'lose'} something, but you do not have "
                f"enough {label}!\n"
                "  `5Come back later when you level up or have more stuff... \n"
            )
            await ctx.term.pause()
            return

        setattr(ctx.player, field, current + delta if good else current - delta)
        await ctx.term.write(
            f"\n  `5This pickle is divine! Your {label} increased by {delta}!\n"
            if good
            else f"\n  `5This pickle taste like poo! Your {label} decreased by {delta}!\n"
        )
        await ctx.term.pause()

    async def _screen(self, ctx: IgmContext, filename: str) -> None:
        """Draw one of the original ``.ANS`` screens, if it is there.

        A missing or unreadable art file is not worth failing a visit over
        -- the IGM plays fine without it, and a raised exception here would
        roll the whole visit back.
        """
        if self.dir is None:
            return
        try:
            await ctx.term.write_screen(load_screen(self.dir / "screens" / filename))
        except OSError:
            return

    async def _read_row(self, ctx: IgmContext) -> int | None:
        """Prompt for a garden row until one in ``1..ROW_MAX`` is given.

        The source loops forever on bad input (``:11-23``) with no way out;
        a blank line leaves here instead, so a confused player is not
        trapped in the garden.
        """
        first = True
        while True:
            if not first:
                await ctx.term.write("\n  `2Must be a choice from 1-9!\n")
            first = False
            entered = (
                await ctx.term.readline(
                    "\n  `2Which row would you like to pick from?\n  ", maxlen=2
                )
            ).strip()
            if entered == "":
                return None
            if entered.isascii() and entered.isdigit() and 1 <= int(entered) <= ROW_MAX:
                return int(entered)
