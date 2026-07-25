"""The Arena of Lords -- paid bouts against the house's champions.

Wave-2 IGM, recreated from the premise (an arena that pays purses) rather
than ported. Audited against the surviving archive documentation for the
real **The Arena Of Lords v2.0** (``igms_to_port/arena20.zip``, Gary Hall
aka "Slammin'", 1995 -- ``ARENA.DOC``/``TECHNOTE.DOC``/``WHATDONE.DOC``/
``FILE_ID.DIZ``). Its own name is this recreation's name, verbatim.

**Documented recreation, verified against archive docs -- not
direct-port-verified.** Unlike Barak's House/Sandtiger's Bar (real Turbo
Pascal source survived for those), only a compiled ``ARENA.EXE`` survives
here, PKLITE-packed -- no source, and no gameplay-relevant strings survive
the packing cleanly enough to trust (spot-checked; the output is a
shuffled mix of real fragments -- ``TYR``, ``gladiator``, ``FAIRY`` --
and packer noise, not readable prose). ``ARENA.DAT`` is pure ANSI
escape-code title art (verified: no gameplay text, just cursor moves and
block-graphic bytes), and ``TECHNOTE.DOC`` covers only dropfile/FOSSIL
sysop setup. What's left is prose -- ``ARENA.DOC``'s feature blurb and
``WHATDONE.DOC``'s version-by-version changelog -- and it records no
formulas at all, only what the game *does*.

A second archive, ``igms_to_port/arenav2.zip`` ("Haldar's Arena v2.0b", by
Bram Luknight), was read and ruled out as this recreation's ancestor: a
different author's arena IGM with a materially different premise --
entry is paid entirely in **gems**, never gold ("Haldar's arena is unique
in that a fight is payed for in gems, rather than gold", ``ARENA.DOC``),
against sysop-configured monster data (``HALDAR.DAT``), with its own
hangman-style win/lose ANSI screens (the archive's stray ``0``-``5``/
``M``/``U`` files -- "IT'S DEAD" / "YOUR'E DEAD"). Nothing about this
recreation (gold-based entry, a fixed named opponent) matches Haldar's
premise better than Gary Hall's -- so Gary Hall's v2.0 is the governing
document, confirmed rather than assumed.

Fights run on the real combat engine (``pylord/engine/combat.py``), so an
arena bout behaves exactly like a forest fight -- the same rolls, the same
skill attacks -- and, like a master, the champions are *arena* opponents:
you cannot run, and you cannot use class skills on them
(reference/lord.js:7001-7006, :7045-7051). Losing costs the entry fee and
leaves you on one hitpoint rather than killing you; the arena has a healer
and an interest in repeat custom.

**Adopted from ARENA.DOC/WHATDONE.DOC:**

* **The gladiator's name, "Tyr"** -- ``ARENA.DOC``: "you can win LOTS of
  gold or gems *IF* you can beat 'TYR' the gladiator of the arena." The
  real IGM has exactly one fixed opponent; this recreation's three-tier
  ladder is itself invented (see below), but the top tier, previously
  invented as "Lord Vane," is now named after the real one.
* **No running, but you can beg for mercy** -- ``WHATDONE.DOC``'s v1.4b
  entry: "You can no longer 'run' from Tyr in the Arena as there would be
  no place to run 'TO' in an event like that. But you CAN beg for mercy
  now." This recreation already had both halves right by design (arena
  opponents block running via ``Combatant.is_arena``, and a yield option
  already existed) -- the yield prompt/flavor text is now worded as
  begging for mercy, to match the documented phrase exactly.
* **Wins can pay gems as well as gold** -- ``ARENA.DOC``'s "gold or gems"
  phrasing. No rate or amount is documented anywhere in the archive (see
  above), so rather than invent a new roll, ``_win()`` now wires in the
  combat engine's own already-ported lord.js overkill mechanic
  (``Fight._loot_bonus``, ``combat.py``, reference/lord.js:6905-6924/
  6973-6991): ``fight.gem_found`` credits a gem, ``fight.bonus_gold``
  doubles the purse -- the same pattern ``igms/warriors_graveyard/igm.py``
  already uses for its own fights. The round text already narrates "You
  find a gem!"/"You find more gold than expected!" when either fires; only
  the actual credit was missing. The *shape* (gold or gems) is
  doc-adopted; the *rate* (the engine's existing overkill odds) was
  already this project's own invention, just not this IGM's.

**Still invented (no ARENA.DOC/WHATDONE.DOC formula to adopt):** the
three-tier ladder itself and its two lesser champions ("Bruiser Hal," "The
Widow Grey" -- the real IGM has only Tyr); every hp/strength multiplier;
the entry fee (``ENTRY_FEE_PER_LEVEL``); the purse formula and streak
bonus (``STREAK_BONUS``/``STREAK_CAP``); and the daily bout cap
(``BOUTS_PER_DAY``). The archive documents no formulas anywhere -- only
prose describing the fight and its win condition -- so there is nothing
concrete to adopt for any of these; a fidelity-tier "no-source-record."

**Not ported** (real ``ARENA.DOC``/``WHATDONE.DOC`` content with no
equivalent in this recreation):

* The "random extras" ``ARENA.DOC`` says winning throws in -- "changes in
  level, weapons, hit point, charm, strength, defence, and etc" -- are
  described too vaguely (no trigger odds, no magnitude, no list of which
  stat changes which way, or even whether they're gains or losses) to
  responsibly reproduce.
* The fairy tie-in -- "the arena was basically designed so you had
  something to do with a fairy if you catch one." This project's
  ``Player`` model has no fairy-capture flag to hook into (see
  ``docs/deviations.md``'s Forest/Bank fairy-related rows for the same
  gap elsewhere).
* ``WHATDONE.DOC`` v1.4b's "Added option with dying man" and "Added
  tapestry on waiting room wall to increase amount of options" -- both are
  one-line changelog entries with no description anywhere of what they
  actually do.
"""

