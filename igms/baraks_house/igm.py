"""Barak's House -- pylord's "hello world" IGM (Task 15; audited against the
real Turbo Pascal source in Task 2).

Barak is the official example IGM shipped with the original LORD IGM SDK
(the ``BARAK.EXE`` sample every real-world third-party IGM author cloned to
get started), written by Seth Able Robinson himself. Task 15 built this as a
**recreation** from the historical description in this project's design
docs/task brief, believing the original source lost. It wasn't: Task 2's
audit worked from ``igms_to_port/barsrc.zip``'s ``BARAK.PAS``/``BAR_VAR.PAS``
(Seth's own released full source, "Version 6.2; 04-12-94"), Barak's real
sample-IGM counterpart to ``reference/lord.js`` (which, unlike the
Inn/Forest/Town, never modeled any IGM's internals -- IGMs were always a
separate ``.EXE`` reached through the ``3RDPARTY.DAT`` handshake).

**Direct-port-verified: numbers from BARAK.PAS (barsrc.zip).** The real
``BARAK.EXE`` is a much bigger program than this menu -- a branching
narrative (knock-on-the-door vs. walk-in-uninvited, "shoot the breeze" vs.
borrow-sugar vs. insult-his-beard) gating two real-time ANSI arcade
minigames (``run()``, a directional chase where Barak or his mother hunts
you around the house; ``fly()``, throwing your weapon at an animated flying
wig) and a six-chest basement heist (``chest()``) with a per-chest risk of
his mother catching you and ending the visit. None of that is reproducible
in this project's line-oriented ``TermIO`` (no real-time redraw, no
directional movement), so per this task's own explicit judgment call, it
was **not ported** -- this recreation's much smaller five-item menu
((T)alk/(S)earch/(A)sk to train/(M)other/(L)eave) is kept, and every number
*it* already models was checked against the source and, where a genuine
match exists, adopted verbatim:

* **(A)sk Barak to train you** -- ``+1 strength``, once per day, already
  matched the source by coincidence: ``hair_end()``'s perfect-run reward
  for destroying the flying wig in ``fly()`` includes exactly
  ``inc(pl^.strength, 1)``. A first audit pass claimed that branch grants
  "no exp"; wrong -- ``hair_end()`` (:1117-1130) grants exp
  unconditionally on every path it can be reached by (``times_hit`` 1-5),
  and the ``times_hit = 5`` branch grants the strength point *in addition*
  to exp, not instead of it. Now adopted: ``_train()`` grants
  ``(times_hit + shots_left) * (10 * level) * level`` exp alongside the
  strength point, using ``times_hit = 5`` and, since this recreation
  doesn't model ``fly()``'s minigame (no real ``shots_left`` to read), the
  flawless-run reading the existing reward already implies -- 5 hits on
  the first 5 of the 10 starting throws (``fly()``:1165), leaving
  ``shots_left = 5``. No source day-gate applies to ``fly()``/
  ``hair_end()`` themselves; the source's only whole-visit day-gate is the
  ``bb^.p[play]`` flag (see ``docs/deviations.md``), not a per-action one.
* **(M)eet his mother**, negative outcome ("chased out with a broom") --
  now sets ``hp = 1``, matching ``pl^.hit := 1``, the recurring
  caught-or-defeated punishment. ``beard()`` sets it at the top of *both*
  of its branches -- decline-the-duel (:1318) and agree-to-fight (:1344)
  alike, before either resolves -- and ``run()``'s chase-capture ending
  sets it too. Previously flavor-only (no stat change).
* **(M)eet his mother**, positive outcome ("she feeds you soup") -- now
  uses Barak's "Ultra Ale" reward formula, ``hp = hp_max + hp_max // 4``
  (``chest()``'s full-basement-clear reward and ``walk_in()``'s
  beat-Barak-in-a-fight reward: ``pl^.hit := pl^.hit_max + (pl^.hit_max div
  4)``). The formula always exceeds ``hp_max``, so :class:`~pylord.hooks.
  PlayerView`'s hp clamp turns it into a guaranteed full heal here rather
  than fighting the cap -- previously an invented flat ``+2``.
* **(T)alk to Barak** -- the five rotating quotes (``_QUOTES``) are now
  verbatim lines lifted from BARAK.PAS dialogue (the knock-in greeting,
  the "shoot the breeze" chat, and two lines from getting caught snooping
  around/thrown out), stitched together without their original branching
  consequences since this action is just a flavor quip. Previously
  invented from whole cloth.

**Still invented (no BARAK.PAS equivalent found):**

* **(S)earch the couch cushions** -- the flat 5-50 gold find
  (``_SEARCH_MIN``/``_MAX``) has no source counterpart; the word "couch"
  never appears anywhere in ``BARAK.PAS``. The closest source content is
  the basement ``chest()`` heist -- a level-scaled formula
  (``random(20 * level * level * level) + 1`` gold, or a gem, 50/50) --
  but that's a materially different mechanic (six chests, directional
  movement, per-chest risk of the mother catching you and ending the run
  empty-handed) this port doesn't model. Kept as an invented deviation;
  see ``docs/deviations.md``.

**Not ported** (real BARAK.PAS content with no equivalent in this
recreation, beyond the arcade minigames noted above): the knock-vs-walk-in
top-level branch and its own dialogue; the "borrow sugar" sub-flow (a gem
reward for laughing at Barak's joke, or a fight for taking offense); the
"read one of Barak's books" sub-flow (random history/newspaper flavor
text, or +1 to the reading player's class skill counter, capped at 40);
walk-in's -1 charm penalties; the whole-visit once-per-day gate tied to
consuming a forest fight (``dec(pl^.fights_left)`` plus a ``bb^.p[]``
per-player flag covering the *entire* house, not per-mechanic) -- see
``docs/deviations.md`` for why this port keeps its existing per-mechanic
gates instead.

**Daily-gate design (Task 15, unchanged by the audit).** ``ctx.enter()``
(:class:`~pylord.hooks.IgmContext`) has no day-number access, so the couch
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

# Verbatim lines lifted from BARAK.PAS dialogue -- see module docstring.
# Collected across different in-story branches (the knock-in greeting, the
# "shoot the breeze" chat, and getting caught snooping/thrown out) and
# presented here without their original branching consequences.
_QUOTES = (
    "`0\"Whadaya ya want, kid?\"",  # knock(): Barak's greeting
    "`0\"Shoot the breeze?\" Barak asks, obviously puzzled.",  # shoot()
    "`0\"Books?!  BOOKS?!  You know I can't read!\"",  # shoot(), ch='C'
    "`0\"You insolent pubby!  You will die for this.\"",  # walk_in()
    "`0\"Alright!  I'll give you a flask of my Ultra Ale, damnit!\"",  # walk_in(), ch='K' win
)

_SEARCH_MIN = 5
_SEARCH_MAX = 50

# BARAK.PAS: `pl^.hit := 1` -- the recurring "caught/defeated" punishment.
# Set at the top of both of beard()'s branches (decline-the-duel and
# agree-to-fight alike, :1318/:1344) and by run()'s chase-capture ending.
# Adopted verbatim for mother's negative outcome (Task 2 audit).
_CAUGHT_HP = 1

# BARAK.PAS's fly() minigame: `tries := 10;` (:1165), the shot budget
# hair_end()'s exp formula spends down via `shots_left` (tries remaining
# when the flying wig is destroyed). This port doesn't model fly() at
# all, so _train()'s deterministic reward assumes the flawless run its
# existing +1 strength reward already implies: 5 hits on 5 of the 10
# throws, leaving 5 tries unused. See _train() and the module docstring.
_FLY_TRIES = 10
_PERFECT_HITS = 5


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
        # Once per day. BARAK.PAS's hair_end() (:1117-1130) grants exp
        # *and* +1 strength on a perfect run (times_hit = 5) -- an earlier
        # audit pass wrongly read that branch as granting "no exp"; see
        # module docstring. This port doesn't model fly()'s minigame, so
        # it assumes the flawless run the +1 strength reward already
        # implies (_PERFECT_HITS on _FLY_TRIES, shots_left = 5). Source
        # math, same order (exp announced before strength):
        #   num_end := (times_hit + shots_left) * (10 * level)
        #   num_end := num_end * level
        p = ctx.player
        gate = f"trained:{p.id}"
        if ctx.store.get(gate, False):
            await ctx.term.write(
                '\n  `2"Already trained you today, come back tomorrow!"`0 Barak says.\n'
            )
            await ctx.term.pause()
            return
        ctx.store.set(gate, True)
        shots_left = _FLY_TRIES - _PERFECT_HITS
        num_end = (_PERFECT_HITS + shots_left) * (10 * p.level)
        num_end *= p.level
        p.exp += num_end
        p.strength += 1
        await ctx.term.write(
            "\n  `2Barak wrestles you around the yard for a while.\n"
            f"  `0YOU GET {num_end} EXPERIENCE.\n"
            "  `0YOUR STRENGTH INCREASES BY 1!\n"
        )
        await ctx.term.pause()

    async def _mother(self, ctx: IgmContext) -> bool:
        """Returns ``True`` if the chase ends the visit."""
        p = ctx.player
        outcome = ctx.rng.randrange(2)
        if outcome == 0:
            p.hp = _CAUGHT_HP  # BARAK.PAS: `pl^.hit := 1` -- see _CAUGHT_HP.
            await ctx.term.write(
                "\n  `4Barak's mother spots you and grabs her broom!\n"
                '  `4"GET OUT OF MY HOUSE!"`0 she shrieks, chasing you out the door!\n'
                "  `4YOU FEEL AWFULLY WEAK.\n"
            )
            await ctx.term.pause()
            return True
        # BARAK.PAS's "Ultra Ale" reward: `pl^.hit := pl^.hit_max + (pl^.
        # hit_max div 4)` -- always exceeds hp_max, so PlayerView's hp clamp
        # (pylord/hooks.py) turns this into a guaranteed full heal.
        p.hp = p.hp_max + p.hp_max // 4
        await ctx.term.write(
            "\n  `2Barak's mother smiles and ladles you a bowl of soup.\n"
            "  `0YOU FEEL WONDERFUL!\n"
        )
        await ctx.term.pause()
        return False

    async def daily_maint(self, ctx: IgmMaintContext) -> None:
        for player in ctx.repo.all_players():
            ctx.store.delete(f"couch:{player.id}")
            ctx.store.delete(f"trained:{player.id}")
