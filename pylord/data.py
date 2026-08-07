"""Every SQL statement in the game, over an async engine.

Phase 1 gathered the SQL behind repositories; this is the same shape with
SQLAlchemy Core underneath, so the realm runs on MySQL in the homelab and
on SQLite locally and in tests from one set of definitions
(``pylord/schema.py``).

**Why async.** A query against a local SQLite file costs microseconds, so
blocking the event loop for one was free. A query to MySQL crosses a
socket, and this server runs every telnet session on a single loop -- one
blocking call would stall everybody's game. Repository methods are
therefore awaitable.

**Transactions.** ``async with db.transaction() as tx`` is one unit of
work. Nesting joins the outer transaction rather than opening a second one,
which is the behaviour the old ``with conn:`` idiom lacked and which cost
us a partly-committed daily pass. Never hold one across player input: a
transaction holds a pooled connection, and a player staring at a menu for a
minute must not hold a database connection while they do it.

**The IGM surface stays synchronous.** Plugins call ``ctx.store.get()`` and
``ctx.other_players()`` without awaiting, as documented, because a visit
loads what it needs up front and buffers what it writes -- see
``pylord/hooks.py``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import fields
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from pylord import schema
from pylord.models import Player, hash_password, verify_password

logger = logging.getLogger(__name__)

#: Armor defense powers by armor_num (index 0 = unarmored) before and
#: after the schema-version-6 rebalance
#: (docs/superpowers/specs/2026-08-07-armor-rebalance-design.md). V5 is
#: frozen history -- it must match what players actually bought under
#: version 5, not the live table in pylord/engine/data/armor.py, which
#: may drift again behind a future migration.
_ARMOR_POWERS_V5 = (0, 1, 3, 10, 15, 25, 35, 50, 75, 100, 150, 225, 300, 400, 600, 1000)
_ARMOR_POWERS_V6 = (0, 3, 8, 25, 38, 63, 88, 125, 188, 250, 375, 560, 750, 950, 1150, 1350)

_PLAYER_COLS = [f.name for f in fields(Player) if f.name not in ("id", "name")]
_ALL_PLAYER_COLS = [f.name for f in fields(Player)]


def create_engine(url: str, **kwargs: Any) -> AsyncEngine:
    """Build the async engine for ``url``.

    Accepts the shorthand this project has always used for SQLite -- a bare
    path, or ``:memory:`` -- as well as a full SQLAlchemy URL such as
    ``mysql+aiomysql://user:pass@host/db``.
    """
    if "://" not in url:
        url = f"sqlite+aiosqlite:///{url}"
    options: dict[str, Any] = {"future": True, **kwargs}
    if url.startswith("sqlite"):
        if ":memory:" in url:
            # One in-memory database shared by every connection, so a test
            # sees the schema it just created.
            from sqlalchemy.pool import StaticPool

            options.setdefault("poolclass", StaticPool)
            options.setdefault("connect_args", {"check_same_thread": False})
    else:
        options.setdefault("pool_pre_ping", True)
        options.setdefault("pool_recycle", 3600)
    return create_async_engine(url, **options)


def _row_to_player(row: Any) -> Player:
    return Player(**{col: getattr(row, col) for col in _ALL_PLAYER_COLS})


class _Repo:
    def __init__(self, db: Database) -> None:
        self._db = db


class GameStateRepo(_Repo):
    """The ``game_state`` key/value table: the game day, the last
    maintenance date, the NPC marriages, the realm's winner."""

    async def get(self, key: str, default: str | None = None) -> str | None:
        row = await self._db.fetch_one(
            select(schema.game_state.c.value).where(schema.game_state.c.key == key)
        )
        return row.value if row is not None else default

    async def get_int(self, key: str, default: int) -> int:
        raw = await self.get(key)
        try:
            return int(raw) if raw is not None else default
        except (TypeError, ValueError):
            return default

    async def set(self, key: str, value: str | int) -> None:
        await self._db.upsert(
            schema.game_state,
            {"key": key, "value": str(value)},
            index_elements=["key"],
            update_columns=["value"],
        )

    async def delete(self, key: str) -> None:
        await self._db.execute(
            delete(schema.game_state).where(schema.game_state.c.key == key)
        )

    async def all_rows(self) -> dict[str, str]:
        """Every key at once, for callers that need a snapshot to read
        from synchronously afterwards (see ``hooks.StateView``)."""
        rows = await self._db.fetch_all(
            select(schema.game_state.c.key, schema.game_state.c.value)
        )
        return {row.key: row.value for row in rows}


