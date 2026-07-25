"""Copy a whole realm from one database to another.

Written for the SQLite-to-MySQL move, but there is nothing directional
about it: both sides are described by ``pylord/schema.py``, so this copies
between any two databases the game can open.

What it guarantees, in the order the guarantees matter:

* **It never writes into a realm that already has characters.** Running it
  twice, or pointing it at the wrong side, is the mistake that would cost
  someone their character. Pass ``overwrite=True`` to mean it.
* **Ids are preserved.** ``players.id`` is a foreign key in all but name --
  ``mail.to_id``, ``players.married_to``, and every IGM store key that
  embeds a player id ("digs:7"). Renumbering during the copy would quietly
  re-marry people and hand out someone else's daily allowance.
* **It is one transaction on the destination.** A copy that fails half way
  leaves nothing behind.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, insert, select

from pylord import data, schema

#: Copied in this order so anything anyone reads for a sanity check
#: (players first) is there before the rows that reference it.
TABLES = [
    schema.players,
    schema.game_state,
    schema.daily_news,
    schema.mail,
    schema.igm_data,
]


async def copy_realm(
    source: data.Database, dest: data.Database, *, overwrite: bool = False
) -> dict[str, int]:
    """Copy every table from ``source`` into ``dest``.

    Returns the row count per table. Raises ``ValueError`` if ``dest``
    already holds characters and ``overwrite`` is not set.
    """
    existing = await dest.players.count()
    if existing and not overwrite:
        raise ValueError(
            f"the destination already has {existing} character(s); "
            "pass overwrite=True to replace them"
        )

    rows_by_table: dict[Any, list[dict]] = {}
    for table in TABLES:
        result = await source.fetch_all(select(table))
        rows_by_table[table] = [dict(row._mapping) for row in result]

    counts: dict[str, int] = {}
    async with dest.transaction() as tx:
        if existing:
            for table in reversed(TABLES):
                await tx.execute(delete(table))
        for table in TABLES:
            rows = rows_by_table[table]
            counts[table.name] = len(rows)
            if rows:
                await tx.execute(insert(table), rows)

    await _resync_autoincrement(dest)
    return counts


async def _resync_autoincrement(dest: data.Database) -> None:
    """Make the next insert pick up after the copied ids.

    MySQL derives a table's next AUTO_INCREMENT from its contents at
    startup, but an explicit-id insert inside a live server does not always
    advance the counter -- and a second character created with id 1 would
    collide with the one just copied. SQLite reads ``MAX(id)`` on every
    insert and needs nothing.
    """
    if dest.dialect != "mysql":
        return

    from sqlalchemy import text

    for table in TABLES:
        if "id" not in table.c:
            continue
        row = await dest.fetch_one(select(func.max(table.c.id)))
        next_id = (row[0] or 0) + 1
        await dest.execute(text(f"ALTER TABLE `{table.name}` AUTO_INCREMENT = {next_id}"))


async def migrate(
    source_url: str, dest_url: str, *, overwrite: bool = False
) -> dict[str, int]:
    """Open both databases, copy, and close them."""
    source = await data.connect(source_url)
    dest = await data.connect(dest_url)
    try:
        return await copy_realm(source, dest, overwrite=overwrite)
    finally:
        await source.dispose()
        await dest.dispose()
