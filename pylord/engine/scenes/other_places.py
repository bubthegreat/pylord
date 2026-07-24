"""The Town Square's "Other Places" menu -- the entry point into IGM plugins.

This is the runtime counterpart to :mod:`pylord.igm_loader` (discovery) and
:mod:`pylord.hooks` (the plugin surface). It lists every enabled IGM and,
when the player picks one, runs the **visit protocol** -- the transactional
sandbox that makes a drop-in plugin safe to run against a live character:

1. Snapshot the player (a plain dataclass copy).
2. Commit any pending session state so our transaction is self-contained,
   then build the guardrailed :class:`~pylord.hooks.IgmContext`.
3. ``await igm.enter(igm_ctx)``.
4. **Clean exit** -> flush the store + buffered news and persist the
   (possibly mutated) player, all in one ``commit()``.
5. **Any exception** -> ``rollback()`` (undoing store/news/mail writes the
   plugin made mid-visit), restore the player's fields **in place** from the
   snapshot (preserving object identity -- see ``_restore_in_place``), log,
   and show the "strange force" flavor line. ``ConnectionClosed`` /
   ``OutOfKeys`` are re-raised after the rollback so the session's own
   teardown still sees the real "input is gone" signal; every other
   exception (including :class:`~pylord.hooks.IgmViolation`) is swallowed
   and the player is bounced back to the forest.

**Transaction mechanics.** The session's ``sqlite3`` connection runs in the
stdlib default ``isolation_level=""`` (implicit-BEGIN-before-DML, manual
commit). The visit brackets its work with a leading ``commit()`` (to close
any implicit transaction left open earlier in the session, so our
``rollback()`` can only ever affect *this* visit) and a trailing
``commit()``/``rollback()``. Crucially, nothing inside the visit uses the
``with conn:`` context manager or the repo/ctx ``save``/``news`` helpers
(which self-commit) -- store flush, news flush, mail insert, and the player
UPDATE are all raw ``conn.execute`` calls, so the visit really is one
atomic unit.
"""

from __future__ import annotations

import logging
from dataclasses import fields, replace
from typing import TYPE_CHECKING

from pylord.engine.game import scene
from pylord.engine.persist import save_player_raw
from pylord.hooks import IgmContext
from pylord.models import Player
from pylord.terminal import ConnectionClosed, OutOfKeys

if TYPE_CHECKING:
    from pylord.engine.game import GameCtx
    from pylord.hooks import IGM

logger = logging.getLogger("pylord.igm")

_PROMPT = "`2Your choice`0? `2"

_HEADER = (
    "\n`5  Other Places\n"
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-"
)


def _restore_in_place(player: Player, snapshot: Player) -> None:
    """Copy ``snapshot``'s fields back onto ``player`` **in place**.

    Object identity matters: ``server.handle_connection`` holds its own
    reference to the very same ``Player`` object (its ``finally:`` clears
    ``online`` and re-saves it). If a crashing/disconnecting visit merely
    rebound ``ctx.player`` to a fresh snapshot copy, that dangling original
    would still carry the IGM's mutations and the cleanup save would
    re-persist them -- silently undoing the DB rollback. Mutating the
    original back to its pre-visit state keeps every holder of the object
    consistent.
    """
    for f in fields(Player):
        setattr(player, f.name, getattr(snapshot, f.name))


async def _visit(ctx: GameCtx, igm: IGM) -> None:
    """Run one IGM visit under the transactional sandbox (see module doc)."""
    conn = ctx.conn
    # Close any implicit transaction from earlier this session so our
    # rollback can only affect this visit.
    conn.commit()
    snapshot = replace(ctx.player)
    igm_ctx = IgmContext(ctx, igm)

    try:
        await igm.enter(igm_ctx)
    except (ConnectionClosed, OutOfKeys):
        conn.rollback()
        _restore_in_place(ctx.player, snapshot)
        raise
    except Exception:
        conn.rollback()
        _restore_in_place(ctx.player, snapshot)
        logger.exception("IGM %s crashed during enter()", igm.key)
        await ctx.io.write(
            "\n  `%A strange force pushes you back to the forest...`0\n"
        )
        return

    # Clean exit: flush everything the visit produced, atomically. Skip the
    # player UPDATE when nothing was written (PlayerView tracks this).
    igm_ctx.store.flush()
    igm_ctx.flush_news()
    if igm_ctx.player.dirty:
        save_player_raw(ctx.conn, ctx.player)
    conn.commit()


@scene("other_places")
async def other_places(ctx: GameCtx) -> str:
    """The IGM hub, reached from the Town Square's ``O``
    (reference/lord.js:17003-17077).

    lord.js numbers the places (1..N) and loops until ``Q``, so several
    can be visited in one trip; both are reproduced here. lord.js reads
    the list length to decide between a single keypress and a typed
    number -- this port always takes a typed number, since ``menu()`` is
    single-key and a realm with ten or more IGMs is normal.
    """
    while True:
        registry = ctx.igms
        places = registry.other_places() if registry is not None else []
        if not places:
            await ctx.io.write(
                "\n  `2The path is overgrown... nothing here yet.`0\n"
            )
            await ctx.io.pause()
            return "town"

        lines = [_HEADER]
        for idx, igm in enumerate(places, start=1):
            lines.append(f"  `2(`0{idx}`2) {igm.name}")
        lines.append("  `2(`0Q`2) Return to town")
        lines.append("")
        await ctx.io.write("\n".join(lines))

        raw = (await ctx.io.readline(_PROMPT, maxlen=3)).strip().upper()
        if raw in ("", "Q"):  # reference/lord.js:17039-17041, blank == Q
            return "town"
        if not raw.isdigit():
            continue
        choice = int(raw)
        if 1 <= choice <= len(places):  # reference/lord.js:17061-17066
            await _visit(ctx, places[choice - 1])
