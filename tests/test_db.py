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


def test_migration_two_adds_record_flags(tmp_path):
    """MIGRATIONS[1] backfills the original player-record flags
    (reference/recorddefs.js) the post-v0.1 mechanics gate on."""
    conn = db.connect(tmp_path / "g.db")
    db.migrate(conn)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(players)")}
    assert {
        "high_spirits",
        "weird",
        "has_fairy",
        "fairy_lore",
        "amulet",
        "pvp_kills",
        "magically_delicious",
        "divorced",
        "mastered_dk",
        "mastered_my",
        "mastered_th",
    } <= cols


def test_migration_two_applies_to_an_existing_v1_database(tmp_path):
    """A database created before migration 2 existed must upgrade in
    place rather than being recreated."""
    path = tmp_path / "old.db"
    conn = db.connect(path)
    conn.executescript(db.MIGRATIONS[0])
    conn.execute(
        "CREATE TABLE schema_version (applied_count INTEGER NOT NULL DEFAULT 0)"
    )
    conn.execute("INSERT INTO schema_version (applied_count) VALUES (1)")
    conn.execute(
        "INSERT INTO players (name, password_hash) VALUES ('Old', 'x')"
    )
    conn.commit()

    db.migrate(conn)

    row = conn.execute("SELECT * FROM players WHERE name = 'Old'").fetchone()
    assert row["high_spirits"] == 0
    assert conn.execute(
        "SELECT applied_count FROM schema_version"
    ).fetchone()[0] == len(db.MIGRATIONS)
