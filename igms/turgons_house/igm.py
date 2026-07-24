"""Turgon's House -- Turgon's off-duty home, away from the Training Hall
(Task 18).

Turgon himself is a core LORD character (his Training Hall is
``pylord/engine/scenes/training.py``), but no historical record survives of
a *house* IGM ever having been written for him -- unlike Barak's House /
Sandtiger's Bar / Violet's Cottage (the "starter six"'s first three), whose
authorship is documented in this project's design docs, Turgon's House has
no attested real-world author or binary to recreate. This is a **from-brief
recreation**: the room-search / guard-dog / coupon / off-duty-Turgon shape
below comes entirely from this task's brief, not from a lost transcript.

**Reconstruction notes (invented filler):**

* The room-search outcome table (``_search`` -- guard dog / gems / Turgon
  chat / coupon / nothing, and their exact odds) is entirely invented; the
  brief only lists the four possible outcomes with no odds attached. A flat
  ``rng.randrange(10)`` decile split was chosen: 1/10 guard dog, 1/10 gems,
  1/10 off-duty Turgon, 1/10 coupon, 6/10 nothing -- "mostly empty rooms,
  same as any real house-search" felt truer to a *search* than an even
  four-way split.
* The guard-dog hp loss (1-3, ``_DOG_MIN``/``_DOG_MAX``) and the gem find
  (1-2, ``_GEM_MIN``/``_GEM_MAX``) ranges are both taken verbatim from the
  brief's own numbers. The dog bite floors hp at 1 rather than letting it
  reach 0 -- the same no-kill guard ``warriors_graveyard``'s undead fight
  uses (see that module's docstring), applied here for consistency even
  though a 1-3 hp nibble can only zero out an already-critical player.
* **The coupon is inert by design, not a bug.** The brief is explicit:
  finding a weapon-shop discount coupon here grants nothing yet --
  redemption in the actual Weapons Shop (``pylord/engine/scenes/town.py``'s
  ``weapons`` scene, from the batch-A task set) is **not wired this task**.
  ``ctx.store`` just records that the player is holding one
  (``coupon:<player_id>``, a plain boolean -- "one at a time" per the
  brief, so finding a second one while still holding the first is folded
  into the "nothing" branch instead of stacking). A future task that wires
  shop-side coupon redemption should read this same key.
  TODO(future task): consume ``coupon:<player_id>`` in the Weapons Shop for
  a discount; until then it's purely a "you're holding something" flag.
* Turgon quotes (``_QUOTES``) are invented flavor text, same convention as
  Barak's/Sandtiger's own flavor pools.

**Daily-gate design**, same pattern as Barak's House/Violet's Cottage:
plain per-player counters/flags in the store, reset by :meth:`daily_maint`
(run once per game-day) rather than day-suffixed keys, since ``enter()``'s
:class:`~pylord.hooks.IgmContext` has no day-number access.

* ``searches:<player_id>`` -- integer counter, 3 searches/day.
* ``talked:<player_id>`` -- boolean, once/day gate for talking to Turgon
  (the +1 defense at level >= 6 only fires once per day even if the
  player re-enters the house and talks again).
"""

from __future__ import annotations

from pylord.hooks import IGM, IgmContext, IgmMaintContext

_MENU = (
    "\n  `5Turgon's House   `8(? for menu)\n"
    "  `2(`0S`2)earch a room   (`0T`2)alk to Turgon   (`0L`2)eave\n"
)

_SEARCHES_PER_DAY = 3
_DOG_MIN = 1
_DOG_MAX = 3
_GEM_MIN = 1
_GEM_MAX = 2
_TALK_EXP = 15
_TALK_LEVEL_FOR_DEFENSE = 6

# Invented flavor text -- see module docstring's Reconstruction notes.
_QUOTES = (
    "`0\"Even a Trainer needs a day off now and then, you know.\"",
    "`0\"Between you and me, half the warriors I train couldn't find their own sword.\"",
    "`0\"I keep meaning to redecorate.  Somehow there's never time.\"",
    "`0\"You're doing fine out there.  Keep at it.\"",
    "`0\"Don't tell anyone at the Hall I let you in here.\"",
)


