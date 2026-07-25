"""Tests for pylord.cli's sysop commands (``edit``/``players``).

Each test writes a throwaway ``config.toml`` + sqlite db under ``tmp_path``
(the same DB-path-resolution rule ``load_config`` documents), seeds a player
via ``PlayerRepo`` directly, then drives ``await _run()`` with a monkeypatched
``sys.argv`` -- exactly how a sysop would invoke the real ``pylord`` CLI.
"""

from __future__ import annotations

import asyncio

from pylord import data
from pylord.cli import main
from pylord.models import verify_password


async def _run(argv):
    """Drive ``await _run()`` the way a sysop's shell does.

    ``await _run()`` owns its own ``asyncio.run()``, which cannot be nested
    inside the loop these async tests already run on, so it goes to a
    worker thread -- and that is also closer to the real invocation than
    reaching past it into the private ``_edit``/``_delete`` coroutines.
    """
    return await asyncio.to_thread(main, argv)


async def _make_config(tmp_path):
    db_path = tmp_path / "lord.db"
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f'[server]\ndb = "{db_path}"\n\n[game]\n'
    )
    database = await data.connect(str(db_path))
    return config_path, database


async def _seed_player(database, name="Hero", **overrides):
    repo = database.players
    player = await repo.create(name, "pw", "M")
    for key, value in overrides.items():
        setattr(player, key, value)
    await repo.save(player)
    return player


async def test_edit_gold_persists(tmp_path, capsys):
    config_path, database = await _make_config(tmp_path)
    await _seed_player(database, gold=500)

    rc = await _run(["edit", "Hero", "--config", str(config_path), "--gold", "1234"])

    assert rc == 0
    reloaded = await database.players.get_by_name("Hero")
    assert reloaded.gold == 1234
    out = capsys.readouterr().out
    assert "gold" in out.lower()
    assert "500" in out
    assert "1234" in out


async def test_edit_level_99_clamps_to_12(tmp_path, capsys):
    config_path, database = await _make_config(tmp_path)
    await _seed_player(database, level=5)

    rc = await _run(["edit", "Hero", "--config", str(config_path), "--level", "99"])

    assert rc == 0
    reloaded = await database.players.get_by_name("Hero")
    assert reloaded.level == 12


async def test_edit_level_0_clamps_to_1(tmp_path):
    config_path, database = await _make_config(tmp_path)
    await _seed_player(database, level=5)

    rc = await _run(["edit", "Hero", "--config", str(config_path), "--level", "0"])

    assert rc == 0
    reloaded = await database.players.get_by_name("Hero")
    assert reloaded.level == 1


async def test_edit_unknown_player_exits_1(tmp_path, capsys):
    config_path, _conn = await _make_config(tmp_path)

    rc = await _run(["edit", "Nobody", "--config", str(config_path), "--gold", "1"])

    assert rc == 1
    err = capsys.readouterr().err
    assert "Nobody" in err


async def test_edit_no_flags_prints_stats_without_modifying(tmp_path, capsys):
    config_path, database = await _make_config(tmp_path)
    await _seed_player(database, gold=777, level=3)

    rc = await _run(["edit", "Hero", "--config", str(config_path)])

    assert rc == 0
    reloaded = await database.players.get_by_name("Hero")
    assert reloaded.gold == 777
    assert reloaded.level == 3
    out = capsys.readouterr().out
    assert "Hero" in out
    assert "777" in out


async def test_edit_gems_and_alive_and_reset_password(tmp_path):
    config_path, database = await _make_config(tmp_path)
    await _seed_player(database, gems=0, alive=1)

    rc = await _run([
            "edit",
            "Hero",
            "--config",
            str(config_path),
            "--gems",
            "5",
            "--alive",
            "0",
            "--reset-password",
            "newpass",
        ]
    )

    assert rc == 0
    reloaded = await database.players.get_by_name("Hero")
    assert reloaded.gems == 5
    assert reloaded.alive == 0
    assert verify_password("newpass", reloaded.password_hash)


async def test_edit_lowercase_name_finds_player(tmp_path):
    config_path, database = await _make_config(tmp_path)
    await _seed_player(database, gold=500)

    rc = await _run(["edit", "hero", "--config", str(config_path), "--gold", "42"])

    assert rc == 0
    reloaded = await database.players.get_by_name("Hero")
    assert reloaded.gold == 42


async def test_players_lists_roster_with_created_player(tmp_path, capsys):
    config_path, database = await _make_config(tmp_path)
    await _seed_player(database, name="Hero", level=4, gold=999)

    rc = await _run(["players", "--config", str(config_path)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "Hero" in out
    assert "4" in out
    assert "999" in out
    # Header row present with expected columns.
    assert "name" in out.lower()
    assert "level" in out.lower()
    assert "online" in out.lower()


async def _config_with_player(tmp_path, name="Doomed", **fields):
    from pylord import data
    
    db_path = tmp_path / "lord.db"
    database = await data.connect(str(db_path))
    repo = database.players
    player = await repo.create(name, "pw", "M")
    for key, value in fields.items():
        setattr(player, key, value)
    await repo.save(player)
    await database.dispose()

    config = tmp_path / "config.toml"
    config.write_text(f'[server]\ndb = "{db_path}"\n\n[game]\n')
    return config, db_path


async def test_delete_requires_yes(tmp_path, capsys):
    config, db_path = await _config_with_player(tmp_path)
    assert await _run(["delete", "Doomed", "--config", str(config)]) == 1
    assert "pass --yes" in capsys.readouterr().out

    database = await data.connect(str(db_path))
    assert await database.players.get_by_name("Doomed") is not None


async def test_delete_removes_the_player_and_their_mail(tmp_path):
    config, db_path = await _config_with_player(tmp_path)
    database = await data.connect(str(db_path))
    doomed = await database.players.get_by_name("Doomed")
    async with database.transaction() as tx:
        await tx.mail.send(doomed.id, "Someone", text="hi")
    await database.dispose()

    assert await _run(["delete", "Doomed", "--config", str(config), "--yes"]) == 0

    database = await data.connect(str(db_path))
    assert await database.players.get_by_name("Doomed") is None
    assert await database.mail.unread_for(doomed.id) == []
    await database.dispose()


async def test_delete_refuses_while_the_player_is_online(tmp_path, capsys):
    config, _db_path = await _config_with_player(tmp_path, online=1)
    assert await _run(["delete", "Doomed", "--config", str(config), "--yes"]) == 1
    assert "online right now" in capsys.readouterr().err


async def test_serve_configures_logging(tmp_path, monkeypatch):
    """Engine logs (crashing IGMs, DB errors) are invisible without this."""
    import logging

    config, _db_path = await _config_with_player(tmp_path)
    logging.getLogger().handlers.clear()

    started = {}

    async def _fake_start(config):
        started["config"] = config
        raise KeyboardInterrupt  # unwind before the server really runs

    monkeypatch.setattr("pylord.server.start", _fake_start)
    await _run(["serve", "--config", str(config)])

    assert logging.getLogger().handlers, "no logging handler was installed"
    assert logging.getLogger().level == logging.INFO
