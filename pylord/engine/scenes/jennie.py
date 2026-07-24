"""The forest's hidden JENNIE codeword.

Port of ``forest()``'s ``J`` case, reference/lord.js:15396-15566. Typing
``J`` in the forest -- while in high spirits, which ``wake_up()`` rolls at
2-in-3 every morning (:5565-5573) -- starts an unadvertised exchange: the
game asks you to spell out JENNIE, then to "Define her" in four letters.
Each answer has its own outcome, from an extra forest fight to being turned
into a frog to being thrown off the server.

The spirits flag is spent on the attempt whether or not you spell the name
right (:15398), so the easter egg is once per day.

Two of lord.js's answers are settings-gated toggles in the original
(``FAIR`` and ``GIFT``, both marked with a "TODO: option to turn this off"
comment there); both are ported as-is, since neither setting exists in this
project's config. ``NICE`` is a pre-version-4 answer lord.js itself no
longer implements (:15584) and is not ported.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylord.engine import limits

if TYPE_CHECKING:
    from pylord.engine.game import GameCtx

_CODEWORD = "ENNIE"  # `J` was the key that got us here (reference/lord.js:15396)
_ANSWER_LEN = 4  # reference/lord.js:15408 (getstr({len:4}))


async def run(ctx: GameCtx) -> None:
    """Run the exchange. The player may end the session (the ``UGLY``
    answer, reference/lord.js:15508-15518) -- the caller checks
    ``player.alive`` afterwards."""
    p = ctx.player
    if not p.high_spirits:  # reference/lord.js:15397
        return
    p.high_spirits = 0  # reference/lord.js:15398 -- spent either way

    for expected in _CODEWORD:  # reference/lord.js:15399-15403
        if (await ctx.io.readkey()).upper() != expected:
            return

    await ctx.io.write(
        "\n\n  `0Jennie?  Jennie Garth?\n"
    )
    answer = (await ctx.io.readline("  `2Define her. ", maxlen=_ANSWER_LEN)).upper()
    await ctx.io.write("\n\n")

    handler = _ANSWERS.get(answer.strip())
    if handler is None:  # reference/lord.js:15555-15561
        if p.gender == "M":
            await ctx.io.write("  You do not understand her, my son.\n")
        else:
            await ctx.io.write(
                "  Perhaps if you were male you might understand better.\n"
            )
        await ctx.io.pause()
        return

    await handler(ctx)
    await ctx.io.pause()


async def _babe(ctx: GameCtx) -> None:  # reference/lord.js:15413-15419
    p = ctx.player
    p.forest_fights = limits.clamp("forest_fights", p.forest_fights + 1)
    await ctx.io.write(
        "  `0That is correct. `2(YOU RECIEVE AN EXTRA FOREST FIGHT!)\n"
    )


async def _sexy(ctx: GameCtx) -> None:  # reference/lord.js:15420-15426
    p = ctx.player
    p.player_fights = limits.clamp("player_fights", p.player_fights + 1)
    await ctx.io.write("  `0Exellent. `2(YOU RECIEVE AN EXTRA USER FIGHT!)\n")


async def _lady(ctx: GameCtx) -> None:  # reference/lord.js:15427-15433
    p = ctx.player
    p.gold = limits.clamp("gold", p.gold + 1000 * p.level)
    await ctx.io.write("  `0Very true.  `2(YOU GET SOME GOLD!)\n")


async def _dumb(ctx: GameCtx) -> None:  # reference/lord.js:15434-15436
    await ctx.io.write(
        "  `0You idiot.  You will `)never`0 be a useful member of society.\n"
    )


async def _star(ctx: GameCtx) -> None:  # reference/lord.js:15437-15440
    await ctx.io.write(
        "  `0A huge star, infant.\n"
        "  `4(YOU GET NOTHING, YOU STATED THE OBVIOUS)\n"
    )


async def _dung(ctx: GameCtx) -> None:
    """Turned into a frog until you apologize. reference/lord.js:15441-15474."""
    p = ctx.player
    insult = "sir" if p.gender == "M" else "woman"
    await ctx.io.write(
        f"  `0You are a fool, {insult}.  `4(YOU ARE TURNED INTO A FROG)`2\n"
    )
    await ctx.io.pause()
    while True:
        choice = await ctx.io.menu(
            {"H": "hop", "A": "apologize"},
            "\n  `c`2The Forest Floor\n\n"
            "  `2(`0H`2)op Like Crazy\n  `2(`0A`2)pologize\n\n"
            "  `2Your command, greeny? : `%",
        )
        if choice == "A":
            break
        await ctx.io.write(
            "\n  You hop around like a crazy frog.  What\n"
            "  is this accomplishing, pray tell?\n"
        )
        await ctx.io.pause()
    await ctx.io.write(
        "\n  `2You apologize humbly, knowing what you did was wrong.\n\n"
        "  `%(YOU ARE CHANGED BACK TO YOUR (MOSTLY) HUMAN FORM)\n"
    )


async def _foxy(ctx: GameCtx) -> None:  # reference/lord.js:15475-15481
    p = ctx.player
    p.gems = limits.clamp("gems", p.gems + 1)
    await ctx.io.write("  `0Very wise. `%(YOU RECIEVE AN EXTRA GEM!)\n")


async def _fair(ctx: GameCtx) -> None:  # reference/lord.js:15483-15487
    ctx.player.flirts_today = 0
    await ctx.io.write("  `0Very fair. `2(YOU FEEL EXCITED!)\n")


async def _ugly(ctx: GameCtx) -> None:
    """Thrown out of the realm on one hitpoint. reference/lord.js:15488-15497
    (lord.js exits the door outright; here the session ends and the player
    keeps the single hitpoint until tomorrow's reset)."""
    p = ctx.player
    p.hp = 1
    p.alive = 0
    await ctx.io.write(
        "  `0You understand nothing.  `4(YOU ARE BITCH SLAPPED!)\n"
    )


async def _hott(ctx: GameCtx) -> None:  # reference/lord.js:15498-15507
    p = ctx.player
    p.hp = min(p.hp_max + p.hp_max // 5, limits.STAT_CAP)
    await ctx.io.write(
        '  `0"Hot" is spelled with only one T.. But good job, nonetheless.\n\n'
        "  `%(YOU FEEL ENERGIZED!)\n"
    )


async def _cool(ctx: GameCtx) -> None:  # reference/lord.js:15508-15518
    p = ctx.player
    await ctx.io.write("  `0Why, you are cool to notice that.\n\n")
    if p.hp < p.hp_max:
        p.charm = limits.clamp("charm", p.charm + 1)
        await ctx.io.write(
            "  `%GOD NOTICES YOU ARE WOUNDED AND PITIES YOU.  YOU LOOK BETTER!\n"
        )


async def _gift(ctx: GameCtx) -> None:
    """A one-time refill of today's skill uses to the player's full rank.
    reference/lord.js:15519-15553 (``levelX = skillX``, guarded by
    ``magically_delicious`` so it can only ever happen once)."""
    p = ctx.player
    rank_field = {1: "skill_dk", 2: "skill_my", 3: "skill_th"}.get(p.class_type)
    rank = getattr(p, rank_field) if rank_field else 0
    await ctx.io.write("  `0Yes, she is this.  And now, a magical gift for you.\n\n")
    if rank < 1 or p.magically_delicious:
        await ctx.io.write("  `%You are unable to accept the gift.\n")
        return
    p.skill_uses = rank
    p.magically_delicious = 1
    await ctx.io.write("  `5YOU FEEL MAGICALLY DELICIOUS.\n")


#: Answer -> outcome. reference/lord.js:15411-15554.
_ANSWERS = {
    "BABE": _babe,
    "SEXY": _sexy,
    "LADY": _lady,
    "DUMB": _dumb,
    "STAR": _star,
    "DUNG": _dung,
    "FOXY": _foxy,
    "FAIR": _fair,
    "UGLY": _ugly,
    "HOTT": _hott,
    "COOL": _cool,
    "GIFT": _gift,
}
