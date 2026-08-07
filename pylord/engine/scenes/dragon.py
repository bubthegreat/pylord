"""The Red Dragon -- town-square ``X``. Port of ``reference/lord.js``'s
``fight_dragon()`` (``:11919-12217``) plus the pre-fight gate/menu
(``attack_dragon()``, ``:15149-15194``).

**Where the gate lives**: in lord.js, the Dragon isn't its own town-square
letter at all -- it's the Forest's ``S`` ("Search"), itself gated on
``player.level < 12`` (``:15383-15392``, showing ``show_stats()`` instead
below that). This project's town square already dedicates its own ``X`` key
directly to the Dragon (``town.py``, matching the letter list lord.js's
``main()`` prompt advertises, ``:16881``), so no Forest detour is needed
here; the level-12 gate is reproduced directly in this scene instead, with
an invented refusal message (lord.js's own ``show_stats()`` fallback makes
no sense as a direct town destination) -- documented deviation.

**Daily gate**: ``player.seen_dragon`` (reset to ``false`` every day by
``pylord/engine/daily.py``, reference/lord.js:5436) blocks a second attempt
the same day -- "shaking so badly from your previous encounter"
(``:15157-15165``), ported verbatim. Set unconditionally the instant a real
attempt begins (``:12086``, *before* the battle, regardless of its
eventual outcome) -- so a run-away still burns today's one attempt, matching
``attack_dragon()``'s own ``do...while(!player.seen_dragon)`` loop, which
always exits after exactly one ``fight_dragon()`` call no matter how that
call ends.

**Pre-fight screen**: lord.js shows an external asset here (``lrdfile
('LAIRANS')``, ``:15154``) not present anywhere in ``reference/`` -- this
port supplies its own short flavor text instead (documented deviation, same
"asset not in this repo" situation as ``town.py``'s own MAIN menu note).

**Dragon stats**: hardcoded (``:12074-12084``, since ``dragon.bin``/
``lenemy.bin`` -- an optional server-side override file -- doesn't exist in
this repo either): str 2000, hp 15000, gold 1000, exp 1000, weapon
"Scorching Flame", death phrase "The earth shakes as the mighty beast
falls." ``beef_up()`` (``:1445-1471``, a post-first-kill difficulty ramp)
is gated on ``settings.beef_up``, which defaults ``false`` (``:1874``) --
not modeled, matching this project's "default-off deployment toggle"
convention. Fought via the shared combat engine with ``pfight=False``
(masters/monsters/dragon all use this -- see ``combat.py``'s module
docstring note 5; only real player-vs-player combat uses ``pfight=True``);
skill attacks are available exactly as in every other fight (``battle()``'s
``battle_prompt()`` is the same generic menu regardless of opponent type,
``:6841-6869``) -- reusing forest.py's/training.py's/pvp.py's identical
skill-attack battle loop.

**Victory** (``:12116-12217``): news fanfare (``log_line``, ``:12134``,
ported to ``await ctx.news()``), then the full epilogue/reset. The three
class-specific epilogue stories (``:11922-12065``) are long, purely-flavor
prose; this port condenses each to a couple of sentences capturing the same
beats (own class's fate, Barak's jab, the town's reaction) rather than
transcribing every line -- documented deviation, not a mechanical change.

**Reset, field-by-field** (``:12145-12172``, matched against this project's
``Player`` -- see the inline comments in :func:`_victory` for each one):
``level=1``, ``hp_max=20``, ``hp=hp_max``, ``weapon_num=1`` ("Stick"),
``armor_num=1`` ("Coat" -- lord.js's ``arm``/``arm_num``, this project's
``armor_num``), ``gold=500``, ``bank=0``, ``defense=3`` (base 0 + Coat's
power, matching a fresh player -- see ``models.Player.defense``),
``strength=10``, ``gems=10`` (a flat overwrite, **not** additive), ``alive=1``
(``player.dead=false``), ``at_inn=0`` (``player.inn=false``), ``exp=10``,
``forest_fights = min(config forest_fights_per_day + player.kids, 32000)``
(``:12163-12168``), ``player_fights = config player_fights_per_day``
(``:12169``), ``king_count += 1`` (``player.drag_kills += 1``, ``:12172``).
**Explicitly kept, not reset**: ``charm``, ``skill_dk``/``skill_my``/
``skill_th`` (all three "special skills" per the win screen's own promise,
``:12206``), ``kids``, ``married_to``, ``gender``, ``class_type``, ``name``.
``seen_dragon`` is left ``True`` (set at the top of the fight, never
unset here) -- reset the same as any other day, tomorrow, by
``daily.py``. lord.js's own ``player.flirted = false``/``player.
high_spirits = true`` (``:12170-12171``) map to fields this project's
``Player`` doesn't have (``flirts_today`` is a *different* lord.js field,
``player.flirted``, coincidentally spelled the same in this project's own
naming -- not touched here since Task 13a's daily reset already owns it) and
are skipped.

**Session continues** (``:12197-12217``, "YOUR QUEST IS NOT OVER"): the
default case -- the player keeps playing after being reset, same session.
**Global "quest over" tournament win** (``settings.win_deeds``, defaulting
to **3**, ``:1852`` -- *not* off by default): reaching that many dragon
kills (``player.drag_kills >= settings.win_deeds``) ends *this player's*
session immediately with the "YOUR QUEST IS OVER" screen
(``:12186-12196``) and records a ``game_state`` "won_by" marker. lord.js
additionally makes this a **global** gate -- every other player's next
login is redirected to a permanent "PAY HOMAGE" screen instead of being
allowed to play at all (``check_gameover()``, reference/lord.js
``:17293-17324``, wired into the login path, not any in-game scene). That
global login-blocking gate is server/login-flow territory this task's
interface list doesn't touch (only scene files) and is **not** implemented
here -- documented deviation; ``game_state['won_by']`` is recorded for a
future task to consume, but nothing currently reads it.

**Defeat** (``:12098-12115``): ``hp=0`` (explicitly, unlike a forest/PvP
death, which merely lets HP sit wherever combat left it), ``alive=0``,
``gold=0``. **No experience penalty at all** -- unlike every other death
path in this project (forest, PvP), lord.js's dragon-death branch has no
``exp -= exp / 10`` line; ported exactly as the asymmetry it is.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylord.engine.combat import Combatant, Fight, skill_attack
from pylord.engine.data import Monster, armor
from pylord.engine.game import scene
from pylord.engine.scenes import _battle

if TYPE_CHECKING:
    from pylord.engine.game import GameCtx
    from pylord.models import Player

_GOLD_CAP = 2_000_000_000
_STAT_CAP = 32_000
_DEFAULT_FOREST_FIGHTS = 15  # reference/lord.js:1857, matches daily.py
_DEFAULT_PLAYER_FIGHTS = 3  # reference/lord.js:1856, matches daily.py
_DEFAULT_WIN_DEEDS = 3  # reference/lord.js:1852

# reference/lord.js:12074-12084 (the no-dragon.bin hardcoded fallback --
# there is no dragon.bin/lenemy.bin anywhere in this repo, so this is
# unconditionally what gets used).
_DRAGON = Monster(
    name="`4The Red Dragon`2",
    weapon="`)Scorching Flame`2",
    strength=2000,
    hp=15000,
    gold=1000,
    exp=1000,
    death_phrase="  The earth shakes as the mighty beast falls.",
)

# Mirrors forest.py's/training.py's/pvp.py's identical table -- battle_prompt()
# is the same generic menu for every kind of fight in lord.js.
_SKILL_BY_CLASS: dict[int, tuple[str, str, str]] = {
    1: ("skill_dk", "dk", "Death Knight Attack"),
    2: ("skill_my", "my", "Mystical Skills"),
    3: ("skill_th", "th", "Thieving Skills"),
}

_INTRO = (
    "\n\n  `%The Dragon's Lair`0\n"
    "`2-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
    "  Deep in the forest, past bones bleached white by the sun, the cave\n"
    "  mouth glows with a dull red light.  You can feel the heat from here.\n"
    "  This is it -- the lair of the Red Dragon.\n\n"
    "  `2(`5A`2)ttack   (`5R`2)eturn\n"
)


def _can_skill(p: Player) -> bool:
    return p.class_type in _SKILL_BY_CLASS and p.skill_uses > 0


def _battle_options(p: Player) -> dict[str, str]:
    options = {"A": "attack", "R": "run"}
    if _can_skill(p):
        options["S"] = "skill"
    options.update(_battle.extra_options(p))
    return options


async def _battle_prompt(ctx: GameCtx, fight: Fight) -> None:
    p = ctx.player
    lines = [
        "",
        f"  `2Your Hitpoints : `0{fight.player_side.hp}",
        f"  `2{_DRAGON.name}`2's Hitpoints : `0{max(fight.enemy.hp, 0)}",
        "",
        "  `2(`5A`2)ttack",
        "  `2(`5R`2)un",
    ]
    entry = _SKILL_BY_CLASS.get(p.class_type)
    if entry is not None and _can_skill(p):
        _field, _kind, label = entry
        lines.append(f"  `2(`0S`2)kill: {label} (`%{p.skill_uses}`0)")
    lines.extend(_battle.extra_menu_lines(p))
    lines.append("")
    lines.append(f"  `2Your command, `0{p.name}`2?  [`5A`2] : ")
    await ctx.io.write("\n".join(lines))


@scene("dragon")
async def dragon(ctx: GameCtx) -> str | None:
    p = ctx.player
    if p.level < 12:  # deviation: invented refusal, see module docstring
        await ctx.io.write(
            "\n\n  A booming voice echoes from the cave: `4\"You are not yet\n"
            "  strong enough to face me, little one.  Return when you have\n"
            "  proven yourself to Turgon.\"`2\n\n"
        )
        await ctx.io.pause()
        return "town"

    if p.seen_dragon:  # reference/lord.js:15157-15165
        await ctx.io.write(
            "\n\n  You are shaking so badly from your previous encounter,\n"
            "  you deem it wise to wait and gather your strength!\n\n"
        )
        await ctx.io.pause()
        return "town"

    await ctx.io.write(_INTRO)
    choice = await ctx.io.menu({"A": "attack", "R": "return"}, "  `2Your choice`0? `2")
    if choice == "R":  # reference/lord.js:15183-15191
        await ctx.io.write(
            "\n  You decide it would be wise to depart from this wicked place.\n\n"
        )
        await ctx.io.pause()
        return "town"

    ended = await _fight_dragon(ctx)
    return None if ended else "town"


async def _fight_dragon(ctx: GameCtx) -> bool:
    """Port of ``fight_dragon(false)``. reference/lord.js:11919-12217.
    Returns ``True`` if the session should end -- either the player died,
    or won and immediately completed the ``win_deeds`` "quest over" ending
    (see ``_victory``'s docstring)."""
    p = ctx.player
    p.seen_dragon = 1  # reference/lord.js:12086 -- set before the battle,
    # unconditionally, regardless of outcome (see module docstring).

    await ctx.io.write(
        "\n\n  `%**`4DRAGON ENCOUNTER`%**\n\n  `2The Red Dragon approaches.\n\n"
    )  # reference/lord.js:12089-12093

    fight = Fight(
        Combatant.from_player(p),
        # is_dragon drives the per-swing weapon switch, whose Flaming
        # Breath outcome doubles the damage roll (reference/lord.js:6704-6720).
        Combatant.from_monster(_DRAGON, is_dragon=True),
        ctx.rng,
        pfight=False,
    )
    await _battle.opening(ctx, fight)  # reference/lord.js:7375-7391
    p.hp = fight.player_side.hp

    while not fight.over:
        await _battle_prompt(ctx, fight)
        action = await ctx.io.menu(
            # _battle_prompt() already wrote the prompt (which
            # advertises [A]), so name the default here.
            _battle_options(p), "", default="A"
        )

        if action == "A":
            round_ = fight.player_attack()
            await ctx.io.write(f"\n  {round_.text}\n")
            await _battle.enemy_turn(ctx, fight, round_)
        elif action == "H":
            round_ = await _battle.fairy_lore_heal(ctx, fight)
        elif action == "S":
            field, kind, _label = _SKILL_BY_CLASS[p.class_type]
            round_ = skill_attack(
                fight, kind, p.skill_uses, skill_rank=getattr(p, field)
            )
            cost = fight.last_spell_cost if kind == "my" else 1
            p.skill_uses -= cost
            await ctx.io.write(f"\n  {round_.text}\n")
            await _battle.enemy_turn(ctx, fight, round_)
        elif action == "R":
            hp_before = fight.player_side.hp
            ran = fight.attempt_run()
            if ran:  # reference/lord.js:7022-7027, try_running()'s is_dragon branch
                await ctx.io.write(
                    "\n  `2You barely flip out of the way, as the `4Dragon`2 breathes huge\n"
                    "  amounts of fire where you were a second ago!  You run towards\n"
                    "  the forest, screaming all the way!\n"
                )
            else:
                dmg = hp_before - fight.player_side.hp
                await ctx.io.write(f"\n  {_DRAGON.name}`2 sees you!\n")
                if dmg > 0:
                    await ctx.io.write(f"  {_DRAGON.name}`2 hits you for {dmg} damage!\n")
                else:
                    await ctx.io.write(f"  {_DRAGON.name}`2 misses you completely!\n")

        p.hp = fight.player_side.hp

    if fight.ran_away:  # neither the dead nor the hp<1 branch fires in
        await ctx.io.pause()  # lord.js on a pure run-away.
        return False

    if fight.winner == "enemy":
        await _defeat(ctx)
        return True

    # A win can also end the session -- see _victory()'s "quest over" branch.
    return await _victory(ctx)


async def _defeat(ctx: GameCtx) -> None:
    """Port of the loss tail of ``fight_dragon()``. reference/lord.js:
    12098-12115. No experience penalty here -- see module docstring."""
    p = ctx.player
    p.hp = 0  # reference/lord.js:12099
    p.alive = 0  # reference/lord.js:12100 (player.dead = true)
    p.gold = 0  # reference/lord.js:12101

    await ctx.io.write(
        "\n\n  The Dragon pauses to look at you, then snorts in a Dragon laugh, and\n"
        "  delicately rips your head off, with the finesse only a Dragon well\n"
        "  practiced in the art could do.\n\n"
    )
    await ctx.news(f"  `2The `4Red Dragon `2has killed `5{p.name}`2!")  # lord.js:12113
    await ctx.io.pause()


_EPILOGUES = {
    1: (  # reference/lord.js:11923-11965, condensed -- Death Knight
        "  `2You carve the still-warm heart from the beast and carry it back to\n"
        "  town as proof.  When Barak sneers that you probably just skinned a\n"
        "  sheep, you remind him you're a LEVEL 12 warrior -- he has no reply.\n"
        "  The crowd declares you a hero.\n"
    ),
    2: (  # reference/lord.js:11967-12005, condensed -- Mystical
        "  `2Still shaking from the battle, you teleport back near Abdul's\n"
        "  Armour and walk the rest of the way to the Inn.  When you announce\n"
        "  the Dragon is no more, Barak bolts for the door without a word.\n"
        "  The bar gives you a standing ovation.\n"
    ),
    3: (  # reference/lord.js:12006-12064, condensed -- Thieving
        "  `2You clean your daggers and pocket a little gold from the bones on\n"
        "  your way out.  The town is deserted -- everyone is celebrating at\n"
        "  Turgon's already.  You slip in and tell your story, embellishing it\n"
        "  just enough to be believed.\n"
    ),
}


async def _victory(ctx: GameCtx) -> bool:
    """Port of the win tail of ``fight_dragon()``. reference/lord.js:
    12116-12217. Returns ``True`` if this win also ended the session (the
    ``win_deeds`` "quest over" branch -- lord.js's own ``exit(0)``,
    :12195), ``False`` if the player keeps playing (the reset happens
    either way)."""
    p = ctx.player
    await ctx.io.write("\n\n  You have defeated The Red Dragon!\n\n")
    await ctx.io.pause()

    await ctx.io.write(
        "\n\n  You have defeated the Dragon, and saved the town.  Your stomach\n"
        "  churns at the site of stacks of clean white bones - Bones of small\n"
        "  children.\n\n"
        "  THANKS TO YOU, THE HORROR HAS ENDED!\n\n"
    )
    await ctx.news(f"`.  `%{p.name} `2has slain the `4Red Dragon`2 and become a hero.")  # lord.js:12134
    await ctx.io.pause()

    await ctx.io.write(_EPILOGUES.get(p.class_type, _EPILOGUES[1]) + "\n")
    await ctx.io.pause()
    await ctx.io.write(
        "\n             Thanks for being tough enough to win the game,\n\n"
        "                              -Seth Able\n\n"
    )
    await ctx.io.pause()

    # --- Reset, field-by-field -- see module docstring. -----------------
    p.level = 1
    p.hp_max = 20
    p.hp = p.hp_max
    p.weapon_num = 1
    p.armor_num = 1
    p.gold = 500
    p.bank = 0
    p.defense = armor(1).power  # base 0 + Coat's power -- see models.Player.defense
    p.strength = 10
    p.gems = 10
    p.alive = 1
    p.at_inn = 0
    p.exp = 10

    # ctx.config *is* the [game] table (pylord/server.py passes
    # config["game"]); the old ctx.config["game"] lookup always missed, so
    # a sysop's fights-per-day and win_deeds settings were ignored here.
    game_cfg = ctx.config or {}
    forest_fights = game_cfg.get("forest_fights_per_day", _DEFAULT_FOREST_FIGHTS)
    p.forest_fights = min(forest_fights + p.kids, _STAT_CAP)  # lord.js:12163-12168
    p.player_fights = game_cfg.get("player_fights_per_day", _DEFAULT_PLAYER_FIGHTS)  # :12169
    p.king_count += 1  # reference/lord.js:12172 (player.drag_kills += 1)
    p.flirts_today = 0  # reference/lord.js:12170 (player.flirted = false)
    p.high_spirits = 1  # reference/lord.js:12171

    # reference/lord.js:12181 -- the realm remembers its latest hero.
    async with ctx.db.transaction() as tx:
        await tx.state.set("latesthero", p.name)

    win_deeds = game_cfg.get("win_deeds", _DEFAULT_WIN_DEEDS)
    if win_deeds > 0 and p.king_count >= win_deeds:  # reference/lord.js:12183-12196
        # lord.js overwrites state.won_by unconditionally (:12184-12185).
        async with ctx.db.transaction() as tx:
            await tx.state.set("won_by", p.id)
        await ctx.io.write(
            "\n`c  `%** YOUR QUEST IS OVER **`0\n\n"
            "  `2You must indeed be the chosen one.  The ancient magic that\n"
            "  kept the `4dragon `2alive is now truly no more.\n\n"
        )
        await ctx.io.pause()
        await ctx.io.write(
            "  `0Now begone, blessed among warriors - Your fight is over.\n\n"
        )
        return True

    await ctx.io.write(
        "\n`c  `%                ** YOUR QUEST IS NOT OVER **`0\n\n"
        "  `2You are a hero.  Bards will sing of your deeds, but that doesn't\n"
        "  mean your life doesn't go on.\n\n"
        "  `%YOUR CHARACTER WILL NOW BE RESET.  `2But you will keep a few things\n"
        "  you have earned.  Like the following.\n\n"
        "  `%ALL SPECIAL SKILLS.\n"
        "  CHARM.\n"
        "  A FEW OTHER THINGS.\n\n"
    )
    await ctx.io.pause()
    await ctx.io.write(
        "\n`c  `%YOU FEEL STRANGE.`0\n\n"
        "  `2Apparently, you have been sleeping.  You dust yourself off, and\n"
        "  regain your bearings.  You feel like a new person!\n\n"
    )
    await ctx.io.pause()
    return False
