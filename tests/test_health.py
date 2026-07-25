"""The health endpoint Kubernetes probes.

Two things worth pinning: that readiness actually reflects the database
(the TCP probe it replaces said "ready" whatever state the database was
in), and that liveness deliberately does *not* -- a liveness probe failing
on a database blip would restart a pod mid-session for everyone on it.
"""

from __future__ import annotations

import asyncio

from pylord import data, health


async def _request(port: int, path: str) -> tuple[int, str]:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
    await writer.drain()
    raw = (await asyncio.wait_for(reader.read(), timeout=5.0)).decode()
    writer.close()
    status = int(raw.split()[1])
    body = raw.split("\r\n\r\n", 1)[1].strip()
    return status, body


async def _serve(database):
    server = await health.start(database, host="127.0.0.1", port=0)
    return server, server.sockets[0].getsockname()[1]


async def test_liveness_and_readiness_answer_when_all_is_well():
    database = await data.connect(":memory:")
    server, port = await _serve(database)
    try:
        assert await _request(port, "/healthz") == (200, "alive")
        assert await _request(port, "/readyz") == (200, "ready")
    finally:
        server.close()
        await server.wait_closed()


async def test_readiness_fails_when_the_database_is_unreachable():
    """A pod that cannot reach the realm's database should leave the
    Service rather than accept players it cannot save.

    Pointed at a closed port rather than a disposed SQLite pool: disposing
    one just makes SQLAlchemy open a fresh connection to the same file, so
    that would have tested nothing.
    """
    unreachable = data.Database(
        data.create_engine("mysql+aiomysql://nobody:nobody@127.0.0.1:1/nothing")
    )
    server, port = await _serve(unreachable)
    try:
        status, body = await _request(port, "/readyz")
        assert status == 503
        assert "unreachable" in body
        # ... and liveness still answers, so the pod is not restarted for it.
        assert await _request(port, "/healthz") == (200, "alive")
    finally:
        server.close()
        await server.wait_closed()
        await unreachable.dispose()


async def test_anything_else_is_a_404():
    database = await data.connect(":memory:")
    server, port = await _serve(database)
    try:
        status, _body = await _request(port, "/")
        assert status == 404
    finally:
        server.close()
        await server.wait_closed()
