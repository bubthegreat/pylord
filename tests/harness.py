"""Test harness for driving a scripted game session end-to-end.

Builds a throwaway in-memory database, a fresh (or caller-supplied) player,
a scripted ``FakeIO``, and a ``GameCtx``, then runs ``run_session`` until the
scripted key queue is exhausted (or the session logs off on its own). Every
scene module must be imported (via ``pylord.engine.scenes``) before ``play``
is used so ``SCENES`` is fully populated.
"""

from __future__ import annotations

import random
import re

# Import for side effect: registers every scene module into game.SCENES.
import pylord.engine.scenes  # noqa: F401
from pylord import data
from pylord.engine.game import GameCtx, run_session
from pylord.models import Player
from pylord.terminal import FakeIO, OutOfKeys

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


async def query(database, sql: str, **params):
    """Run raw SQL for an assertion. Tests may look at the database
    directly; game code goes through the repositories."""
    from sqlalchemy import text

    statement = text(sql)
    return await database.fetch_all(
        statement.bindparams(**params) if params else statement
    )


async def query_one(database, sql: str, **params):
    rows = await query(database, sql, **params)
    return rows[0] if rows else None


def screen(io: FakeIO) -> str:
    """Join every rendered write() call in ``io.output`` and strip ANSI
    escape sequences, leaving plain text suitable for substring assertions."""
    return _ANSI_RE.sub("", "".join(io.output))


async def play(
    keys: list[str],
    player: Player | None = None,
    igms=None,
    overrides: dict | None = None,
    **config,
) -> tuple[FakeIO, Player]:
    """Run a scripted session and return (io, reloaded player).

    A reserved ``start`` config key (popped before it reaches
    ``GameCtx.config``) picks the starting scene; defaults to "town".
    ``igms`` (an IgmRegistry) stays ``None`` by default -- most scene tests
    don't exercise plugins; the IGM framework's own tests pass one in.
    ``overrides`` sets fields on the freshly-created player before the
    session starts (e.g. ``{"weapon_num": 0}`` to test the unarmed path a
    new character no longer starts in -- see pylord/db.py's Stick/Coat
    defaults, reference/recorddefs.js:47-51, 136-141).
    """
    start = config.pop("start", "town")

    database = await data.connect(":memory:")
    repo = database.players

    if player is None:
        player = await repo.create("Tester", "pw", "M")
    for key, value in (overrides or {}).items():
        setattr(player, key, value)

    io = FakeIO(keys)
    ctx = GameCtx(player=player, db=database, io=io, config=config, igms=igms)
    ctx.rng = random.Random(0)

    try:
        await run_session(ctx, start=start)
    except OutOfKeys:
        await ctx.save()

    reloaded = await repo.get(player.id)
    assert reloaded is not None
    return io, reloaded
