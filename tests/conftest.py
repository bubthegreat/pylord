"""Test-wide fixtures, and the switch that runs the suite on real MySQL.

The suite asks for ``:memory:`` databases everywhere, which is SQLite. That
is the right default -- it is instant and needs nothing installed. But the
homelab runs MySQL, and the two disagree about enough (upsert syntax,
collations, reserved words, what a ``VARCHAR`` needs a length for) that
"the tests pass" on SQLite alone does not mean the game works in
production.

Set ``PYLORD_TEST_DB_URL`` to a MySQL URL and the same 500-odd tests run
against that server instead. CI runs them both ways.

**How the redirect works.** One database is created for the whole session
and every ``connect()`` hands back a handle on it; between tests its tables
are truncated. Truncation (not ``DELETE``) because it also resets
``AUTO_INCREMENT``, and a fair number of tests assume the first character
created is id 1 -- IGM store keys like ``"bouts:1"`` are written that way.

An earlier version gave every ``connect()`` call its own freshly created
database, on the theory that ``:memory:`` means a private realm under
SQLite's ``StaticPool`` and two calls should not see each other. True, but
nothing needs it: of the nine tests that open a second database, every one
is *reopening the same realm* to inspect it. That fidelity cost a
``CREATE DATABASE`` and a ``DROP DATABASE`` per connection, which is the
most expensive statement pair in the file, and it made the MySQL run take
minutes per test file.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

from pylord import data, schema

_TEST_DB_URL = os.environ.get("PYLORD_TEST_DB_URL", "")

#: The session's database, created once by ``_test_database`` below.
_DB_NAME = "pylord_test"


def pytest_report_header(config):
    return f"pylord database: {_TEST_DB_URL or 'sqlite (in-memory)'}"


def _url(url) -> str:
    """Render a URL *with* its password.

    ``str(URL)`` masks it as ``***`` -- good for logs, silently unusable
    for connecting.
    """
    return url.render_as_string(hide_password=False)


async def _exec(url: str, *statements: str) -> None:
    engine = data.create_engine(url)
    try:
        async with engine.begin() as conn:
            for statement in statements:
                await conn.execute(text(statement))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def test_db_url() -> str:
    """The URL every ``connect()`` is redirected to, or "" for SQLite."""
    if not _TEST_DB_URL:
        return ""
    return _url(make_url(_TEST_DB_URL).set(database=_DB_NAME))


@pytest.fixture(scope="session", autouse=True)
async def _create_test_database(test_db_url):
    """One database for the whole run."""
    if not test_db_url:
        yield
        return

    server = _url(make_url(_TEST_DB_URL).set(database=""))
    await _exec(
        server,
        f"DROP DATABASE IF EXISTS `{_DB_NAME}`",
        f"CREATE DATABASE `{_DB_NAME}`",
    )
    # Build the tables now, so the per-test reset has something to
    # truncate before any test has connected.
    db = await data.connect(test_db_url)
    await db.dispose()
    try:
        yield
    finally:
        await _exec(server, f"DROP DATABASE IF EXISTS `{_DB_NAME}`")


def _truncate_all() -> list[str]:
    """Empty every table and reset its id counter.

    ``TRUNCATE`` rather than ``DELETE`` because it also resets
    ``AUTO_INCREMENT``, and a fair number of tests assume the first
    character created is id 1 -- IGM store keys like ``"bouts:1"`` are
    written that way.
    """
    return [f"TRUNCATE TABLE `{t.name}`" for t in schema.metadata.sorted_tables]


@pytest.fixture(autouse=True)
async def _redirect_and_reset(test_db_url, monkeypatch):
    """Point ``connect()`` at the session database, with SQLite's meaning.

    The two forms the suite uses mean different things, and the difference
    matters -- a test may play two whole sessions, each expecting its own
    empty realm:

    * ``":memory:"`` is a *fresh, private* realm. Under SQLite's
      ``StaticPool`` each such call really is a separate database, so this
      empties the tables before handing one back.
    * a file path is *the same* realm reopened -- how the server, CLI and
      schema tests inspect what the code under test just wrote. Handed
      back untouched.
    """
    if not test_db_url:
        yield
        return

    real_connect = data.connect

    async def connect(url: str, **kwargs):
        if url == ":memory:":
            await _exec(test_db_url, *_truncate_all())
            url = test_db_url
        elif not url.startswith(("sqlite", "mysql", "postgresql")):
            url = test_db_url  # a file path: the same realm, left as it is
        return await real_connect(url, **kwargs)

    monkeypatch.setattr(data, "connect", connect)
    try:
        yield
    finally:
        await _exec(test_db_url, *_truncate_all())


@pytest.fixture(autouse=True)
async def _close_databases(monkeypatch):
    """Dispose every database a test opened, once it is done.

    Defined after the redirect above so it tears down *first*: pools are
    disposed before the tables they point at are truncated.

    Tests call ``connect()`` freely and rarely close, which costs nothing
    on an in-memory SQLite database. Against a real server each of those
    leaves a live connection pool behind, and a few dozen tests is enough
    to exhaust ``max_connections`` and hang the rest of the run -- which is
    exactly how this was found.
    """
    opened: list[data.Database] = []
    real_connect = data.connect

    async def connect(url: str, **kwargs):
        db = await real_connect(url, **kwargs)
        opened.append(db)
        return db

    monkeypatch.setattr(data, "connect", connect)
    try:
        yield
    finally:
        for db in opened:
            await db.dispose()