class NewsRepo(_Repo):
    """Today's happenings, and yesterday's."""

    async def add(self, day: str | int, text: str) -> None:
        await self._db.execute(
            insert(schema.daily_news).values(day=str(day), text=text)
        )

    async def for_day(self, day: str | int) -> list[str]:
        rows = await self._db.fetch_all(
            select(schema.daily_news.c.text)
            .where(schema.daily_news.c.day == str(day))
            .order_by(schema.daily_news.c.id)
        )
        return [row.text for row in rows]


class MailRepo(_Repo):
    """Player mail, including the async stat effects it can carry."""

    async def send(
        self,
        to_id: int,
        from_name: str,
        text: str | None = None,
        effect: dict | None = None,
    ) -> None:
        await self._db.execute(
            insert(schema.mail).values(
                to_id=to_id,
                from_name=from_name,
                text=text,
                effect=json.dumps(effect) if effect is not None else None,
                created=datetime.now(UTC).isoformat(),
                read=0,
            )
        )

    async def unread_for(self, player_id: int) -> list[Any]:
        return await self._db.fetch_all(
            select(
                schema.mail.c.id,
                schema.mail.c.from_name,
                schema.mail.c.text,
                schema.mail.c.effect,
            )
            .where(schema.mail.c.to_id == player_id, schema.mail.c.read == 0)
            .order_by(schema.mail.c.id)
        )

    async def mark_read(self, mail_id: int) -> None:
        await self._db.execute(
            update(schema.mail).where(schema.mail.c.id == mail_id).values(read=1)
        )

    async def delete_for(self, player_id: int) -> None:
        await self._db.execute(
            delete(schema.mail).where(schema.mail.c.to_id == player_id)
        )


class IgmDataRepo(_Repo):
    """The ``igm_data`` key/value table, namespaced per IGM."""

    async def all_for(self, igm_key: str) -> dict[str, str]:
        """Every row for one IGM. A visit loads these up front so the
        plugin API can stay synchronous."""
        rows = await self._db.fetch_all(
            select(schema.igm_data.c.k, schema.igm_data.c.v).where(
                schema.igm_data.c.igm_key == igm_key
            )
        )
        return {row.k: row.v for row in rows}

    async def get_raw(self, igm_key: str, key: str) -> str | None:
        row = await self._db.fetch_one(
            select(schema.igm_data.c.v).where(
                schema.igm_data.c.igm_key == igm_key, schema.igm_data.c.k == key
            )
        )
        return row.v if row is not None else None

    async def set_raw(self, igm_key: str, key: str, value: str) -> None:
        await self._db.upsert(
            schema.igm_data,
            {"igm_key": igm_key, "k": key, "v": value},
            index_elements=["igm_key", "k"],
            update_columns=["v"],
        )

    async def delete(self, igm_key: str, key: str) -> None:
        await self._db.execute(
            delete(schema.igm_data).where(
                schema.igm_data.c.igm_key == igm_key, schema.igm_data.c.k == key
            )
        )


