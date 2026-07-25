"""Who Violet and Seth Able are married to, realm-wide.

lord.js keeps a singleton ``state`` object shared by every player
(``state.married_to_violet`` / ``state.married_to_seth``,
reference/lord.js:2494-2495). This project has no such table, so the two
NPC marriages live in ``game_state`` key/value rows -- the same place the
game day and the realm's winner are kept.

Distinct from ``player.married_to``, which is a real player-to-player
marriage (see ``pylord/engine/scenes/conjugality.py``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pylord.data import Database

#: Nobody is married to this NPC.
NONE = -1

#: Public so a caller holding only a ``game_state`` snapshot -- an IGM's
#: ``ctx.state`` -- can read the same rows these helpers write.
KEY_VIOLET = "married_to_violet"
KEY_SETH = "married_to_seth"

_KEY_VIOLET = KEY_VIOLET
_KEY_SETH = KEY_SETH


async def _get(db: Database, key: str) -> int:
    return await db.state.get_int(key, NONE)


async def _set(db: Database, key: str, player_id: int) -> None:
    async with db.transaction() as tx:
        await tx.state.set(key, player_id)


async def married_to_violet(db: Database) -> int:
    """Player id currently married to Violet, or ``NONE`` (-1)."""
    return await _get(db, _KEY_VIOLET)


async def set_married_to_violet(db: Database, player_id: int) -> None:
    await _set(db, _KEY_VIOLET, player_id)


async def married_to_seth(db: Database) -> int:
    """Player id currently married to Seth Able, or ``NONE`` (-1)."""
    return await _get(db, _KEY_SETH)


async def set_married_to_seth(db: Database, player_id: int) -> None:
    await _set(db, _KEY_SETH, player_id)
