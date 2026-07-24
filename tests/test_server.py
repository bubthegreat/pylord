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


async def _start_test_server(tmp_path, game_config=None):
    db_path = tmp_path / "lord.db"
    config = {
        "server": {"host": "127.0.0.1", "port": 0, "db": str(db_path)},
        "game": game_config or {},
    }
    server = await start(config)
    port = server.sockets[0].getsockname()[1]
    return server, port, db_path


async def _wait_until(predicate, timeout: float = 2.0, interval: float = 0.05) -> None:
    async def _poll() -> None:
        while not predicate():
            await asyncio.sleep(interval)

    await asyncio.wait_for(_poll(), timeout)


async def test_server_negotiates_character_at_a_time_mode(tmp_path):
    """The server must open every connection with IAC WILL ECHO + IAC WILL
    SGA so real telnet clients drop out of line mode. Without this, a
    client buffers a whole line locally and sends it only on Enter --
    readkey() then eats the first character and the leftover CR hits the
    next menu() as an invalid key, silently re-printing its prompt (the
    doubled "Your choice? Your choice?"), and any hotkey+argument screen
    (e.g. buying in the weapons shop) only works when typed as one line
    like "b 2". Probed with a raw asyncio socket, NOT a telnetlib3 client,
    because the client library performs its own negotiation and would mask
    what the server actually sent."""
    server, port, _db_path = await _start_test_server(tmp_path)
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        try:
            # Refuse the server's DO TTYPE probe so it stops waiting for
            # negotiation (telnetlib3 holds the shell back for
            # connect_maxwait, ~4s, when the peer never answers).
            writer.write(b"\xff\xfc\x18")  # IAC WONT TTYPE
            await writer.drain()
            data = b""
            async def _collect() -> None:
                nonlocal data
                while not (b"\xff\xfb\x01" in data and b"\xff\xfb\x03" in data):
                    chunk = await reader.read(4096)
                    if chunk == b"":
                        raise AssertionError(
                            f"connection closed; bytes so far: {data.hex()}"
                        )
                    data += chunk

            await asyncio.wait_for(_collect(), 2.0)  # WILL ECHO + WILL SGA
        finally:
            writer.close()
    finally:
        server.close()
        await server.wait_closed()


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


async def test_new_character_gets_configured_daily_fight_counts(tmp_path):
    """Task 14 config audit: a brand-new character created *after* today's
    daily.maintenance() batch pass has already run (the common case -- see
    handle_connection's docstring) must still get configured
    forest_fights_per_day/player_fights_per_day, not the DB schema's
    literal 15/3 defaults (models.py's Player.forest_fights/player_fights),
    which only match lord.js's *own* stock defaults
    (reference/lord.js:1857/1856) coincidentally."""
    server, port, db_path = await _start_test_server(
        tmp_path,
        game_config={"forest_fights_per_day": 20, "player_fights_per_day": 7},
    )
    try:
        reader, writer = await telnetlib3.open_connection(
            host="127.0.0.1", port=port, **_CONNECT_KWARGS
        )
        recv = Recv(reader)

        await recv.until("warrior?")
        writer.write("Trillian\r\n")

        await recv.until("] : ")
        writer.write("Y")

        await recv.until("gender?")
        writer.write("F")

        await recv.until("Pick one")
        writer.write("K")

        await recv.until("Password:")
        writer.write("hunter2\r\n")

        await recv.until("Confirm password:")
        writer.write("hunter2\r\n")

        await recv.until("Town Square")
        writer.close()

        conn = db.connect(str(db_path))
        try:
            repo = PlayerRepo(conn)
            await _wait_until(lambda: repo.get_by_name("Trillian") is not None)
            player = repo.get_by_name("Trillian")
            assert player.forest_fights == 20
            assert player.player_fights == 7
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
