"""Tests for pylord.engine.daily -- see the module for lord.js line-number
citations behind every formula ported here."""

from __future__ import annotations

from pylord import db
from pylord.engine import daily
from pylord.models import PlayerRepo


def _setup():
    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)
    return conn, repo


def test_maintenance_resets_daily_counters_and_resurrects():
    conn, repo = _setup()
    p = repo.create("Hero", "pw", "M")
    p.forest_fights = 0
    p.player_fights = 0
    p.flirts_today = 5
    p.seen_master = 1
    p.alive = 0
    p.hp = 0
    p.hp_max = 50
    repo.save(p)

    daily.maintenance(conn, {"game": {}}, "2026-07-23")

    reloaded = repo.get(p.id)
    assert reloaded.forest_fights == 15
    assert reloaded.player_fights == 3
    assert reloaded.flirts_today == 0
    assert reloaded.seen_master == 0
    assert reloaded.alive == 1
    assert reloaded.hp == 50


def test_maintenance_respects_configured_daily_fight_counts():
    conn, repo = _setup()
    p = repo.create("Hero", "pw", "M")
    repo.save(p)

    daily.maintenance(
        conn,
        {"game": {"forest_fights_per_day": 20, "player_fights_per_day": 5}},
        "2026-07-23",
    )

    reloaded = repo.get(p.id)
    assert reloaded.forest_fights == 20
    assert reloaded.player_fights == 5


def test_maintenance_pays_ten_percent_bank_interest():
    conn, repo = _setup()
    p = repo.create("Hero", "pw", "M")
    p.bank = 1000
    repo.save(p)

    daily.maintenance(conn, {}, "2026-07-23")

    assert repo.get(p.id).bank == 1100  # reference/lord.js:5507-5517


def test_maintenance_caps_bank_at_two_billion():
    conn, repo = _setup()
    p = repo.create("Hero", "pw", "M")
    p.bank = 1_999_999_999
    repo.save(p)

    daily.maintenance(conn, {}, "2026-07-23")

    assert repo.get(p.id).bank == 2_000_000_000


def test_maintenance_runs_interest_exactly_once_per_date():
    conn, repo = _setup()
    p = repo.create("Hero", "pw", "M")
    p.bank = 1000
    repo.save(p)

    daily.maintenance(conn, {}, "2026-07-23")
    daily.maintenance(conn, {}, "2026-07-23")  # same date: no-op

    assert repo.get(p.id).bank == 1100  # not 1210


def test_maintenance_runs_again_on_a_new_date():
    conn, repo = _setup()
    p = repo.create("Hero", "pw", "M")
    p.bank = 1000
    repo.save(p)

    daily.maintenance(conn, {}, "2026-07-23")
    daily.maintenance(conn, {}, "2026-07-24")

    assert repo.get(p.id).bank == 1210


def test_maintenance_increments_day_from_existing_value():
    conn, _repo = _setup()
    conn.execute("INSERT INTO game_state (key, value) VALUES ('day', '7')")

    daily.maintenance(conn, {}, "2026-07-23")

    row = conn.execute("SELECT value FROM game_state WHERE key = 'day'").fetchone()
    assert row["value"] == "8"


def test_maintenance_defaults_day_to_two_when_unset():
    conn, _repo = _setup()

    daily.maintenance(conn, {}, "2026-07-23")

    row = conn.execute("SELECT value FROM game_state WHERE key = 'day'").fetchone()
    assert row["value"] == "2"


def test_maintenance_sets_last_maint_marker():
    conn, _repo = _setup()

    daily.maintenance(conn, {}, "2026-07-23")

    row = conn.execute(
        "SELECT value FROM game_state WHERE key = 'last_maint'"
    ).fetchone()
    assert row["value"] == "2026-07-23"


def test_skill_uses_death_knight_and_thief_use_rank_over_four_plus_one():
    conn, repo = _setup()
    dk = repo.create("DK", "pw", "M")
    dk.class_type = 1
    dk.skill_dk = 9
    repo.save(dk)

    th = repo.create("Th", "pw", "M")
    th.class_type = 3
    th.skill_th = 9
    repo.save(th)

    daily.maintenance(conn, {}, "2026-07-23")

    assert repo.get(dk.id).skill_uses == 9 // 4 + 1  # reference/lord.js:5449, 5462
    assert repo.get(th.id).skill_uses == 9 // 4 + 1  # reference/lord.js:5456, 5468


def test_skill_uses_mystical_uses_rank_plus_one_no_division():
    conn, repo = _setup()
    my = repo.create("My", "pw", "M")
    my.class_type = 2
    my.skill_my = 9
    repo.save(my)

    daily.maintenance(conn, {}, "2026-07-23")

    assert repo.get(my.id).skill_uses == 9 + 1  # reference/lord.js:5454, 5465


def test_skill_uses_baseline_is_one_even_with_zero_rank():
    conn, repo = _setup()
    p = repo.create("Hero", "pw", "M")
    p.class_type = 1
    p.skill_dk = 0
    repo.save(p)

    daily.maintenance(conn, {}, "2026-07-23")

    assert repo.get(p.id).skill_uses == 1
