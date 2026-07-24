"""The forest's "Other Places" menu -- the entry point into IGM plugins.

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
from pylord.hooks import IgmContext
from pylord.models import Player
from pylord.terminal import ConnectionClosed, OutOfKeys

if TYPE_CHECKING:
    from pylord.engine.game import GameCtx
    from pylord.hooks import IGM

logger = logging.getLogger("pylord.igm")

# Player columns to persist on a clean visit -- everything but the two
# immutable identity fields (mirrors PlayerRepo.save()'s own set, but as a
# raw UPDATE so it can share the visit's single transaction).
_SAVE_COLS = [f.name for f in fields(Player) if f.name not in ("id", "name")]

_PROMPT = "`2Your choice`0? `2"

_HEADER = (
    "\n`5  Other Places\n"
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-"
)


def _save_player_raw(ctx: GameCtx) -> None:
    set_clause = ", ".join(f"{c} = :{c}" for c in _SAVE_COLS)
    params = {c: getattr(ctx.player, c) for c in _SAVE_COLS}
    params["id"] = ctx.player.id
    ctx.conn.execute(f"UPDATE players SET {set_clause} WHERE id = :id", params)


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
        _save_player_raw(ctx)
    conn.commit()


@scene("other_places")
async def other_places(ctx: GameCtx) -> str:
    registry = ctx.igms
    places = registry.other_places() if registry is not None else []
    if not places:
        await ctx.io.write(
            "\n  `2The path is overgrown... nothing here yet.`0\n"
        )
        return "forest"

    # A..Z, one letter per IGM (capped at 26 -- far more than any realm
    # would ever enable), plus (R)eturn.
    places = places[:26]
    options: dict[str, str] = {}
    lines = [_HEADER]
    for idx, igm in enumerate(places):
        letter = chr(ord("A") + idx)
        options[letter] = igm.key
        lines.append(f"  `2(`0{letter}`2){igm.name}")
    options["R"] = "return"
    lines.append("  `2(`0R`2)eturn to forest")
    lines.append("")
    await ctx.io.write("\n".join(lines))

    choice = await ctx.io.menu(options, _PROMPT)
    if choice == "R":
        return "forest"

    igm = places[ord(choice) - ord("A")]
    await _visit(ctx, igm)
    return "forest"
