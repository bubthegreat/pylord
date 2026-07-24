"""The Town Square -- the hub scene every non-logoff action returns to.

lord.js's own town-square prompt (``reference/lord.js:16874-16902``,
function ``prompt()`` inside ``main()``) only emits a short heading plus a
letter list (``'  (F,S,K,A,H,V,I,T,Y,L,W,D,C,O,X,M,P,Q)'``, line 16881) and
then defers the actual menu *body* to an external asset the game loads with
``lrdfile('MAIN')`` (line 16900) -- that MAIN.ANS/MAIN.LRD file isn't part
of this repo, so there is no literal lord.js text to port line-for-line for
the full menu. The menu below is a faithful reconstruction of the classic
LORD town square menu wording/colors from lord.js's letter list and its
in-game function names (``king_arthurs()``, ``abduls_armour()``,
``turgons()``, ``slaughter_others()``, etc., all found near line 16960+),
using the same backtick color-code conventions (`` `2`` green body text,
`` `0`` bright-green highlight) the rest of lord.js's screens use.

Letters and where they go (lord.js's ``main()`` switch, :16942-17170):
``F``\\ orest, ``S``\\ laughter, ``K``\\ ing Arthur's, ``A``\\ bdul's,
``H``\\ ealer, ``V``\\ iew stats, ``I``\\ nn, ``T``\\ urgon's, ``Y``\\ e Old
Bank, ``L``\\ ist warriors, ``W``\\ rite mail, ``D``\\ aily news,
``C``\\ onjugality, ``O``\\ ther places (the IGM hub, :17003-17077),
``M`` announce (:17110), ``P`` who's on now (:17113), ``R`` read mail
(:16950), ``1`` game statistics (:17120), ``Q``\\ uit (:16853).

``X`` is this project's Dragon key rather than lord.js's expert-mode
toggle -- see ``docs/deviations.md``, which also records the two letters
lord.js has that this port doesn't reach (``2``/``3``/``4`` are RIP-only
no-ops there).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylord.engine.game import scene

if TYPE_CHECKING:
    from pylord.engine.game import GameCtx

_MENU_LINES = (
    "",
    "`2  The Town Square",
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-",
    "  `2(`0F`2)orest                      (`0L`2)ist Warriors",
    "  `2(`0S`2)laughter other players     (`0W`2)rite Mail",
    "  `2(`0K`2)ing Arthur's Weapons       (`0R`2)ead Mail",
    "  `2(`0A`2)bdul's Armour              (`0D`2)aily News",
    "  `2(`0H`2)ealer's Hut                (`0C`2)onjugality List",
    "  `2(`0V`2)iew your stats             (`0O`2)ther places",
    "  `2(`0I`2)nn                         (`0M`2)ake an announcement",
    "  `2(`0T`2)urgon's Warrior Training   (`0P`2)eople on now",
    "  `2(`0Y`2)e Old Bank                 (`01`2) Game statistics",
    "  `2(`0X`2) The Red Dragon            (`0Q`2)uit to fields",
    "",
)
_MENU = "\n".join(_MENU_LINES)

_PROMPT = "`2Your choice`0? `2"

# Letter -> next scene key.
_DESTINATIONS: dict[str, str] = {
    "F": "forest",
    "S": "pvp",
    "K": "weapons",
    "A": "armor",
    "H": "healer",
    "V": "stats",
    "I": "inn",
    "T": "training",
    "Y": "bank",
    "L": "list_warriors",
    "W": "mail",
    "R": "read_mail",
    "D": "news",
    "C": "conjugality",
    "O": "other_places",
    "M": "announce",
    "P": "who_is_on",
    "1": "game_stats",
    "X": "dragon",
}

_GOODBYE = (
    "\n`c\n\n  `%Quitting To The Fields...\n"
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
    "`2  You find a comfortable place to sleep under a small tree...\n\n"
)  # reference/lord.js:16832-16841 (goodbye())

# Values passed to TermIO.menu() only need to be present (its return value
# is always the matching *key*, never the value -- see TermIO.menu()'s
# docstring); human-readable labels here just aid debugging/readability.
_MENU_OPTIONS = {**_DESTINATIONS, "Q": "logoff"}


@scene("town")
async def town(ctx: GameCtx) -> str | None:
    p = ctx.player
    # reference/lord.js:16887-16895 -- menu() floors these three every
    # redraw, so a bug elsewhere can't leave a negative balance on screen.
    p.bank = max(0, p.bank)
    p.gold = max(0, p.gold)
    p.exp = max(0, p.exp)

    await ctx.io.write(_MENU)
    choice = await ctx.io.menu(_MENU_OPTIONS, _PROMPT)
    if choice != "Q":
        return _DESTINATIONS[choice]

    # reference/lord.js:16853-16871 (do_quit) -- confirm, then goodbye().
    confirm = await ctx.io.menu({"Y": "yes", "N": "no"}, "\n`2  Quit game?  [`0Y`2] : ")
    if confirm == "N":
        return "town"
    await ctx.io.write(_GOODBYE)
    return None
