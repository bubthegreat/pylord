"""Shared battle-loop bits every fight scene needs, in lord.js's shape.

The four fight scenes (``forest``, ``training``, ``dragon``, ``pvp``) each
own their own screens and rewards, but lord.js drives all four through the
same ``battle()`` frame (reference/lord.js:7365-7475). The pieces of that
frame that are pure sequencing -- who swings first, whether the enemy swings
back, the fairy death-save, the fairy-lore heal key -- live here so the four
scenes can't drift apart from each other (they had, before this module: the
opening roll was missing everywhere and Light Shield/Mind Heal wrongly
handed the enemy a free hit).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pylord.engine.combat import Fight, Round
    from pylord.engine.game import GameCtx
    from pylord.models import Player


async def opening(ctx: GameCtx, fight: Fight, *, enemy_level: int = 0) -> Round:
    """Roll and narrate ``battle()``'s opening initiative.
    reference/lord.js:7375-7391 -- a flat 1-in-10 chance the enemy swings
    first (guaranteed in PvP against a higher-level opponent).

    Returns the resulting ``Round`` so the caller can notice a first-swing
    kill (possible against a badly wounded player).
    """
    result = fight.opening(
        player_level=ctx.player.level, enemy_level=enemy_level
    )
    await ctx.io.write(f"\n  {result.text}\n")
    await _fairy_save(ctx, fight)
    return result


async def enemy_turn(ctx: GameCtx, fight: Fight, last_round: Round) -> Round | None:
    """Give the enemy its swing back, unless the player's action was one
    lord.js resolves without reaching ``handle_hit()``
    (reference/lord.js:6926-6928) -- Light Shield, Mind Heal, the fairy-lore
    heal, a refused skill. Returns the enemy's ``Round``, or ``None`` when
    it doesn't get one.
    """
    if not last_round.counter or fight.over:
        return None
    enemy_round = fight.enemy_attack()
    await ctx.io.write(f"  {enemy_round.text}\n")
    await _fairy_save(ctx, fight)
    return enemy_round


async def _fairy_save(ctx: GameCtx, fight: Fight) -> None:
    """Release a captured fairy rather than die. reference/lord.js:6771-6793."""
    if not ctx.player.has_fairy:
        return
    saved = fight.fairy_save()
    if saved is None:
        return
    ctx.player.has_fairy = 0  # lord.js:6790
    ctx.player.hp = fight.player_side.hp
    await ctx.io.write(f"\n  {saved.text}\n")
    await ctx.io.pause()


def extra_options(p: Player) -> dict[str, str]:
    """Battle-menu keys beyond the per-scene ones: ``(H)eal`` when today's
    fairy-lore training is unspent. reference/lord.js:6851-6855."""
    return {"H": "fairy heal"} if p.fairy_lore else {}


def extra_menu_lines(p: Player) -> list[str]:
    return ["  `2(`5H`2)eal (fairy lore)"] if p.fairy_lore else []


async def fairy_lore_heal(ctx: GameCtx, fight: Fight) -> Round:
    """The ``(H)eal`` key. reference/lord.js:7480-7501 -- one-shot per day,
    heals to full, and the enemy does not swing back."""
    result = fight.fairy_lore_heal()
    ctx.player.fairy_lore = 0  # lord.js:7498
    ctx.player.hp = fight.player_side.hp
    await ctx.io.write(f"\n  {result.text}\n")
    return result
