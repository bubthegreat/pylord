"""The Forest -- monster fights, forest-events, and the daily fight budget.

Ported from ``reference/lord.js``'s ``forest()`` (``:12220-15247``), in
particular its inner functions ``menu()``/``prompt()`` (``:15196-15246``,
the persistent forest menu), ``look_to_kill()`` (``:14474-15119``, the 'L'
handler -- forest events + monster encounter), and the shared combat-loop
wiring in ``battle_prompt()``/``do_attack()``/``handle_hit()`` (already
ported onto ``pylord.engine.combat`` in Task 7).

Menu letters/destinations: the top-level task brief's "Produce" section
(the authoritative, most specific source -- see also the module-level
"Deviations" note below) asks for **(L)ook for something to kill,
(H)ealer's Hut -> "healer", (R)eturn to town -> "town", (V)iew your
stats -> "stats"**. ``(L)``/``(H)``/``(R)`` text matches lord.js's own
persistent forest menu verbatim (``:15210-15216``); ``(V)`` is a
reconstruction matching Town Square's own "(V)iew your stats" wording
(``pylord/engine/scenes/town.py:39``) since lord.js's forest menu itself
has no stats option at all (it's on the *battle* prompt instead, as `S`
-- lord.js ``:15382-15395``; see the "Deviations" note for why this
project drops that and uses `S` for skill-attacks in-battle instead, per
this task's own explicit instruction).

Deviations from lord.js (also mirrored into ``docs/deviations.md``):

1. **No forest fights left**: lord.js's own handler (``:15308-15316``) just
   shows "You are too tired. / Try again tomorrow." and loops back to the
   *forest* menu (the `over` flag is never set) -- it does **not** send the
   player back to town. This module follows lord.js here rather than an
   earlier draft of this task's own brief text (which suggested "back to
   town"): lord.js's actual behavior wins per this project's established
   convention (see e.g. ``pylord/engine/combat.py``'s module docstring,
   note 5).
2. **In-battle menu**: lord.js's real ``battle_prompt()`` (``:6841-6869``)
   offers ``(A)ttack``, ``(S)tats``, ``(R)un``, and a *per-class-lettered*
   skill option (`D`eath Knight / `M`ystical / `T`hieving). This task's
   brief explicitly asks for a single generic **(S)kill attack** letter
   instead (gated on the player's class skill rank *and* a shared daily
   ``skill_uses`` budget) and drops the in-battle "(S)tats" view entirely
   ("stats after fight" instead) -- both are deliberate simplifications
   requested by the brief, not lord.js's own letters.
3. **``skill_uses`` vs. ``skill_dk``/``skill_my``/``skill_th``**: lord.js
   keeps two numbers per class -- a permanent trained rank
   (``skillw``/``skillm``/``skillt``, set at Turgon's) and a *daily*
   spendable budget derived from it (``levelw``/``levelm``/``levelt``,
   recomputed every ``wake_up()`` and decremented per use --
   ``:7107``/``:7183``/``:7295`` etc.). This project's ``Player`` model
   collapses that to ``skill_dk``/``skill_my``/``skill_th`` (the permanent
   rank, used *only* by ``pylord/engine/daily.py``'s once-a-day
   ``skill_uses`` formula -- ``:5448-5469``) plus a single shared
   ``skill_uses`` (the daily budget). **Everywhere combat actually reads a
   "how much can I still spend" value, lord.js reads the daily
   levelw/levelm/levelt -- never the permanent rank** (menu visibility:
   ``:6858``, ``:6861``, ``:6864``; eligibility inside
   ``use_death_knight()``/``use_thief_skill()``: implicit, no rank check
   at all; Mystical tier auto-selection: ``:7251-7267``, gated on
   ``player.levelm`` primarily, with a ``player.skillm`` check that's
   provably redundant given ``levelm <= skillm`` always holds after
   ``wake_up()``'s ``levelm = skillm`` reset). So this module passes
   ``p.skill_uses`` -- never the rank field -- into ``skill_attack()`` as
   its ``skill_points`` argument (see ``_can_skill()`` and the "S" branch
   of ``_run_fight()``), for all three classes. Cost: DK/Thief always cost
   a flat 1 use point (lord.js ``:7107``, ``:7183``); Mystical costs the
   chosen tier's real price (1/4/8/12/16/20) -- see
   ``pylord.engine.combat.Fight.last_spell_cost``, which
   ``skill_attack(..., kind='my')`` sets to whatever was actually cast, so
   the caller here decrements ``skill_uses`` by the right amount instead
   of a flat 1.
4. **Forest events implemented**: lord.js's event table
   (``look_to_kill()``'s ``switch(random(15+horse))``, ``:14482-15041``)
   has up to 16 cases, several of which are entire sub-minigames (a horse
   trader, a full gambling tavern, a shared-pool "find lost gold" IGM
   protocol, an NPC "Olivia" easter egg gated behind a server setting that
   defaults off). Per the brief's explicit "keep scope sane: the 4-6 core
   events" instruction, this port implements exactly six: the "old man"
   escort (case 0, ``:14483-14523``), "find a gold sack" (case 2,
   ``:14571-14581``), "Merry Men" full heal (case 3, ``:14582-14592``),
   "find a gem" (case 4, ``:14593-14602``), the fairy blessing (case 9,
   ``:14779-14951``, simplified -- see ``_event_fairy``), and "nothing"
   (case 14, ``:15026-15027``, which is genuinely silent in lord.js -- no
   text at all). Every other index (1, 5, 6, 7, 8, 10, 11, 12, 13, 15)
   falls back to the same silent "nothing" outcome rather than being
   individually ported; skipped cases are itemized in ``docs/deviations.md``
   along with why (multiplayer shared state, sub-minigame complexity,
   settings-gated easter egg, or dependent on fields/systems this task
   doesn't own -- horse trading, skill-track leveling, charm-stick RNG).
   The *overall probability shape* (1-in-5 chance of any event firing,
   uniform over 15 or 16 sub-outcomes -- 16 when the player has a horse,
   ``:14482``) is preserved even though most of those 15/16 slots now
   resolve to "nothing".
5. **Run-away combat text**: ``Fight.attempt_run()`` (``pylord/engine/
   combat.py``) already applies the enemy's free counter-attack on a failed
   run internally (matching lord.js's ``try_running()``, ``:7008-7013``)
   but -- by its own documented interface -- returns only a ``bool``, not
   the ``Round`` describing that counter-attack. Rather than re-invoke
   ``enemy_attack()`` a second time here (which would double the damage and
   desync the shared RNG stream), this module infers the counter-attack's
   damage from the HP delta and reconstructs lord.js's own wording
   ("X hits you for N damage!" / "X misses you completely!" -- the exact
   phrasing ``Fight.enemy_attack()`` itself uses) around that number.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylord.engine import data
from pylord.engine.combat import Combatant, Fight, skill_attack
from pylord.engine.game import grant_exp, scene
from pylord.engine.scenes import _battle, jennie

if TYPE_CHECKING:
    from pylord.engine.data import Monster
    from pylord.engine.game import GameCtx
    from pylord.models import Player

# lord.js caps both gold and exp at 2,000,000,000 everywhere they're
# credited (e.g. reference/lord.js:15093-15095, :15108-15110).
_GOLD_CAP = 2_000_000_000
_EXP_CAP = 2_000_000_000

_MENU_LINES = (
    "",
    "`5  The Forest",
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-",
    "  `2(`0L`2)ook for something to kill       (`0H`2)ealer's Hut",
    "  `2(`0R`2)eturn to town                 (`0V`2)iew your stats",
    "",
)
_MENU = "\n".join(_MENU_LINES)
_PROMPT = "`2Your choice`0? `2"

# lord.js's forest switch (reference/lord.js:15258-15420). "Other Places"
# is *not* here -- it is a Town Square key (:17003), which is where this
# port now puts it too. `B` is the vulture that banks your gold (:15260),
# and `J` opens the JENNIE codeword easter egg (:15396) for a player in
# high spirits.
_MENU_OPTIONS = {
    "L": "look",
    "H": "healer",
    "R": "town",
    "Q": "town",
    "V": "stats",
    "B": "bank_gold",
    "J": "jennie",
    "T": "thief_flavor",
    "M": "mystic_flavor",
    "D": "dk_flavor",
    "A": "brandish",
}

# reference/lord.js:15319-15352 -- flavor-only keys that just print a line.
_FLAVOR_LINES = {
    "T": "  Your Thieving skills cannot help you here.",
    "M": "  Your Mystical skills cannot help you here.",
    "D": "  Your Death Knight skills cannot help you here.",
    "A": "  You brandish your weapon dramatically.",
}

# class_type -> (skill_points field, skill_attack() 'kind', display label).
# reference/lord.js:6858-6866 (per-class letters D/M/T); this project uses
# one generic 'S' letter instead -- see module docstring, deviation 2.
_SKILL_BY_CLASS: dict[int, tuple[str, str, str]] = {
    1: ("skill_dk", "dk", "Death Knight Attack"),
    2: ("skill_my", "my", "Mystical Skills"),
    3: ("skill_th", "th", "Thieving Skills"),
}


def _cap(value: int, cap: int) -> int:
    return min(value, cap)


def _status_line(p: Player) -> str:
    """reference/lord.js:15227-15246 -- the forest prompt's live status."""
    return (
        f"\n  `2HitPoints: (`0{p.hp}`2 of `0{p.hp_max}`2)"
        f"  Fights: `0{p.forest_fights}`2 Gold: `0{p.gold}"
        f"  `2Gems: `0{p.gems}\n"
    )