from __future__ import annotations

from pylord.engine.combat import Combatant, Fight
from pylord.hooks import IGM, IgmContext, IgmMaintContext

#: (name, weapon, hp multiplier, strength multiplier, purse multiplier)
#: The top tier is named "Tyr" -- ARENA.DOC: the real IGM's one fixed
#: opponent, "'TYR' the gladiator of the arena" (see module docstring).
#: The other two tiers, and every multiplier/purse figure, are invented --
#: the real IGM has no ladder, just Tyr.
_CHAMPIONS = (
    ("Bruiser Hal", "a knotted club", 6, 3, 400),
    ("The Widow Grey", "twin hooks", 10, 5, 1200),
    ("Tyr", "a black halberd", 16, 8, 3000),
)
ENTRY_FEE_PER_LEVEL = 200
#: Bouts allowed per day. A strong enough warrior nets fee-minus-purse on
#: every win, so without a cap the arena prints gold.
BOUTS_PER_DAY = 3
#: Purse multiplier for each consecutive win, capped so it can't run away.
STREAK_BONUS = 0.25
STREAK_CAP = 4


def _menu(p) -> str:
    lines = [
        "\n  `5The Arena of Lords`2\n",
        "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n",
    ]
    for index, (name, _weapon, hp_mult, str_mult, purse) in enumerate(_CHAMPIONS, 1):
        lines.append(
            f"  `2(`0{index}`2) {name:<16} `8{p.level * hp_mult} hp, "
            f"{p.level * str_mult} str`2   purse `%{p.level * purse}`2\n"
        )
    lines.append("  `2(`0L`2)eave\n")
    return "".join(lines)


