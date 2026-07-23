import sqlite3
from pathlib import Path


def connect(path: str | Path) -> sqlite3.Connection:
    """Connect to SQLite database with proper configuration."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")

    return conn


MIGRATIONS = [
    """
    CREATE TABLE players (
      id INTEGER PRIMARY KEY,
      name TEXT UNIQUE COLLATE NOCASE NOT NULL,
      password_hash TEXT NOT NULL,
      gender TEXT NOT NULL DEFAULT 'M',
      class_type INTEGER NOT NULL DEFAULT 1,
      level INTEGER NOT NULL DEFAULT 1,
      exp INTEGER NOT NULL DEFAULT 1,
      hp INTEGER NOT NULL DEFAULT 20,
      hp_max INTEGER NOT NULL DEFAULT 20,
      strength INTEGER NOT NULL DEFAULT 10,
      defense INTEGER NOT NULL DEFAULT 1,
      charm INTEGER NOT NULL DEFAULT 2,
      gold INTEGER NOT NULL DEFAULT 500,
      bank INTEGER NOT NULL DEFAULT 0,
      gems INTEGER NOT NULL DEFAULT 0,
      weapon_num INTEGER NOT NULL DEFAULT 0,
      armor_num INTEGER NOT NULL DEFAULT 0,
      forest_fights INTEGER NOT NULL DEFAULT 15,
      player_fights INTEGER NOT NULL DEFAULT 3,
      flirts_today INTEGER NOT NULL DEFAULT 0,
      alive INTEGER NOT NULL DEFAULT 1,
      at_inn INTEGER NOT NULL DEFAULT 0,
      seen_master INTEGER NOT NULL DEFAULT 0,
      seen_dragon INTEGER NOT NULL DEFAULT 0,
      seen_violet INTEGER NOT NULL DEFAULT 0,
      seen_bard INTEGER NOT NULL DEFAULT 0,
      married_to INTEGER,
      lays INTEGER NOT NULL DEFAULT 0,
      kids INTEGER NOT NULL DEFAULT 0,
      king_count INTEGER NOT NULL DEFAULT 0,
      skill_dk INTEGER NOT NULL DEFAULT 0,
      skill_my INTEGER NOT NULL DEFAULT 0,
      skill_th INTEGER NOT NULL DEFAULT 0,
      skill_uses INTEGER NOT NULL DEFAULT 0,
      horse INTEGER NOT NULL DEFAULT 0,
      last_played TEXT NOT NULL DEFAULT '',
      online INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE game_state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE daily_news (id INTEGER PRIMARY KEY, day TEXT NOT NULL, text TEXT NOT NULL);
    CREATE TABLE mail (
      id INTEGER PRIMARY KEY, to_id INTEGER NOT NULL, from_name TEXT NOT NULL,
      text TEXT, effect TEXT, created TEXT NOT NULL, read INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE igm_data (
      igm_key TEXT NOT NULL, k TEXT NOT NULL, v TEXT NOT NULL,
      PRIMARY KEY (igm_key, k));
    """
]


def migrate(conn: sqlite3.Connection) -> None:
    """Apply pending migrations idempotently."""
    # Create schema_version table if it doesn't exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            applied_count INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Get current schema version
    cursor = conn.execute("SELECT applied_count FROM schema_version")
    row = cursor.fetchone()
    if row is None:
        applied_count = 0
        conn.execute("INSERT INTO schema_version (applied_count) VALUES (0)")
    else:
        applied_count = row[0]

    # Apply pending migrations
    for i in range(applied_count, len(MIGRATIONS)):
        conn.executescript(MIGRATIONS[i])
        conn.execute("UPDATE schema_version SET applied_count = ?", (i + 1,))

    conn.commit()
