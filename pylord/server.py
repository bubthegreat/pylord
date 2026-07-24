"""Telnet server + classic LORD login flow.

``handle_connection`` is the ``telnetlib3`` shell callback for a single
connection: it drives the name/password/character-creation dance and then
hands off to ``run_session`` (the scene engine, Task 8) for the rest of the
session. ``start`` wires that callback into ``telnetlib3.create_server``
with one ``sqlite3.Connection`` shared by every connection the returned
server accepts (safe because ``sqlite3`` connections are only unsafe across
*threads*, and every connection here is driven from the same asyncio event
loop thread).

Class-selection wording ("Killing A Lot Of Woodland Creatures" / "Dabbling
In The Mystical Forces" / "Lying, Cheating, And Stealing From The Blind")
is ported verbatim from ``reference/lord.js``'s ``choose_profession()``
(lines 4837-4888); the ``' KDL'.indexOf(ch)`` trick there is why K/D/L map
to class_type 1/2/3 (index 0 is the leading space -> "no class chosen",
which this project's ``Player.class_type`` default of 1 preempts, so it's
not reachable from this flow).
"""

from __future__ import annotations

import logging
import random
import sqlite3
import string
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import telnetlib3
from telnetlib3.telopt import ECHO, SGA, WILL

import pylord.engine.scenes  # noqa: F401 -- registers SCENES (town, stats, ...)
from pylord import db, igm_loader
from pylord.engine import daily, fights
from pylord.engine.game import GameCtx, run_session
from pylord.engine.scenes import mail as mail_scene
from pylord.models import Player, PlayerRepo
from pylord.terminal import ConnectionClosed, TelnetIO

NAME_MAXLEN = 20
NAME_MINLEN = 3  # reference/lord.js:6092-6096 ("Try a longer name!")
NAME_LIMIT = 18  # reference/lord.js:6088-6091 ("Try a shorter name!")
PASSWORD_MAXLEN = 30
# Letters, digits, and spaces only. Filtered character-by-character by
# TelnetIO.readline()/FakeIO.readline().
NAME_CHARSET = string.ascii_letters + string.digits + " "

# reference/lord.js:4766-4834 (check_name()) -- names the game refuses,
# each with its own retort. Keys are upper-cased for comparison.
RESERVED_NAMES: dict[str, str] = {
    "BARAK": "Naw, the real Barak would decapitate you if he found out.",
    "SETH": "You are not Seth Able!  Don't take his name in vain!",
    "SETH ABLE": "You are not God!",
    "TURGON": "Haw.  Hardly - Turgon has muscles.",
    "VIOLET": "Haw.  Hardly - Violet has breasts.",
    "RED DRAGON": "Oh go plague some other land!",
    "DRAGON": "You ain't Bruce Lee, so get out!",
    "JENNIE GARTH": "You are not a goddess, don't use her name!",
    "KIRSTEN DUNST": "Hardly! You only wish you were in a movie with Wynona!",
    "BUSH": "Lower my taxes!",
    "BAGGIO": "Darius sucks!",
    "DAVID FOLLEY": "You rule, dude - but use a handle or you will mobbed!",
    "ARNOLD PALMER": "Ha!  You're too old to be playing games.",
    "BARTENDER": "Nah, the bartender is smarter than you!",
    "CHANCE": "Why not go take a chance with a rattlesnake?",
    "MICHAEL PRESLAR": "You want to be a small town kid?",
    "GOD": "Why arent you in church?",
    "JESUS": "Why arent you in church?",
}

# reference/lord.js:6132-6172 -- one of five lines after the gender pick.
_GENDER_FLAVOR = {
    "M": (
        'With a name like "{name}", no one is going to believe it.',
        "ALL RIGHT!!  A member of the more ADVANCED sex.  You had better win.",
        "Good.  Men rule this earth.  We own and run EVERYTHING.",
        "Then don't be wearing any dresses, eh.",
        "Very good.  If a woman ever beats you in battle, go into exile.",
    ),
    "F": (
        "Good.  Teach those men that they do NOT rule the world.",
        "ALL RIGHT!!  A member of the more ADVANCED sex.  You had better win.",
        "Excellent.  Taunt the men, tease them, and break their hearts!",
        "Be warned, you are going to have to fight, kill and maim here.",
        "Good.  There are way too many men in this land..",
    ),
}

_NAME_PROMPT = "`0What be thy name, warrior? `%"

_WELCOME_SPLASH = (
    "\n"
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
    "`%          Legend of the Red Dragon`0\n"
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
    "\n"
    "`2                  ** Welcome to the realm, new warrior! **`0\n"
)

