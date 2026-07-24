"""End-to-end feature harness, run as a test.

Plays every base feature over a real telnet connection against a real
server and checks each screen -- the same walkthrough a human gets from
``uv run pylord smoke``. See ``pylord/e2e.py`` for the thin client and the
step list.

The single ``test_walkthrough`` case reports *all* failing steps at once
rather than stopping at the first assertion, since a wording change
usually breaks several screens together.
"""

from __future__ import annotations

from pylord.e2e import STEPS, LordClient, run_walkthrough, running_server


async def test_walkthrough(tmp_path):
    results = await run_walkthrough(tmp_path)

    failures = [f"{r.name}: {r.detail}" for r in results if not r.ok]
    assert not failures, "\n".join(failures)
    assert len(results) == len(STEPS), (
        f"walkthrough stopped early after {len(results)} of {len(STEPS)} steps"
    )


async def test_client_reports_what_it_saw_on_a_missing_marker(tmp_path):
    """The harness is only useful if a failure shows the screen. A marker
    that never arrives must raise with the text received so far."""
    async with running_server(tmp_path) as (port, _db_path):
        client = await LordClient.connect("127.0.0.1", port)
        try:
            try:
                await client.expect("no such text anywhere", timeout=1.0)
            except AssertionError as exc:
                assert "--- seen ---" in str(exc)
                assert "warrior" in str(exc)  # the login prompt it did get
            else:
                raise AssertionError("expected a Timeout")
        finally:
            client.close()


async def test_duplicate_login_is_refused(tmp_path):
    """One live session per character (pylord/server.py's online guard)."""
    async with running_server(tmp_path) as (port, _db_path):
        first = await LordClient.connect("127.0.0.1", port)
        second = None
        try:
            await first.create_character("Twin", "pw")
            second = await LordClient.connect("127.0.0.1", port)
            await second.expect("warrior?")
            second.line("Twin")
            await second.expect("Password:")
            second.line("pw")
            await second.expect("already adventuring elsewhere")
        finally:
            first.close()
            if second is not None:
                second.close()
