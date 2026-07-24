"""End-to-end smoke test (Task 21).

One full journey over a real telnet connection against a real server:
create a character, kill a forest monster, visit Barak's House through
the Other Places IGM hub, return to town, and quit -- then assert the
database recorded all of it (player row, gold/exp gains, spent forest
fight, IGM store flush).

Forest combat is driven by an unseeded per-session RNG (the server never
injects one -- see GameCtx in pylord/engine/game.py), so this test cannot
script an exact byte sequence. Instead it:

* creates the character over telnet (exercising the real signup flow),
  logs out, and buffs the row directly in SQLite (huge strength/defense/
  hp) so the eventual fight cannot be lost, then logs back in; and
* drives the forest with a small marker automaton (``Recv.until_any``)
  that reacts to whichever random branch actually happened -- a fight,
  any of the pause-only forest events, the old-man yes/no event, or the
  silent "nothing" event -- looping until one monster is dead.

Marker strings deliberately avoid letters that scenes wrap in color
codes (e.g. the forest menu is matched on "ook for something to kill"
because the leading ``(L)`` renders with ANSI escapes inside it).
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import telnetlib3

from pylord import db
from pylord.models import PlayerRepo
from pylord.server import start

_CONNECT_KWARGS = {"connect_minwait": 0.05, "connect_maxwait": 1.0}
_FOREST_MENU = "ook for something to kill"
_REPO_ROOT = Path(__file__).resolve().parent.parent


class Recv:
    """Accumulates telnet client output and waits for markers.

    Same consume-through-the-marker contract as tests/test_server.py's
    Recv, plus ``until_any`` for points where the server's RNG decides
    which of several outputs comes next.
    """

    def __init__(self, reader):
        self.reader = reader
        self.buf = ""

    async def until(self, marker: str, timeout: float = 5.0) -> str:
        async def _pump() -> None:
            while marker not in self.buf:
                chunk = await self.reader.read(4096)
                if chunk == "":
                    raise AssertionError(
                        f"connection closed waiting for {marker!r}; "
                        f"buf so far: {self.buf!r}"
                    )
                self.buf += chunk

        await asyncio.wait_for(_pump(), timeout)
        idx = self.buf.index(marker) + len(marker)
        seen, self.buf = self.buf[:idx], self.buf[idx:]
        return seen

    async def until_any(self, markers: list[str], timeout: float = 5.0) -> str:
        """Wait until any marker appears; consume through the *earliest*
        occurrence in the stream and return which marker matched."""

        async def _pump() -> tuple[int, str]:
            while True:
                hits = [(self.buf.index(m), m) for m in markers if m in self.buf]
                if hits:
                    return min(hits)
                chunk = await self.reader.read(4096)
                if chunk == "":
                    raise AssertionError(
                        f"connection closed waiting for any of {markers!r}; "
                        f"buf so far: {self.buf!r}"
                    )
                self.buf += chunk

        idx, marker = await asyncio.wait_for(_pump(), timeout)
        self.buf = self.buf[idx + len(marker):]
        return marker


async def _fight_one_monster(recv: Recv, writer) -> None:
    """Press (L)ook until a monster shows up, then attack it to death.

    Handles every random pre-fight branch: pause-only events, the
    old-man yes/no event, and the silent no-op event. The player is
    buffed beforehand, so losing is impossible; 60 presses bounds the
    loop far above any plausible run of non-fight events."""
    for _ in range(60):
        writer.write("L")
        branch = await recv.until_any(
            [
                "You have encountered",
                "Event In The Forest",
                "YOU ARE NOTICED",
                _FOREST_MENU,
            ]
        )
        if branch == "You have encountered":
            while True:
                turn = await recv.until_any(["You have killed", "Your command"])
                if turn == "Your command":
                    writer.write("A")
                    continue
                await recv.until("MORE")
                writer.write(" ")
                return
        if branch == "Event In The Forest":
            sub = await recv.until_any(["take the old man", "MORE"])
            if sub == "take the old man":
                writer.write("N")
                await recv.until("MORE")
            writer.write(" ")
            await recv.until(_FOREST_MENU)
        elif branch == "YOU ARE NOTICED":
            await recv.until("MORE")
            writer.write(" ")
            await recv.until(_FOREST_MENU)
        # else: silent "nothing" event -- the menu reprint we just
        # consumed IS the next prompt; loop around and press L again.
    raise AssertionError("no monster encountered in 60 (L)ook presses")


async def test_full_session_smoke(tmp_path):
    shutil.copytree(
        _REPO_ROOT / "igms" / "baraks_house", tmp_path / "igms" / "baraks_house"
    )
    db_path = tmp_path / "lord.db"
    config = {
        "server": {"host": "127.0.0.1", "port": 0, "db": str(db_path)},
        "game": {},
        "igms": {"baraks_house": True},
    }
    server = await start(config)
    port = server.sockets[0].getsockname()[1]
    try:
        # --- Leg 1: create the character over telnet, then quit. ---
        reader, writer = await telnetlib3.open_connection(
            host="127.0.0.1", port=port, **_CONNECT_KWARGS
        )
        recv = Recv(reader)
        await recv.until("warrior?")
        writer.write("Smoke\r\n")
        await recv.until("] : ")
        writer.write("Y")
        await recv.until("gender?")
        writer.write("M")
        await recv.until("Pick one")
        writer.write("K")
        await recv.until("Password:")
        writer.write("hunter2\r\n")
        await recv.until("Confirm password:")
        writer.write("hunter2\r\n")
        await recv.until("Town Square")
        writer.write("Q")
        writer.close()

        # --- Buff the row directly so the coming fight can't be lost. ---
        conn = db.connect(str(db_path))
        try:
            repo = PlayerRepo(conn)

            async def _offline() -> None:
                while (p := repo.get_by_name("Smoke")) is None or p.online:
                    await asyncio.sleep(0.05)

            await asyncio.wait_for(_offline(), 5.0)
            player = repo.get_by_name("Smoke")
            player.strength = 30_000
            player.defense = 30_000
            player.hp_max = 30_000
            player.hp = 30_000
            repo.save(player)
            gold_before = player.gold
            fights_before = player.forest_fights
        finally:
            conn.close()

        # --- Leg 2: log back in and take the full tour. ---
        reader, writer = await telnetlib3.open_connection(
            host="127.0.0.1", port=port, **_CONNECT_KWARGS
        )
        recv = Recv(reader)
        await recv.until("warrior?")
        writer.write("Smoke\r\n")
        await recv.until("Password:")
        writer.write("hunter2\r\n")
        await recv.until("Town Square")

        writer.write("F")
        await recv.until(_FOREST_MENU)
        await _fight_one_monster(recv, writer)
        await recv.until(_FOREST_MENU)

        writer.write("O")
        await recv.until("Barak's House")
        writer.write("A")
        await recv.until("couch cushions")
        writer.write("S")
        await recv.until("gold!")
        await recv.until("MORE")
        writer.write(" ")
        await recv.until("couch cushions")
        writer.write("L")
        await recv.until("Barak waves")

        await recv.until(_FOREST_MENU)
        writer.write("R")
        await recv.until("Town Square")
        writer.write("Q")
        writer.close()

        # --- Assert the database recorded the whole journey. ---
        conn = db.connect(str(db_path))
        try:
            repo = PlayerRepo(conn)

            async def _logged_off() -> None:
                while repo.get_by_name("Smoke").online:
                    await asyncio.sleep(0.05)

            await asyncio.wait_for(_logged_off(), 5.0)
            player = repo.get_by_name("Smoke")
            assert player.exp > 1  # monster kill credited exp
            assert player.forest_fights == fights_before - 1
            # Couch search alone guarantees +5..50; kill/event gold only adds.
            assert player.gold > gold_before
            row = conn.execute(
                "SELECT k FROM igm_data WHERE igm_key = 'baraks_house'"
            ).fetchone()
            assert row is not None and row[0] == f"couch:{player.id}"
        finally:
            conn.close()
    finally:
        server.close()
        await server.wait_closed()
