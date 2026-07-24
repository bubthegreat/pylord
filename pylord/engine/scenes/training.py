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

from pylord.engine import data
from pylord.engine.combat import Combatant, Fight, skill_attack
from pylord.engine.game import scene

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
            {"Q": "ask", "A": "attack", "R": "town"},
            "  `2(Q,A,R)`2 : ",
        )
        if choice == "R":
            return "town"
        if choice == "Q":
            await _ask(ctx, trainer)
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


def _can_skill(p: Player) -> bool:
    return p.class_type in _SKILL_BY_CLASS and p.skill_uses > 0


def _battle_options(p: Player) -> dict[str, str]:
    options = {"A": "attack", "R": "run"}
    if _can_skill(p):
        options["S"] = "skill"
    return options


async def _battle_prompt(ctx: GameCtx, fight: Fight, trainer: Master) -> None:
    p = ctx.player
    lines = [
        "",
        f"  `2Your Hitpoints : `0{fight.player_side.hp}",
        f"  `2{trainer.name}`2's Hitpoints : `0{max(fight.enemy.hp, 0)}",
        "",
        "  `2(`5A`2)ttack",
        "  `2(`5R`2)un",
    ]
    entry = _SKILL_BY_CLASS.get(p.class_type)
    if entry is not None and _can_skill(p):
        _field, _kind, label = entry
        lines.append(f"  `2(`0S`2)kill: {label} (`%{p.skill_uses}`0)")
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

    while not fight.over:
        await _battle_prompt(ctx, fight, trainer)
        action = await ctx.io.menu(_battle_options(p), "")

        if action == "A":
            last_round = fight.player_attack()
            await ctx.io.write(f"\n  {last_round.text}\n")
            if not fight.over:
                enemy_round = fight.enemy_attack()
                await ctx.io.write(f"  {enemy_round.text}\n")
        elif action == "S":
            _field, kind, _label = _SKILL_BY_CLASS[p.class_type]
            last_round = skill_attack(fight, kind, p.skill_uses)
            cost = fight.last_spell_cost if kind == "my" else 1
            p.skill_uses -= cost
            await ctx.io.write(f"\n  {last_round.text}\n")
            if not fight.over:
                enemy_round = fight.enemy_attack()
                await ctx.io.write(f"  {enemy_round.text}\n")
        elif action == "R":
            hp_before = fight.player_side.hp
            ran = fight.attempt_run()
            if ran:
                await ctx.io.write(
                    f"\n  You turn to run, and dash into the forest, "
                    f"leaving {trainer.name} behind!\n"
                )
            else:
                dmg = hp_before - fight.player_side.hp
                await ctx.io.write(f"\n  {trainer.name} sees you!\n")
                if dmg > 0:
                    await ctx.io.write(f"  {trainer.name} hits you for {dmg} damage!\n")
                else:
                    await ctx.io.write(f"  {trainer.name} misses you completely!\n")

        p.hp = fight.player_side.hp

    if fight.ran_away:
        await ctx.io.pause()

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

    if fight.gem_found:  # reference/lord.js:6905-6924/6973-6991 -- gem
        p.gems += 1  # bonus applies regardless of monster vs. master.

    p.seen_master = 0  # reference/lord.js:15804

    await ctx.io.write("\n".join(lines) + "\n")
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