class PlayersRepo(_Repo):
    """Characters: the only table anyone would cry over losing."""

    async def create(self, name: str, password: str, gender: str = "M") -> Player:
        from sqlalchemy.exc import IntegrityError

        try:
            async with self._db.transaction() as tx:
                result = await tx.execute(
                    insert(schema.players).values(
                        name=name, password_hash=hash_password(password), gender=gender
                    )
                )
                player_id = result.inserted_primary_key[0]
        except IntegrityError as exc:
            raise ValueError(f"player name already exists: {name}") from exc

        player = await self.get(player_id)
        assert player is not None
        return player

    async def get(self, player_id: int) -> Player | None:
        row = await self._db.fetch_one(
            select(schema.players).where(schema.players.c.id == player_id)
        )
        return _row_to_player(row) if row is not None else None

    async def get_by_name(self, name: str) -> Player | None:
        row = await self._db.fetch_one(
            select(schema.players).where(schema.players.c.name == name)
        )
        return _row_to_player(row) if row is not None else None

    async def all_players(self) -> list[Player]:
        rows = await self._db.fetch_all(
            select(schema.players).order_by(schema.players.c.id)
        )
        return [_row_to_player(row) for row in rows]

    async def save(self, player: Player) -> None:
        """Persist every mutable column. Joins the caller's transaction when
        there is one, and commits on its own when there isn't."""
        await self._db.execute(
            update(schema.players)
            .where(schema.players.c.id == player.id)
            .values({col: getattr(player, col) for col in _PLAYER_COLS})
        )

    async def check_password(self, name: str, password: str) -> Player | None:
        player = await self.get_by_name(name)
        if player is None or not verify_password(password, player.password_hash):
            return None
        return player

    async def clear_online_flags(self) -> int:
        """Used at startup: no session can exist before the listener does,
        so anything still marked online is stale."""
        result = await self._db.execute(
            update(schema.players).where(schema.players.c.online != 0).values(online=0)
        )
        return result.rowcount

    async def delete(self, player_id: int) -> None:
        await self._db.execute(
            delete(schema.players).where(schema.players.c.id == player_id)
        )
        await self._db.execute(
            update(schema.players)
            .where(schema.players.c.married_to == player_id)
            .values(married_to=None)
        )

    async def count(self) -> int:
        row = await self._db.fetch_one(select(func.count()).select_from(schema.players))
        return int(row[0])


