"""The four smaller Town Square destinations.

Each is a short lord.js ``main()`` case that has no scene file of its own:

* ``M`` -> ``announce()``          (reference/lord.js:9397-9432)
* ``P`` -> ``warriors_on_now()``   (reference/lord.js:5671-5710)
* ``1`` -> ``show_game_stats()``   (reference/lord.js:16251-16276)
* ``R`` -> ``check_mail()``        (reference/lord.js:16950-16959)

``R`` is the "read what's waiting for me" key. This project applies mail
once at login (``pylord/engine/scenes/mail.py``'s ``apply_unread_mail``,
see its docstring for why), so pressing ``R`` mid-session shows anything
that has arrived since -- the same net effect as lord.js's polling, minus
the poll.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylord.engine.game import scene
from pylord.engine.scenes import mail as mail_scene

if TYPE_CHECKING:
    from pylord.engine.game import GameCtx

_LINE_MAXLEN = 75  # reference/lord.js:9424 (getstr({len:75}))


@scene("announce")
async def announce(ctx: GameCtx) -> str:
    """Port of ``announce()``. reference/lord.js:9397-9432 -- a free-text
    broadcast that lands in today's news for everyone to read."""
    await ctx.io.write(
        "\n\n  `2Are you sure you want to announce something?  It will appear to\n"
        "  EVERYONE in the daily happenings.\n\n"
    )
    if await ctx.io.menu(
        {"Y": "yes", "N": "no"}, "  Make Announcement? [`0Y`2] :`% "
    ) == "N":
        return "town"

    await ctx.io.write("\n  Enter message now..Blank line quits!\n")
    lines: list[str] = []
    while True:
        line = await ctx.io.readline(" `2>`% ", maxlen=_LINE_MAXLEN)
        if not line.strip():
            break
        lines.append(f"  `%{line}")
    if lines:
        body = "\n".join(lines)
        ctx.news(f"  `0{ctx.player.name}`2 Announces:`%\n{body}")
        await ctx.io.write("\n  Announcement Made!\n")
    await ctx.io.pause()
    return "town"


@scene("who_is_on")
async def who_is_on(ctx: GameCtx) -> str:
    """Port of ``warriors_on_now()``. reference/lord.js:5671-5710.

    lord.js reports where each player currently is by reading their IGM
    drop file; this project has no such per-session location record, so the
    listing is name + level only.
    """
    await ctx.io.write(
        "\n                         `%Warriors in the Realm Now\n"
        "`2-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
    )
    online = [p for p in ctx.repo.all_players() if p.online]
    if not online:
        await ctx.io.write("\n  `2Nobody else is in the realm right now.\n")
    for p in online:
        await ctx.io.write(f"  `0{p.name:<25} `2Level `0{p.level}\n")
    await ctx.io.pause()
    return "town"


@scene("game_stats")
async def game_stats(ctx: GameCtx) -> str:
    """Port of ``show_game_stats()``. reference/lord.js:16251-16276."""
    day_row = ctx.conn.execute(
        "SELECT value FROM game_state WHERE key = 'day'"
    ).fetchone()
    day = day_row["value"] if day_row is not None else "1"
    win_deeds = ctx.config.get("win_deeds", 3)  # reference/lord.js:1852
    players = ctx.repo.all_players()

    lines = [
        "",
        "                     `%** GAME STATISTICS **`2",
        "",
        f" `2 This game has been running for `%{day}`2 days.",
        "  `2You are playing a `0P`2Y`0T`2H`0O`2N`0 game.",
    ]
    if win_deeds > 0:
        lines.append(
            f"  `2Game can be `0FINISHED `2by getting {win_deeds} heroic deeds"
        )
    else:
        lines.append("  `2Game is set to run indefinitely.")
    lines.append("")
    lines.append(f"  `2There are currently `%{len(players)} `2people playing.")
    lines.append("")
    await ctx.io.write("\n".join(lines) + "\n")
    await ctx.io.pause()
    return "town"


@scene("read_mail")
async def read_mail(ctx: GameCtx) -> str:
    """The ``R`` key -- show (and apply) anything that has arrived since
    login. reference/lord.js:16950-16959 (``main()``'s own ``R`` case,
    which calls ``check_mail()`` when ``mail_check()`` says there is
    something waiting)."""
    shown = await mail_scene.apply_unread_mail(ctx)
    if not shown:
        await ctx.io.write("\n  You have no mail.\n")
        await ctx.io.pause()
    return "town"
