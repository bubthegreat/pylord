"""The Warrior's Graveyard (Task 19; source-audited).

**Lineage verdict, checked both ways per this audit's brief:**

* ``igms_to_port/grave330.zip`` is **"The GraveYard v3.3"** -- a *different*
  IGM: a DOS ``.EXE`` shareware door by **Tommy Baker** (``FILE_ID.DIZ``:
  "The GraveYard v3.3 LORD IGM ... Written By Tommy Baker"; ``GRAVEYD.DOC``:
  "Program & Design by Tommy Baker"). No source survives, only the compiled
  ``GRAVEYD.EXE``/``GRAVECFG.EXE`` and prose docs. Different title, different
  author, different program -- **not** this IGM's ancestor.
* ``igms_to_port/grave20.zip`` is **"The Graveyard"** for **WT-LORD**
  (Wildcat Tournament LORD, a different game entirely from real LORD),
  by Joe Marcelletti and James Cornman of IceRage Technologies
  (``GRAVE.DOC``). A wcCODE binary module, no portable source, and not even
  the same host game. Also **not** this IGM's ancestor.
* ``reference/igm-sources/lordts/gravyard/`` **is** the real ancestor: a
  faithful TypeScript port (``gravyard.ts``, 1841 lines) of **"The
  Warrior's Graveyard"** -- the exact same title as this IGM -- originally
  written for Synchronet/JSLord by **Lloyd Hannesson** (Copyright
  1995-2023; ``reference/igm-sources/synchronet/gravyard/gravyard.js`` and
  ``gravyard.txt`` carry the same title/author/copyright, confirming the
  TS port is a faithful transcription, not a fresh invention under a
  recycled name). ``README.md`` there: "Original Versions: DOS v1.8
  (01/25/02, 'last version'), JS v1.1 (04/01/23)."

**Direct-port-verified provenance tier applies (a real, readable source
survives and governs over doc prose) -- but this recreation's own shape is
almost entirely alien to it.** Task 19 built this IGM from-brief, believing
no record survived; this audit found one, and it changes the picture
completely: the real Warrior's Graveyard has **13 named graveplots** to
rob (``Graveplots``, ``gravyard.ts`` :35-192, each with a canned
gravestone epitaph, a `good`/`evil` flag, and fixed `gold`/`gems` values),
**four hidden ghosts** (Jim Bob Jones, George, Mike, Tanya -- gendered and
RNG-gated), an Old Hag who brews a 12-outcome potion and runs a marble-draw
gambling game, a Lemon-Aide stand, a Grave Digger for dialogue, and a
secret Kitten easter egg -- and **no combat of any kind, anywhere**. This
recreation's three-action menu (dig / Old Hag hp-trade / a single generic
ghost) shares only the setting and title with that source; almost none of
its specific numbers transfer onto this recreation's structurally
different shape (the same conclusion Sandtiger's Bar's audit reached
against its own, differently-alien real source -- see that module's
docstring).

**Adopted from the real source:**

* **Grave-robbing is gated once per day, not 5 digs/day.** The real
  ``(G)`` "Rob a Grave" is a single boolean gate (``graRecord.graverobbed``,
  reset by ``runMaint()``'s day rollover, ``gravyard.ts`` :312-330):
  attempting it twice in a day gets "You think that robbing more than one
  grave today would be too DANGEROUS!" (``gravyard.ts`` :1795-1807). This
  recreation's ``_DIGS_PER_DAY`` is now ``1`` to match; previously an
  invented "5 digs/day" with no source backing at all.
* **The no-kill guard is now source-confirmed, not just an invented safety
  net.** ``grep``ing the entire 1842-line source for ``alive``/a death flag
  finds nothing -- the real Warrior's Graveyard *never* kills the player.
  Its two "bad outcome" paths both do exactly what this recreation already
  does: floor hp to 1 and stop. Getting caught grave-robbing sets
  ``this.player.hp=1`` (``gravyard.ts`` :1476, the ``_attemptGraveRob``
  catch branch) and the Hag's potion table's one bad roll ("You feel as
  though you died!") also just sets ``this.player.hp=1`` (``gravyard.ts``
  :918) -- neither ever touches an alive/death flag, because there isn't
  one. So the no-kill floor documented below isn't only this project's own
  architectural boundary (IGMs cannot kill) -- it's independently what the
  real IGM already did. No source mechanic here needed the
  exp-drain/no-kill adaptation the audit brief anticipated, because nothing
  in the real source ever kills to begin with.

**Still invented (no clean source equivalent to adopt -- kept as
deviations, see ``docs/deviations.md``):**

* **The dig outcome table's shape and odds** (``_dig`` -- 4/10 gold cache,
  1/10 gem, 2/10 nothing, 3/10 undead fight) has no counterpart: the real
  grave-rob is deterministic per named grave (fixed ``gold * level`` +
  fixed ``gems``, plus a 50% chance of a bonus potion, ``gravyard.ts``
  :1104-1176/:1458-1497), not a procedural random-bucket roll, and it has
  no "find nothing" outcome at all.
* **The undead-fight combat encounter is entirely invented.** The real
  Warrior's Graveyard has *no combat mechanic whatsoever* -- disturbing a
  grave never spawns a monster fight; its only risk is the flat
  catch-and-mug penalty above (11% chance for a "good" grave, 6% for
  "evil", ``gravyard.ts`` :1459-1463: "``random(100)`` returns 0-99; ``<=
  10`` is 11 values, ``<= 5`` is 6 values"). The previous docstring's claim
  that "a disturbed grave fights back... [is] its one connection to the
  ported engine" no longer holds now that the real source is known -- there
  was no engine to be connected to. Kept anyway: this recreation's whole
  three-action shape is built around it, and replacing it would be a
  redesign, not an audit fix. The monster stats/reward formulas remain
  this project's own invention (see the constants below).
* **The Old Hag's hp<->stat trade** has no source equivalent -- the real
  Hag's potion is *free* (a once/day request, gated only by the day-flag,
  never an hp cost) and rolls a 12-outcome table (+2 charm / +2 defense /
  +2 strength / +5 forest fights / ``min(level,5)*1024`` exp / +1 hp_max /
  nothing (x2) / the hp=1 "died" mishap / -2 strength / -2 defense / -1
  charm; ``graGetPotion``, ``gravyard.ts`` :876-933). She also runs a
  separate marble-draw gambling game (``graPlayGame``/``_playGameRound``,
  :611-654/:656-749: pull 2 of 4 marbles, lose all / lose half / win back /
  double your bet, 25% each). Neither maps onto a flat hp-for-stat trade.
* **The ghost's listen-for-exp/flee choice** (+25 exp or nothing) has no
  matching flat figure anywhere. The real source's four named ghosts each
  offer richer, structurally different rewards (see "Not ported" below);
  none of them is a binary listen/flee pick, and none hands out a flat 25
  exp.

**Not ported** (real ``gravyard.ts``/``gravyard.js`` content with no
equivalent in this recreation, disclosed per this audit's "nothing
silently dropped" rule):

* The 13 named graveplots and their canned epitaphs/`good`/`evil` flags
  (``Graveplots``, :35-192); the +1 charm reward for declining to rob a
  "good" grave (:1162-1168).
* **Jim Bob Jones** -- a 1%-per-visit random event (``doRandomStuff``,
  :537-547, checked on entering the Shack or Lemon-Aide stand), once/day,
  offering a player-chosen reward from six (``graJimBob``, :935-1045:
  ``level*5`` strength, ``level*5`` defense, ``level*1024`` exp, a flat 4
  gems, ``level`` charm, or ``level*5000`` gold).
* **George** -- talk (3 rotating flavor lines, :1423-1456) and ask-for-help
  (once, random of: +10 forest fights / +1 strength +1 defense / a
  good-only potion roll, :1381-1421), reached via the Grave Digger's
  secret ``1`` option (male players only, :1730-1737) or a secret ``G``
  typed at the rob-grave prompt (:1173-1175).
* **Mike**/**Tanya** -- gendered ghosts (male sees Mike, female sees Tanya,
  reached from the Shack, :1568-1575/:1730-1737) each offering an
  once-only "ask a favor" (Mike: +2 charm, :1207-1222; Tanya: a good-only
  potion roll, :1283-1295) and a shared once/day "flirt" branch
  (``graFlirtMike``/``graFlirtTanya``, :751-767, incrementing
  ``player.laid`` -- this project's romance/`lays` counter this IGM would
  otherwise have no reason to touch).
* The **Lemon-Aide stand** (``graBuyAide``/``_drinkLemonAide``,
  :769-806/:808-874): once/day, priced ``1000`` gold under level 5 or
  ``10000`` at level 5+, a 4-outcome roll (full heal / reset today's
  flirt-and-romance flags / gain a fairy / +5 gems).
* The **Grave Digger**'s dialogue (whose-grave/treasure/ghost-hints/Hag
  lore flavor text, ``graDigger``, :1644-1751).
* The secret **Kitten** easter egg (a backtick "look around quietly" key
  on the main menu, once/day: +level strength / +level defense / +1 charm
  / +15 forest fights, ``graKitten``, :1047-1102).
* Multi-node/file-based per-player record storage (``GraveyardRecord``/
  ``graFile``, a real record-file abstraction) and the exit/day-rollover
  bookkeeping (``exitGame``, ``runMaint``) -- this recreation's
  store-key/``daily_maint`` pattern already covers the same ground in this
  project's own idiom (see "Daily-gate design" below).

**The no-kill guard (why an undead fight can never actually end a
character).** :class:`~pylord.hooks.PlayerView` clamps ``hp`` to
``[0, hp_max]`` but does *not* forbid writing 0 -- and this recreation
enforces "IGM cannot kill" as an architectural boundary, unlike a real
Forest monster encounter (``pylord/engine/scenes/forest.py``'s
``_death()``, which sets ``player.alive = 0`` and runs the full
death/resurrection flow). This audit confirms the boundary isn't only this
project's own invention: the real Warrior's Graveyard never kills either
(see "Adopted from the real source" above). ``player.alive`` *is*
technically writable through the guardrail (it isn't in
``PlayerView._IMMUTABLE`` and isn't one of the clamped
``limits.VALIDATED_FIELDS``), but this IGM deliberately never touches it:
setting it here would improvise a whole death/scoring side-effect this
IGM has no business owning (that's the Forest's job, and only the Forest's
job). Instead, :meth:`_dig`'s fight loop checks after every round whether
the player's hp has reached 0 and, if so, floors it back up to **1**
(never 0, never touches ``alive``), prints a "your heart pounds as you
scramble from the grave" scare line, and ends the visit immediately -- a
graveyard mugging that leaves you badly hurt, not a death scene. This is
the same "sync the standalone Combatant's hp back onto the live PlayerView
every round" pattern ``forest.py``'s ``_run_fight`` uses (see that
module's own comment on ``p.hp = fight.player_side.hp``), just with an
added floor.

**Daily-gate design**, same pattern as the rest of the starter six: plain
per-player counters/flags in the store, reset by :meth:`daily_maint`. This
matches the real source's own per-player once-daily record fields
(``GraveyardRecord``, reset by day-rollover -- see "Not ported" above),
just in this project's own store-key idiom rather than a record-file.

* ``digs:<player_id>`` -- integer counter, 1 dig/day (adopted -- see
  above).
* ``hag:<player_id>`` -- boolean, once/day gate for the Old Hag's trade.
* ``ghost:<player_id>`` -- boolean, once/day gate for the ghost encounter.
"""

