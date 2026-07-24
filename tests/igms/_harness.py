"""Shared test harness for the starter-six IGM test modules (Task 15/16/17).

Not itself a test module -- just the "build a fresh in-memory DB + player +
IgmContext" plumbing every ``tests/igms/test_<slug>.py`` needs, copied from
the construction pattern in ``tests/test_igm_framework.py`` /
``tests/igm_contract.py`` so each IGM's tests don't hand-roll it. Also
provides :class:`SeqRandom`, a tiny scripted stand-in for ``random.Random``
so gambling/charm-check outcomes can be pinned exactly rather than
seed-hunted -- an IGM's ``ctx.rng`` is duck-typed (only ``.randrange``/
``.randint``/``.choice`` are ever called on it), so a non-``random.Random``
object works fine here.
"""

from __future__ import annotations

from pylord import db
from pylord.engine.game import GameCtx
from pylord.hooks import IgmContext, IgmMaintContext
from pylord.models import PlayerRepo
from pylord.terminal import FakeIO


class SeqRandom:
    """Scripted RNG: each call to ``randrange``/``randint``/``choice`` pops
    the next entry off a pre-supplied queue.

    * ``randrange(n)`` / ``randint(a, b)`` -- queue holds the integer the
      call should return.
    * ``choice(seq)`` -- queue holds the *index* into ``seq`` to return.
    """

    def __init__(self, values: list[int]) -> None:
        self._values = list(values)

    def _next(self) -> int:
        if not self._values:
            raise AssertionError("SeqRandom ran out of scripted values")
        return self._values.pop(0)

    def randrange(self, *_a, **_k) -> int:
        return self._next()

    def randint(self, _a, _b) -> int:
        return self._next()

    def choice(self, seq):
        return seq[self._next()]


def make_db():
    """A fresh, migrated in-memory DB + repo."""
    conn = db.connect(":memory:")
    db.migrate(conn)
    return conn, PlayerRepo(conn)


def make_ctx(conn, repo, player, keys=None, rng=None) -> GameCtx:
    io = FakeIO(list(keys) if keys is not None else [])
    return GameCtx(player=player, repo=repo, io=io, conn=conn, rng=rng)


def make_igm_ctx(gctx: GameCtx, igm) -> IgmContext:
    return IgmContext(gctx, igm)


def make_maint_ctx(conn, config, igm_key: str) -> IgmMaintContext:
    return IgmMaintContext(conn, config or {}, igm_key)