_GENDER_PROMPT = "  `2And your gender?  (`0M`2/`0F`2): `%"
_GENDER_OPTIONS = {"M": "male", "F": "female"}

# Ported verbatim from reference/lord.js:4845-4849 (choose_profession()).
_CLASS_MENU = (
    "\n"
    "  `%As you remember your childhood, you remember...\n"
    "\n"
    "  `0(`5K`0)illing A Lot Of Woodland Creatures\n"
    "  `0(`5D`0)abbling In The Mystical Forces\n"
    "  `0(`5L`0)ying, Cheating, And Stealing From The Blind\n"
)
_CLASS_PROMPT = "  `2Pick one.  (`0K`2,`0D`2,`0L`2) : `%"
_CLASS_OPTIONS = {"K": "warrior", "D": "mystic", "L": "thief"}
# ' KDL'.indexOf(ch) in lord.js -- K=1, D=2, L=3 (see module docstring).
_CLASS_TYPES = {"K": 1, "D": 2, "L": 3}

logger = logging.getLogger(__name__)


async def _prompt_name(io: TelnetIO) -> str:
    """Read a usable name, re-prompting until one is given.

    Applies lord.js's own new-character name rules: 3..18 characters
    (reference/lord.js:6088-6096) and ``check_name()``'s reserved-name
    list (:4766-4834), each with the original's retort. An *existing*
    character of any name can still log in -- the rules gate creation, and
    ``handle_connection`` only reaches them for a name that isn't in the
    database.
    """
    while True:
        name = await io.readline(_NAME_PROMPT, maxlen=NAME_MAXLEN, charset=NAME_CHARSET)
        name = " ".join(name.split())
        if not name:
            await io.write("\n`)You must give a name.`0\n")
            continue
        return name


async def _name_is_allowed(io: TelnetIO, name: str) -> bool:
    """False (with lord.js's own message) if this name can't be created."""
    if len(name) > NAME_LIMIT:  # reference/lord.js:6088-6091
        await io.write("\n  Try a shorter name!\n")
        return False
    if len(name) < NAME_MINLEN:  # reference/lord.js:6092-6096
        await io.write("\n  Try a longer name!\n")
        return False
    retort = RESERVED_NAMES.get(name.upper())
    if retort is not None:  # reference/lord.js:4827-4832
        await io.write(f"\n  `)** `%{retort} `)**`2\n\n")
        return False
    return True


async def _prompt_password(io: TelnetIO, prompt: str) -> str:
    return await io.readline(prompt, maxlen=PASSWORD_MAXLEN)


async def _login_existing(io: TelnetIO, repo: PlayerRepo, name: str) -> Player | None:
    """Password prompt, up to 3 tries. Returns the authenticated Player, or
    None if all 3 tries failed (caller disconnects)."""
    for attempt in range(3):
        password = await _prompt_password(io, "  `2Password: `%")
        authed = repo.check_password(name, password)
        if authed is not None:
            return authed
        remaining = 2 - attempt
        if remaining > 0:
            await io.write(f"\n`)Wrong password. {remaining} tries left.`0\n")
    return None


async def _create_character(
    io: TelnetIO, repo: PlayerRepo, name: str, game_config: dict[str, Any]
) -> Player | None:
    """Full new-character flow: confirm name, splash, gender, class, set
    password, then create. Returns the new Player, or None if the caller
    should re-prompt for a name (creation declined, or lost a race to
    another connection creating the same name concurrently -- see
    reference/lord.js:6125's own TODO about this exact race).

    ``game_config`` (``config["game"]``) applies ``forest_fights_per_day``/
    ``player_fights_per_day`` to the freshly-created player, the same
    config keys ``pylord/engine/daily.py``'s ``maintenance()`` uses. Without
    this, a character created any time *after* today's ``maintenance()``
    batch pass has already run (the common case -- see
    ``handle_connection``) would silently keep the DB schema's literal
    15/3 defaults (``pylord/db.py``) instead of the sysop's configured
    values until the next day's reset -- a config-consumption gap found in
    Task 14's audit."""
    if not await _name_is_allowed(io, name):
        return None

    confirm = await io.menu({"Y": "yes", "N": "no"}, f"  `0{name}`2? `2[`0Y`2] : `%")
    if confirm == "N":
        return None

    await io.write(_WELCOME_SPLASH)

    gender = await io.menu(_GENDER_OPTIONS, _GENDER_PROMPT)
    # reference/lord.js:6132-6172 -- a random remark on the choice.
    flavor = random.choice(_GENDER_FLAVOR[gender])
    await io.write(f"\n  `2{flavor.format(name=name)}`0\n")

    await io.write(_CLASS_MENU)
    class_letter = await io.menu(_CLASS_OPTIONS, _CLASS_PROMPT)

    while True:
        pw1 = await _prompt_password(io, "\n  `2Password: `%")
        if not pw1:
            await io.write("\n`)Password cannot be empty.`0\n")
            continue
        pw2 = await _prompt_password(io, "  `2Confirm password: `%")
        if pw1 == pw2:
            break
        await io.write("\n`)Passwords did not match. Try again.`0\n")

    try:
        player = repo.create(name, pw1, gender)
    except ValueError:
        await io.write("\n`)That name was just taken by another warrior.`0\n")
        return None

    player.class_type = _CLASS_TYPES[class_letter]
    player.forest_fights = game_config.get("forest_fights_per_day", player.forest_fights)
    player.player_fights = game_config.get("player_fights_per_day", player.player_fights)
    # Today's maintenance() pass already ran (see handle_connection), so
    # this character would otherwise start with the schema default of 0
    # skill uses and be unable to use a skill attack until tomorrow. In
    # lord.js a brand-new player always passes through wake_up() on their
    # first login (player.time defaults to a sentinel that never equals
    # state.days, reference/recorddefs.js:124-129), so they always have at
    # least the flat "+1 for being a <class>" grant.
    player.skill_uses = daily.skill_uses_for(player)
    player.last_played = datetime.now(UTC).date().isoformat()
    player.fights_regen_at = datetime.now(UTC).isoformat()
    repo.save(player)
    return player


