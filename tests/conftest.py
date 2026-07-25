"""Test-wide fixtures, and the switch that runs the suite on real MySQL.

The suite asks for ``:memory:`` databases everywhere, which is SQLite. That
is the right default -- it is instant and needs nothing installed. But the
homelab runs MySQL, and the two disagree about enough (upsert syntax,
collations, reserved words, what a ``VARCHAR`` needs a length for) that
"the tests pass" on SQLite alone does not mean the game works in
production.

So: set ``PYLORD_TEST_DB_URL`` to a MySQL URL and every ``:memory:`` request
is redirected to a private, freshly-created database on that server. The
same 500-odd tests then exercise the real dialect, and CI runs them both
ways.

A private database per request, rather than one shared and emptied
in between, because ``:memory:`` means exactly that under SQLite's
``StaticPool``: a test that opens two of them expects two unrelated
realms, right down to both their first characters getting id 1.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

from pylord import data

_TEST_DB_URL = os.environ.get("PYLORD_TEST_DB_URL", "")


def pytest_report_header(config):
    return f"pylord database: {_TEST_DB_URL or 'sqlite (in-memory)'}"


def _url(url) -> str:
    """Render a URL *with* its password.

    ``str(URL)`` masks it as ``***`` -- good for logs, silently unusable
    for connecting.
    """
    return url.render_as_string(hide_password=False)


def _server_url() -> str:
    """``_TEST_DB_URL`` with its database name stripped, for CREATE/DROP."""
    return _url(make_url(_TEST_DB_URL).set(database=""))


async def _run(sql: str) -> None:
    engine = data.create_engine(_server_url())
    try:
        async with engine.begin() as conn:
            await conn.execute(text(sql))
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True)
async def _redirect_in_memory_databases(monkeypatch):
    if not _TEST_DB_URL:
        yield
        return

    base = make_url(_TEST_DB_URL)
    real_connect = data.connect
    created: list[str] = []
    # Named per test, so a leftover database says which test leaked it.
    prefix = os.environ.get("PYTEST_CURRENT_TEST", "t").split("::")[-1]
    prefix = "".join(c if c.isalnum() else "_" for c in prefix)[:40]

    async def connect(url: str, **kwargs):
        if url == ":memory:":
            name = f"lordt_{abs(hash(prefix)) % 10**8}_{len(created)}"
            await _run(f"CREATE DATABASE IF NOT EXISTS `{name}`")
            created.append(name)
            url = _url(base.set(database=name))
        elif url.endswith(".db"):
            # A file path means "the same database reopened", which the
            # per-test database already models.
            name = f"lordt_{abs(hash(prefix + url)) % 10**8}_file"
            await _run(f"CREATE DATABASE IF NOT EXISTS `{name}`")
            if name not in created:
                created.append(name)
            url = _url(base.set(database=name))
        return await real_connect(url, **kwargs)

    monkeypatch.setattr(data, "connect", connect)
    try:
        yield
    finally:
        for name in created:
            await _run(f"DROP DATABASE IF EXISTS `{name}`")
