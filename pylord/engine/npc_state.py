"""Global, game-wide NPC marriage state -- who (if anyone) is currently
married to Violet the barmaid / Seth Able the bard.

lord.js keeps this on its own global ``state`` object
(``state.married_to_violet`` / ``state.married_to_seth``, set up at
reference/lord.js:2494-2495 and read/written throughout ``red_dragon_inn()``
and its helpers, e.g. lines 9460-9490, 9832, 16234-16241) -- a singleton
across *all* players, distinct from ``player.married_to`` (a real
player-to-player marriage, reference/lord.js:4096 -- see
``pylord/engine/scenes/conjugality.py``'s module docstring for why
player-to-player marriage itself is out of this task's scope).

This project has no equivalent global ``state`` table, but the existing
``game_state`` key/value table (``pylord/db.py``, already used by
``GameCtx.news()`` for the ``'day'`` counter) is exactly that shape, so the
two NPC marriages are stored there as ``'married_to_violet'`` /
``'married_to_seth'`` rows holding a player id (or ``'-1'`` for "no one").
"""

from __future__ import annotations

import sqlite3

from pylord.data import Database

NONE = -1

_KEY_VIOLET = "married_to_violet"
_KEY_SETH = "married_to_seth"


def _get(conn: sqlite3.Connection, key: str) -> int:
    return Database(conn).state.get_int(key, NONE)


def _set(conn: sqlite3.Connection, key: str, player_id: int) -> None:
    db = Database(conn)
    with db.transaction():
        db.state.set(key, player_id)


def married_to_violet(conn: sqlite3.Connection) -> int:
    """Player id currently married to Violet, or ``NONE`` (-1)."""
    return _get(conn, _KEY_VIOLET)


def set_married_to_violet(conn: sqlite3.Connection, player_id: int) -> None:
    _set(conn, _KEY_VIOLET, player_id)


def married_to_seth(conn: sqlite3.Connection) -> int:
    """Player id currently married to Seth Able, or ``NONE`` (-1)."""
    return _get(conn, _KEY_SETH)


def set_married_to_seth(conn: sqlite3.Connection, player_id: int) -> None:
    _set(conn, _KEY_SETH, player_id)
