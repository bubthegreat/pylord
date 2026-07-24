"""A thin telnet client and a scripted feature walkthrough.

This is the end-to-end harness: it starts a real ``pylord`` server on an
ephemeral port, connects over real telnet with ``telnetlib3``, plays
through every base feature the way a player would, and checks that each
screen says what it is supposed to say. Nothing here reaches into the
engine -- the only interface used is bytes over a socket, plus SQLite
reads/writes for the setup a player can't do from the keyboard (buffing a
character so a random forest fight can't be lost).

Two front ends share it:

* ``uv run pylord smoke`` -- run it against a throwaway database and print
  a pass/fail line per feature (``--verbose`` also prints every screen
  captured, which is the quickest way to eyeball wording/colour changes).
* ``tests/test_e2e_features.py`` -- the same walkthrough as a pytest, so
  a regression in any base screen fails CI.

``LordClient`` is deliberately small: send keys or lines, wait for a
marker, and keep the text seen so far. Markers should avoid characters
that scenes wrap in colour codes -- e.g. match ``"ook for something to
kill"`` rather than ``"(L)ook ..."``, because the ``(L)`` renders with
ANSI escapes inside it.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
import shutil
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

import telnetlib3

from pylord import db
from pylord.models import PlayerRepo
from pylord.server import start

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_CONNECT_KWARGS = {"connect_minwait": 0.05, "connect_maxwait": 1.0}
_REPO_ROOT = Path(__file__).resolve().parent.parent

FOREST_MENU = "ook for something to kill"
#: Last line of the town menu, matched without the colour-wrapped "(Q)".
TOWN_MENU = "uit to fields"


#: A trailing escape sequence or CR that a read may have cut in half.
_PARTIAL_TAIL_RE = re.compile(r"(\x1b\[?[0-9;]*|\r)$")


def plain(text: str) -> str:
    """Strip ANSI escapes and normalise CRLF, leaving what a player
    actually reads -- which is what markers are written against."""
    return _ANSI_RE.sub("", text).replace("\r\n", "\n")


class Timeout(AssertionError):
    """A marker never arrived. Carries the text seen while waiting."""


class LordClient:
    """One telnet session against a running pylord server."""

    def __init__(self, reader, writer, *, timeout: float = 5.0) -> None:
        self.reader = reader
        self.writer = writer
        self.timeout = timeout
        #: Everything received and not yet consumed, as plain text.
        self.buf = ""
        #: Raw tail held back because a read may have split an escape.
        self._partial = ""
        self.transcript: list[str] = []

    @classmethod
    async def connect(cls, host: str, port: int, **kwargs) -> LordClient:
        reader, writer = await telnetlib3.open_connection(
            host=host, port=port, **{**_CONNECT_KWARGS, **kwargs}
        )
        return cls(reader, writer)

    # -- input ---------------------------------------------------------

    def key(self, ch: str) -> None:
        """Press a single key (what ``TermIO.readkey()`` reads)."""
        self.writer.write(ch)

    def line(self, text: str) -> None:
        """Type a line and press Enter (what ``readline()`` reads)."""
        self.writer.write(f"{text}\r\n")

    def close(self) -> None:
        self.writer.close()

    # -- output --------------------------------------------------------

    async def expect(self, marker: str, timeout: float | None = None) -> str:
        """Wait for ``marker``, consuming the stream through it. Returns
        the text consumed (ANSI stripped)."""
        matched = await self.expect_any([marker], timeout)
        return matched.text

    def _ingest(self, chunk: str) -> None:
        """Normalise a raw read into :attr:`buf`, holding back a tail that
        might be half of an escape sequence or a CRLF."""
        raw = self._partial + chunk
        match = _PARTIAL_TAIL_RE.search(raw)
        if match:
            raw, self._partial = raw[: match.start()], raw[match.start():]
        else:
            self._partial = ""
        self.buf += plain(raw)

    async def expect_any(
        self, markers: list[str], timeout: float | None = None
    ) -> Match:
        """Wait until any of ``markers`` appears; consume through the
        earliest one and report which matched."""

        async def _pump() -> tuple[int, str]:
            while True:
                hits = [(self.buf.index(m), m) for m in markers if m in self.buf]
                if hits:
                    return min(hits)
                chunk = await self.reader.read(4096)
                if chunk == "":
                    raise Timeout(
                        f"connection closed waiting for any of {markers!r}\n"
                        f"--- seen ---\n{self.buf}"
                    )
                self._ingest(chunk)

        try:
            idx, marker = await asyncio.wait_for(
                _pump(), self.timeout if timeout is None else timeout
            )
        except TimeoutError as exc:
            raise Timeout(
                f"timed out waiting for any of {markers!r}\n"
                f"--- seen ---\n{self.buf}"
            ) from exc
        end = idx + len(marker)
        seen, self.buf = self.buf[:end], self.buf[end:]
        self.transcript.append(seen)
        return Match(marker=marker, text=seen)

    # -- common flows --------------------------------------------------

    async def create_character(
        self,
        name: str,
        password: str,
        *,
        gender: str = "M",
        clss: str = "K",
    ) -> str:
        await self.expect("warrior?")
        self.line(name)
        await self.expect("] : ")
        self.key("Y")
        await self.expect("gender?")
        self.key(gender)
        await self.expect("Pick one")
        self.key(clss)
        await self.expect("Password:")
        self.line(password)
        await self.expect("Confirm password:")
        self.line(password)
        return await self.town()

    async def login(self, name: str, password: str) -> str:
        await self.expect("warrior?")
        self.line(name)
        await self.expect("Password:")
        self.line(password)
        return await self.town()

    async def forest(self) -> str:
        """Wait for the Forest menu and its prompt (same leftover-prompt
        reason as :meth:`town`)."""
        screen = await self.expect(FOREST_MENU)
        await self.expect("Your choice")
        return screen

    async def town(self) -> str:
        """Wait for the Town Square menu *and* its prompt, so a later
        ``expect("Your choice")`` can't match this screen's leftovers."""
        screen = await self.expect(TOWN_MENU)
        await self.expect("Your choice")
        return screen

    async def quit(self) -> None:
        self.key("Q")
        self.close()


@dataclass(frozen=True)
class Match:
    marker: str
    text: str


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str = ""
    screens: list[str] = field(default_factory=list)


@asynccontextmanager
async def running_server(work_dir: Path, *, igms: list[str] | None = None):
    """Start a server on an ephemeral port against a fresh database in
    ``work_dir``. Yields ``(port, db_path)``.

    ``igms`` names bundled IGM directories to copy in and enable; the
    loader resolves ``igms/`` next to the database (see
    ``pylord.server.start``), so they are copied there.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    for igm in igms or []:
        target = work_dir / "igms" / igm
        if not target.exists():
            shutil.copytree(_REPO_ROOT / "igms" / igm, target)
    db_path = work_dir / "lord.db"
    config = {
        "server": {"host": "127.0.0.1", "port": 0, "db": str(db_path)},
        "game": {},
        "igms": {igm: True for igm in igms or []},
    }
    server = await start(config)
    try:
        yield server.sockets[0].getsockname()[1], db_path
    finally:
        server.close()
        await server.wait_closed()