class ArenaOfLords(IGM):
    key = "arena_of_lords"
    name = "The Arena of Lords"
    author = "pylord (recreation)"
    default_enabled = True

    async def enter(self, ctx: IgmContext) -> None:
        await ctx.term.write(
            "\n  `2Sand, sawdust and a crowd that has seen better men than you\n"
            "  carried out.  The master of the games raises an eyebrow.\n"
        )
        while True:
            p = ctx.player
            streak = ctx.store.get(f"streak:{p.id}", 0)
            await ctx.term.write(_menu(p))
            fee = ENTRY_FEE_PER_LEVEL * p.level
            await ctx.term.write(
                f"  `2Entry `%{fee}`2 gold.  You have `%{p.gold}`2."
                + (f"  Win streak: `%{streak}`2.\n\n" if streak else "\n\n")
            )
            choice = await ctx.term.menu(
                {"1": "hal", "2": "grey", "3": "vane", "L": "leave"},
                "  `2Your choice? [`0L`2] : `%",
            )
            if choice == "L":
                await ctx.term.write("\n  `2The crowd does not notice you go.\n")
                return
            await self._bout(ctx, _CHAMPIONS[int(choice) - 1], fee)

    async def _bout(self, ctx: IgmContext, champion, fee: int) -> None:
        p = ctx.player
        name, weapon, hp_mult, str_mult, purse_mult = champion
        fought = ctx.store.get(f"bouts:{p.id}", 0)
        if fought >= BOUTS_PER_DAY:
            await ctx.term.write(
                '\n  `0"Three bouts is a day\'s work, and the crowd wants someone\n'
                '  new. Come back tomorrow."`2\n'
            )
            await ctx.term.pause()
            return
        if p.gold < fee:
            await ctx.term.write(
                '\n  `0"No coin, no bout,"`2 says the master of the games.\n'
            )
            await ctx.term.pause()
            return
        if p.hp < p.hp_max // 4:
            await ctx.term.write(
                '\n  `0"Come back when you can stand up straight."`2\n'
            )
            await ctx.term.pause()
            return
        p.gold -= fee
        ctx.store.set(f"bouts:{p.id}", fought + 1)

        enemy = Combatant(
            name=name,
            hp=p.level * hp_mult,
            hp_max=p.level * hp_mult,
            strength=p.level * str_mult,
            defense=0,
            weapon_name=weapon,
            is_arena=True,  # no running, no skills -- see the module docstring
        )
        fight = Fight(Combatant.from_player(p), enemy, ctx.rng, pfight=False)
        await ctx.term.write(f"\n  `2**`%ARENA BOUT`2**  `0{name}`2 steps onto the sand.\n")
        opening = fight.opening()
        await ctx.term.write(f"\n  {opening.text}\n")
        p.hp = fight.player_side.hp

        while not fight.over:
            await ctx.term.write(
                f"\n  `2Your Hitpoints : `0{max(0, fight.player_side.hp)}\n"
                f"  `2{name}`2's Hitpoints : `0{max(0, fight.enemy.hp)}\n\n"
            )
            if await ctx.term.menu(
                {"A": "attack", "Y": "yield"},
                "  `2(`0A`2)ttack  (`0Y`2)ield and beg for mercy  [`0A`2] : `%",
            ) == "Y":
                await ctx.term.write(
                    "\n  `2You raise a hand and beg for mercy.  The crowd jeers.\n"
                )
                await ctx.term.pause()
                return
            round_ = fight.player_attack()
            await ctx.term.write(f"\n  {round_.text}\n")
            if not fight.over and round_.counter:
                await ctx.term.write(f"  {fight.enemy_attack().text}\n")
            p.hp = max(0, fight.player_side.hp)

        if fight.winner == "player":
            await self._win(ctx, fight, name, purse_mult)
        else:
            p.hp = 1  # the arena's healer earns his keep
            ctx.store.set(f"streak:{p.id}", 0)
            await ctx.term.write(
                f"\n  `4{name}`2 puts you on your back.  You wake in the undercroft\n"
                "  with a bucket of water in your face and nothing in your purse.\n"
            )
            await ctx.term.pause()

    async def _win(self, ctx: IgmContext, fight: Fight, name: str, purse_mult: int) -> None:
        p = ctx.player
        streak = min(ctx.store.get(f"streak:{p.id}", 0) + 1, STREAK_CAP)
        ctx.store.set(f"streak:{p.id}", streak)
        purse = int(p.level * purse_mult * (1 + STREAK_BONUS * (streak - 1)))
        # ARENA.DOC: "you can win LOTS of gold or gems IF you can beat
        # 'TYR'" -- no rate/amount is documented, so this wires the
        # already-ported lord.js overkill loot bonus (Fight._loot_bonus,
        # combat.py) into the purse instead of inventing a new roll:
        # gem_found -> +1 gem, bonus_gold -> double the purse. Same pattern
        # as igms/warriors_graveyard/igm.py's _win(). The round text
        # already announced "You find a gem!"/"You find more gold than
        # expected!" above.
        if fight.bonus_gold:
            purse *= 2
        if fight.gem_found:
            p.gems += 1
        p.gold += purse
        await ctx.term.write(
            f"\n  `2{name}`2 goes down, and the sand drinks it up.\n"
            f"  `%YOU WIN {purse} GOLD.`2"
            + (f"  `8({streak} in a row)`2\n" if streak > 1 else "\n")
        )
        if streak >= STREAK_CAP:
            ctx.news(f"`0{p.name} `2is unbeaten in the Arena of Lords!")
        await ctx.term.pause()

    async def daily_maint(self, ctx: IgmMaintContext) -> None:
        """Streaks are a day's work, not a lifetime's."""
        for player in ctx.repo.all_players():
            ctx.store.delete(f"streak:{player.id}")
            ctx.store.delete(f"bouts:{player.id}")
