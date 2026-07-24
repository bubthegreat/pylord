"""Turgon's Warrior Training -- port of ``reference/lord.js``'s
``turgons()`` (``:15572-15884``): question your master, fight your master,
and (on a win) level up.

``MASTERS[player.level]`` is always "your current master" while
``player.level < 12`` (fight them to advance to ``level + 1``); at level 12
(only reachable after beating ``MASTERS[11]``, Turgon) there's no master
left to fight at all -- the scene shows the "find the Red Dragon" send-off
and returns straight to town (lord.js:15817-15840).

**`` `Q`uestion `` vs `` `A`ttack `` -- who gets ``needstr1``/``needstr2``**
(post-review correction against an earlier draft of this task's own brief,
which described the *attack* flow as showing ``needstr1`` "when not
ready"): lord.js's actual ``ask()`` (`` `Q` ``, lord.js:15577-15610) shows
``needstr1``/``needstr2`` when the player *already* has enough exp
(``player.exp > trainer.need``) -- flavor text for "you don't need me
anymore". When the player *doesn't* have enough exp yet, ``ask()`` instead
shows a generic "you need about N more experience" line; ``needstr1`` is
never shown there. Separately, ``attack_master()`` (`` `A` ``,
lord.js:15649-15807) has its own *own* under-threshold response -- a
comedic "your weapon disappears, the crowd laughs at you" sequence that
doesn't reference ``needstr1``/``needstr2`` at all. Ported here exactly as
lord.js has it (lord.js wins over the brief's paraphrase, this project's
established convention -- see e.g. ``combat.py``'s module docstring, note
5, or ``forest.py``'s module docstring, deviation 1).

**``seen_master`` (once-per-day gate)**: set the instant a real fight
*could* have started -- either the comedic under-threshold "not ready"
sequence, or right before an actual master fight begins
(lord.js:15726/15745) -- and checked only by `` `A`ttack `` (not `` `Q` ``,
which can be pressed any number of times): a second `` `A` `` press the same
day gets "I would like to battle again, but it is too late" instead of
another attempt (lord.js:15666-15682). Reset to ``False`` on a win
(lord.js:15804, so the *new* current master can potentially be challenged
the same day) and, globally, once a day by
``pylord/engine/daily.py``'s ``maintenance()``.

**Deviations** (mirrored into ``docs/deviations.md``):

1. **No `` `V`iew rankings`` (Heroes Of The Realm)** -- lord.js's `` `V` ``
   (lord.js:15870-15881) writes a dragon-kill leaderboard
   (``rank_king()``/``drag_kills``); ``Player`` has no ``drag_kills`` field
   and there's no dragon-kill tracking anywhere in this project yet
   (Task 13+). Dropped.
2. **No ``raise_class()`` class-skill-rank increase on a win**
   (lord.js:15803, function body lord.js:10578-10771) -- a real, sizeable
   mechanic (permanent ``skillw``/``skillm``/``skillt`` rank +1 per win, up
   to a class-mastery/"choose a new profession" branch at rank 40) that
   this task's brief doesn't ask for and that depends on the
   ``levelw``/``levelm``/``levelt`` daily-counter fields this project
   collapsed away (see ``forest.py``'s module docstring, deviation 3).
   Deferred; not silently -- flagged here and in ``docs/deviations.md``.
3. **No ``tournament_check()``** (lord.js:15805, body lord.js:3362-3420) --
   an end-game dragon-kill tournament trigger, out of scope (no
   ``drag_kills``/PvP-kill/tournament-settings modeling exists yet).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylord.engine import data, fights
from pylord.engine.combat import Combatant, Fight
from pylord.engine.game import scene
from pylord.engine.scenes import _battle

if TYPE_CHECKING:
    from pylord.engine.data import Master
    from pylord.engine.game import GameCtx
    from pylord.models import Player

# class_type -> (skill_points field, skill_attack() 'kind', display label).
# Mirrors forest.py's identical table -- see that module's docstring
# (deviation 3) for why p.skill_uses (not the permanent rank field) is what
# gets passed as skill_attack()'s skill_points argument.
_SKILL_BY_CLASS: dict[int, tuple[str, str, str]] = {
    1: ("skill_dk", "dk", "Death Knight Attack"),
    2: ("skill_my", "my", "Mystical Skills"),
    3: ("skill_th", "th", "Thieving Skills"),
}


def _weapon_name(p: Player) -> str:
    return "Fists" if p.weapon_num == 0 else data.weapon(p.weapon_num).name


def _current_master(p: Player) -> Master:
    return data.MASTERS[p.level] if p.level < 12 else data.MASTERS[11]


@scene("training")
async def training(ctx: GameCtx) -> str:
    while True:
        p = ctx.player
        trainer = _current_master(p)
        await ctx.io.write(
            f"\n  `3`2Your master is `%{trainer.name}`2.\n\n"
            "  `5Turgon's Warrior Training`2\n"
        )
        if p.level > 11:  # reference/lord.js:15828-15836
            await ctx.io.write(
                "\n  You pay your respects to Turgon, and stroll around the grounds.  Lesser\n"
                "  warriors bow low as you pass.  Turgon's last words advise you to find and\n"
                "  kill the `4Red Dragon`2..\n\n"
            )
            await ctx.io.pause()
            return "town"

        choice = await ctx.io.menu(
            # `V` is lord.js's own "View the rankings" key
            # (reference/lord.js:15870-15881), which shows rank_king()'s
            # dragon-slayer board -- this project's `hall` scene.
            # lord.js also exits on Enter (:15883); this port doesn't
            # register it, because TermIO.menu() deliberately swallows a
            # stray CR for line-mode clients (see its docstring) and a
            # quit-on-Enter key would fire on every such client's input.
            # `E` is this project's own endurance training -- see
            # pylord/engine/fights.py and docs/deviations.md.
            {"Q": "ask", "A": "attack", "E": "endurance", "V": "hall", "R": "town"},
            "  `2(Q,A,E,V,R)`2 : ",
        )
        if choice == "R":
            return "town"
        if choice == "V":
            return "hall"
        if choice == "Q":
            await _ask(ctx, trainer)
        elif choice == "E":
            await _endurance(ctx)
        else:
            await _attack_master(ctx, trainer)


async def _ask(ctx: GameCtx, trainer: Master) -> None:
    """Port of ``ask()``. reference/lord.js:15577-15610."""
    p = ctx.player
    lines = [
        "",
        "  `%Questioning Your Master`2",
        "-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-",
        "",
    ]
    if p.exp > trainer.exp_reward:
        lines.append(f"  `0{trainer.name} `2looks at your carefully and says: ")
        lines.append("")
        if trainer.needstr1:
            text = trainer.needstr1.replace("&PWE", _weapon_name(p))
            lines.append(f'  `2"`0{text}`2"')
        if trainer.needstr2:
            lines.append(f'  `2"`0{trainer.needstr2}`2"')
    else:
        lines.append("")
        lines.append(f"  `0{trainer.name}`2 looks at you carefully.")
        lines.append("")
        need = trainer.exp_reward - p.exp
        lines.append(f'  `2"`0You need about `%{need}`0 more experience before')
        lines.append('   you will be as good as I am.`2"')
    lines.append("")
    await ctx.io.write("\n".join(lines) + "\n")
    await ctx.io.pause()


async def _attack_master(ctx: GameCtx, trainer: Master) -> None:
    """Port of ``attack_master()``. reference/lord.js:15649-15807."""
    p = ctx.player
    await ctx.io.write(
        "\n\n  `%Fighting Your Master\n"
        "`2-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n\n"
    )

    if p.seen_master:  # reference/lord.js:15666-15682
        son = "son" if p.gender == "M" else "daughter"
        await ctx.io.write(
            f'  "I would like to battle again, but it is too late my {son}."\n'
            f"  `2{trainer.name} tells you.  You figure you will try again\n"
            "  tomorrow.\n\n"
        )
        await ctx.io.pause()
        return

    if p.exp < trainer.exp_reward:  # reference/lord.js:15683-15727
        await ctx.io.write(
            "  You are escorted down the hallway and into the battle arena.\n\n"
            "  THE BATTLE BEGINS!\n\n"
        )
        await ctx.io.pause()
        await ctx.io.write(
            f"  `2You raise your `0{_weapon_name(p)} `2to strike!  You wonder why everyone\n"
            "  is looking at you with grins on their faces...\n\n"
        )
        await ctx.io.pause()
        await ctx.io.write("  Your weapon is gone!  You are holding air!\n\n")
        await ctx.io.pause()
        await ctx.io.write(
            "  Your Master is holding it!  The entire crowd is laughing at you!\n\n"
        )
        await ctx.io.write(
            "  You meekly accept the fact that you are not ready for your testing.\n\n"
        )
        await ctx.io.pause()
        p.seen_master = 1
        return

    # Ready: real fight. reference/lord.js:15729-15807.
    await ctx.io.write(
        f"`2  You enter the fighting arena, ready with your `0{_weapon_name(p)}`2.\n\n"
        "  When your name is called, you move to the proper position and take a\n"
        "  fighting stance against your master.\n"
    )
    p.seen_master = 1  # reference/lord.js:15745
    await ctx.io.write(
        f"\n\n  `2**`%MASTER FIGHT`2**\n\n  You have encountered {trainer.name}`2!!\n\n"
    )

    fight, last_round = await _run_master_fight(ctx, trainer)

    if fight.winner == "player":
        await _victory(ctx, trainer, fight, last_round)
    elif fight.winner == "enemy":
        await _mercy(ctx, trainer)
    # else: ran away -- lord.js falls through attack_master() silently in
    # this case (neither the `player.dead` nor the `trainer.hp < 1` branch
    # fires), so nothing further is shown here either.


async def _endurance(ctx: GameCtx) -> None:
    """Buy one permanent forest fight per day.

    **Not a lord.js mechanic** -- lord.js's allowance is flat and refills
    only at the daily reset. Here your master will train your stamina for
    gold, each point dearer than the last (see
    ``pylord/engine/fights.py``'s ``endurance_cost``), and the extra
    capacity survives everything except a new character.
    """
    p = ctx.player
    cost = fights.endurance_cost(p, ctx.config)
    ceiling = fights.max_forest_fights(p, ctx.config)
    await ctx.io.write(
        "\n  `2Your master looks you over.\n\n"
        f'  `0"You can take `%{ceiling}`0 trips into the forest a day.  Another\n'
        f'  will cost you `%{cost}`0 gold, and a great deal of sweat."`2\n\n'
        f"  `2You have `0{p.gold}`2 gold.\n"
    )
    if await ctx.io.menu({"Y": "yes", "N": "no"}, "  `2Train? [`0N`2] : `%") == "N":
        await ctx.io.write('\n  `0"Come back when you have the stomach for it."`2\n')
        await ctx.io.pause()
        return
    if p.gold < cost:
        await ctx.io.write(
            '\n  `0"Come back when you can pay for it,"`2 your master grunts.\n'
        )
        await ctx.io.pause()
        return

    p.gold -= cost
    p.endurance_bought += 1
    fights.grant_bonus(p)
    p.forest_fights = min(
        p.forest_fights + 1, fights.max_forest_fights(p, ctx.config)
    )
    await ctx.io.write(
        "\n  `2Hours of drills later you can barely stand -- but you can go\n"
        "  one trip further into the forest than you could this morning.\n\n"
        f"  `%YOU CAN NOW TAKE {fights.max_forest_fights(p, ctx.config)} FOREST "
        "FIGHTS A DAY.`2\n"
    )
    await ctx.io.pause()


def _can_skill(p: Player) -> bool:
    return p.class_type in _SKILL_BY_CLASS and p.skill_uses > 0


def _battle_options(p: Player) -> dict[str, str]:
    """No `(R)un` and no `(S)kill` here: your master is an arena opponent,
    and lord.js refuses both against one (reference/lord.js:7001-7006 and
    :7045-7051/:7118-7124/:7211-7217 -- "You came here to prove your
    worth" / "Your honor stops you...")."""
    options = {"A": "attack"}
    options.update(_battle.extra_options(p))
    return options


async def _battle_prompt(ctx: GameCtx, fight: Fight, trainer: Master) -> None:
    p = ctx.player
    lines = [
        "",
        f"  `2Your Hitpoints : `0{fight.player_side.hp}",
        f"  `2{trainer.name}`2's Hitpoints : `0{max(fight.enemy.hp, 0)}",
        "",
        "  `2(`5A`2)ttack",
    ]
    lines.extend(_battle.extra_menu_lines(p))
    lines.append("")
    lines.append(f"  `2Your command, `0{p.name}`2?  [`5A`2] : ")
    await ctx.io.write("\n".join(lines))


async def _run_master_fight(ctx: GameCtx, trainer: Master):
    """Drives one master fight to completion via the shared combat engine
    (``pfight=False`` -- masters are always fought this way, see
    ``combat.py``'s module docstring note 5). Mirrors ``forest.py``'s
    ``_run_fight`` battle loop; not shared code with it because the two
    diverge sharply once the fight ends (death vs. mercy, no gold/news).

    Returns ``(fight, last_round)`` -- ``last_round`` is the final
    ``player_attack()``/``skill_attack()`` ``Round`` (or ``None``), needed
    by ``_victory()`` to decide whether the overkill "death" phrase fires.
    """
    p = ctx.player
    fight = Fight(
        Combatant.from_player(p), Combatant.from_master(trainer), ctx.rng, pfight=False
    )
    last_round = None
    await _battle.opening(ctx, fight)  # reference/lord.js:7375-7391
    p.hp = fight.player_side.hp

    while not fight.over:
        await _battle_prompt(ctx, fight, trainer)
        action = await ctx.io.menu(_battle_options(p), "")

        if action == "H":
            last_round = await _battle.fairy_lore_heal(ctx, fight)
        else:  # action == "A"
            last_round = fight.player_attack()
            await ctx.io.write(f"\n  {last_round.text}\n")
            await _battle.enemy_turn(ctx, fight, last_round)

        p.hp = fight.player_side.hp

    return fight, last_round


async def _victory(ctx: GameCtx, trainer: Master, fight: Fight, last_round) -> None:
    """Port of the win tail of ``attack_master()``.
    reference/lord.js:15773-15806.

    **Post-review fix**: the "Ultimate Warrior" line (lord.js:15792-15801)
    is built into ``mline`` and sent to ``log_line(mline)`` (lord.js:15802)
    -- it's a *news* broadcast, never printed to the winning player's own
    screen (the player-visible text ends at "YOU ARE NOW LEVEL N.",
    lord.js:15789). An earlier draft of this function printed it directly
    to the player and never called ``log_line``'s equivalent
    (``ctx.news()``) at all -- both are corrected here.
    """
    p = ctx.player
    lines = [""]

    overkill = (
        last_round is not None
        and last_round.killed
        and (last_round.damage > p.strength)
    )  # reference/lord.js:6973/6905, gates op.death for a non-pfight fight
    if overkill:
        lines.append(f"  {trainer.death}")
        lines.append("")

    lines.append(f"  `%You have bested {trainer.name}`%!")
    lines.append("")
    lines.append(f"`%  {trainer.swear}")
    lines.append("")

    gain = data.LEVEL_STATS[p.level]
    p.hp_max += gain.hp
    p.hp = p.hp_max
    p.strength += gain.strength
    p.defense += trainer.defense  # == gain.defense, see levels.py's docstring
    p.level += 1

    lines.append(
        f"  `2You receive `0{gain.hp}`2 hitpoints, `0{gain.strength}`2 strength"
        f" and `0{trainer.defense}`2 defense points!"
    )
    lines.append("")
    lines.append(f"  `%YOU ARE NOW LEVEL {p.level}.")
    lines.append("")
    # Not lord.js: every master win also raises the forest-fight ceiling
    # by one (pylord/engine/fights.py).
    fights.grant_bonus(p)
    p.forest_fights = min(
        p.forest_fights + 1, fights.max_forest_fights(p, ctx.config)
    )
    lines.append(
        "  `2Your stamina grows with your skill -- `0one `2more forest fight "
        "a day."
    )
    lines.append("")

    if fight.gem_found:  # reference/lord.js:6905-6924/6973-6991 -- gem
        p.gems += 1  # bonus applies regardless of monster vs. master.

    p.seen_master = 0  # reference/lord.js:15804

    await ctx.io.write("\n".join(lines) + "\n")
    await _raise_class(ctx)  # reference/lord.js:15803
    # reference/lord.js:15791-15802 (mline / log_line()) -- news-only, never
    # shown to the player. Built *after* player.level += 1 above, matching
    # lord.js's own ordering (mline is assembled right after the increment).
    mline = f"  `0{p.name} `2has beaten `%{trainer.name}!"
    if p.level == 12:
        pronoun = "He" if p.gender == "M" else "She"
        mline += f"\n  {pronoun} has become the Ultimate Warrior!"
    ctx.news(mline)
    # No pause() here -- lord.js's win branch has no more()/more_nomail()
    # call anywhere between the stat-gain text and the news broadcast; the
    # player falls straight back to turgons()'s own prompt() (this
    # module's outer training() loop redraws immediately).


# class_type -> (rank field, mastery flag, display name). reference/lord.js's
# skillw/skillm/skillt and the class names raise_class() prints.
_CLASS_SKILL: dict[int, tuple[str, str, str]] = {
    1: ("skill_dk", "mastered_dk", "Death Knight Skills"),
    2: ("skill_my", "mastered_my", "Mystical Skills"),
    3: ("skill_th", "mastered_th", "Thieving Skills"),
}

_MASTERY_RANK = 40  # reference/lord.js:10583-10607 (`> 39`)

# Letter -> class_type, the same mapping choose_profession() uses
# (`' KDL'.indexOf(ch)`, reference/lord.js:4837-4888).
_PROFESSION_KEYS = {"K": 1, "D": 2, "L": 3}


async def _raise_class(ctx: GameCtx) -> None:
    """Port of ``raise_class()``. reference/lord.js:10578-10771.

    Every master win raises the player's *permanent* class rank by one
    (lord.js:15803 calls this right after the level-up). Rank is what gates
    the Mystical spell tiers in battle (:7247-7268) and what the rankings
    screen's "Mastered" column reads; ``pylord/engine/daily.py`` already
    recomputes the daily use budget from it.

    Uses-per-day also rises immediately, without waiting for tomorrow's
    maintenance: every 4th rank for a Death Knight/Thief
    (``settings.old_skill_points`` defaults false, so the divisor is 4 --
    :1866, :10645-10658) and every rank for a Mystical (:10672-10676).
    At rank 40 the class is mastered and the player picks a new profession
    (:10620-10625); the flavor instruction screens (:10680-10771) are
    condensed to their mechanical outcome.
    """
    p = ctx.player
    entry = _CLASS_SKILL.get(p.class_type)
    if entry is None:
        return
    field, mastered_flag, label = entry

    if all(
        getattr(p, f) >= _MASTERY_RANK for f, _flag, _lbl in _CLASS_SKILL.values()
    ):  # reference/lord.js:10582-10585
        await ctx.io.write("\n  `%** `0YOU HAVE ALREADY MASTERED ALL SKILLS `%**`2\n")
        return
    if getattr(p, field) >= _MASTERY_RANK:  # reference/lord.js:10588-10606
        await ctx.io.write("\n  `%** `0YOU HAVE ALREADY MASTERED THIS CLASS `%**`2\n")
        return

    rank = getattr(p, field) + 1
    setattr(p, field, rank)
    lines = ["", "  `%** `0YOUR CLASS SKILL IS RAISED BY ONE! `%**`2", ""]

    if p.class_type == 2:  # reference/lord.js:10671-10676
        p.skill_uses += 1
        lines.append(f"  `2You now have `0{rank}`2 Mystical Skill points a day.")
    elif rank % 4 == 0:  # reference/lord.js:10645-10650
        p.skill_uses += 1
        lines.append(f"  `2You now have `0{rank // 4}`2 uses of {label} a day.")
        if rank < _MASTERY_RANK:
            lines.append("  (four more lessons needed for next raise in uses per day)")
    else:  # reference/lord.js:10659-10668
        needed = 4 - (rank % 4)
        plural = "lesson" if needed == 1 else "lessons"
        lines.append(
            f"  You need {needed} more {plural} to also raise your "
            f"{label} Uses Per Day."
        )
    await ctx.io.write("\n".join(lines) + "\n")

    if rank >= _MASTERY_RANK:  # reference/lord.js:10620-10625
        setattr(p, mastered_flag, 1)
        await _choose_new_profession(ctx, label)


async def _choose_new_profession(ctx: GameCtx, label: str) -> None:
    """The rank-40 "learn a NEW skill" branch (reference/lord.js:10620-10625,
    which calls ``choose_profession(false)``). Classes already mastered are
    not offered again."""
    p = ctx.player
    await ctx.io.write(
        f"\n  You have mastered The {label} Completely.  You may choose to\n"
        "  learn a NEW skill now.\n\n"
        "  `0(`5K`0)illing A Lot Of Woodland Creatures\n"
        "  `0(`5D`0)abbling In The Mystical Forces\n"
        "  `0(`5L`0)ying, Cheating, And Stealing From The Blind\n"
    )
    options = {
        letter: str(clss)
        for letter, clss in _PROFESSION_KEYS.items()
        if getattr(p, _CLASS_SKILL[clss][1]) == 0
    }
    if not options:
        return
    choice = await ctx.io.menu(options, "  `2Pick one.  (`0K`2,`0D`2,`0L`2) : `%")
    p.class_type = _PROFESSION_KEYS[choice]


async def _mercy(ctx: GameCtx, trainer: Master) -> None:
    """Port of the loss tail of ``attack_master()``.
    reference/lord.js:15761-15772. Unlike a forest death, the master
    resurrects and fully heals the player on the spot -- no gold/exp
    penalty, no news announcement, and the session doesn't end."""
    p = ctx.player
    p.hp = p.hp_max  # reference/lord.js:15763
    await ctx.io.write(
        f"\n  `0{trainer.name} `2raises his {trainer.weapon}`2 to kill you!\n\n"
    )
    await ctx.io.pause()
    await ctx.io.write(
        "  At the last minute, he reaches down and helps you up.  He tells you not to\n"
        "  be discouraged, and for good gesture has you healed before you go.\n\n"
    )
    await ctx.io.pause()