async def edit_player(db_path: Path, name: str, **fields) -> None:
    """Apply field changes straight to the database, once the character is
    logged off (the server writes the row on disconnect, so editing while
    a session is live would be overwritten)."""
    conn = db.connect(str(db_path))
    try:
        repo = PlayerRepo(conn)

        async def _offline() -> None:
            while (p := repo.get_by_name(name)) is None or p.online:
                await asyncio.sleep(0.05)

        await asyncio.wait_for(_offline(), 5.0)
        player = repo.get_by_name(name)
        for key, value in fields.items():
            setattr(player, key, value)
        repo.save(player)
    finally:
        conn.close()


async def read_player(db_path: Path, name: str):
    conn = db.connect(str(db_path))
    try:
        return PlayerRepo(conn).get_by_name(name)
    finally:
        conn.close()


# --- the walkthrough ------------------------------------------------------


async def _step_creation(c: LordClient) -> None:
    screen = await c.create_character("Smoke", "hunter2")
    assert "Smoke" in screen or "Town Square" in screen
    # A brand-new warrior carries the record's own starting gear
    # (reference/recorddefs.js:47-51, 136-141).
    c.key("V")
    stats = await c.expect("MORE")
    assert "Stick" in stats, f"stats screen has no weapon line:\n{stats}"
    assert "Coat" in stats, f"stats screen has no armour line:\n{stats}"
    c.key(" ")
    await c.town()