async def handle_connection(
    reader, writer, *, conn, config: dict[str, Any], igms=None
) -> None:
    """telnetlib3 shell callback: login flow, then hand off to run_session.

    Exactly one live session per character: if the resolved player is
    already marked ``online``, this connection is kicked with a message
    rather than the earlier session being disturbed (simple approach, per
    the task brief). ``online`` is always cleared and the player saved in
    the ``finally`` block, regardless of how the session ends (normal
    logoff, an unhandled scene error, or the client disconnecting).
    """
    # Ask the client for character-at-a-time mode (the standard BBS-door
    # arrangement): WILL ECHO + WILL SGA tell it to stop line-buffering
    # locally and let the server echo. Without this, real telnet clients
    # send nothing until Enter, so readkey() gets the first letter and the
    # leftover CR hits the next menu() as an invalid key (re-printing its
    # prompt), and hotkey+argument screens only work typed as one line.
    # telnetlib3 handles the DO/DONT replies; a client that refuses simply
    # stays in line mode and behaves no worse than before.
    writer.iac(WILL, ECHO)
    writer.iac(WILL, SGA)

    io = TelnetIO(reader, writer)
    repo = PlayerRepo(conn)

    # Cheap once-per-day guard inside maintenance() itself (a single
    # SELECT once today's pass has already run) -- see
    # pylord/engine/daily.py's module docstring for why this is a global
    # batch pass rather than lord.js's per-player lazy wake_up(). UTC
    # (rather than host-local "today") avoids the game's day rollover
    # depending on whatever timezone the server process happens to run in.
    daily.maintenance(conn, config, datetime.now(UTC).date().isoformat(), igms=igms)

    player: Player | None = None
    try:
        while player is None:
            name = await _prompt_name(io)
            existing = repo.get_by_name(name)

            if existing is not None:
                authed = await _login_existing(io, repo, name)
                if authed is None:
                    await io.write("\n`)Too many failed attempts. Goodbye.`0\n")
                    return
                if authed.online:
                    await io.write(
                        "\n`)That character is already adventuring elsewhere.`0\n"
                    )
                    return
                player = authed
            else:
                player = await _create_character(io, repo, name, config.get("game", {}))

        if await _check_gameover(io, conn, repo, player):
            return

        player.online = 1
        repo.save(player)

        ctx = GameCtx(
            player=player,
            repo=repo,
            io=io,
            conn=conn,
            config=config.get("game", {}),
            igms=igms,
        )
        try:
            # Task 13a: apply/show unread mail (including any async IGM
            # "effect" payload -- pylord/engine/effects.py) once, right
            # after login and before the player reaches the Town Square.
            # See pylord/engine/scenes/mail.py's module docstring for why
            # this replaces lord.js's constant check_mail() polling.
            # Credit any fights earned while logged off
            # (pylord/engine/fights.py) before anything else runs.
            regained = fights.apply_regen(player, ctx.config)
            if regained:
                await io.write(
                    f"\n  `2You feel rested: `0{regained}`2 forest "
                    f"{'fight' if regained == 1 else 'fights'} recovered.`0\n"
                )
            await mail_scene.apply_unread_mail(ctx)
            # A player who rented a room wakes up in the Inn
            # (reference/lord.js:16925-16930); the Inn scene itself clears
            # at_inn on the way in (:9920). Starting at the Town Square
            # instead would leave them flagged as sleeping -- and so
            # attackable in their bed -- indefinitely.
            await run_session(ctx, start="inn" if player.at_inn else "town")
        except KeyError:
            # Every town destination is now registered except the
            # remaining "under construction" stubs (weapons shop, bank,
            # etc. -- future tasks) -- those route to the shared `_stub`
            # scene in town.py rather than raising, so this guard should
            # never actually fire anymore. Left in place (not removed) per
            # run_session's documented contract (see game.py): an
            # unregistered scene key is a programming error that should
            # propagate, and this is still the right place to catch it for
            # a telnet client rather than crashing the connection handler.
            await io.write("\n`)That place is not yet built.`0\n")
    except ConnectionClosed:
        pass
    finally:
        if player is not None:
            player.online = 0
            try:
                repo.save(player)
            except sqlite3.Error:
                # Best-effort cleanup: don't let a DB hiccup during
                # shutdown stop us from still closing the connection below.
                logger.exception(
                    "failed to clear online flag for %s during cleanup", player.name
                )
        # TelnetWriter.close() is idempotent and swallows its own internal
        # errors (see telnetlib3.stream_writer.TelnetWriter.close()).
        writer.close()


