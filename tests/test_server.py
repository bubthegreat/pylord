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

from pylord import data
from pylord.e2e import (
    LordClient,
    edit_player,
    running_server,
    wait_offline,
)
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
        # health_port 0: these start many servers at once, and a
        # fixed port would collide. See tests/test_health.py.
        "server": {
            "host": "127.0.0.1", "port": 0, "db": str(db_path),
            "health_port": 0,
        },
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


async def _wait_until_player(database, name, timeout=5.0):
    """The server writes the row as it finishes the signup dance."""
    async def _present():
        while await database.players.get_by_name(name) is None:
            await asyncio.sleep(0.05)

    await asyncio.wait_for(_present(), timeout)


async def _wait_until_offline(database, name, timeout=5.0):
    async def _offline():
        while (await database.players.get_by_name(name)).online:
            await asyncio.sleep(0.05)

    await asyncio.wait_for(_offline(), timeout)


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

        database = await data.connect(str(db_path))
        try:
            await _wait_until_player(database, "Zaphod")
            player = await database.players.get_by_name("Zaphod")
            assert player is not None
            assert player.gender == "M"
            assert player.class_type == 1  # K -> Death Knight / warrior
            await _wait_until_offline(database, "Zaphod")
        finally:
            await database.dispose()
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

        database = await data.connect(str(db_path))
        try:
            await _wait_until_player(database, "Trillian")
            player = await database.players.get_by_name("Trillian")
            assert player.forest_fights == 20
            assert player.player_fights == 7
        finally:
            await database.dispose()
    finally:
        server.close()
        await server.wait_closed()


async def test_wrong_password_three_times_disconnects(tmp_path):
    server, port, db_path = await _start_test_server(tmp_path)
    try:
        setup_db = await data.connect(str(db_path))
        await setup_db.players.create("Marvin", "correcthorse", "M")
        await setup_db.dispose()

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

        database = await data.connect(str(db_path))
        try:
            player = await database.players.get_by_name("Marvin")
            assert player is not None
            assert player.online == 0  # never logged in successfully
        finally:
            await database.dispose()
    finally:
        server.close()
        await server.wait_closed()


# --- Name rules, first-day skill uses, quest-over gate, inn resume --------


async def test_reserved_name_is_refused_at_creation(tmp_path):
    """reference/lord.js:4766-4834 (check_name)."""
    async with running_server(tmp_path) as (port, _db_path):
        client = await LordClient.connect("127.0.0.1", port)
        try:
            await client.expect("warrior?")
            client.line("Turgon")
            refused = await client.expect("warrior?")
            assert "Turgon has muscles" in refused
        finally:
            client.close()


async def test_short_name_is_refused_at_creation(tmp_path):
    """reference/lord.js:6092-6096."""
    async with running_server(tmp_path) as (port, _db_path):
        client = await LordClient.connect("127.0.0.1", port)
        try:
            await client.expect("warrior?")
            client.line("Al")
            refused = await client.expect("warrior?")
            assert "Try a longer name" in refused
        finally:
            client.close()


async def test_new_character_can_use_a_skill_attack_on_day_one(tmp_path):
    """Today's maintenance pass has already run by the time a character is
    created, so creation has to grant the daily use points itself
    (reference/lord.js's wake_up() always runs for a brand-new player)."""
    async with running_server(tmp_path) as (port, db_path):
        client = await LordClient.connect("127.0.0.1", port)
        try:
            await client.create_character("Fresh", "pw")
        finally:
            client.close()
        player = await wait_offline(db_path, "Fresh")
        assert player.skill_uses >= 1


async def test_quest_over_redirects_every_login_to_pay_homage(tmp_path):
    """reference/lord.js:17293-17324 (check_gameover)."""
    async with running_server(tmp_path) as (port, db_path):
        client = await LordClient.connect("127.0.0.1", port)
        try:
            await client.create_character("Winner", "pw")
        finally:
            client.close()
        winner = await wait_offline(db_path, "Winner")

        database = await data.connect(str(db_path))
        try:
            async with database.transaction() as tx:
                await tx.state.set("won_by", winner.id)
        finally:
            await database.dispose()

        client = await LordClient.connect("127.0.0.1", port)
        try:
            await client.expect("warrior?")
            client.line("Winner")
            await client.expect("Password:")
            client.line("pw")
            homage = await client.expect("MORE")
            assert "PAY HOMAGE" in homage
            assert "Winner" in homage
        finally:
            client.close()


async def test_a_player_who_rented_a_room_wakes_up_in_the_inn(tmp_path):
    """reference/lord.js:16925-16930."""
    async with running_server(tmp_path) as (port, db_path):
        client = await LordClient.connect("127.0.0.1", port)
        try:
            await client.create_character("Sleeper", "pw")
        finally:
            client.close()
        await edit_player(db_path, "Sleeper", at_inn=1)

        client = await LordClient.connect("127.0.0.1", port)
        try:
            await client.expect("warrior?")
            client.line("Sleeper")
            await client.expect("Password:")
            client.line("pw")
            screen = await client.expect("eturn\n")
            assert "Red Dragon Inn" in screen
        finally:
            client.close()
        assert (await wait_offline(db_path, "Sleeper")).at_inn == 0


async def test_startup_clears_stale_online_flags(tmp_path):
    """A pod restart mid-session leaves online=1 behind, which locks the
    player out of their own character and inflates "people on now"."""
    db_path = tmp_path / "lord.db"
    database = await data.connect(str(db_path))
    repo = database.players
    ghost = await repo.create("Ghost", "pw", "M")
    ghost.online = 1
    await repo.save(ghost)
    await database.dispose()

    server = await start(
        {# health_port 0: these start many servers at once, and a
        # fixed port would collide. See tests/test_health.py.
        "server": {
            "host": "127.0.0.1", "port": 0, "db": str(db_path),
            "health_port": 0,
        }, "game": {}}
    )
    try:
        database = await data.connect(str(db_path))
        try:
            assert (await database.players.get_by_name("Ghost")).online == 0
        finally:
            await database.dispose()
    finally:
        server.close()
        await server.wait_closed()


async def test_game_statistics_separates_enrolled_from_online(tmp_path):
    """reference/lord.js:16269-16275 counts every registered warrior and
    calls them "people playing"; the screen now says which is which."""
    async with running_server(tmp_path) as (port, db_path):
        first = await LordClient.connect("127.0.0.1", port)
        try:
            await first.create_character("Counter", "pw")
        finally:
            first.close()
        await wait_offline(db_path, "Counter")

        client = await LordClient.connect("127.0.0.1", port)
        try:
            await client.create_character("Watcher", "pw")
            client.key("1")
            stats = await client.expect("MORE")
            assert "2 warriors in the realm" in stats, stats
            assert "1 is playing right now" in stats, stats
        finally:
            client.close()