class TurgonsHouse(IGM):
    key = "turgons_house"
    name = "Turgon's House"
    default_enabled = True

    async def enter(self, ctx: IgmContext) -> None:
        while True:
            await ctx.term.write(_MENU)
            choice = await ctx.term.menu(
                {"S": "search", "T": "talk", "L": "leave"},
                "  `2Your choice? : ",
            )
            if choice == "L":
                await ctx.term.write(
                    "\n  `2You let yourself out, careful not to wake the dog.\n"
                )
                return
            if choice == "S":
                await self._search(ctx)
            elif choice == "T":
                await self._talk(ctx)

    async def _search(self, ctx: IgmContext) -> None:
        p = ctx.player
        gate = f"searches:{p.id}"
        used = ctx.store.get(gate, 0)
        if used >= _SEARCHES_PER_DAY:
            await ctx.term.write(
                "\n  `2You've already searched every room you dare to today.\n"
            )
            await ctx.term.pause()
            return
        ctx.store.set(gate, used + 1)

        outcome = ctx.rng.randrange(10)
        if outcome == 0:
            lost = ctx.rng.randint(_DOG_MIN, _DOG_MAX)
            p.hp = p.hp - lost
            if p.hp <= 0:
                p.hp = 1  # no-kill guard, same as warriors_graveyard's undead fight
            await ctx.term.write(
                "\n  `4A guard dog bursts out of a closet and bites you!\n"
                f"  `4YOU LOSE {lost} HIT POINT{'S' if lost != 1 else ''}!\n"
            )
        elif outcome == 1:
            found = ctx.rng.randint(_GEM_MIN, _GEM_MAX)
            p.gems += found
            await ctx.term.write(
                f"\n  `2You find `0{found} `2gem{'s' if found != 1 else ''} tucked "
                "under a floorboard!\n"
            )
        elif outcome == 2:
            p.exp += _TALK_EXP
            await ctx.term.write(
                "\n  `2You stumble on Turgon relaxing in an armchair.  He waves you\n"
                "  over and shares a training tip or two.\n"
                f"  `0YOU RECEIVE {_TALK_EXP} EXPERIENCE!\n"
            )
        elif outcome == 3:
            coupon_gate = f"coupon:{p.id}"
            if ctx.store.get(coupon_gate, False):
                await ctx.term.write(
                    "\n  `2You search the room but find nothing of interest.\n"
                )
            else:
                ctx.store.set(coupon_gate, True)
                await ctx.term.write(
                    "\n  `2You find a weapon-shop discount coupon!  You tuck it away,\n"
                    "  though you're not sure yet where you could use it.\n"
                )
        else:
            await ctx.term.write(
                "\n  `2You search the room but find nothing of interest.\n"
            )
        await ctx.term.pause()

    async def _talk(self, ctx: IgmContext) -> None:
        p = ctx.player
        quote = ctx.rng.choice(_QUOTES)
        await ctx.term.write(f"\n  `2Turgon leans back and says:\n  {quote}\n")

        gate = f"talked:{p.id}"
        if not ctx.store.get(gate, False):
            ctx.store.set(gate, True)
            if p.level >= _TALK_LEVEL_FOR_DEFENSE:
                p.defense += 1
                await ctx.term.write(
                    "\n  `2Turgon points out an opening in your stance and shows you\n"
                    "  how to close it.\n"
                    "  `0YOUR DEFENSE INCREASES BY 1!\n"
                )
        await ctx.term.pause()

    async def daily_maint(self, ctx: IgmMaintContext) -> None:
        # Note: `coupon:<id>` is deliberately NOT cleared here -- it's a
        # held-item flag ("do you have an unredeemed coupon"), not a daily
        # gate, and persists until a future task's shop-side redemption
        # consumes it.
        for player in ctx.repo.all_players():
            ctx.store.delete(f"searches:{player.id}")
            ctx.store.delete(f"talked:{player.id}")