_WEAPON_PROMPT = "(B,S,R)"
_ARMOR_PROMPT = "(B,S,R)"


async def _step_weapons_shop(c: LordClient) -> None:
    c.key("K")
    listing = await c.expect(_WEAPON_PROMPT)
    assert "King Arthur" in listing, f"not the weapon shop:\n{listing}"
    assert "Death Sword" in listing, f"weapon list is short:\n{listing}"
    c.key("S")  # sell the starting Stick back
    sale = await c.expect("Agreed?")
    assert "Stick" in sale, f"selling something other than the Stick:\n{sale}"
    c.key("Y")
    await c.expect("MORE")
    c.key(" ")
    await c.expect(_WEAPON_PROMPT)
    c.key("B")
    await c.expect("Number Of Weapon")
    c.line("1")
    offer = await c.expect("strength points")
    assert "FAVORITE" in offer, f"no buy offer:\n{offer}"
    c.key("Y")
    bought = await c.expect("MORE")
    assert "takes your gold" in bought or "Great" in bought, bought
    c.key(" ")
    await c.expect(_WEAPON_PROMPT)
    c.key("R")
    await c.town()


async def _step_armor_shop(c: LordClient) -> None:
    c.key("A")
    listing = await c.expect(_ARMOR_PROMPT)
    assert "Abdul" in listing, f"not the armour shop:\n{listing}"
    assert "Coat" in listing, f"armour list is short:\n{listing}"
    c.key("R")
    await c.town()


async def _step_bank(c: LordClient) -> None:
    c.key("Y")
    await c.expect("The Bank")
    c.key("D")
    await c.expect("deposit")
    c.line("100")
    balances = await c.expect("The Bank")
    assert "Gold In Bank" in balances, balances
    c.key("W")
    await c.expect("withdraw")
    c.line("100")
    await c.expect("The Bank")
    c.key("R")
    await c.town()


async def _step_healer(c: LordClient) -> None:
    """An unwounded warrior is turned away ("You look fine to us!",
    reference/lord.js:10903); a wounded one gets the priced menu."""
    c.key("H")
    branch = await c.expect_any(["look fine to us", "(H,C,R)"])
    assert "Healers" in branch.text, f"not the healers:\n{branch.text}"
    if branch.marker == "look fine to us":
        await c.expect("MORE")
        c.key(" ")
    else:
        assert "it costs" in branch.text, branch.text
        c.key("R")
    await c.town()


async def _step_training(c: LordClient) -> None:
    c.key("T")
    screen = await c.expect("(Q,A,R)")
    assert "Halder" in screen, f"wrong master for level 1:\n{screen}"
    c.key("Q")  # question the master
    asked = await c.expect("MORE")
    assert "experience" in asked.lower(), asked
    c.key(" ")
    await c.expect("(Q,A,R)")
    c.key("R")
    await c.town()


async def _step_inn(c: LordClient) -> None:
    c.key("I")
    # The menu prints "(R)eturn" with colour codes inside the parens.
    screen = await c.expect("eturn\n")
    assert "Red Dragon Inn" in screen, f"not the inn:\n{screen}"
    c.key("R")
    await c.town()


async def _step_listings(c: LordClient) -> None:
    c.key("L")
    rankings = await c.expect("eturn : ")
    assert "Player Rankings" in rankings, rankings
    assert "Smoke" in rankings, f"the player is missing from the rankings:\n{rankings}"
    c.key("R")
    await c.town()

    c.key("D")
    news = await c.expect("[C] : ")
    assert "Daily Happenings" in news, news
    c.key("C")
    await c.town()

    c.key("C")
    conj = await c.expect("MORE")
    assert "CONJUGALITY LIST" in conj, conj
    c.key(" ")
    await c.town()


async def _step_mail(c: LordClient) -> None:
    c.key("W")
    screen = await c.expect("NAME: ")
    assert "PARTIAL" in screen, f"not the mail recipient prompt:\n{screen}"
    c.line("")  # a blank name aborts
    aborted = await c.expect("MORE")
    assert "No matching names found" in aborted, aborted
    c.key(" ")
    await c.town()


