"""The Arena of Lords -- paid bouts against the house's champions.

Wave-2 IGM, recreated from the premise (an arena that pays purses) rather
than ported; no source survives. Invented: the three tiers, their stats,
the purses and the streak bonus.

Fights run on the real combat engine (``pylord/engine/combat.py``), so an
arena bout behaves exactly like a forest fight -- the same rolls, the same
skill attacks -- and, like a master, the champions are *arena* opponents:
you cannot run, and you cannot use class skills on them
(reference/lord.js:7001-7006, :7045-7051). Losing costs the entry fee and
leaves you on one hitpoint rather than killing you; the arena has a healer
and an interest in repeat custom.
"""

from __future__ import annotations

from pylord.engine.combat import Combatant, Fight
from pylord.hooks import IGM, IgmContext, IgmMaintContext

#: (name, weapon, hp multiplier, strength multiplier, purse multiplier)
_CHAMPIONS = (
    ("Bruiser Hal", "a knotted club", 6, 3, 400),
    ("The Widow Grey", "twin hooks", 10, 5, 1200),
    ("Lord Vane", "a black halberd", 16, 8, 3000),
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
                {"A": "attack", "Y": "yield"}, "  `2(`0A`2)ttack  (`0Y`2)ield  [`0A`2] : `%"
            ) == "Y":
                await ctx.term.write("\n  `2You raise a hand.  The crowd jeers.\n")
                await ctx.term.pause()
                return
            round_ = fight.player_attack()
            await ctx.term.write(f"\n  {round_.text}\n")
            if not fight.over and round_.counter:
                await ctx.term.write(f"  {fight.enemy_attack().text}\n")
            p.hp = max(0, fight.player_side.hp)

        if fight.winner == "player":
            await self._win(ctx, name, purse_mult)
        else:
            p.hp = 1  # the arena's healer earns his keep
            ctx.store.set(f"streak:{p.id}", 0)
            await ctx.term.write(
                f"\n  `4{name}`2 puts you on your back.  You wake in the undercroft\n"
                "  with a bucket of water in your face and nothing in your purse.\n"
            )
            await ctx.term.pause()

    async def _win(self, ctx: IgmContext, name: str, purse_mult: int) -> None:
        p = ctx.player
        streak = min(ctx.store.get(f"streak:{p.id}", 0) + 1, STREAK_CAP)
        ctx.store.set(f"streak:{p.id}", streak)
        purse = int(p.level * purse_mult * (1 + STREAK_BONUS * (streak - 1)))
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
