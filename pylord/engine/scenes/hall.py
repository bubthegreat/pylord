"""Hall of Honors -- port of ``reference/lord.js``'s ``rank_king()``
(``:15612-15647``), the dragon-slayer leaderboard ("Heroes Of The Realm").

Not reachable from any town-square letter this project wires up -- see
``list_warriors.py``'s module docstring for why (lord.js nests it inside
Turgon's Training's un-ported `` `V`iew rankings`` key). Reached instead as
a submenu of List Warriors (`` `H` ``).

lord.js's ``drag_kills`` (a per-player dragon-kill counter) is this
project's ``Player.king_count`` (same concept -- see ``pylord/models.py``);
sort order (dragon kills desc, then level desc, then exp desc) and the
"no heroes yet" empty-state line are both ported verbatim
(reference/lord.js:15622-15630, 15643-15645).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylord.engine.game import scene

if TYPE_CHECKING:
    from pylord.engine.game import GameCtx

_HEADER = (
    "\n\n                       `%Heroes Of The Realm`2\n\n"
    "  `0Name                       Heroic Deeds Done         Current Level\n"
    "`2-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
)


@scene("hall")
async def hall(ctx: GameCtx) -> str:
    heroes = [p for p in ctx.repo.all_players() if p.king_count > 0]
    heroes.sort(key=lambda p: (p.king_count, p.level, p.exp), reverse=True)

    await ctx.io.write(_HEADER)
    if not heroes:
        await ctx.io.write(
            "  `0Sad times indeed, there are no heroes in this realm.\n"
        )
    for p in heroes:
        await ctx.io.write(
            f"`0  {p.name:<22}           `%{p.king_count:>3}                       "
            f"`0{p.level:>2}\n"
        )
    await ctx.io.pause()
    return "town"
