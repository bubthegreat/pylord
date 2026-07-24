"""Slaughter Other Players -- port of ``reference/lord.js``'s
``slaughter_others()`` (``:16363-16590``, the town-square ``S`` menu) and
``attack_player()`` (``:7731-7977``, the shared fight engine both the field
attack and the Inn bribe-attack funnel into). The Inn's bribe-to-attack-
sleepers path (``attack_in_inn()``, ``:7979-8088``, reached from the
bartender's ``B`` case, ``:8388-8418``) is wired into ``inn.py`` (this task's
own TODO left there by Task 13a) and calls back into this module's public
:func:`find_attackable`/:func:`run_attack` to share the actual fight engine
rather than duplicate it.

**Eligibility, ported exactly (two independent gates, per entry point):**

* Field attack (``slaughter_others``'s own ``S`` case, ``:16427-16515``):
  self-exclusion (``:16433-16434``), dead ("rotting corpse...too late",
  ``:16461-16468``), and sleeping-at-the-Inn ("staying at the Inn",
  ``:16469-16479``) -- but **no level-range restriction at all**. The
  "visiting another section of the realm" check (``:16444-16460``, lord.js's
  file-mutex "is this player mid-IGM elsewhere" probe) has no equivalent
  concept in this project (no cross-scene "currently busy" state) and is
  dropped -- see ``docs/deviations.md``.
* Inn bribe-attack (``attack_in_inn()``'s own ``S`` case, ``:8038-8051``):
  dead ("isn't at the Inn...dead", different wording from the field
  version), not-at-the-Inn ("probably in the fields"), **and** a level-range
  gate lord.js's field attack does *not* have: ``op.level + 1 <
  player.level`` refuses ("A child could beat that wimp!").

Both then confirm (Y/N) and fall through to :func:`run_attack` --
``attack_player()`` itself -- which does the *shared* checks common to
both entry points, in lord.js's own order: the daily ``player_fights``
budget (``:7741-7747``), then whether the target is currently online
(``:7802-7809`` in local/non-remote mode, the branch this project's
single-shared-database architecture matches) -- **both checked before**
``player.pvp_fights`` is decremented (``:7814``), so an online-blocked or
too-tired attempt costs nothing. This project has no realtime "online duel"
system (``online_battle()``, lord.js ``:7524-7576``, a live challenge/
response protocol with no async equivalent here) so an online target is
simply refused with lord.js's own "currently online!" line
(``:7805``/``:7763``) instead of starting one -- documented deviation.

**Victim heals to full before the fight** (``:7821-7823``,
``if (op.hp < op.hp_max) op.hp = op.hp_max``) -- the stored opponent always
fights back at full health, never at whatever HP they happened to log off
at. lord.js then fights the *real* ``op`` object in place (every
``do_attack``/``enemy_attack`` call mutates it directly), so whatever HP is
left over at the end is what ultimately gets persisted (``op.put()``) --
but **only on a win or a loss**; a run-away calls neither ``op.put()`` nor
``mail_to()`` at all (mail's a local variable that's simply discarded), so
the heal-to-full is quietly not persisted and no mail is sent on a run.
Ported exactly: :func:`_run_battle` only persists/mails the target in
:func:`_win`/:func:`_lose`.

**Win** (``:7861-7966``): attacker's gold ``+= op.gold`` (**all** on-hand
gold, not a fraction), exp ``+= floor(op.exp / 2)``, gems ``+=
floor(op.gems / 2)`` (only shown/credited when ``op.gems >= 2``, though the
floor-division transfer is a no-op below that anyway) -- all capped at
2,000,000,000. Victim: gems ``-= floor(gems / 2)``, exp ``-= floor(exp /
10)``, gold ``= 0``, ``dead = true`` / ``inn = false`` (this project's
``alive = 0`` / ``at_inn = 0``). The ``def_for_pk``/``str_for_pk`` bonus
stat points (``:7886-7905``) are gated on server settings that default to
``false`` (``:1867-1868``) -- not modeled, matching this project's existing
"default-off deployment toggle" convention (e.g. ``beef_up``, see
``dragon.py``). No player-kill counter is credited anywhere (lord.js's
``player.pvp``/``op.pvp`` -- used only by the "Examine The Dirt" top-killer
board, ``:16376-16385``) since ``Player`` has no such field and this task's
brief doesn't ask for one -- see the "dirt wall" deviation below.

**Loss** (``:7825-7859``, self-defense death): attacker's gold ``= 0``, exp
``-= floor(exp / 10)``, ``alive = 0`` -- reusing ``forest.py``'s own
``dead_screen()`` wording (identical text, reference/lord.js ``:3342-3360``)
with the victim's name as killer. The *victim* (who never left their own
session to see any of this) is credited directly and immediately --
``op.exp += floor(player.exp / 2)`` (using the attacker's **already**
-reduced exp, ``:7841`` running after ``:7828``'s 10% cut) -- not via the
async mail-effect channel, since both players' rows are always reachable
from this single shared database (unlike lord.js's optional split-process
"remote game" mode). The mail sent to the victim is purely a text
notification of what already happened synchronously.

**Mail to the victim** (``mail_to(op.Record, mail)``, only ever called from
the win or loss branch -- see above): always starts with the same "YOU HAVE
BEEN ATTACKED!" header (``:7813``) plus one outcome-specific tail line
(``:7919`` on a win, ``:7829`` on a loss) -- ported verbatim in
:data:`_ATTACK_HEADER`/:func:`_win`/:func:`_lose`.

**News**: ``good_say(op, '...has killed...')`` (``:7964``) / ``bad_say(op,
'...has killed...in self defence!')`` (``:7852``) both funnel into
``say()``'s ``log_line(header + '\\n' + force)`` (``:7690-7718``), where
``force`` is either a random line from an external ``goodsay.lrd``/
``badsay.lrd`` flavor file (not present anywhere in ``reference/``) or an
interactive "say something to the press?" custom quote
(``custom_saying()``, ``:7578-7654``). Neither is portable without that
missing asset / without an extra out-of-scope interactive prompt, so only
the ``header`` half of the broadcast survives here -- documented deviation.

**Weapon-steal on a bribed-Inn win** (``:7921-7953``, only when
``inn=true``): 1-in-10 chance, gated on the attacker being at least 2
levels below the victim (``player.level < op.level - 1``) *and* the
victim's weapon being strictly better (``op.weapon_num > player.weapon_num``)
-- an interactive Y/N trade offer. **Bug fix, not a deviation**: the
literal source computes the victim's *outgoing* weapon's strength bonus via
``get_weapon(op.weapon)`` (``:7935``) -- passing a display **name** to a
function whose parameter is a **numeric id** (``get_weapon(num)``, lord.js
``:1842-1845``) -- almost certainly a transcription typo (same pattern as
``inn.py``'s documented ``player.ext`` fix). This port uses
``op.weapon_num`` instead, which is what every other line in this same
block already keys off of (and is the only reading that produces the
clearly-intended symmetric swap).

**Not ported (documented deviations, see ``docs/deviations.md``)**:
"Examine The Dirt" (``E``) and "Write In The Dirt" (``W``) -- an entire
separate graffiti-wall mini-game (``:16517-16590``+) this task's brief never
asks for, reusing the same "external minigame, no test coverage requested"
rationale already used to drop the Dark Cloak Tavern gambling game
(``inn.py``'s module docstring). ``(V)iew stats`` is kept (routes to the
standalone ``stats`` scene, ending this visit, the same "detour scene always
returns to town" convention ``inn.py`` established).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylord.engine import data
from pylord.engine.combat import Combatant, Fight, skill_attack
from pylord.engine.game import grant_exp, scene
from pylord.engine.scenes import _battle

if TYPE_CHECKING:
    from pylord.engine.game import GameCtx
    from pylord.models import Player

_GOLD_CAP = 2_000_000_000
_EXP_CAP = 2_000_000_000
_NAME_MAXLEN = 20

_MENU = (
    "\n  `5Slaughter Other Players\n"
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
    "  `2(`0S`2)laughter   (`0L`2)ist Warriors   (`0V`2)iew Stats   (`0R`2)eturn\n"
)

_ATTACK_HEADER = (
    "  `%YOU HAVE BEEN ATTACKED!\n"
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
)

# class_type -> (skill_points field, skill_attack() 'kind', display label).
# Mirrors forest.py's/training.py's identical table -- battle_prompt() is
# the same generic function for every kind of fight in lord.js (monster,
# master, or PvP), so PvP gets skill attacks too.
_SKILL_BY_CLASS: dict[int, tuple[str, str, str]] = {
    1: ("skill_dk", "dk", "Death Knight Attack"),
    2: ("skill_my", "my", "Mystical Skills"),
    3: ("skill_th", "th", "Thieving Skills"),
}


def _weapon_name(p: Player) -> str:
    return "Fists" if p.weapon_num == 0 else data.weapon(p.weapon_num).name


def _weapon_power(num: int) -> int:
    return data.weapon(num).power if num else 0


def _can_skill(p: Player) -> bool:
    return p.class_type in _SKILL_BY_CLASS and p.skill_uses > 0


def _battle_options(p: Player) -> dict[str, str]:
    options = {"A": "attack", "R": "run"}
    if _can_skill(p):
        options["S"] = "skill"
    options.update(_battle.extra_options(p))
    return options


async def _battle_prompt(ctx: GameCtx, fight: Fight, enemy_name: str) -> None:
    p = ctx.player
    lines = [
        "",
        f"  `2Your Hitpoints : `0{fight.player_side.hp}",
        f"  `2{enemy_name}`2's Hitpoints : `0{max(fight.enemy.hp, 0)}",
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


async def find_attackable(ctx: GameCtx) -> Player | None:
    """Port of ``find_player()``. reference/lord.js:4890-4926: prompt for a
    full-or-partial name, confirm the first case-insensitive substring
    match, keep scanning on a declined match. Returns ``None`` if nothing
    is confirmed. Shared by both the field ``S`` case and the Inn's
    bribe-attack (``inn.py``)."""
    await ctx.io.write("\n  `2(full or `0PARTIAL`2 name)\n")
    raw = await ctx.io.readline("  NAME: `%", maxlen=_NAME_MAXLEN)
    needle = raw.strip().upper()
    if not needle:
        return None
    for candidate in ctx.repo.all_players():
        if needle in candidate.name.upper():
            choice = await ctx.io.menu(
                {"Y": "yes", "N": "no"},
                f'\n  `2You mean "`0{candidate.name}`2"? `2[`%Y`2] : ',
            )
            if choice == "Y":
                return candidate
    return None


async def run_attack(ctx: GameCtx, target: Player, *, from_inn: bool) -> bool:
    """Port of ``attack_player(op, inn)``. reference/lord.js:7731-7977.

    The daily ``player_fights`` gate and the "target is online" refusal --
    both checked *before* the fight-count decrement, so neither one costs an
    attempt (see module docstring). Returns ``True`` if the *attacking*
    player died (self-defense loss) so the caller can end the session,
    matching every other death path in this project (forest.py's own
    convention)."""
    p = ctx.player
    if p.player_fights < 1:  # reference/lord.js:7741-7747
        await ctx.io.write(
            "\n  You are too tired to look for that warrior.  Try again tomorrow.\n\n"
        )
        await ctx.io.pause()
        return False

    if target.online:  # reference/lord.js:7802-7809 (local/non-remote mode)
        await ctx.io.write("\n  That warrior is currently online!\n\n")
        await ctx.io.pause()
        return False

    target.hp = max(target.hp, target.hp_max)  # reference/lord.js:7821-7823
    p.player_fights -= 1  # reference/lord.js:7814

    await ctx.io.write(
        f"\n\n  `2** `%PLAYER FIGHT `2**\n\n  You have encountered {target.name}`2!!\n\n"
    )  # reference/lord.js:7816-7820

    target_combatant = Combatant.from_player(target)
    fight = Fight(Combatant.from_player(p), target_combatant, ctx.rng, pfight=True)
    last_round = None
    # reference/lord.js:7375-7391 -- and in a player fight, a
    # higher-level opponent turns any roll over 60 into a guaranteed
    # surprise (:7377-7383).
    await _battle.opening(ctx, fight, enemy_level=target.level)
    p.hp = fight.player_side.hp

    while not fight.over:
        await _battle_prompt(ctx, fight, target.name)
        action = await ctx.io.menu(_battle_options(p), "")

        if action == "A":
            last_round = fight.player_attack()
            await ctx.io.write(f"\n  {last_round.text}\n")
            await _battle.enemy_turn(ctx, fight, last_round)
        elif action == "H":
            last_round = await _battle.fairy_lore_heal(ctx, fight)
        elif action == "S":
            field, kind, _label = _SKILL_BY_CLASS[p.class_type]
            last_round = skill_attack(
                fight, kind, p.skill_uses, skill_rank=getattr(p, field)
            )
            cost = fight.last_spell_cost if kind == "my" else 1
            p.skill_uses -= cost
            await ctx.io.write(f"\n  {last_round.text}\n")
            await _battle.enemy_turn(ctx, fight, last_round)
        elif action == "R":
            hp_before = fight.player_side.hp
            ran = fight.attempt_run()
            if ran:  # reference/lord.js:7016-7020
                await ctx.io.write(
                    f"\n  `2You barely manage to escape!  `0{target.name}`2 laughs as you\n"
                    "  scurry away.\n"
                )
            else:
                dmg = hp_before - fight.player_side.hp
                await ctx.io.write(f"\n  {target.name} sees you!\n")  # lord.js:7010
                if dmg > 0:
                    await ctx.io.write(f"  {target.name} hits you for {dmg} damage!\n")
                else:
                    await ctx.io.write(f"  {target.name} misses you completely!\n")

        p.hp = fight.player_side.hp

    if fight.ran_away:  # no mail_to()/op.put() happens on a run -- see
        await ctx.io.pause()  # module docstring.
        return False

    if fight.winner == "player":
        await _win(ctx, target, fight, from_inn)
        return False

    # fight.winner == "enemy"
    await _lose(ctx, target, fight)
    return True


async def _win(ctx: GameCtx, target: Player, fight: Fight, from_inn: bool) -> None:
    """Port of the victory tail of ``attack_player()``.
    reference/lord.js:7861-7966.

    **Displayed gold/exp are the actual post-cap delta, not the raw
    transfer amount** -- lord.js computes them the same way (``tmp =
    player.gold; player.gold += op.gold; ...; lw(player.gold - tmp)``,
    ``:7867-7872``/``:7873-7878``): if the attacker is already near the
    2,000,000,000 cap, the screen shows however little actually landed,
    not the victim's full on-hand total/half-exp."""
    p = ctx.player
    gold_before = p.gold
    p.gold = min(p.gold + target.gold, _GOLD_CAP)
    gold_delta = p.gold - gold_before

    exp_before = p.exp
    await grant_exp(ctx, target.exp // 2)
    exp_delta = p.exp - exp_before

    lines = [
        "",
        f"  You have killed {target.name}`%!",
        "",
        f"  You receive `%{gold_delta}`2 gold, and `%{exp_delta}`2 experience!",
    ]

    half_gems = target.gems // 2
    if target.gems >= 2:  # reference/lord.js:7879-7885
        p.gems += half_gems
        lines.append("")
        lines.append(f"  `2You also find `0{half_gems} `%{'Gem' if half_gems == 1 else 'Gems'}`2!")
    target.gems -= half_gems

    target.exp -= target.exp // 10  # reference/lord.js:15072-style 10% loss
    target.gold = 0
    target.alive = 0
    target.at_inn = 0
    target.hp = max(0, fight.enemy.hp)

    mail_body = _ATTACK_HEADER + f"  `0{p.name}`2 has attacked you!"
    mail_body += f"\n`.  `0{p.name}`2 has killed you!"  # reference/lord.js:7919

    if from_inn:
        stolen = await _maybe_steal_weapon(ctx, target)
        if stolen:
            mail_body += f"\n  `${p.name} took your weapon!"

    ctx.repo.save(target)
    with ctx.conn:
        ctx.conn.execute(
            "INSERT INTO mail (to_id, from_name, text, effect, created, read) "
            "VALUES (?, ?, ?, NULL, datetime('now'), 0)",
            (target.id, p.name, mail_body),
        )
    ctx.news(f"`.  `0{p.name}`2 has killed `5{target.name}`2!")  # lord.js:7964

    await ctx.io.write("\n".join(lines) + "\n")
    await ctx.io.pause()


async def _maybe_steal_weapon(ctx: GameCtx, target: Player) -> bool:
    """Port of the Inn-bribe weapon-steal chance. reference/lord.js:7921-7953
    (see module docstring for the ``get_weapon(op.weapon)`` bug fix). Returns
    ``True`` if the trade actually happened."""
    p = ctx.player
    if ctx.rng.randrange(10) != 1:  # reference/lord.js:7923
        return False
    if not (p.level < target.level - 1):  # reference/lord.js:7924
        return False
    if not (target.weapon_num > p.weapon_num):  # reference/lord.js:7925
        return False

    pronoun = "his" if target.gender == "M" else "her"
    my_weapon = _weapon_name(p)
    their_weapon = _weapon_name(target)
    await ctx.io.write(
        f"\n  `2Do you wish to trade your {my_weapon} `2for {pronoun}\n"
        f"  `%{their_weapon}`2? `0[N] : `%"
    )
    choice = await ctx.io.menu({"Y": "yes", "N": "no"}, "")
    if choice != "Y":
        return False

    old_p_num, old_t_num = p.weapon_num, target.weapon_num
    p.strength += _weapon_power(old_t_num) - _weapon_power(old_p_num)
    target.strength += _weapon_power(old_p_num) - _weapon_power(old_t_num)
    p.weapon_num, target.weapon_num = old_t_num, old_p_num
    await ctx.io.write(f"  `2Done! You now have a {_weapon_name(p)}`2!\n")
    return True


async def _lose(ctx: GameCtx, target: Player, fight: Fight) -> None:
    """Port of the self-defense-death tail of ``attack_player()``.
    reference/lord.js:7825-7859. Text reuses forest.py's ``_death`` wording
    (identical source, reference/lord.js:3342-3360) with the victim as
    killer."""
    p = ctx.player
    p.gold = 0  # reference/lord.js:7827
    p.exp -= p.exp // 10  # reference/lord.js:7828
    p.alive = 0

    gained = p.exp // 2  # reference/lord.js:7829/7841 -- uses the *already*-reduced exp
    target.exp = min(target.exp + gained, _EXP_CAP)
    target.hp = max(0, fight.enemy.hp)

    mail_body = _ATTACK_HEADER + f"  `0{p.name}`2 has attacked you!"
    mail_body += (
        f"\n`.  `2You have killed `0{p.name}`2 in self defense!\n"
        f"`.  `2You receive `%{gained}`2 experience!"
    )  # reference/lord.js:7829
    ctx.repo.save(target)
    with ctx.conn:
        ctx.conn.execute(
            "INSERT INTO mail (to_id, from_name, text, effect, created, read) "
            "VALUES (?, ?, ?, NULL, datetime('now'), 0)",
            (target.id, p.name, mail_body),
        )
    ctx.news(f"`.  `0{target.name}`2 has killed `5{p.name}`2 in self defence!")  # lord.js:7852

    lines = [
        "",
        f"  `4You have been killed by {target.name}`2.",
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


async def _slaughter(ctx: GameCtx) -> bool:
    """Port of ``slaughter_others()``'s own ``S`` case (the pre-checks that
    are *specific* to the field-attack entry point).
    reference/lord.js:16427-16515. Returns ``True`` if the attacking player
    died this press (caller ends the session)."""
    p = ctx.player
    await ctx.io.write("\n  Who would you like to attack?\n")
    target = await find_attackable(ctx)
    if target is None:
        await ctx.io.write("\n  No warriors found.\n")
        await ctx.io.pause()
        return False

    if target.id == p.id:  # reference/lord.js:16433-16434
        await ctx.io.write(
            "\n  You wish to attack yourself?!!  You decide against it.\n"
        )
        await ctx.io.pause()
        return False

    if not target.alive:  # reference/lord.js:16461-16468
        pronoun = "him" if target.gender == "M" else "her"
        await ctx.io.write(
            f"\n  You look for that warrior...And you find {pronoun}...\n"
            "  A rotting corpse...Looks like you were a little late..\n"
        )
        await ctx.io.pause()
        return False

    if target.at_inn:  # reference/lord.js:16469-16479
        pronoun = "she" if target.gender == "F" else "he"
        await ctx.io.write(
            "\n  You search the fields but do not find that warrior.\n"
            f"  You conclude {pronoun} is staying at the Inn.\n"
        )
        await ctx.io.pause()
        return False

    await ctx.io.write(
        f"\n  `2You hunt around for `0{target.name}`2..."
    )  # reference/lord.js:16489
    if target.gender == "M":
        await ctx.io.write("YOU FIND HIM!\n  He")
    else:
        await ctx.io.write("YOU FIND HER!\n  She")
    await ctx.io.write(
        f" is brandishing a dangerous looking {_weapon_name(target)}.\n\n"
    )
    choice = await ctx.io.menu(
        {"Y": "yes", "N": "no"}, f"  `2Attack `5{target.name} `2[`0Y`2] : `%"
    )
    if choice == "N":
        return False
    return await run_attack(ctx, target, from_inn=False)


async def _list(ctx: GameCtx) -> None:
    """Port of ``generate_rankings(fname, false, false, false)``'s field-list
    filter (reference/lord.js:6580-6689): alive, not currently sleeping at
    the Inn. **Deviation** (matching this task's explicit test brief over
    lord.js's own literal listing, which includes self/online players in the
    list -- only the attack itself blocks them): also excludes the caller
    and currently-online players, since neither can actually be attacked
    from here."""
    p = ctx.player
    players = [
        pl
        for pl in ctx.repo.all_players()
        if pl.id != p.id and pl.alive and not pl.at_inn and not pl.online
    ]
    players.sort(key=lambda pl: pl.exp, reverse=True)
    await ctx.io.write(
        "\n\n  `%Legend Of The Red Dragon - Player Rankings`2\n"
        "  Name                    Experience    Level\n"
        "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
    )
    for pl in players:
        await ctx.io.write(f"  `2{pl.name:<22}`2{pl.exp:>13}    `%{pl.level:>2}`2\n")
    await ctx.io.pause()


@scene("pvp")
async def pvp(ctx: GameCtx) -> str | None:
    while True:
        await ctx.io.write(_MENU)
        choice = await ctx.io.menu(
            {"S": "slaughter", "L": "list", "V": "stats", "R": "town"},
            "  `2Your choice`0? `2",
        )
        if choice == "R":
            return "town"
        if choice == "V":
            return "stats"
        if choice == "L":
            await _list(ctx)
            continue
        # choice == "S"
        died = await _slaughter(ctx)
        if died:
            return None
