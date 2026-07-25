"""A tiny HTTP health endpoint, for Kubernetes to probe.

The probes used to open a TCP connection to the telnet port every few
seconds. That works, but each one is a real session as far as the game is
concerned: it negotiates, logs "Connection from <Peer ...>", and logs the
close a moment later. The result was a log full of connections that were
never players, which buries the ones that were.

So the probes get their own port and their own answers:

* ``/healthz`` -- **liveness**. Is this process still running its event
  loop? Deliberately checks nothing else. A liveness probe that fails on a
  database blip would restart a pod that was about to recover, mid-session,
  for everybody.
* ``/readyz`` -- **readiness**. Can the realm's database actually be
  reached? A pod that cannot reach MySQL should be taken out of the Service
  rather than accepting players into a game that cannot save them. This is
  new: a TCP probe against the telnet port said "ready" as long as the
  listener was up, whatever state the database was in.

Written on ``asyncio.start_server`` rather than a web framework -- the
whole protocol here is "read a request line, write a status" and the game
has no other HTTP surface.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

if TYPE_CHECKING:
    from pylord.data import Database

logger = logging.getLogger(__name__)

_RESPONSE = (
    "HTTP/1.1 {status}\r\n"
    "Content-Type: text/plain; charset=utf-8\r\n"
    "Content-Length: {length}\r\n"
    "Connection: close\r\n"
    "\r\n"
    "{body}"
)


def _http(status: str, body: str) -> bytes:
    payload = body + "\n"
    return _RESPONSE.format(
        status=status, length=len(payload.encode()), body=payload
    ).encode()


async def _database_reachable(database: Database) -> bool:
    try:
        await asyncio.wait_for(database.fetch_one(text("SELECT 1")), timeout=5.0)
    except Exception:
        logger.warning("readiness: database unreachable", exc_info=True)
        return False
    return True


async def start(database: Database, host: str = "0.0.0.0", port: int = 8080) -> Any:
    """Start the health server and return it."""

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            try:
                request = await asyncio.wait_for(reader.readline(), timeout=5.0)
            except TimeoutError:
                return
            parts = request.decode("latin-1", "replace").split()
            path = parts[1] if len(parts) > 1 else "/"

            if path.startswith("/readyz"):
                ok = await _database_reachable(database)
                writer.write(
                    _http("200 OK", "ready")
                    if ok
                    else _http("503 Service Unavailable", "database unreachable")
                )
            elif path.startswith(("/healthz", "/livez")):
                writer.write(_http("200 OK", "alive"))
            else:
                writer.write(_http("404 Not Found", "try /healthz or /readyz"))

            await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            writer.close()

    server = await asyncio.start_server(handle, host=host, port=port)
    logger.info("health endpoint listening on %s:%s", host, port)
    return server
