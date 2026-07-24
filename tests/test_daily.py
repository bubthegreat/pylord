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


# --- Post-audit fixes: seen_dragon, per-player guard, wake_up extras -------


def test_seen_dragon_is_reset_so_the_dragon_is_a_daily_event():
    """reference/lord.js:5436. Without this the Dragon can only ever be
    fought once per character."""
    conn, repo = _setup()
    p = repo.create("Hero", "pw", "M")
    p.seen_dragon = 1
    repo.save(p)

    daily.maintenance(conn, {}, "2026-07-24")

    assert repo.get(p.id).seen_dragon == 0


def test_second_pass_on_the_same_day_does_not_pay_interest_twice():
    """The per-player last_played guard: even if the global marker is
    cleared (a crashed pass, a session that spanned the rollover), a
    player already reset today is skipped."""
    conn, repo = _setup()
    p = repo.create("Rich", "pw", "M")
    p.bank = 1000
    repo.save(p)

    daily.maintenance(conn, {}, "2026-07-24")
    assert repo.get(p.id).bank == 1100

    conn.execute("DELETE FROM game_state WHERE key = 'last_maint'")
    conn.commit()
    daily.maintenance(conn, {}, "2026-07-24")

    assert repo.get(p.id).bank == 1100  # not 1210
    assert repo.get(p.id).last_played == "2026-07-24"


def test_kids_and_horse_add_forest_fights():
    """reference/lord.js:5490-5505 (kids) and :5575-5582 (horse)."""
    conn, repo = _setup()
    p = repo.create("Parent", "pw", "F")
    p.kids = 3
    p.horse = 1
    repo.save(p)

    daily.maintenance(conn, {}, "2026-07-24")

    # 15 (config default) + 3 kids = 18, then +18//4 = 4 for the horse
    assert repo.get(p.id).forest_fights == 22


def test_high_spirits_and_weird_are_rolled():
    """reference/lord.js:5565-5573 and :5433-5435."""

    class _Rng:
        """random(3) -> 2 (high spirits), random(5) -> 1 (weird), then the
        pregnancy roll misses."""

        def randrange(self, n):
            return {3: 2, 5: 1}.get(n, 0)

    conn, repo = _setup()
    p = repo.create("Hero", "pw", "M")

    daily.maintenance(conn, {}, "2026-07-24", rng=_Rng())

    reloaded = repo.get(p.id)
    assert reloaded.high_spirits == 1
    assert reloaded.weird == 1


def test_pregnancy_adds_a_kid_and_a_news_line():
    """reference/lord.js:5595-5597 -> have_baby() (:5180-5312)."""

    class _Rng:
        """high spirits, no weird event, then random(34) -> 10 (i.e. 11),
        random(20) -> 0 (the baby lives), random(2) -> 0 (a boy)."""

        def __init__(self):
            self.calls = []

        def randrange(self, n):
            self.calls.append(n)
            return {3: 2, 5: 0, 34: 10, 20: 0, 2: 0}[n]

    conn, repo = _setup()
    mother = repo.create("Mother", "pw", "F")
    mother.lays = 4
    repo.save(mother)

    daily.maintenance(conn, {}, "2026-07-24", rng=_Rng())

    assert repo.get(mother.id).kids == 1
    row = conn.execute("SELECT text FROM daily_news").fetchone()
    assert row is not None and "gives birth to a boy" in row["text"]