async def _bank_gold(ctx: GameCtx) -> None:
    """The hidden `B` key: a vulture carries your purse to the bank.
    reference/lord.js:15260-15272."""
    p = ctx.player
    if p.gold <= 0:
        return
    await ctx.io.write(
        "\n\n  You throw your gold pouch up into the air gleefully.\n\n"
        "  `0AN UGLY VULTURE `)GRABS `0IT IN MID AIR!`2\n"
    )
    p.bank = min(p.bank + p.gold, _GOLD_CAP)  # reference/lord.js:15267-15270
    p.gold = 0


@scene("forest")
async def forest(ctx: GameCtx) -> str | None:
    while True:
        await ctx.io.write(_MENU)
        await ctx.io.write(_status_line(ctx.player))
        choice = await ctx.io.menu(_MENU_OPTIONS, _PROMPT)
        if choice in ("R", "Q"):
            return "town"
        if choice == "V":
            return "stats"
        if choice == "H":
            return "healer"
        if choice in _FLAVOR_LINES:
            await ctx.io.write(f"\n\n{_FLAVOR_LINES[choice]}\n")
            continue
        if choice == "B":
            await _bank_gold(ctx)
            continue
        if choice == "J":
            await jennie.run(ctx)
            if not ctx.player.alive:  # the UGLY answer ends the session
                return None
            continue
        # choice == "L"
        died = await _look_to_kill(ctx)
        if died:
            return None


