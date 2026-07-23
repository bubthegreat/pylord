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

Destinations not yet implemented by an earlier/this task (everything except
``stats`` and the town loop itself) route to a single shared "coming soon"
stub scene (see ``_stub`` below) until their own task lands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylord.engine.game import SCENES, scene

if TYPE_CHECKING:
    from pylord.engine.game import GameCtx

_MENU_LINES = (
    "",
    "`2  The Town Square",
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-",
    "  `2(`0F`2)orest",
    "  `2(`0S`2)laughter other players",
    "  `2(`0K`2)ing Arthur's Weapons",
    "  `2(`0A`2)bdul's Armour",
    "  `2(`0H`2)ealer's Hut",
    "  `2(`0V`2)iew your stats",
    "  `2(`0I`2)nn",
    "  `2(`0T`2)urgon's Warrior Training",
    "  `2(`0Y`2)e Old Bank",
    "  `2(`0L`2)ist Warriors",
    "  `2(`0W`2)rite Mail",
    "  `2(`0D`2)aily News",
    "  `2(`0C`2)onjugality List",
    "  `2(`0O`2)ther places",
    "  `2(`0X`2) The Red Dragon",
    "  `2(`0Q`2)uit to fields",
    "",
)
_MENU = "\n".join(_MENU_LINES)

_PROMPT = "`2Your choice`0? `2"

# Letter -> next scene key. Faithful to lord.js's letter list (line 16881);
# everything but Forest/Stats/Quit is an "under construction" stub until
# its own task lands.
_DESTINATIONS: dict[str, str | None] = {
    "F": "forest",
    "S": "pvp_stub",
    "K": "weapons_stub",
    "A": "armor_stub",
    "H": "healer_stub",
    "V": "stats",
    "I": "inn_stub",
    "T": "training_stub",
    "Y": "bank_stub",
    "L": "list_stub",
    "W": "mail_stub",
    "D": "news_stub",
    "C": "conjugality_stub",
    "O": "other_stub",
    "X": "dragon_stub",
    "Q": None,
}

# Values passed to TermIO.menu() only need to be present (its return value
# is always the matching *key*, never the value -- see TermIO.menu()'s
# docstring); human-readable labels here just aid debugging/readability.
_MENU_OPTIONS = {key: (dest or "logoff") for key, dest in _DESTINATIONS.items()}


@scene("town")
async def town(ctx: GameCtx) -> str | None:
    await ctx.io.write(_MENU)
    choice = await ctx.io.menu(_MENU_OPTIONS, _PROMPT)
    return _DESTINATIONS[choice]


async def _stub(ctx: GameCtx) -> str:
    """Shared placeholder for every town destination not yet implemented."""
    await ctx.io.write("\n`%Under construction.`0\n")
    await ctx.io.pause()
    return "town"


for _key in (
    "pvp_stub",
    "weapons_stub",
    "armor_stub",
    "healer_stub",
    "inn_stub",
    "training_stub",
    "bank_stub",
    "list_stub",
    "mail_stub",
    "news_stub",
    "conjugality_stub",
    "other_stub",
    "dragon_stub",
):
    SCENES[_key] = _stub
