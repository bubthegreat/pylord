"""Every SQL statement in the game lives here.

Until now the engine reached for ``conn.execute`` wherever it needed
something: the news day was read in four places with four copies of the
same ``SELECT``, mail was inserted from three, and each caller decided its
own transaction boundaries. That worked because SQLite is a local file --
a query costs microseconds and a mistake is cheap.

This module gathers those statements behind small repositories so that:

* the SQL exists once, in one dialect, where it can be reviewed and later
  translated;
* transaction boundaries are explicit (``db.transaction()``) rather than a
  ``with conn:`` idiom whose re-entrancy has already bitten this codebase
  twice -- see ``pylord/engine/daily.py`` and ``pylord/hooks.py``;
* the method signatures are the seam a future async engine slots into,
  without every scene and IGM changing again.

:class:`Database` owns the connection and hands out the repositories. Game
code should ask it for what it wants, not for a cursor.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import fields
from datetime import UTC, datetime

from pylord.models import Player, PlayerRepo

# Every mutable player column -- everything but the two identity fields.
_PLAYER_COLS = [f.name for f in fields(Player) if f.name not in ("id", "name")]


class GameStateRepo:
    """The ``game_state`` key/value table: the game day, the last
    maintenance date, the NPC marriages, the realm's winner."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, key: str, default: str | None = None) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM game_state WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row is not None else default

    def get_int(self, key: str, default: int) -> int:
        raw = self.get(key)
        try:
            return int(raw) if raw is not None else default
        except (TypeError, ValueError):
            return default

    def set(self, key: str, value: str | int) -> None:
        self._conn.execute(
            "INSERT INTO game_state (key, value) VALUES (:key, :value) "
            "ON CONFLICT(key) DO UPDATE SET value = :value",
            {"key": key, "value": str(value)},
        )

    def delete(self, key: str) -> None:
        self._conn.execute("DELETE FROM game_state WHERE key = ?", (key,))


class NewsRepo:
    """Today's happenings, and yesterday's."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(self, day: str | int, text: str) -> None:
        self._conn.execute(
            "INSERT INTO daily_news (day, text) VALUES (?, ?)", (str(day), text)
        )

    def for_day(self, day: str | int) -> list[str]:
        rows = self._conn.execute(
            "SELECT text FROM daily_news WHERE day = ? ORDER BY id", (str(day),)
        ).fetchall()
        return [row["text"] for row in rows]


class MailRepo:
    """Player mail, including the async stat effects it can carry."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def send(
        self,
        to_id: int,
        from_name: str,
        text: str | None = None,
        effect: dict | None = None,
    ) -> None:
        self._conn.execute(
            "INSERT INTO mail (to_id, from_name, text, effect, created, read) "
            "VALUES (?, ?, ?, ?, ?, 0)",
            (
                to_id,
                from_name,
                text,
                json.dumps(effect) if effect is not None else None,
                datetime.now(UTC).isoformat(),
            ),
        )

    def unread_for(self, player_id: int) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT id, from_name, text, effect FROM mail "
            "WHERE to_id = ? AND read = 0 ORDER BY id",
            (player_id,),
        ).fetchall()

    def mark_read(self, mail_id: int) -> None:
        self._conn.execute("UPDATE mail SET read = 1 WHERE id = ?", (mail_id,))

    def delete_for(self, player_id: int) -> None:
        self._conn.execute("DELETE FROM mail WHERE to_id = ?", (player_id,))


class Players(PlayerRepo):
    """:class:`~pylord.models.PlayerRepo` plus the writes the engine needs
    inside a caller-managed transaction.

    ``save`` commits on its own (it opens ``with self.conn``), which is
    right for a one-off edit and wrong inside a larger unit of work.
    ``save_in_transaction`` is the same UPDATE with no commit of its own --
    the caller's ``Database.transaction()`` decides when it lands.
    """

    def save_in_transaction(self, player: Player) -> None:
        set_clause = ", ".join(f"{c} = :{c}" for c in _PLAYER_COLS)
        params = {c: getattr(player, c) for c in _PLAYER_COLS}
        params["id"] = player.id
        self.conn.execute(f"UPDATE players SET {set_clause} WHERE id = :id", params)

    def clear_online_flags(self) -> int:
        """Used at startup: no session can exist before the listener does,
        so anything still marked online is stale."""
        return self.conn.execute(
            "UPDATE players SET online = 0 WHERE online != 0"
        ).rowcount

    def delete(self, player_id: int) -> None:
        self.conn.execute("DELETE FROM players WHERE id = ?", (player_id,))
        self.conn.execute(
            "UPDATE players SET married_to = NULL WHERE married_to = ?", (player_id,)
        )

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) AS n FROM players").fetchone()["n"]


class IgmDataRepo:
    """The ``igm_data`` key/value table, namespaced per IGM.

    :class:`pylord.hooks.IgmStore` layers the buffering and JSON encoding
    the plugin API promises on top of this; the SQL lives here.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_raw(self, igm_key: str, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT v FROM igm_data WHERE igm_key = ? AND k = ?", (igm_key, key)
        ).fetchone()
        return row["v"] if row is not None else None

    def set_raw(self, igm_key: str, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO igm_data (igm_key, k, v) VALUES (?, ?, ?) "
            "ON CONFLICT(igm_key, k) DO UPDATE SET v = excluded.v",
            (igm_key, key, value),
        )

    def delete(self, igm_key: str, key: str) -> None:
        self._conn.execute(
            "DELETE FROM igm_data WHERE igm_key = ? AND k = ?", (igm_key, key)
        )


class Database:
    """The engine's whole view of storage: repositories, and the
    transaction boundary they share."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.players = Players(conn)
        self.state = GameStateRepo(conn)
        self.news = NewsRepo(conn)
        self.mail = MailRepo(conn)
        self.igm_data = IgmDataRepo(conn)

    @contextmanager
    def transaction(self) -> Iterator[Database]:
        """One unit of work: everything inside lands, or none of it does.

        Do not nest these. ``sqlite3`` connections are not re-entrant
        context managers -- an inner block commits the outer one, which is
        how the daily pass once ended up committing player-by-player (see
        ``pylord/engine/daily.py``).
        """
        with self.conn:
            yield self

    def commit(self) -> None:
        self.conn.commit()

    def rollback(self) -> None:
        self.conn.rollback()