async def _look_to_kill(ctx: GameCtx) -> bool:
    """Port of ``look_to_kill()``. reference/lord.js:14474-15119.

    Returns ``True`` if the player died this press (caller ends the
    session), ``False`` otherwise (stay in the forest menu).
    """
    p = ctx.player
    if p.forest_fights < 1:  # reference/lord.js:15308
        await ctx.io.write(
            "\n\n  You are too tired.\n\n  Try again tomorrow.\n\n"
        )  # lord.js:15309-15314
        await ctx.io.pause()
        return False

    if ctx.rng.randrange(5) == 1:  # reference/lord.js:14480, 1-in-5 chance
        await _forest_event(ctx)
        return False

    monster = _pick_monster(ctx)
    p.forest_fights -= 1  # reference/lord.js:15057
    await ctx.io.write(
        f"\n\n  `2**`%FIGHT`2**\n\n  You have encountered {monster.name}`2!!\n\n"
    )  # lord.js:15062-15065
    return await _run_fight(ctx, monster)


def _pick_monster(ctx: GameCtx) -> Monster:
    """Port of the ``mnum`` monster-selection formula.
    reference/lord.js:15045-15056.

    ``MONSTERS`` is already sliced to the 10 reachable-per-level monsters
    (see ``pylord/engine/data/monsters.py`` for why), so this indexes
    straight into it instead of reproducing lord.js's flat 131-record
    ``mnum`` arithmetic.
    """
    p = ctx.player
    rng = ctx.rng
    if p.level == 1:
        return data.MONSTERS[1][rng.randrange(10)]
    if rng.randrange(6) != 2:  # normal case, 5-in-6
        return data.MONSTERS[p.level][rng.randrange(10)]
    # wildcard case, 1-in-6: any level from 1..player.level
    wildcard_level = rng.randrange(p.level) + 1
    return data.MONSTERS[wildcard_level][rng.randrange(10)]


