"""pylord CLI entry point: ``pylord serve``, ``pylord edit``, ``pylord players``.

DB path resolution (documented per this task's brief): ``pylord serve``
reads ``config.toml``'s ``[server]`` table. If it has a ``db`` key, that
path is used (resolved relative to the config file's directory when not
absolute); otherwise the database defaults to ``lord.db`` sitting next to
the config file.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import tomllib
from pathlib import Path
from typing import Any


def load_config(config_path: Path) -> dict[str, Any]:
    """Load ``config_path`` and resolve ``[server] db`` per the module
    docstring's rule. Mutates and returns the parsed config dict."""
    with config_path.open("rb") as f:
        config = tomllib.load(f)

    server_cfg = config.setdefault("server", {})
    if "db" in server_cfg:
        db_path = Path(server_cfg["db"])
        if not db_path.is_absolute():
            db_path = config_path.parent / db_path
    else:
        db_path = config_path.parent / "lord.db"
    server_cfg["db"] = str(db_path)
    return config


def _cmd_serve(args: argparse.Namespace) -> int:
    from pylord.server import start

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"config file not found: {config_path}", file=sys.stderr)
        return 1
    config = load_config(config_path)

    async def _run() -> None:
        server = await start(config)
        server_cfg = config["server"]
        print(
            f"pylord listening on {server_cfg.get('host', '0.0.0.0')}:"
            f"{server_cfg.get('port', 2323)} (db: {server_cfg['db']})"
        )
        await server.wait_closed()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass
    return 0


def _open_repo(config: dict[str, Any]):
    from pylord import db
    from pylord.models import PlayerRepo

    conn = db.connect(config["server"]["db"])
    db.migrate(conn)
    return PlayerRepo(conn)


_STATS_FIELDS = [
    "name",
    "level",
    "exp",
    "gold",
    "gems",
    "bank",
    "alive",
    "forest_fights",
    "player_fights",
    "king_count",
    "last_played",
    "online",
]

_ROSTER_FIELDS = [
    "name",
    "level",
    "exp",
    "gold",
    "bank",
    "alive",
    "online",
    "king_count",
    "last_played",
]


def _print_table(headers: list[str], rows: list[list[str]]) -> None:
    """Print a left-aligned, whitespace-padded table -- no external deps."""
    widths = [
        max(len(headers[i]), *(len(row[i]) for row in rows)) if rows else len(headers[i])
        for i in range(len(headers))
    ]
    header_line = "  ".join(h.ljust(w) for h, w in zip(headers, widths))
    print(header_line)
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print("  ".join(cell.ljust(w) for cell, w in zip(row, widths)))


def _print_player_stats(player) -> None:
    rows = [[field, str(getattr(player, field))] for field in _STATS_FIELDS]
    _print_table(["field", "value"], rows)


def _cmd_edit(args: argparse.Namespace) -> int:
    from pylord.engine import limits
    from pylord.models import hash_password

    if not args.name:
        print("usage: pylord edit NAME [--gold N] [--gems N] [--level N] "
              "[--alive 0|1] [--reset-password PW]", file=sys.stderr)
        return 1

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"config file not found: {config_path}", file=sys.stderr)
        return 1
    config = load_config(config_path)
    repo = _open_repo(config)

    player = repo.get_by_name(args.name)
    if player is None:
        print(f"no such player: {args.name}", file=sys.stderr)
        return 1

    changes: list[tuple[str, str, str]] = []

    if args.gold is not None:
        before, after = player.gold, limits.clamp("gold", args.gold)
        changes.append(("gold", str(before), str(after)))
        player.gold = after
    if args.gems is not None:
        before, after = player.gems, limits.clamp("gems", args.gems)
        changes.append(("gems", str(before), str(after)))
        player.gems = after
    if args.level is not None:
        before, after = player.level, max(1, min(args.level, 12))
        changes.append(("level", str(before), str(after)))
        player.level = after
    if args.alive is not None:
        before, after = player.alive, 1 if args.alive else 0
        changes.append(("alive", str(before), str(after)))
        player.alive = after
    if args.reset_password is not None:
        changes.append(("password", "(hidden)", "(reset)"))
        player.password_hash = hash_password(args.reset_password)

    if not changes:
        print(f"{player.name} (no changes requested)")
        _print_player_stats(player)
        return 0

    print(f"{player.name}:")
    _print_table(["field", "before", "after"], changes)
    repo.save(player)
    return 0


def _cmd_players(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"config file not found: {config_path}", file=sys.stderr)
        return 1
    config = load_config(config_path)
    repo = _open_repo(config)

    players = repo.all_players()
    rows = [[str(getattr(p, field)) for field in _ROSTER_FIELDS] for p in players]
    _print_table(_ROSTER_FIELDS, rows)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pylord", description="pylord -- Legend of the Red Dragon telnet remake"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve", help="run the telnet server")
    serve_parser.add_argument(
        "--config",
        default="config.toml",
        help="path to config.toml (default: ./config.toml)",
    )
    serve_parser.set_defaults(func=_cmd_serve)

    edit_parser = subparsers.add_parser("edit", help="edit a player's stats")
    edit_parser.add_argument("name", nargs="?", help="player name")
    edit_parser.add_argument(
        "--config",
        default="config.toml",
        help="path to config.toml (default: ./config.toml)",
    )
    edit_parser.add_argument("--gold", type=int, help="set gold on hand")
    edit_parser.add_argument("--gems", type=int, help="set gems")
    edit_parser.add_argument("--level", type=int, help="set level (clamped 1..12)")
    edit_parser.add_argument(
        "--alive", type=int, choices=[0, 1], help="1 = alive, 0 = dead"
    )
    edit_parser.add_argument(
        "--reset-password", help="set a new password for this player"
    )
    edit_parser.set_defaults(func=_cmd_edit)

    players_parser = subparsers.add_parser("players", help="list players")
    players_parser.add_argument(
        "--config",
        default="config.toml",
        help="path to config.toml (default: ./config.toml)",
    )
    players_parser.set_defaults(func=_cmd_players)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
