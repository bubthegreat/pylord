"""Tests for pylord.cli's sysop commands (``edit``/``players``).

Each test writes a throwaway ``config.toml`` + sqlite db under ``tmp_path``
(the same DB-path-resolution rule ``load_config`` documents), seeds a player
via ``PlayerRepo`` directly, then drives ``main()`` with a monkeypatched
``sys.argv`` -- exactly how a sysop would invoke the real ``pylord`` CLI.
"""

from __future__ import annotations

from pylord import db
from pylord.cli import main
from pylord.models import PlayerRepo, verify_password


def _make_config(tmp_path):
    db_path = tmp_path / "lord.db"
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f'[server]\ndb = "{db_path}"\n\n[game]\n'
    )
    conn = db.connect(str(db_path))
    db.migrate(conn)
    return config_path, conn


def _seed_player(conn, name="Hero", **overrides):
    repo = PlayerRepo(conn)
    player = repo.create(name, "pw", "M")
    for key, value in overrides.items():
        setattr(player, key, value)
    repo.save(player)
    return player


def test_edit_gold_persists(tmp_path, capsys):
    config_path, conn = _make_config(tmp_path)
    _seed_player(conn, gold=500)

    rc = main(["edit", "Hero", "--config", str(config_path), "--gold", "1234"])

    assert rc == 0
    reloaded = PlayerRepo(conn).get_by_name("Hero")
    assert reloaded.gold == 1234
    out = capsys.readouterr().out
    assert "gold" in out.lower()
    assert "500" in out
    assert "1234" in out


def test_edit_level_99_clamps_to_12(tmp_path, capsys):
    config_path, conn = _make_config(tmp_path)
    _seed_player(conn, level=5)

    rc = main(["edit", "Hero", "--config", str(config_path), "--level", "99"])

    assert rc == 0
    reloaded = PlayerRepo(conn).get_by_name("Hero")
    assert reloaded.level == 12


def test_edit_level_0_clamps_to_1(tmp_path):
    config_path, conn = _make_config(tmp_path)
    _seed_player(conn, level=5)

    rc = main(["edit", "Hero", "--config", str(config_path), "--level", "0"])

    assert rc == 0
    reloaded = PlayerRepo(conn).get_by_name("Hero")
    assert reloaded.level == 1


def test_edit_unknown_player_exits_1(tmp_path, capsys):
    config_path, _conn = _make_config(tmp_path)

    rc = main(["edit", "Nobody", "--config", str(config_path), "--gold", "1"])

    assert rc == 1
    err = capsys.readouterr().err
    assert "Nobody" in err


def test_edit_no_flags_prints_stats_without_modifying(tmp_path, capsys):
    config_path, conn = _make_config(tmp_path)
    _seed_player(conn, gold=777, level=3)

    rc = main(["edit", "Hero", "--config", str(config_path)])

    assert rc == 0
    reloaded = PlayerRepo(conn).get_by_name("Hero")
    assert reloaded.gold == 777
    assert reloaded.level == 3
    out = capsys.readouterr().out
    assert "Hero" in out
    assert "777" in out


def test_edit_gems_and_alive_and_reset_password(tmp_path):
    config_path, conn = _make_config(tmp_path)
    _seed_player(conn, gems=0, alive=1)

    rc = main(
        [
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
    reloaded = PlayerRepo(conn).get_by_name("Hero")
    assert reloaded.gems == 5
    assert reloaded.alive == 0
    assert verify_password("newpass", reloaded.password_hash)


def test_edit_lowercase_name_finds_player(tmp_path):
    config_path, conn = _make_config(tmp_path)
    _seed_player(conn, gold=500)

    rc = main(["edit", "hero", "--config", str(config_path), "--gold", "42"])

    assert rc == 0
    reloaded = PlayerRepo(conn).get_by_name("Hero")
    assert reloaded.gold == 42


def test_players_lists_roster_with_created_player(tmp_path, capsys):
    config_path, conn = _make_config(tmp_path)
    _seed_player(conn, name="Hero", level=4, gold=999)

    rc = main(["players", "--config", str(config_path)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "Hero" in out
    assert "4" in out
    assert "999" in out
    # Header row present with expected columns.
    assert "name" in out.lower()
    assert "level" in out.lower()
    assert "online" in out.lower()
