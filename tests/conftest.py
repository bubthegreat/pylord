"""Test-wide fixtures, and the switch that runs the suite on real MySQL.

The suite asks for ``:memory:`` databases everywhere, which is SQLite. That
is the right default -- it is instant and needs nothing installed. But the
homelab runs MySQL, and the two disagree about enough (upsert syntax,
collations, reserved words, what a ``VARCHAR`` needs a length for) that
"the tests pass" on SQLite alone does not mean the game works in
production.

Set ``PYLORD_TEST_DB_URL`` to a MySQL URL and the same 500-odd tests run
against that server instead. CI runs them both ways.

**How the redirect works.** A small pool of databases is created once for
the whole run, and each ``:memory:`` request inside a test takes the next
one, emptied first. Truncation (not ``DELETE``) because it also resets
``AUTO_INCREMENT``, and a fair number of tests assume the first character
created is id 1 -- IGM store keys like ``"bouts:1"`` are written that way.

A pool, rather than one shared database, because ``:memory:`` really does
mean a *private* realm under SQLite's ``StaticPool``, and some tests need
two at once -- ``pylord/migrate.py``'s copy one realm into another, and
collapsing both onto one database made them pass while testing nothing.
A pool, rather than creating a database per connection, because
``CREATE DATABASE``/``DROP DATABASE`` is the most expensive statement pair
here and a truncate says the same thing.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

from pylord import data, schema

_TEST_DB_URL = os.environ.get("PYLORD_TEST_DB_URL", "")

#: The session's databases, created once by ``_create_test_database``.
#:
#: More than one, because ``:memory:`` means a *private* realm under
#: SQLite's ``StaticPool`` and some tests genuinely need two at once --
#: ``pylord/migrate.py``'s, most obviously, which copy one realm into
#: another. Each ``:memory:`` request inside a test takes the next of
#: these, emptied; a pool means that costs a truncate rather than a
#: CREATE DATABASE.
_DB_COUNT = 4
_DB_NAMES = [f"pylord_test_{i}" for i in range(_DB_COUNT)]


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
def test_db_urls() -> list[str]:
    """The pool of realm URLs, or [] when running on SQLite."""
    if not _TEST_DB_URL:
        return []
    base = make_url(_TEST_DB_URL)
    return [_url(base.set(database=name)) for name in _DB_NAMES]


@pytest.fixture(scope="session", autouse=True)
async def _create_test_databases(test_db_urls):
    """Build the pool once for the whole run."""
    if not test_db_urls:
        yield
        return

    server = _url(make_url(_TEST_DB_URL).set(database=""))
    statements = []
    for name in _DB_NAMES:
        statements += [
            f"DROP DATABASE IF EXISTS `{name}`",
            f"CREATE DATABASE `{name}`",
        ]
    await _exec(server, *statements)

    # Build the tables now, so the per-test reset has something to
    # truncate before any test has connected.
    for url in test_db_urls:
        db = await data.connect(url)
        await db.dispose()
    try:
        yield
    finally:
        await _exec(server, *[f"DROP DATABASE IF EXISTS `{n}`" for n in _DB_NAMES])


def _truncate_all() -> list[str]:
    """Empty every table and reset its id counter.

    ``TRUNCATE`` rather than ``DELETE`` because it also resets
    ``AUTO_INCREMENT``, and a fair number of tests assume the first
    character created is id 1 -- IGM store keys like ``"bouts:1"`` are
    written that way.
    """
    return [f"TRUNCATE TABLE `{t.name}`" for t in schema.metadata.sorted_tables]


@pytest.fixture(autouse=True)
async def _redirect_and_reset(test_db_urls, monkeypatch):
    """Point ``connect()`` at the pool, keeping SQLite's own meanings.

    The two forms the suite uses mean different things, and the difference
    matters -- a test may play two whole sessions, or copy one realm into
    another, each expecting its own database:

    * ``":memory:"`` is a *fresh, private* realm: each call takes the next
      database from the pool, emptied first.
    * a file path is *the same* realm reopened -- how the server, CLI and
      schema tests inspect what the code under test just wrote. The first
      such path in a test claims a database; asking again for the same
      path returns it untouched.
    """
    if not test_db_urls:
        yield
        return

    real_connect = data.connect
    taken = 0
    by_path: dict[str, str] = {}

    async def next_url() -> str:
        nonlocal taken
        if taken >= len(test_db_urls):
            raise RuntimeError(
                f"this test opened more than {len(test_db_urls)} databases; "
                "raise _DB_COUNT in tests/conftest.py"
            )
        url = test_db_urls[taken]
        taken += 1
        await _exec(url, *_truncate_all())
        return url

    async def connect(url: str, **kwargs):
        if url == ":memory:":
            url = await next_url()
        elif not url.startswith(("sqlite", "mysql", "postgresql")):
            if url not in by_path:
                by_path[url] = await next_url()
            url = by_path[url]
        return await real_connect(url, **kwargs)

    monkeypatch.setattr(data, "connect", connect)
    try:
        yield
    finally:
        for url in test_db_urls[:taken]:
            await _exec(url, *_truncate_all())


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