def _can_skill(p: Player) -> bool:
    """Gate purely on the remaining daily budget (``skill_uses``), matching
    lord.js's own in-battle gate -- ``player.levelw``/``levelm``/``levelt``
    > 0 (reference/lord.js:6858, 6861, 6864), *not* the permanent rank
    (``skillw``/``skillm``/``skillt``). A rank-0 player of a skilled class
    still gets a nonzero daily budget from the flat "+1 for being a
    <class>" bonus (``pylord/engine/daily.py``), so a rank check here
    would wrongly hide the option in that case."""
    return p.class_type in _SKILL_BY_CLASS and p.skill_uses > 0


def _battle_options(p: Player) -> dict[str, str]:
    options = {"A": "attack", "R": "run"}
    if _can_skill(p):
        options["S"] = "skill"
    options.update(_battle.extra_options(p))
    return options


async def _battle_prompt(ctx: GameCtx, fight: Fight, monster: Monster) -> None:
    """Port of ``battle_prompt()``. reference/lord.js:6841-6869 (trimmed
    per module docstring deviation 2 -- no in-battle Stats, one generic
    Skill-attack letter)."""
    p = ctx.player
    lines = [
        "",
        f"  `2Your Hitpoints : `0{fight.player_side.hp}",
        f"  `2{monster.name}`2's Hitpoints : `0{max(fight.enemy.hp, 0)}",
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


async def _run_fight(ctx: GameCtx, monster: Monster) -> bool:
    p = ctx.player
    fight = Fight(
        Combatant.from_player(p), Combatant.from_monster(monster), ctx.rng, pfight=False
    )
    last_round = None
    await _battle.opening(ctx, fight)  # reference/lord.js:7375-7391

    while not fight.over:
        await _battle_prompt(ctx, fight, monster)
        action = await ctx.io.menu(_battle_options(p), "")

        if action == "A":
            last_round = fight.player_attack()
            await ctx.io.write(f"\n  {last_round.text}\n")
            await _battle.enemy_turn(ctx, fight, last_round)
        elif action == "H":
            last_round = await _battle.fairy_lore_heal(ctx, fight)
        elif action == "S":
            field, kind, _label = _SKILL_BY_CLASS[p.class_type]
            # Today's budget (skill_uses) gates eligibility; the permanent
            # class rank additionally gates which Mystical tier is castable
            # (lord.js:7247-7268 checks levelm AND skillm).
            last_round = skill_attack(
                fight, kind, p.skill_uses, skill_rank=getattr(p, field)
            )
            # DK/Thief always cost a flat 1 use point (lord.js:7107, 7183).
            # Mystical costs vary by tier (1/4/8/12/16/20); skill_attack()
            # records the real cost of whatever was actually cast (0 if
            # the cast failed) on fight.last_spell_cost -- see combat.py's
            # Fight docstring. Module docstring deviation 3.
            cost = fight.last_spell_cost if kind == "my" else 1
            p.skill_uses -= cost
            await ctx.io.write(f"\n  {last_round.text}\n")
            await _battle.enemy_turn(ctx, fight, last_round)
        elif action == "R":
            hp_before = fight.player_side.hp
            ran = fight.attempt_run()
            if ran:
                await ctx.io.write(
                    f"\n  You turn to run, and dash into the forest, "
                    f"leaving {monster.name} behind!\n"
                )  # lord.js:7015 (player.ran_away = true)
            else:
                dmg = hp_before - fight.player_side.hp
                await ctx.io.write(f"\n  {monster.name} sees you!\n")  # lord.js:7010
                if dmg > 0:
                    await ctx.io.write(f"  {monster.name} hits you for {dmg} damage!\n")
                else:
                    await ctx.io.write(f"  {monster.name} misses you completely!\n")

        # ``Fight.player_side`` is a standalone Combatant snapshotted from
        # ``p`` at fight-start (Combatant.from_player() copies scalar
        # fields, it isn't a live view) -- every action above mutates
        # *its* hp (damage, or a Mystical heal/light-shield), not `p`'s.
        # Sync it back every round so the persisted Player always reflects
        # combat, not just the in-fight display in _battle_prompt().
        p.hp = fight.player_side.hp

    if fight.ran_away:
        await ctx.io.pause()
        return False

    if fight.winner == "player":
        await _victory(ctx, monster, fight, last_round)
        return False

    # fight.winner == "enemy"
    await _death(ctx, monster)
    return True


async def _victory(ctx: GameCtx, monster: Monster, fight: Fight, last_round) -> None:
    """Port of the victory tail of ``look_to_kill()``.
    reference/lord.js:15084-15116."""
    p = ctx.player
    lines = ["", ""]

    overkill = (
        last_round is not None
        and last_round.killed
        and (last_round.damage > p.strength)
    )  # reference/lord.js:6973 / :6905 -- gates op.death being shown
    if overkill:
        lines.append(f"  {monster.death_phrase}")
        lines.append("")

    lines.append(f"  You have killed {monster.name}`%!")
    lines.append("")

    monster_gold = monster.gold * 2 if fight.bonus_gold else monster.gold
    gold_before = p.gold
    p.gold = _cap(p.gold + monster_gold, _GOLD_CAP)
    gained = p.gold - gold_before
    if gained == 0:
        lines.append("  You don't find any gold, but you do get")
    else:
        lines.append(f"  You receive {gained} gold, and")
    lines.append(f" {monster.exp} experience!")

    if fight.gem_found:
        p.gems += 1

    lines.append("")
    await ctx.io.write("\n".join(lines))
    # grant_exp() (pylord/engine/game.py) owns crediting the exp itself
    # (capped, same as gold above) plus the level-threshold announcement
    # -- shared with Turgon's master-fight exp gains (Task 11).
    await grant_exp(ctx, monster.exp)
    await ctx.io.pause()


async def _death(ctx: GameCtx, monster: Monster) -> None:
    """Port of the death tail of ``look_to_kill()`` (reference/lord.js:
    15067-15083) and ``dead_screen()`` (reference/lord.js:3342-3360).

    lord.js sweeps the player's on-hand gold into a shared "forest gold"
    pool (``save_forest_gold()``, later recoverable via the
    ``find_lost_gold`` event) rather than simply discarding it; that
    shared multiplayer pool isn't modeled here (see module docstring /
    deviation 4's note on ``find_lost_gold``), so the gold is discarded
    outright -- net effect on this player is identical (``gold = 0``).
    """
    p = ctx.player
    p.gold = 0  # reference/lord.js:15071
    p.exp -= p.exp // 10  # reference/lord.js:15072, 10% exp loss
    p.alive = 0  # reference/lord.js:15073 (player.on_now = false)

    ctx.news(f"  `5{p.name}`2 has been killed by `0{monster.name}`2!")  # lord.js:15069

    lines = [
        "",
        f"  `4You have been killed by {monster.name}`2.",
        "",
        "  `2GOLD ON HAND WAS `4LOST`2.",
        "",
        "  `2TEN PERCENT OF EXPERIENCE `4LOST`2.",
        "",
        "  You have been defeated on your way to glory.  The road to success",
        "  is long and hard.  You have encountered a minor setback.  But do `0NOT`2",
        "  lose heart, you can continue your struggle tomorrow.",
        "",
    ]  # reference/lord.js:3346-3358 (dead_screen())
    await ctx.io.write("\n".join(lines))
    await ctx.io.pause()


# --- Forest events -----------------------------------------------------
# Port of the ``switch(random(15+horse))`` in look_to_kill().
# reference/lord.js:14482-15041. See module docstring deviation 4 for
# which of the up-to-16 cases are ported vs. collapsed into "nothing".


async def _event_nothing(ctx: GameCtx) -> None:
    """Case 14 (reference/lord.js:15026-15027) -- and every other
    unported index (see deviation 4). lord.js's own case 14 is genuinely
    silent (a bare ``break``), so this intentionally writes nothing."""


async def _event_old_man(ctx: GameCtx) -> None:
    """Case 0. reference/lord.js:14483-14523."""
    p = ctx.player
    await ctx.io.write(
        "\n\n`%Event In The Forest`0\n\n"
        "  You come across an old man.  He seems confused and asks if\n"
        "  you would direct him to the Inn.  You know that if you do,\n"
        "  you will lose time for one fight today.\n\n"
    )
    choice = await ctx.io.menu(
        {"Y": "yes", "N": "no"}, "  Do you take the old man? [`0Y`2] : "
    )
    if choice == "Y":
        tmp = p.level * 500
        p.gold = _cap(p.gold + tmp, _GOLD_CAP)
        p.charm += 1
        p.forest_fights -= 1
        await ctx.io.write(
            f"\n  You gladly take the old man to the Inn. He is pleased\n"
            f"  with you, and gives you {tmp} gold!\n\n"
            f"  `%**CHARM GOES UP BY 1**`0\n"
        )
    else:
        await ctx.io.write(
            '\n  `0"I don\'t have time for you old man..Goodbye.."`2\n'
            "  You tell him coldly.  The old man shakes his head very sadly.\n"
        )
    await ctx.io.pause()


async def _event_find_gold(ctx: GameCtx) -> None:
    """Case 2. reference/lord.js:14571-14581."""
    p = ctx.player
    tmp = (ctx.rng.randrange(500) + 250) * p.level * p.level
    p.gold = _cap(p.gold + tmp, _GOLD_CAP)
    await ctx.io.write(
        f"\n\n`%Event In The Forest`0\n\n  You find a sack with {tmp} gold in it!\n\n"
    )
    await ctx.io.pause()


async def _event_merry_men(ctx: GameCtx) -> None:
    """Case 3. reference/lord.js:14582-14592."""
    p = ctx.player
    p.hp = p.hp_max
    await ctx.io.write(
        "\n\n`%Event In The Forest`0\n\n"
        "  You stumble upon a group of Merry Men!  After partying with them\n"
        "  for 2 hours you feel totally refreshed.\n\n"
    )
    await ctx.io.pause()


async def _event_find_gem(ctx: GameCtx) -> None:
    """Case 4. reference/lord.js:14593-14602."""
    p = ctx.player
    p.gems += 1
    await ctx.io.write(
        "\n\n`%Event In The Forest`0\n\n  Fortune smiles, and you find a gem!\n\n"
    )
    await ctx.io.pause()


async def _event_fairy(ctx: GameCtx) -> None:
    """Case 9, simplified. reference/lord.js:14779-14951.

    lord.js gates two sub-choices here (ask for a blessing / try to catch
    one) on a ``player.has_fairy`` flag this project's ``Player`` model
    doesn't have, and the "catch" branch has no mechanical effect beyond
    setting that flag (flavor text + a 50/50 HP-crash risk). This port
    keeps only the "ask for a blessing" branch (lord.js's own default
    when 'T' isn't pressed) and its 3 damage-free outcomes -- the 4th
    ("a companion for your travels", a horse) is dropped along with the
    rest of this project's horse-trading scope (see deviation 4).
    """
    p = ctx.player
    await ctx.io.write(
        "\n\n`%YOU ARE NOTICED!`0\n\n"
        "  The small things encircle you.  A small wet female bangs your\n"
        '  shin.  `0"How dare you spy on us, human!"`2 you can\'t help but\n'
        "  smile, the defiance in her silvery voice is truly a sight, you\n"
        "  think to yourself.\n\n"
        '  `%"Bless me!"`2 you implore the small figure.\n\n'
    )
    roll = ctx.rng.randrange(3)
    if roll == 0:  # reference/lord.js:14826-14844
        p.hp = p.hp_max
        await ctx.io.write(
            "  A fairy near her wordlessly upstretches its arms to you.\n\n"
            "  `%THE KISS IS STRANGELY FULFILLING! `2(You're refreshed)\n\n"
        )
    elif roll == 1:  # reference/lord.js:14845-14862
        p.gems += 2
        await ctx.io.write(
            "  You almost immediately begin to cry.\n\n"
            "  `%YOUR TEARS TURN INTO GEMS AND FALL INTO YOUR HANDS!\n\n"
        )
    else:  # reference/lord.js:14863-14888
        bonus = 10 * p.level * p.level
        exp_before = p.exp
        p.exp = _cap(p.exp + bonus, _EXP_CAP)
        gained = p.exp - exp_before
        await ctx.io.write(
            "  The strange sounds send thousands of images to your mind.\n\n"
            f"  `%YOU LEARN FAIRY LORE - AND GET {gained} EXPERIENCE!\n\n"
        )
    await ctx.io.pause()


_EVENT_TABLE = {
    0: _event_old_man,
    2: _event_find_gold,
    3: _event_merry_men,
    4: _event_find_gem,
    9: _event_fairy,
}


async def _forest_event(ctx: GameCtx) -> None:
    slots = 16 if ctx.player.horse else 15  # reference/lord.js:14482
    roll = ctx.rng.randrange(slots)
    handler = _EVENT_TABLE.get(roll, _event_nothing)
    await handler(ctx)
