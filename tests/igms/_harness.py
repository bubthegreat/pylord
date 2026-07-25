"""Shared test harness for the starter-six IGM test modules (Task 15/16/17).

Not itself a test module -- just the "build a fresh in-memory DB + player +
IgmContext" plumbing every ``tests/igms/test_<slug>.py`` needs, copied from
the construction pattern in ``tests/test_igm_framework.py`` /
``tests/igm_contract.py`` so each IGM's tests don't hand-roll it. Also
provides :class:`SeqRandom`, a tiny scripted stand-in for ``random.Random``
so gambling/charm-check outcomes can be pinned exactly rather than
seed-hunted -- an IGM's ``ctx.rng`` is duck-typed (only ``.randrange``/
``.randint``/``.choice``/``.shuffle`` are ever called on it), so a
non-``random.Random`` object works fine here.

``shuffle`` (added for Task 20's LORD Gambling Casino, which shuffles a
real 52-card deck) is a scripted forward Fisher-Yates: each queued value is
an *offset* added to the current index ``i`` to pick the swap partner
``j = i + offset`` (so a whole ``len(x)``-long shuffle needs ``len(x)``
queued offsets). An offset of ``0`` is a same-index no-op swap, which lets
a test cheaply pin just the handful of cards it cares about (put a nonzero
offset only at the positions being dealt, ``0`` everywhere else) without
scripting a full realistic shuffle.
"""

from __future__ import annotations

from pylord import data
from pylord.engine.game import GameCtx
from pylord.hooks import IgmContext, IgmMaintContext
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

    def shuffle(self, x: list) -> None:
        """Scripted forward Fisher-Yates -- see class docstring."""
        n = len(x)
        for i in range(n):
            j = i + self._next()
            x[i], x[j] = x[j], x[i]


async def make_db():
    """A fresh in-memory database, and its players repository."""
    database = await data.connect(":memory:")
    return database, database.players


def make_ctx(database, repo, player, keys=None, rng=None) -> GameCtx:
    io = FakeIO(list(keys) if keys is not None else [])
    return GameCtx(player=player, db=database, io=io, rng=rng)


async def make_igm_ctx(gctx: GameCtx, igm) -> IgmContext:
    """The context an IGM sees: a snapshot loaded up front, writes
    buffered -- exactly what the visit protocol builds."""
    return await IgmContext.create(gctx, igm)


async def make_maint_ctx(database, config, igm_key: str) -> IgmMaintContext:
    return await IgmMaintContext.create(database, config or {}, igm_key)
