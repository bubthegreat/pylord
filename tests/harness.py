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
from pylord import db
from pylord.engine.game import GameCtx, run_session
from pylord.models import Player, PlayerRepo
from pylord.terminal import FakeIO, OutOfKeys

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def screen(io: FakeIO) -> str:
    """Join every rendered write() call in ``io.output`` and strip ANSI
    escape sequences, leaving plain text suitable for substring assertions."""
    return _ANSI_RE.sub("", "".join(io.output))


async def play(
    keys: list[str], player: Player | None = None, igms=None, **config
) -> tuple[FakeIO, Player]:
    """Run a scripted session and return (io, reloaded player).

    A reserved ``start`` config key (popped before it reaches
    ``GameCtx.config``) picks the starting scene; defaults to "town".
    ``igms`` (an IgmRegistry) stays ``None`` by default -- most scene tests
    don't exercise plugins; the IGM framework's own tests pass one in.
    """
    start = config.pop("start", "town")

    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)

    if player is None:
        player = repo.create("Tester", "pw", "M")

    io = FakeIO(keys)
    ctx = GameCtx(
        player=player, repo=repo, io=io, conn=conn, config=config, igms=igms
    )
    ctx.rng = random.Random(0)

    try:
        await run_session(ctx, start=start)
    except OutOfKeys:
        ctx.save()

    reloaded = repo.get(player.id)
    assert reloaded is not None
    return io, reloaded