class Database:
    """The engine's whole view of storage: repositories, and the
    transaction boundary they share."""

    def __init__(
        self, engine: AsyncEngine, conn: AsyncConnection | None = None
    ) -> None:
        self._engine = engine
        self._conn = conn
        self.players = PlayersRepo(self)
        self.state = GameStateRepo(self)
        self.news = NewsRepo(self)
        self.mail = MailRepo(self)
        self.igm_data = IgmDataRepo(self)

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @property
    def dialect(self) -> str:
        return self._engine.dialect.name

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[Database]:
        """One unit of work: everything inside lands, or none of it does.

        Nesting joins the outer transaction rather than opening a second
        one, so a helper that wants atomicity can be called from inside a
        larger operation without quietly committing it.
        """
        if self._conn is not None:
            yield self
            return
        async with self._engine.begin() as conn:
            yield Database(self._engine, conn)

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[AsyncConnection]:
        if self._conn is not None:
            yield self._conn
            return
        async with self._engine.connect() as conn:
            yield conn
            await conn.commit()

    async def execute(self, statement: Any, parameters: Any = None) -> Any:
        """Run ``statement``. ``parameters`` may be a list of dicts, which
        executes it once per entry -- how a bulk copy inserts (see
        ``pylord/migrate.py``)."""
        async with self._connection() as conn:
            if parameters is None:
                return await conn.execute(statement)
            return await conn.execute(statement, parameters)

    async def fetch_one(self, statement: Any) -> Any:
        async with self._connection() as conn:
            result = await conn.execute(statement)
            return result.first()

    async def fetch_all(self, statement: Any) -> list[Any]:
        async with self._connection() as conn:
            result = await conn.execute(statement)
            return list(result.all())

    async def upsert(
        self,
        table: Any,
        values: dict[str, Any],
        *,
        index_elements: list[str],
        update_columns: list[str],
    ) -> None:
        """INSERT ... ON CONFLICT/DUPLICATE KEY UPDATE, spelled for the
        dialect in use -- the one statement the two databases disagree
        about."""
        if self.dialect == "mysql":
            stmt = mysql_insert(table).values(**values)
            stmt = stmt.on_duplicate_key_update(
                **{col: getattr(stmt.inserted, col) for col in update_columns}
            )
        else:
            stmt = sqlite_insert(table).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=index_elements,
                set_={col: getattr(stmt.excluded, col) for col in update_columns},
            )
        await self.execute(stmt)

    async def create_schema(self) -> None:
        """Bring the database up to the schema the code expects."""
        async with self._engine.begin() as conn:
            await conn.run_sync(schema.metadata.create_all)
            await conn.run_sync(self._add_missing_columns)
        existing = await self.fetch_one(select(schema.schema_version.c.applied_count))
        if existing is not None and existing.applied_count < 6:
            await self._rebalance_armor_defense()
        if existing is None:
            await self.execute(
                insert(schema.schema_version).values(
                    applied_count=schema.CURRENT_VERSION
                )
            )
        else:
            await self.execute(
                update(schema.schema_version).values(
                    applied_count=schema.CURRENT_VERSION
                )
            )

    async def _rebalance_armor_defense(self) -> None:
        """Schema-version-6 data migration: armor powers were rescaled
        (see _ARMOR_POWERS_V5/_V6), so re-base every armored player's
        defense by the delta for their equipped armor. A delta rather
        than a recompute, so defense bought at SunShines' Fairy Land or
        granted by IGMs survives."""
        from pylord.engine.limits import STAT_CAP

        for player in await self.players.all_players():
            if player.armor_num == 0:
                continue
            if not 1 <= player.armor_num < len(_ARMOR_POWERS_V5):
                logger.warning(
                    "player %s has armor_num %s outside 1..15; "
                    "skipping armor rebalance for them",
                    player.id,
                    player.armor_num,
                )
                continue
            delta = (
                _ARMOR_POWERS_V6[player.armor_num]
                - _ARMOR_POWERS_V5[player.armor_num]
            )
            player.defense = max(0, min(player.defense + delta, STAT_CAP))
            await self.players.save(player)

    @staticmethod
    def _add_missing_columns(conn: Any) -> None:
        """Add columns a release introduced to a database that predates it.

        ``create_all`` only creates whole tables that are absent -- it will
        not touch a table that already exists. Without this, adding a field
        to ``schema.py`` would work perfectly on a fresh database and on
        every test, and silently never reach the live realm, where the code
        would then query a column that isn't there.

        Deliberately additive only. Dropping or retyping a column is
        destructive and is not something a server should do to a realm on
        startup because its code changed; those need a considered
        migration. This exists so *adding* a field -- which is what a game
        gaining features actually does -- is safe.
        """
        from sqlalchemy import inspect, text
        from sqlalchemy.schema import CreateColumn

        inspector = inspect(conn)
        preparer = conn.dialect.identifier_preparer
        for table in schema.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            present = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in present:
                    continue
                if column.server_default is None and not column.nullable:
                    raise RuntimeError(
                        f"cannot add {table.name}.{column.name} to an existing "
                        "database: a NOT NULL column needs a server_default so "
                        "the rows already there get a value"
                    )
                spec = CreateColumn(column).compile(dialect=conn.dialect)
                logger.info("adding new column %s.%s", table.name, column.name)
                conn.execute(
                    text(
                        f"ALTER TABLE {preparer.format_table(table)} ADD COLUMN {spec}"
                    )
                )

    async def dispose(self) -> None:
        await self._engine.dispose()


async def connect(url: str, **kwargs: Any) -> Database:
    """Open a database and make sure its schema exists."""
    db = Database(create_engine(url, **kwargs))
    await db.create_schema()
    return db
