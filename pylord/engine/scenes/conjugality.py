"""Conjugality List -- port of ``reference/lord.js``'s ``conjugality_list()``
(``:16207-16249``): every married pair in the realm, plus whoever currently
belongs to Violet or Seth Able.

**Player-to-player marriage** (``op.married_to``) is real on this project's
``Player`` model (``married_to``, ``pylord/models.py``) and this scene
displays it exactly like lord.js does, but nothing in this task's own scope
*sets* it -- lord.js's own player-to-player marriage path is the
interactive mail-based ``marry_mail()`` (reference/lord.js:4072-4208),
which ``mail.py``'s module docstring explains is out of scope for this
task. So a fresh install of this listing is expected to only ever show
Violet/Seth Able rows until a later task (PvP-adjacent player-to-player
romance) starts writing ``married_to``.

**NPC marriage** (Violet / Seth Able) uses the same global
``pylord/engine/npc_state.py`` helpers ``inn.py`` writes to.

The rotating "hitched with / attached to / ..." phrase list is ported
verbatim (reference/lord.js:16212-16213); each married pair is shown once
(guarded by ``i < op.married_to`` in lord.js, reference/lord.js:16225 --
this port uses the equivalent ``op.id < op.married_to``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylord.engine import npc_state
from pylord.engine.game import scene

if TYPE_CHECKING:
    from pylord.engine.game import GameCtx

_HEADER = (
    "\n                     `%** CONJUGALITY LIST **`2\n"
    "                    `2-=-=-=-=-=-=-=-=-=-=-=-=-\n\n"
)

_PHRASES = (
    "hitched with", "attached to", "in love with", "a love slave to",
    "smitten with love for", "in matrimony with", "in marital bliss with",
    "wedded to",
)


@scene("conjugality")
async def conjugality(ctx: GameCtx) -> str:
    await ctx.io.write(_HEADER)
    players = await ctx.repo.all_players()
    by_id = {p.id: p for p in players}
    married_to_violet = await npc_state.married_to_violet(ctx.db)
    married_to_seth = await npc_state.married_to_seth(ctx.db)

    some = False
    phrase_i = 0
    for p in players:
        if p.married_to is not None and p.married_to > -1 and p.id < p.married_to:
            spouse = by_id.get(p.married_to)
            if spouse is not None:
                some = True
                phrase = _PHRASES[phrase_i % len(_PHRASES)]
                phrase_i += 1
                await ctx.io.write(f"  `0{p.name} `2is {phrase} `0{spouse.name}`2.\n")
        if p.id == married_to_seth:
            some = True
            await ctx.io.write(f"  `0{p.name} `2is the property of `0Seth Able`2.\n")
        if p.id == married_to_violet:
            some = True
            await ctx.io.write(f"  `0{p.name} `2belongs to `0Violet`2.\n")

    if not some:
        await ctx.io.write("  `%No one is married in this realm.\n")
    await ctx.io.pause()
    return "town"