async def _step_forest_fight(c: LordClient) -> None:
    """(L)ook until a monster appears, then attack it to death. The
    character is buffed beforehand, so the fight cannot be lost; the loop
    reacts to whichever random branch actually happened."""
    c.key("F")
    await c.expect(FOREST_MENU)
    for _ in range(60):
        c.key("L")
        branch = await c.expect_any(
            ["You have encountered", "Event In The Forest", "YOU ARE NOTICED", FOREST_MENU]
        )
        if branch.marker == "You have encountered":
            while True:
                turn = await c.expect_any(["You have killed", "Your command"])
                if turn.marker == "Your command":
                    c.key("A")
                    continue
                await c.expect("MORE")
                c.key(" ")
                await c.forest()
                c.key("R")
                await c.town()
                return
        if branch.marker == "Event In The Forest":
            sub = await c.expect_any(["take the old man", "MORE"])
            if sub.marker == "take the old man":
                c.key("N")
                await c.expect("MORE")
            c.key(" ")
            await c.expect(FOREST_MENU)
        elif branch.marker == "YOU ARE NOTICED":
            await c.expect("MORE")
            c.key(" ")
            await c.expect(FOREST_MENU)
        # else: the silent "nothing" event reprinted the menu -- loop.
    raise AssertionError("no monster encountered in 60 (L)ook presses")


async def _step_other_places(c: LordClient) -> None:
    """The IGM hub, and one full visit to Barak's House."""
    c.key("F")
    await c.forest()
    c.key("O")
    hub = await c.expect("Your choice")
    assert "Other Places" in hub, hub
    assert "Barak's House" in hub, hub
    c.key("A")
    await c.expect("couch cushions")
    c.key("S")
    await c.expect("gold!")
    await c.expect("MORE")
    c.key(" ")
    await c.expect("couch cushions")
    c.key("L")
    await c.expect("Barak waves")
    await c.forest()
    c.key("R")
    await c.town()


#: Every base feature the harness walks, in play order.
STEPS: list[tuple[str, Callable]] = [
    ("character creation + stats screen", _step_creation),
    ("King Arthur's Weapons (buy/sell)", _step_weapons_shop),
    ("Abdul's Armour", _step_armor_shop),
    ("Ye Old Bank (deposit/withdraw)", _step_bank),
    ("Healer's Hut", _step_healer),
    ("Turgon's Warrior Training", _step_training),
    ("The Red Dragon Inn", _step_inn),
    ("List Warriors / News / Conjugality", _step_listings),
    ("Write Mail", _step_mail),
    ("Forest fight", _step_forest_fight),
    ("Other Places (IGM hub)", _step_other_places),
]


async def run_walkthrough(
    work_dir: Path, *, verbose_sink: Callable[[str], None] | None = None
) -> list[StepResult]:
    """Play every base feature over real telnet. Returns one
    :class:`StepResult` per step; never raises for a failed assertion (the
    caller decides what to do with a failure)."""
    results: list[StepResult] = []
    async with running_server(work_dir, igms=["baraks_house"]) as (port, db_path):
        client = await LordClient.connect("127.0.0.1", port)
        try:
            for name, step in STEPS:
                if name == "Forest fight":
                    # Buff the character so a random fight can't be lost.
                    await client.quit()
                    await edit_player(
                        db_path,
                        "Smoke",
                        strength=30_000,
                        defense=30_000,
                        hp_max=30_000,
                        hp=30_000,
                    )
                    client = await LordClient.connect("127.0.0.1", port)
                    await client.login("Smoke", "hunter2")

                mark = len(client.transcript)
                try:
                    await step(client)
                except AssertionError as exc:
                    results.append(
                        StepResult(
                            name=name,
                            ok=False,
                            detail=str(exc).split("\n")[0][:300],
                            screens=client.transcript[mark:],
                        )
                    )
                    break
                results.append(
                    StepResult(name=name, ok=True, screens=client.transcript[mark:])
                )
                if verbose_sink is not None:
                    for screen in client.transcript[mark:]:
                        verbose_sink(screen)
        finally:
            with contextlib.suppress(Exception):
                # Teardown of a possibly-dead socket: nothing useful to do
                # if the session already ended (a step may have quit it).
                await client.quit()
    return results
