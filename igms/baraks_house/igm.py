"""Barak's House -- pylord's "hello world" IGM (Task 15).

Barak is the official example IGM shipped with the original LORD IGM SDK
(the ``BARAK.EXE`` sample every real-world third-party IGM author cloned to
get started), written by Seth Able Robinson himself. The original DOS
binary's source is lost -- there is no surviving screen-by-screen transcript
to port line-for-line -- so this is a **recreation** built from the
historical description in this project's design docs/task brief (visiting
Barak and his "crazy mother"), not a byte-for-byte port of
``reference/lord.js`` (which, unlike the Inn/Forest/Town, never modeled any
IGM's internals -- IGMs were always a separate ``.EXE`` reached through the
``3RDPARTY.DAT`` handshake).

**Reconstruction notes (invented filler, since no original transcript
survives):**

* The five Barak quotes (``_QUOTES``) are invented flavor text -- no source
  records what Barak actually said.
* The couch-cushion gold find range (5-50 gold, ``_SEARCH_MIN``/``_MAX``) is
  an invented small-find range with no historical basis beyond "small gold
  find" in the brief.
* Barak's mother's chase-vs-soup split is a flat 50/50 (``ctx.rng.randrange(2)``)
  -- no record of the real odds, if any existed at all.
* The brief's *generic* six-IGM overview also mentions a "steal from Barak"
  event; this task's specific spec for Barak's House (given directly, not
  the generic overview) defines a five-item menu -- (T)alk/(S)earch/
  (A)sk to train/(M)other/(L)eave -- with no steal option. Omitted
  deliberately, not a gap.

**Daily-gate design.** ``ctx.enter()`` (:class:`~pylord.hooks.IgmContext`)
has no day-number access, so -- per the brief's own suggestion -- the couch
search and Barak's training use plain per-player boolean flags
(``couch:<player_id>`` / ``trained:<player_id>``) rather than day-suffixed
keys, and :meth:`BaraksHouse.daily_maint` (run once per game-day, see
``pylord/engine/daily.py``) clears every player's flags. This gets the same
"once per day" behavior as a day-suffixed key without needing a day number
inside ``enter()``.
"""

from __future__ import annotations

from pylord.hooks import IGM, IgmContext, IgmMaintContext

_MENU = (
    "\n  `5Barak's House   `8(? for menu)\n"
    "  `2(`0T`2)alk to Barak   (`0S`2)earch the couch cushions\n"
    "  `2(`0A`2)sk Barak to train you   (`0M`2)eet his mother   (`0L`2)eave\n"
)

# Invented flavor text -- see module docstring's Reconstruction notes.
_QUOTES = (
    "`0\"You know, I once found a whole gold piece under this couch!\"",
    "`0\"My mother says I should get a real job.  I told her IGMs ARE a real job!\"",
    "`0\"Careful in the forest today -- I hear the wolves are extra hungry!\"",
    "`0\"I used to be an adventurer like you, then I took a nap and never left.\"",
    "`0\"Don't mind mother, she's just protective.  Mostly of the couch.\"",
)

_SEARCH_MIN = 5
_SEARCH_MAX = 50


class BaraksHouse(IGM):
    key = "baraks_house"
    name = "Barak's House"
    author = "Seth Able Robinson"
    default_enabled = True

    async def enter(self, ctx: IgmContext) -> None:
        while True:
            await ctx.term.write(_MENU)
            choice = await ctx.term.menu(
                {
                    "T": "talk",
                    "S": "search",
                    "A": "train",
                    "M": "mother",
                    "L": "leave",
                },
                "  `2Your choice? : ",
            )
            if choice == "L":
                await ctx.term.write("\n  `2Barak waves as you head back outside.\n")
                return
            if choice == "T":
                await self._talk(ctx)
            elif choice == "S":
                await self._search(ctx)
            elif choice == "A":
                await self._train(ctx)
            elif choice == "M":
                chased_out = await self._mother(ctx)
                if chased_out:
                    return

    async def _talk(self, ctx: IgmContext) -> None:
        quote = ctx.rng.choice(_QUOTES)
        await ctx.term.write(f"\n  `2Barak leans back and says:\n  {quote}\n")
        await ctx.term.pause()

    async def _search(self, ctx: IgmContext) -> None:
        p = ctx.player
        gate = f"couch:{p.id}"
        if ctx.store.get(gate, False):
            await ctx.term.write(
                "\n  `2You've already checked every cushion on this couch today.\n"
            )
            await ctx.term.pause()
            return
        ctx.store.set(gate, True)
        found = ctx.rng.randint(_SEARCH_MIN, _SEARCH_MAX)
        p.gold += found
        await ctx.term.write(
            f"\n  `2You dig through the couch cushions and find `0{found} `2gold!\n"
        )
        await ctx.term.pause()

    async def _train(self, ctx: IgmContext) -> None:
        p = ctx.player
        gate = f"trained:{p.id}"
        if ctx.store.get(gate, False):
            await ctx.term.write(
                '\n  `2"Already trained you today, come back tomorrow!"`0 Barak says.\n'
            )
            await ctx.term.pause()
            return
        ctx.store.set(gate, True)
        p.strength += 1
        await ctx.term.write(
            "\n  `2Barak wrestles you around the yard for a while.\n"
            "  `0YOUR STRENGTH INCREASES BY 1!\n"
        )
        await ctx.term.pause()

    async def _mother(self, ctx: IgmContext) -> bool:
        """Returns ``True`` if the chase ends the visit."""
        p = ctx.player
        outcome = ctx.rng.randrange(2)
        if outcome == 0:
            await ctx.term.write(
                "\n  `4Barak's mother spots you and grabs her broom!\n"
                '  `4"GET OUT OF MY HOUSE!"`0 she shrieks, chasing you out the door!\n'
            )
            await ctx.term.pause()
            return True
        p.hp = p.hp + 2
        await ctx.term.write(
            "\n  `2Barak's mother smiles and ladles you a bowl of soup.\n"
            "  `0YOU RECOVER 2 HIT POINTS!\n"
        )
        await ctx.term.pause()
        return False

    async def daily_maint(self, ctx: IgmMaintContext) -> None:
        for player in ctx.repo.all_players():
            ctx.store.delete(f"couch:{player.id}")
            ctx.store.delete(f"trained:{player.id}")
