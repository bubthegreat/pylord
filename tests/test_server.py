"""Integration tests for pylord/server.py's telnet login flow.

Drives ``start(config)`` on an ephemeral port with a real ``telnetlib3``
client connection (``telnetlib3.open_connection``) -- this is the first
time ``TelnetIO`` is exercised against a real ``telnetlib3`` reader/writer
pair rather than ``FakeIO`` (see pylord/terminal.py's ``TelnetIO._raw_read``
docstring for two bugs that surfaced doing this and were fixed there).

Every read waits for a specific marker substring with a bounded timeout
(``Recv.until``) rather than sleeping fixed amounts, so a protocol mistake
fails fast instead of hanging the suite.
"""

from __future__ import annotations

import asyncio

import telnetlib3

from pylord import db
from pylord.models import PlayerRepo
from pylord.server import start

_CONNECT_KWARGS = {"connect_minwait": 0.05, "connect_maxwait": 1.0}


class Recv:
    """Accumulates telnet client output and waits for markers.

    Each ``until(marker)`` call consumes everything up to and including the
    first occurrence of ``marker`` from the internal buffer, so calling it
    twice with the same marker correctly waits for a *second* occurrence
    (e.g. the Town Square menu appearing again after a round trip) instead
    of matching the same bytes twice.
    """

    def __init__(self, reader):
        self.reader = reader
        self.buf = ""

    async def until(self, marker: str, timeout: float = 2.0) -> str:
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


async def _start_test_server(tmp_path):
    db_path = tmp_path / "lord.db"
    config = {
        "server": {"host": "127.0.0.1", "port": 0, "db": str(db_path)},
        "game": {},
    }
    server = await start(config)
    port = server.sockets[0].getsockname()[1]
    return server, port, db_path


async def _wait_until(predicate, timeout: float = 2.0, interval: float = 0.05) -> None:
    async def _poll() -> None:
        while not predicate():
            await asyncio.sleep(interval)

    await asyncio.wait_for(_poll(), timeout)


async def test_new_character_creation_view_stats_and_quit(tmp_path):
    server, port, db_path = await _start_test_server(tmp_path)
    try:
        reader, writer = await telnetlib3.open_connection(
            host="127.0.0.1", port=port, **_CONNECT_KWARGS
        )
        recv = Recv(reader)

        await recv.until("warrior?")
        writer.write("Zaphod\r\n")

        await recv.until("] : ")  # name confirmation, e.g. "Zaphod? [Y] : "
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
        writer.write("V")

        await recv.until("Experience")
        await recv.until("MORE")
        writer.write(" ")

        await recv.until("Town Square")
        writer.write("Q")

        writer.close()

        conn = db.connect(str(db_path))
        try:
            repo = PlayerRepo(conn)
            await _wait_until(lambda: repo.get_by_name("Zaphod") is not None)
            player = repo.get_by_name("Zaphod")
            assert player is not None
            assert player.gender == "M"
            assert player.class_type == 1  # K -> Death Knight / warrior
            await _wait_until(lambda: repo.get_by_name("Zaphod").online == 0)
        finally:
            conn.close()
    finally:
        server.close()
        await server.wait_closed()


async def test_wrong_password_three_times_disconnects(tmp_path):
    server, port, db_path = await _start_test_server(tmp_path)
    try:
        setup_conn = db.connect(str(db_path))
        PlayerRepo(setup_conn).create("Marvin", "correcthorse", "M")
        setup_conn.close()

        reader, writer = await telnetlib3.open_connection(
            host="127.0.0.1", port=port, **_CONNECT_KWARGS
        )
        recv = Recv(reader)

        await recv.until("warrior?")
        writer.write("Marvin\r\n")

        await recv.until("Password:")
        writer.write("wrong1\r\n")
        await recv.until("Password:")
        writer.write("wrong2\r\n")
        await recv.until("Password:")
        writer.write("wrong3\r\n")

        await recv.until("Goodbye")

        # The server closes the connection after 3 failed attempts, so the
        # next read must reach EOF rather than block forever.
        eof = await asyncio.wait_for(reader.read(1), 1.0)
        assert eof == ""

        conn = db.connect(str(db_path))
        try:
            player = PlayerRepo(conn).get_by_name("Marvin")
            assert player is not None
            assert player.online == 0  # never logged in successfully
        finally:
            conn.close()
    finally:
        server.close()
        await server.wait_closed()
