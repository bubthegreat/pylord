"""Session game loop: scene registry + dispatcher, and the per-session
``GameCtx`` every scene function is handed.

A "scene" is an ``async def scene_xxx(ctx: GameCtx) -> str | None`` function
registered into the module-level ``SCENES`` dict via the ``@scene(name)``
decorator. Returning a string names the next scene to run; returning
``None`` ends the session (logoff). ``run_session`` is the tiny trampoline
that drives that loop -- it intentionally does no validation of the
returned key beyond the dict lookup: an unregistered scene name is a
programming error (a scene routing to a destination that was never
registered) and is left to raise ``KeyError`` rather than being swallowed.
"""

from __future__ import annotations

import random
import sqlite3
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pylord.models import Player, PlayerRepo
    from pylord.terminal import TermIO

SceneFn = Callable[["GameCtx"], Awaitable["str | None"]]

SCENES: dict[str, SceneFn] = {}


def scene(name: str) -> Callable[[SceneFn], SceneFn]:
    """Decorator: register ``fn`` under ``name`` in ``SCENES``.

    Usage::

        @scene("town")
        async def town(ctx: GameCtx) -> str | None:
            ...
    """

    def decorator(fn: SceneFn) -> SceneFn:
        SCENES[name] = fn
        return fn

    return decorator


class GameCtx:
    """Everything a scene needs: the player, repo, terminal I/O, db
    connection, config, and a seedable RNG. One instance per session."""

    def __init__(
        self,
        player: Player,
        repo: PlayerRepo,
        io: TermIO,
        conn: sqlite3.Connection,
        config: dict[str, Any] | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.player = player
        self.repo = repo
        self.io = io
        self.conn = conn
        self.config: dict[str, Any] = {} if config is None else config
        self.rng: random.Random = random.Random() if rng is None else rng
        self.igms = None  # Task 12: IGM registry.

    def news(self, text: str) -> None:
        """Append ``text`` to today's daily news log.

        Day comes from ``game_state`` key ``'day'``, defaulting to "1" when
        that row hasn't been set yet.
        """
        row = self.conn.execute(
            "SELECT value FROM game_state WHERE key = 'day'"
        ).fetchone()
        day = row["value"] if row is not None else "1"
        with self.conn:
            self.conn.execute(
                "INSERT INTO daily_news (day, text) VALUES (?, ?)", (day, text)
            )

    def save(self) -> None:
        """Persist ``self.player`` inside a transaction."""
        with self.conn:
            self.repo.save(self.player)


async def run_session(ctx: GameCtx, start: str = "town") -> None:
    """Drive scenes starting at ``start`` until one returns ``None``.

    A scene key with no entry in ``SCENES`` raises ``KeyError`` -- callers
    (tests, the telnet server loop) are expected to let this propagate.
    """
    key: str | None = start
    while key is not None:
        scene_fn = SCENES[key]
        key = await scene_fn(ctx)
    ctx.save()
