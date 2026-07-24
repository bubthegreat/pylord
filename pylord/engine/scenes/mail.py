"""Mail: write a letter to another player, and the login-time "messenger"
that shows/applies unread mail.

**Scope, and what's deliberately NOT here.** lord.js's ``compose_mail()``
(reference/lord.js:4990-5178) is really two features fused together: (a) a
plain "pick a recipient, type some lines" letter (``write_mail()``,
lord.js:3179-3301, reached whenever the sender declines the romantic
branch or the two players are the same sex), and (b) an elaborate
player-to-player flirtation mini-game (wink/kiss/dinner/invite-to-room/
propose-marriage, each with its own charm-gated reply screen the *recipient*
sees when their mail is next read -- ``wink_mail()``/``kiss_mail()``/
``dinner_mail()``/``sleep_mail()``/``marry_mail()``, lord.js:3820-4209) that
drives lord.js's real player-to-player ``player.married_to``
(reference/lord.js:4096, see ``conjugality.py``). This task's brief scopes
the Mail scene to a generic async "effect" channel (``gold``/``gems``/
``exp``/.../``player_fights``, see ``pylord/engine/effects.py``) with no
romance-specific effect type in that list, and the Inn scene (this task's
actual romance surface) already covers Violet/Seth Able. So only (a) is
ported here; the interactive charm-gated reply-mail mini-game (b) is out of
scope -- ``player.married_to`` is written by ``pylord/engine/scenes/inn.py``
(marrying an NPC leaves it alone) and is otherwise never set by anything in
this task, which is fine: ``conjugality.py``'s listing still works (it just
never has a player-to-player row to show until a later task adds one).

**Login-time mail check**: lord.js's ``check_mail()``
(reference/lord.js:2300-2360) is invoked constantly throughout a session
(every town/inn/forest menu redraw) and shows unread letters via a
"stopped by a messenger" banner. This project applies/shows mail exactly
once, at login (``server.py``, right after the session's ``GameCtx`` is
built and before ``run_session`` starts) via :func:`apply_unread_mail`
-- a deliberate architecture simplification (this project's sessions are
long-lived telnet connections, not lord.js's one-shot BBS door calls where
re-checking on every menu redraw is the only way to notice new mail that
arrived *during* the session).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pylord.engine.effects import apply_effect
from pylord.engine.game import scene
from pylord.engine.persist import save_player_raw

if TYPE_CHECKING:
    from pylord.engine.game import GameCtx
    from pylord.models import Player

_NAME_MAXLEN = 20
_LINE_MAXLEN = 75


async def apply_unread_mail(ctx: GameCtx) -> int:
    """Show every unread letter addressed to ``ctx.player``, applying any
    JSON ``effect`` payload and marking each row read. Returns the count
    shown. Safe to call multiple times -- rows already marked read are
    never re-applied (the ``read = 0`` filter), so a re-login (or a second
    call in the same session) is a no-op. Mirrors the "stopped by a
    messenger" banner text (reference/lord.js:2322-2323/2347-2348).

    **Durability** (post-review fix): marking a row read and persisting the
    player's mutated stats happen in the *same* transaction
    (``save_player_raw``, a raw ``UPDATE`` sharing this loop iteration's
    ``with ctx.conn:`` block -- see ``pylord/engine/persist.py``). An
    earlier version committed ``read = 1`` immediately but left the
    in-memory ``gold``/``exp``/etc. mutation to be persisted only by
    whatever eventually calls ``GameCtx.save()`` at session end -- so a
    crash between those two points would durably mark the mail read while
    silently discarding the effect it was supposed to deliver (a
    lost-update bug). Now either both commit or neither does, and a
    dropped commit is safe to retry: the row is still unread, so the next
    login re-shows and re-applies the very same letter."""
    rows = ctx.conn.execute(
        "SELECT id, from_name, text, effect FROM mail "
        "WHERE to_id = ? AND read = 0 ORDER BY id",
        (ctx.player.id,),
    ).fetchall()
    if not rows:
        return 0

    await ctx.io.write(
        "\n  `%** YOU ARE STOPPED BY A MESSENGER WITH THE FOLLOWING NEWS: **`0\n"
    )
    for row in rows:
        await ctx.io.write(f"\n  `0{row['from_name']} `2sent you this:\n")
        if row["text"]:
            await ctx.io.write(f"{row['text']}\n")
        if row["effect"]:
            apply_effect(ctx.player, json.loads(row["effect"]))
        with ctx.conn:
            ctx.conn.execute("UPDATE mail SET read = 1 WHERE id = ?", (row["id"],))
            save_player_raw(ctx.conn, ctx.player)
    await ctx.io.pause()
    return len(rows)


async def _find_player(ctx: GameCtx) -> Player | None:
    """Port of ``find_player()``. reference/lord.js:4890-4926: prompt for a
    full-or-partial name, confirm the first case-insensitive substring
    match, keep scanning on a declined match. Returns ``None`` if nothing
    is confirmed."""
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


async def _compose(ctx: GameCtx) -> list[str]:
    """Port of the ``write_mail()`` line-editor loop (simplified: no
    word-wrap, no quoting a prior message -- reference/lord.js:3225-3265).
    A blank line ends the message; a blank *first* line still sends
    (matching lord.js's own "derp" one-liner fallback, lord.js:3256-3260,
    though this port sends an explicit note rather than a random one-liner
    -- see ``docs/deviations.md``)."""
    await ctx.io.write("\n  Enter message now..Blank line quits!\n")
    lines: list[str] = []
    while True:
        line = await ctx.io.readline("  `2>`0 ", maxlen=_LINE_MAXLEN)
        if not line:
            break
        lines.append(line)
    return lines or ["(no message)"]


@scene("mail")
async def mail(ctx: GameCtx) -> str:
    """Port of ``write_mail()``'s recipient-and-compose flow
    (reference/lord.js:3179-3301), minus the romantic branch -- see this
    module's docstring."""
    p = ctx.player
    await ctx.io.write(
        "\n  `5Write Mail`2\n`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
        "  Who would you like to send mail to?\n"
    )
    recipient = await _find_player(ctx)
    if recipient is None:
        await ctx.io.write("\n  `%No matching names found.`2\n")
        await ctx.io.pause()
        return "town"

    lines = await _compose(ctx)
    body = "\n".join(lines)
    now = datetime.now(UTC).isoformat()
    with ctx.conn:
        ctx.conn.execute(
            "INSERT INTO mail (to_id, from_name, text, effect, created, read) "
            "VALUES (?, ?, ?, NULL, ?, 0)",
            (recipient.id, p.name, body, now),
        )

    if recipient.id == p.id:  # reference/lord.js:3295-3300
        await ctx.io.write("\n  You are a very stupid individual.\n")
    else:
        await ctx.io.write(f"\n  `2Mail sent to `0{recipient.name}`2.\n")
    await ctx.io.pause()
    return "town"
