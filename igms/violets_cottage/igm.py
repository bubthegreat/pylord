"""Violet's Cottage -- home of Violet's family, by Trevor Herndon (Task 17).

Like the other two starter-six IGMs in this batch, the original binary's
source is lost -- no surviving screen transcript exists to port
line-for-line, and ``reference/lord.js`` never modeled any IGM's internals
(IGMs were always separate ``.EXE`` files reached through the
``3RDPARTY.DAT`` handshake). This is a **recreation** built from the
historical description in this project's design docs/task brief.

**Reconstruction notes (invented filler):**

* The charm-check for "impress her parents" is a flat 50/50
  (``ctx.rng.randrange(2)``) -- no record of the real odds survives.
* The tea heal amount (+2 hp) and kids-play exp (flat +10, not
  level-scaled -- the brief explicitly calls for "flat +10 exp", no
  level-scaling invention) are both taken directly from the brief.
* All flavor/dialogue text is invented.

**Married-to-Violet detection, and why it's a day-old cache.**
:class:`~pylord.hooks.IgmContext` (what ``enter()`` receives) deliberately
exposes no raw database connection -- only ``player``/``term``/``store``/
``rng``/``mail``/``news``/``other_players`` (see ``pylord/hooks.py``'s
module docstring: the guardrailed façade is scoped on purpose). But
"married to Violet" is *global* NPC-marriage state living in the
``game_state`` table (``pylord/engine/npc_state.py``, written by the Inn's
``_marriage_violet()``), not a field on ``Player`` at all -- so it isn't
reachable through ``ctx.player`` either.

:class:`~pylord.hooks.IgmMaintContext` (what :meth:`daily_maint` receives)
*does* expose ``.conn``/``.repo`` (there's no visiting player to guard
there), so this IGM bridges the two: once a day, :meth:`daily_maint` asks
``npc_state.married_to_violet`` who (if anyone) is married to Violet and
caches a per-player boolean (``married_violet:<player_id>``) in its own
store; :meth:`enter` just reads that cached flag. The practical effect is
a same-day lag between actually marrying Violet at the Inn and this
cottage noticing -- deliberate and documented rather than reaching past
the guardrail (e.g. via the context's private ``_gctx`` attribute) to get
same-visit freshness.
"""

from __future__ import annotations

from pylord.engine import npc_state
from pylord.hooks import IGM, IgmContext, IgmMaintContext

_MENU = (
    "\n  `5Violet's Cottage   `8(? for menu)\n"
    "  `2(`0I`2)mpress her parents   (`0T`2)ea with Grandma   (`0P`2)lay with the kids\n"
    "  `2(`0L`2)eave\n"
)


class VioletsCottage(IGM):
    key = "violets_cottage"
    name = "Violet's Cottage"
    author = "Trevor Herndon"
    default_enabled = True

    async def enter(self, ctx: IgmContext) -> None:
        p = ctx.player
        if ctx.store.get(f"married_violet:{p.id}", False):
            await self._celebration(ctx)
            return

        while True:
            await ctx.term.write(_MENU)
            choice = await ctx.term.menu(
                {"I": "impress", "T": "tea", "P": "play", "L": "leave"},
                "  `2Your choice? : ",
            )
            if choice == "L":
                await ctx.term.write(
                    "\n  `2You wave goodbye to Violet's family and head outside.\n"
                )
                return
            if choice == "I":
                await self._impress(ctx)
            elif choice == "T":
                await self._tea(ctx)
            elif choice == "P":
                await self._play(ctx)

    async def _celebration(self, ctx: IgmContext) -> None:
        p = ctx.player
        gate = f"celebrated:{p.id}"
        if ctx.store.get(gate, False):
            await ctx.term.write(
                "\n  `2Violet's family welcomes you warmly, as always.\n"
            )
        else:
            ctx.store.set(gate, True)
            p.charm += 1
            await ctx.term.write(
                "\n  `2Violet's family throws their arms around you, thrilled to\n"
                "  finally have you as part of the family!\n"
                "  `0YOUR CHARM INCREASES BY 1!\n"
            )
        await ctx.term.pause()

    async def _impress(self, ctx: IgmContext) -> None:
        p = ctx.player
        gate = f"impress:{p.id}"
        if ctx.store.get(gate, False):
            await ctx.term.write(
                "\n  `2You've already tried to impress her parents enough for one day.\n"
            )
            await ctx.term.pause()
            return
        ctx.store.set(gate, True)
        outcome = ctx.rng.randrange(2)
        if outcome == 0:
            p.charm += 1
            await ctx.term.write(
                "\n  `2Her parents are charmed by your manners!\n"
                "  `0YOUR CHARM INCREASES BY 1!\n"
            )
        else:
            p.charm -= 1
            await ctx.term.write(
                "\n  `4You trip over the rug and knock over grandma's teapot!\n"
                "  `4YOUR CHARM DECREASES BY 1!\n"
            )
        await ctx.term.pause()

    async def _tea(self, ctx: IgmContext) -> None:
        p = ctx.player
        gate = f"tea:{p.id}"
        if ctx.store.get(gate, False):
            await ctx.term.write(
                "\n  `2Grandma's teapot is empty for today.\n"
            )
            await ctx.term.pause()
            return
        ctx.store.set(gate, True)
        p.hp = p.hp + 2
        await ctx.term.write(
            "\n  `2Grandma pours you a warm cup of tea and tells old stories.\n"
            "  `0YOU RECOVER 2 HIT POINTS!\n"
        )
        await ctx.term.pause()

    async def _play(self, ctx: IgmContext) -> None:
        p = ctx.player
        gate = f"play:{p.id}"
        if ctx.store.get(gate, False):
            await ctx.term.write(
                "\n  `2The kids are worn out from playing with you earlier today.\n"
            )
            await ctx.term.pause()
            return
        ctx.store.set(gate, True)
        p.exp += 10
        await ctx.term.write(
            "\n  `2You spend a while playing games with Violet's little siblings.\n"
            "  `0YOU RECEIVE 10 EXPERIENCE!\n"
        )
        await ctx.term.pause()

    async def daily_maint(self, ctx: IgmMaintContext) -> None:
        married_id = npc_state.married_to_violet(ctx.conn)
        for player in ctx.repo.all_players():
            ctx.store.delete(f"impress:{player.id}")
            ctx.store.delete(f"tea:{player.id}")
            ctx.store.delete(f"play:{player.id}")
            ctx.store.set(f"married_violet:{player.id}", married_id == player.id)