from __future__ import annotations

from pylord.engine.combat import Combatant, Fight
from pylord.hooks import IGM, IgmContext, IgmMaintContext

_MENU = (
    "\n  `5The Warrior's Graveyard   `8(? for menu)\n"
    "  `2(`0D`2)ig a grave   (`0O`2)ld Hag   (`0G`2)host   (`0L`2)eave\n"
)

# Adopted: the real source gates grave-robbing to once per day (a single
# `graverobbed` boolean, gravyard.ts:1795-1807) -- see module docstring.
_DIGS_PER_DAY = 1
_HAG_HP_COST = 5
_HAG_MIN_HP = 5
_GHOST_EXP = 25
_UNDEAD_EXP_PER_LEVEL = 20
_UNDEAD_GOLD_MIN_PER_LEVEL = 20
_UNDEAD_GOLD_MAX_PER_LEVEL = 80

_UNDEAD_NAMES = ("Restless Corpse", "Grave Wight")


class WarriorsGraveyard(IGM):
    key = "warriors_graveyard"
    name = "The Warrior's Graveyard"
    default_enabled = True

    async def enter(self, ctx: IgmContext) -> None:
        while True:
            await ctx.term.write(_MENU)
            choice = await ctx.term.menu(
                {"D": "dig", "O": "hag", "G": "ghost", "L": "leave"},
                "  `2Your choice? : ",
            )
            if choice == "L":
                await ctx.term.write(
                    "\n  `2You step carefully back through the rusted gate.\n"
                )
                return
            if choice == "D":
                scared_off = await self._dig(ctx)
                if scared_off:
                    return
            elif choice == "O":
                await self._hag(ctx)
            elif choice == "G":
                await self._ghost(ctx)

    async def _dig(self, ctx: IgmContext) -> bool:
        """Returns ``True`` if the no-kill guard tripped and the visit
        should end (see the module docstring's no-kill guard section)."""
        p = ctx.player
        gate = f"digs:{p.id}"
        used = ctx.store.get(gate, 0)
        if used >= _DIGS_PER_DAY:
            await ctx.term.write(
                "\n  `2Your shovel is spent -- you've dug enough graves for one day.\n"
            )
            await ctx.term.pause()
            return False
        ctx.store.set(gate, used + 1)

        outcome = ctx.rng.randrange(10)
        if outcome <= 3:
            found = ctx.rng.randint(p.level * 50, p.level * 200)
            p.gold += found
            await ctx.term.write(
                f"\n  `2Your shovel strikes something -- a buried cache of "
                f"`0{found} `2gold!\n"
            )
            await ctx.term.pause()
            return False
        if outcome == 4:
            p.gems += 1
            await ctx.term.write(
                "\n  `2Glinting in the dirt, you find a single gem!\n"
            )
            await ctx.term.pause()
            return False
        if outcome <= 6:
            await ctx.term.write(
                "\n  `2You dig for a while, find nothing, and fill the hole back in.\n"
            )
            await ctx.term.pause()
            return False
        return await self._undead_fight(ctx)

    async def _undead_fight(self, ctx: IgmContext) -> bool:
        """Returns ``True`` if the no-kill guard tripped and the visit
        should end."""
        p = ctx.player
        name = ctx.rng.choice(_UNDEAD_NAMES)
        monster = Combatant(
            name=name,
            hp=p.level * 15,
            hp_max=p.level * 15,
            strength=p.level * 8,
            defense=0,
            weapon_name="Bony Claws",
        )
        await ctx.term.write(
            f"\n  `4Your shovel breaks through into an old coffin -- a "
            f"{name} claws its way out!\n"
        )
        fight = Fight(Combatant.from_player(p), monster, ctx.rng, pfight=False)

        while not fight.over:
            action = await ctx.term.menu(
                {"A": "attack", "R": "run"},
                f"\n  `2Your Hitpoints: `0{fight.player_side.hp}   "
                f"`2{name}'s Hitpoints: `0{max(fight.enemy.hp, 0)}\n"
                "  `2(`0A`2)ttack   (`0R`2)un : ",
            )
            if action == "A":
                last_round = fight.player_attack()
                await ctx.term.write(f"\n  {last_round.text}\n")
                if not fight.over:
                    enemy_round = fight.enemy_attack()
                    await ctx.term.write(f"  {enemy_round.text}\n")
            else:
                ran = fight.attempt_run()
                if ran:
                    await ctx.term.write(
                        f"\n  You scramble out of the grave and run, leaving "
                        f"{name} behind!\n"
                    )
                else:
                    await ctx.term.write(f"\n  {name} catches you before you escape!\n")

            # Sync the standalone Combatant's hp back onto the live
            # PlayerView every round -- same pattern as forest.py's
            # _run_fight (see that module's comment on the same line).
            p.hp = fight.player_side.hp

            if fight.player_side.hp <= 0:
                # No-kill guard -- see module docstring. Floor to 1, never
                # touch player.alive, end the visit.
                p.hp = 1
                await ctx.term.write(
                    "\n  `4Everything goes black for a moment -- you claw your way\n"
                    "  `4back from the brink and stumble out of the graveyard,\n"
                    "  `4badly hurt but alive.\n"
                )
                await ctx.term.pause()
                return True

        if fight.ran_away:
            await ctx.term.pause()
            return False

        # fight.winner == "player"
        gained_exp = p.level * _UNDEAD_EXP_PER_LEVEL
        gained_gold = ctx.rng.randint(
            p.level * _UNDEAD_GOLD_MIN_PER_LEVEL, p.level * _UNDEAD_GOLD_MAX_PER_LEVEL
        )
        # Overkill loot bonus (Fight._loot_bonus, combat.py) already
        # announced itself in the round text above ("You find a gem!" /
        # "You find more gold than expected!") -- apply the actual reward
        # here, same pattern as forest.py's _victory: gem_found -> a flat
        # +1 gem, bonus_gold -> double this fight's gold reward.
        if fight.bonus_gold:
            gained_gold *= 2
        if fight.gem_found:
            p.gems += 1
        p.exp += gained_exp
        p.gold += gained_gold
        await ctx.term.write(
            f"\n  `2You put {name} back to rest.\n"
            f"  `0YOU RECEIVE {gained_gold} GOLD AND {gained_exp} EXPERIENCE!\n"
        )
        await ctx.term.pause()
        return False

    async def _hag(self, ctx: IgmContext) -> None:
        p = ctx.player
        gate = f"hag:{p.id}"
        if ctx.store.get(gate, False):
            await ctx.term.write(
                "\n  `2The Old Hag waves you off.  \"Come back tomorrow, dearie.\"\n"
            )
            await ctx.term.pause()
            return
        if p.hp <= _HAG_MIN_HP:
            await ctx.term.write(
                "\n  `4\"You're too weak for my kind of bargain,\"`4 the Hag cackles.\n"
            )
            await ctx.term.pause()
            return

        choice = await ctx.term.menu(
            {"S": "strength", "D": "defense"},
            f"\n  `2The Old Hag offers to trade `0{_HAG_HP_COST} `2hit points for a\n"
            "  point of `0(`2S`0)`2trength or `0(`2D`0)`2efense.  Which will it be? : ",
        )
        ctx.store.set(gate, True)
        p.hp = p.hp - _HAG_HP_COST
        if choice == "S":
            p.strength += 1
            await ctx.term.write(
                f"\n  `2The Hag cuts a lock of your hair and mutters a chant.\n"
                f"  `4YOU LOSE {_HAG_HP_COST} HIT POINTS!\n"
                "  `0YOUR STRENGTH INCREASES BY 1!\n"
            )
        else:
            p.defense += 1
            await ctx.term.write(
                f"\n  `2The Hag cuts a lock of your hair and mutters a chant.\n"
                f"  `4YOU LOSE {_HAG_HP_COST} HIT POINTS!\n"
                "  `0YOUR DEFENSE INCREASES BY 1!\n"
            )
        await ctx.term.pause()

    async def _ghost(self, ctx: IgmContext) -> None:
        p = ctx.player
        gate = f"ghost:{p.id}"
        if ctx.store.get(gate, False):
            await ctx.term.write(
                "\n  `2The mist is quiet tonight -- no ghost stirs.\n"
            )
            await ctx.term.pause()
            return

        choice = await ctx.term.menu(
            {"L": "listen", "F": "flee"},
            "\n  `2A translucent figure rises from the fog and beckons you closer.\n"
            "  `2(`0L`2)isten to its tale   (`0F`2)lee : ",
        )
        ctx.store.set(gate, True)
        if choice == "L":
            p.exp += _GHOST_EXP
            await ctx.term.write(
                "\n  `2The ghost whispers the secrets of a battle long forgotten.\n"
                f"  `0YOU RECEIVE {_GHOST_EXP} EXPERIENCE!\n"
            )
        else:
            await ctx.term.write(
                "\n  `2You turn and run, the ghost's cold laughter fading behind you.\n"
            )
        await ctx.term.pause()

    async def daily_maint(self, ctx: IgmMaintContext) -> None:
        for player in ctx.repo.all_players():
            ctx.store.delete(f"digs:{player.id}")
            ctx.store.delete(f"hag:{player.id}")
            ctx.store.delete(f"ghost:{player.id}")
