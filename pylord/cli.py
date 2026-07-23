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


def _cmd_edit(args: argparse.Namespace) -> int:
    # Task 14 fills this in: apply --gold/--level/etc to the named player.
    print("not implemented")
    return 0


def _cmd_players(args: argparse.Namespace) -> int:
    # Task 14 fills this in: list players from the configured database.
    print("not implemented")
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

    edit_parser = subparsers.add_parser(
        "edit", help="edit a player's stats (not implemented until Task 14)"
    )
    edit_parser.add_argument("name", nargs="?", help="player name")
    edit_parser.add_argument("--gold", type=int)
    edit_parser.add_argument("--level", type=int)
    edit_parser.set_defaults(func=_cmd_edit)

    players_parser = subparsers.add_parser(
        "players", help="list players (not implemented until Task 14)"
    )
    players_parser.set_defaults(func=_cmd_players)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
