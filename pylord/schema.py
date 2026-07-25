"""The realm's tables, described once for every database we run on.

The schema used to be SQLite DDL in a list of migration strings, which was
fine while SQLite was the only target. It is expressed as SQLAlchemy Core
tables here so the same definition produces correct DDL on SQLite (tests,
local play) and MySQL (the homelab), rather than two hand-written copies
drifting apart.

Column types are chosen for that portability:

* ``Integer`` booleans, not ``Boolean`` -- the game has always stored 0/1
  and the CLI and screens read them as ints.
* ``String`` lengths everywhere, because MySQL requires a length on an
  indexed/unique column and SQLite ignores it.
* Player names are unique case-insensitively. SQLite gets that from
  ``COLLATE NOCASE``; MySQL's default ``utf8mb4_0900_ai_ci`` collation is
  already case-insensitive, so the constraint means the same thing on both.
"""

from __future__ import annotations

from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
)

metadata = MetaData()

def _name_column() -> Column:
    """Player names are unique *case-insensitively*: the realm has always
    refused a second "hero" when "Hero" exists.

    MySQL's default collation (``utf8mb4_0900_ai_ci``) is already
    case-insensitive; SQLite compares case-sensitively unless the column
    says otherwise, so it gets ``COLLATE NOCASE`` through a dialect
    variant. Losing this is a silent regression -- two players with the
    same name -- so it is pinned by a test.
    """
    return Column(
        "name",
        String(64).with_variant(String(64, collation="NOCASE"), "sqlite"),
        nullable=False,
        unique=True,
    )


players = Table(
    "players",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    _name_column(),
    Column("password_hash", String(255), nullable=False),
    Column("gender", String(1), nullable=False, server_default="M"),
    Column("class_type", Integer, nullable=False, server_default="1"),
    Column("level", Integer, nullable=False, server_default="1"),
    Column("exp", Integer, nullable=False, server_default="1"),
    Column("hp", Integer, nullable=False, server_default="20"),
    Column("hp_max", Integer, nullable=False, server_default="20"),
    Column("strength", Integer, nullable=False, server_default="10"),
    Column("defense", Integer, nullable=False, server_default="1"),
    Column("charm", Integer, nullable=False, server_default="1"),
    Column("gold", Integer, nullable=False, server_default="500"),
    Column("bank", Integer, nullable=False, server_default="0"),
    Column("gems", Integer, nullable=False, server_default="0"),
    Column("weapon_num", Integer, nullable=False, server_default="1"),
    Column("armor_num", Integer, nullable=False, server_default="1"),
    Column("forest_fights", Integer, nullable=False, server_default="15"),
    Column("player_fights", Integer, nullable=False, server_default="3"),
    Column("flirts_today", Integer, nullable=False, server_default="0"),
    Column("alive", Integer, nullable=False, server_default="1"),
    Column("at_inn", Integer, nullable=False, server_default="0"),
    Column("seen_master", Integer, nullable=False, server_default="0"),
    Column("seen_dragon", Integer, nullable=False, server_default="0"),
    Column("seen_violet", Integer, nullable=False, server_default="0"),
    Column("seen_bard", Integer, nullable=False, server_default="0"),
    Column("married_to", Integer, nullable=True),
    Column("lays", Integer, nullable=False, server_default="0"),
    Column("kids", Integer, nullable=False, server_default="0"),
    Column("king_count", Integer, nullable=False, server_default="0"),
    Column("skill_dk", Integer, nullable=False, server_default="0"),
    Column("skill_my", Integer, nullable=False, server_default="0"),
    Column("skill_th", Integer, nullable=False, server_default="0"),
    Column("skill_uses", Integer, nullable=False, server_default="0"),
    Column("horse", Integer, nullable=False, server_default="0"),
    Column("last_played", String(32), nullable=False, server_default=""),
    Column("online", Integer, nullable=False, server_default="0"),
    Column("high_spirits", Integer, nullable=False, server_default="0"),
    Column("weird", Integer, nullable=False, server_default="0"),
    Column("has_fairy", Integer, nullable=False, server_default="0"),
    Column("fairy_lore", Integer, nullable=False, server_default="0"),
    Column("amulet", Integer, nullable=False, server_default="0"),
    Column("pvp_kills", Integer, nullable=False, server_default="0"),
    Column("magically_delicious", Integer, nullable=False, server_default="0"),
    Column("divorced", Integer, nullable=False, server_default="0"),
    Column("mastered_dk", Integer, nullable=False, server_default="0"),
    Column("mastered_my", Integer, nullable=False, server_default="0"),
    Column("mastered_th", Integer, nullable=False, server_default="0"),
    Column("fight_bonus", Integer, nullable=False, server_default="0"),
    Column("endurance_bought", Integer, nullable=False, server_default="0"),
    Column("fights_regen_at", String(40), nullable=False, server_default=""),
    # What the old man in the Dark Cloak Tavern will tell other players
    # about you (recorddefs.js:329-345, two lines the player writes
    # themselves). Empty means he has heard nothing -- lord.js keeps a
    # separate `has_des` flag for that, which two empty strings say just
    # as well.
    Column("description1", String(255), nullable=False, server_default=""),
    Column("description2", String(255), nullable=False, server_default=""),
)

game_state = Table(
    "game_state",
    metadata,
    Column("key", String(64), primary_key=True),
    Column("value", Text, nullable=False),
)

daily_news = Table(
    "daily_news",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("day", String(32), nullable=False, index=True),
    Column("text", Text, nullable=False),
)

mail = Table(
    "mail",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("to_id", Integer, nullable=False, index=True),
    Column("from_name", String(64), nullable=False),
    Column("text", Text, nullable=True),
    Column("effect", Text, nullable=True),
    Column("created", String(40), nullable=False),
    Column("read", Integer, nullable=False, server_default="0"),
)

igm_data = Table(
    "igm_data",
    metadata,
    Column("igm_key", String(64), nullable=False),
    Column("k", String(128), nullable=False),
    Column("v", Text, nullable=False),
    PrimaryKeyConstraint("igm_key", "k"),
)

#: Records which schema revision a database is on, so a future change can
#: tell an empty database from an old one.
schema_version = Table(
    "schema_version",
    metadata,
    Column("applied_count", Integer, nullable=False, server_default="0"),
)

#: Bumped whenever the tables above change in a way an existing database
#: has to be migrated for.
CURRENT_VERSION = 5
