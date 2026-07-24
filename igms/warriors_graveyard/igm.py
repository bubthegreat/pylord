"""The Warrior's Graveyard (Task 19).

No historical record of a real "Warrior's Graveyard" IGM binary/author
survives (unlike Barak's House / Sandtiger's Bar, whose authorship this
project's design docs do attest) -- this is a **from-brief recreation**:
the dig / Old Hag / ghost shape below comes entirely from this task's
brief, not from a lost transcript. Its one connection to the ported engine
is real, though: a disturbed grave fights back using the same combat
primitives the Forest's monster encounters use
(:mod:`pylord.engine.combat`), not a re-implementation.

**Reconstruction notes (invented filler):**

* The dig outcome table (``_dig`` -- gold cache / rare gem / nothing /
  undead fight, and their odds) is entirely invented; the brief only lists
  the four possible outcomes with no odds attached. A
  ``rng.randrange(10)`` split was chosen: 4/10 gold, 1/10 gems ("rare" per
  the brief), 2/10 nothing, 3/10 undead -- graves being disturbed a
  meaningful fraction of the time is the point of a *graveyard*, so undead
  outcomes were weighted higher than a flat 1/4 each.
* The gold-cache range (``level*50``..``level*200``) and the undead
  fight's monster stats (``strength = level*8``, ``hp = level*15``,
  ``defense = 0``) are taken verbatim from the brief's own formulas.
* Undead victory's gold reward has no formula in the brief (only "+exp
  (level*20) +gold" is specified) -- invented as ``level*20``..``level*80``,
  deliberately smaller than a clean dig's cache since fighting off an
  undead is a *side effect* of digging, not the point of it.
* The two undead names (``_UNDEAD_NAMES``) are invented flavor, picked via
  the same rng draw used for every other undead-flavor roll below.
* The Old Hag's trade (hp <-> +1 strength or +1 defense, once/day, refused
  at hp <= 5) and the ghost's listen-for-exp/flee choice (+25 exp, once/
  day) are both taken directly from the brief.

**The no-kill guard (why an undead fight can never actually end a
character).** :class:`~pylord.hooks.PlayerView` clamps ``hp`` to
``[0, hp_max]`` but does *not* forbid writing 0 -- and the brief is
explicit that "IGM cannot kill" here, unlike a real Forest monster
encounter (``pylord/engine/scenes/forest.py``'s ``_death()``, which sets
``player.alive = 0`` and runs the full death/resurrection flow).
``player.alive`` *is* technically writable through the guardrail (it isn't
in ``PlayerView._IMMUTABLE`` and isn't one of the clamped
``limits.VALIDATED_FIELDS``), but this IGM deliberately never touches it:
setting it here would improvise a whole death/scoring side-effect this
IGM has no business owning (that's the Forest's job, and only the Forest's
job, per the brief's own class boundary). Instead, :meth:`_dig`'s fight
loop checks after every round whether the player's hp has reached 0 and,
if so, floors it back up to **1** (never 0, never touches ``alive``),
prints a "your heart pounds as you scramble from the grave" scare line,
and ends the visit immediately -- a graveyard mugging that leaves you
badly hurt, not a death scene. This is the same "sync the standalone
Combatant's hp back onto the live PlayerView every round" pattern
``forest.py``'s ``_run_fight`` uses (see that module's own comment on
``p.hp = fight.player_side.hp``), just with an added floor.

**Daily-gate design**, same pattern as the rest of the starter six: plain
per-player counters/flags in the store, reset by :meth:`daily_maint`.

* ``digs:<player_id>`` -- integer counter, 5 digs/day.
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

_DIGS_PER_DAY = 5
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
