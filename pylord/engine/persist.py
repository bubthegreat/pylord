"""Shared "raw ``UPDATE``, inside the caller's own transaction" player
persistence.

Complements :meth:`pylord.models.PlayerRepo.save` (which self-commits via
its own ``with conn:``) for call sites that need the player row's UPDATE to
be part of a *larger*, caller-managed transaction alongside other writes
(mail read-flags, IGM store/news flushes, ...) -- so a crash between
"mutate the in-memory player" and "persist it" can never silently discard
the mutation while some other, already-committed write (a mail row's
``read`` flag, an IGM's news/store flush) makes it look like the mutation
already happened.

Extracted (post-review, Task 13a) from ``other_places.py``'s original
``_save_player_raw``, which is now just a thin wrapper -- see
``pylord/engine/scenes/mail.py``'s ``apply_unread_mail`` for the second
call site this was written for.
"""

from __future__ import annotations

import sqlite3
from dataclasses import fields

from pylord.models import Player

# Every mutable player column (everything but the two immutable identity
# fields) -- mirrors PlayerRepo.save()'s own column set.
_SAVE_COLS = [f.name for f in fields(Player) if f.name not in ("id", "name")]


def save_player_raw(conn: sqlite3.Connection, player: Player) -> None:
    """``UPDATE`` every mutable column of ``player`` via a raw ``execute``
    -- no implicit commit, so callers bundle this into their own
    transaction (a ``with conn:`` block, or manual ``commit()``/
    ``rollback()``)."""
    set_clause = ", ".join(f"{c} = :{c}" for c in _SAVE_COLS)
    params = {c: getattr(player, c) for c in _SAVE_COLS}
    params["id"] = player.id
    conn.execute(f"UPDATE players SET {set_clause} WHERE id = :id", params)