async def _check_gameover(io: TelnetIO, conn, repo: PlayerRepo, player: Player) -> bool:
    """Port of ``check_gameover()``. reference/lord.js:17293-17324.

    Once someone has finished the quest (``settings.win_deeds`` dragon
    kills -- ``pylord/engine/scenes/dragon.py`` records the winner in
    ``game_state['won_by']``), the realm is over: every login is redirected
    to a "PAY HOMAGE" screen instead of being allowed to play. Returns
    ``True`` when the session was ended this way.
    """
    row = conn.execute(
        "SELECT value FROM game_state WHERE key = 'won_by'"
    ).fetchone()
    if row is None:
        return False
    try:
        winner = repo.get(int(row["value"]))
    except (TypeError, ValueError):
        return False
    if winner is None:
        return False

    await io.write(
        "\n`c                      `%PAY HOMAGE TO YOUR BETTER!\n\n"
        "  `0The incredible warrior whose deeds will grace every tongue of\n"
        "  every minstrel in every town every song of every day is the master\n"
        f"  warrior known as `%{winner.name}`2.\n\n"
    )
    if winner.id == player.id:
        await io.write(
            "  `0You smile modestly.  If only people knew, that incredible\n"
            "  warrior was you.\n\n"
        )
    else:
        await io.write(
            "  `2You bow your head in reverence - vowing to follow the teachings\n"
            "  of this great person - to learn whatever this Godlike wonder can\n"
            "  show you.\n\n"
            "  `#(ASK YOUR SYSOP TO RESET THE REALM)`2\n\n"
        )
    await io.pause()
    return True


async def start(config: dict[str, Any]):
    """Start the telnet server described by ``config`` and return it.

    ``config["server"]`` is expected to look like config.toml's
    ``[server]`` table (``host``, ``port``, and this project's ``db`` path
    key -- see cli.py for how the CLI resolves that path). Opens and
    migrates one ``sqlite3.Connection`` shared by every connection this
    server accepts for as long as it runs.
    """
    server_cfg = config.get("server", {})
    host = server_cfg.get("host", "0.0.0.0")
    port = server_cfg.get("port", 2323)
    db_path = server_cfg.get("db", "lord.db")

    conn = db.connect(db_path)
    db.migrate(conn)

    # No session can exist before the listener does, so any `online` flag
    # still set here is stale -- left by a pod restart, a crash, or a
    # machine losing power mid-session. Left alone it would both inflate
    # "people on now" and lock that character out of their own account
    # ("already adventuring elsewhere") until someone edited the database.
    with conn:
        cleared = conn.execute(
            "UPDATE players SET online = 0 WHERE online != 0"
        ).rowcount
    if cleared:
        logger.info("cleared %d stale online flag(s) from a previous run", cleared)

    # Discover drop-in IGM plugins once at startup; the registry is shared
    # (read-only after discovery) by every connection this server accepts.
    # Resolve ``igms/`` next to the database (which cli.load_config already
    # anchors to the config file's directory), so discovery doesn't depend
    # on the server's current working directory.
    igms_dir = Path(db_path).resolve().parent / "igms"
    igms = igm_loader.discover(igms_dir, config)
    logger.info("loaded %d enabled IGM(s) from %s", len(igms.enabled), igms_dir)

    async def shell(reader, writer) -> None:
        await handle_connection(reader, writer, conn=conn, config=config, igms=igms)

    return await telnetlib3.create_server(host=host, port=port, shell=shell)
