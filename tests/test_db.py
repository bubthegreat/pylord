from pylord import db


def test_migrate_creates_tables(tmp_path):
    conn = db.connect(tmp_path / "g.db")
    db.migrate(conn)
    names = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"players", "game_state", "daily_news", "mail", "igm_data",
            "schema_version"} <= names


def test_migrate_idempotent(tmp_path):
    conn = db.connect(tmp_path / "g.db")
    db.migrate(conn)
    db.migrate(conn)  # must not raise
