"""Daily News -- port of ``reference/lord.js``'s ``show_log()``
(``:5735-5822``), the today/yesterday happenings screen reachable from both
the Town Square (``D``, reference/lord.js:16942-16945) and the Inn (``D``,
lord.js:9968-9971) -- both routed to this same scene by ``town.py``/
``inn.py``.

lord.js's log is a rolling two-file pair (``lognow.lrd`` / ``logold.lrd``,
swapped by ``create_log()`` the first time a new day is detected,
reference/lord.js:3057-3075) fed by ``log_line()``/``ctx.news()`` calls
throughout the game plus one random "happenings" flavor line per day
(lord.js:3040-3055, 3085). This project's ``daily_news`` table
(``pylord/db.py``) already carries a ``day`` column (the same monotonic
counter ``pylord/engine/daily.py`` advances once per calendar day), so
"today" / "yesterday" here means "day N" / "day N-1" by that counter rather
than lord.js's file-swap-on-first-view mechanic -- a wash, functionally.

**Deviation**: no random daily "happenings" flavor line
(reference/lord.js:3040-3055, ``happenings[random(happenings.length)]``,
written once per day by ``create_log()``) -- this project's daily
maintenance pass (``pylord/engine/daily.py``, Task 10) doesn't write one and
extending it is out of this task's scope; ``daily_news`` here only ever
holds real gameplay events (forest deaths, master wins, Inn romance, mail
IGM broadcasts, ...).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylord.engine.game import scene

if TYPE_CHECKING:
    from pylord.engine.game import GameCtx

_HEADER = "\n  `2The Daily Happenings....\n`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"


def _current_day(ctx: GameCtx) -> int:
    row = ctx.conn.execute(
        "SELECT value FROM game_state WHERE key = 'day'"
    ).fetchone()
    return int(row["value"]) if row is not None else 1


async def _show(ctx: GameCtx, *, today: bool) -> None:
    day = _current_day(ctx)
    target = day if today else day - 1
    rows = ctx.conn.execute(
        "SELECT text FROM daily_news WHERE day = ? ORDER BY id", (str(target),)
    ).fetchall()
    if not rows:
        if today:
            await ctx.io.write(f"{_HEADER}\n  Nothing has happened yet today.\n")
        else:  # reference/lord.js:5807-5811
            await ctx.io.write(
                "\n\n  Apparently nothing of importance happened yesterday.\n"
            )
        return
    await ctx.io.write(_HEADER)
    for row in rows:
        await ctx.io.write(f"{row['text']}\n")


@scene("news")
async def news(ctx: GameCtx) -> str:
    await _show(ctx, today=True)
    while True:
        choice = await ctx.io.menu(
            {"C": "continue", "T": "today", "Y": "yesterday"},
            "\n  `2(`5C`2)ontinue   (`5T`2)odays happenings again   "
            "(`5Y`2)esterdays `0[`5C`0] : ",
        )
        if choice == "C":
            return "town"
        await _show(ctx, today=(choice == "T"))
