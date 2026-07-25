"""The data layer: one place where SQL lives, one transaction boundary.

Phase 1 of the MySQL move. These tests pin the behaviour the repositories
promise, so phase 2 can swap the engine underneath them and prove nothing
changed.
"""

from __future__ import annotations

import pytest

from pylord import db as db_module
from pylord.data import Database


def _db() -> Database:
    conn = db_module.connect(":memory:")
    db_module.migrate(conn)
    return Database(conn)


def test_game_state_round_trips_and_upserts():
    db = _db()
    assert db.state.get("day") is None
    assert db.state.get("day", "1") == "1"

    db.state.set("day", 3)
    assert db.state.get("day") == "3"
    assert db.state.get_int("day", 1) == 3

    db.state.set("day", 4)  # upsert, not a second row
    assert db.state.get_int("day", 1) == 4

    db.state.delete("day")
    assert db.state.get("day") is None


def test_game_state_int_tolerates_rubbish():
    db = _db()
    db.state.set("day", "not a number")
    assert db.state.get_int("day", 7) == 7


def test_news_is_scoped_to_its_day_and_ordered():
    db = _db()
    db.news.add(2, "first")
    db.news.add(2, "second")
    db.news.add(3, "another day")

    assert db.news.for_day(2) == ["first", "second"]
    assert db.news.for_day("2") == ["first", "second"]  # int or str
    assert db.news.for_day(99) == []


def test_mail_round_trip_with_effect():
    db = _db()
    hero = db.players.create("Hero", "pw", "M")
    db.mail.send(hero.id, "Barak", text="hello", effect={"gold": 5})

    unread = db.mail.unread_for(hero.id)
    assert len(unread) == 1
    assert unread[0]["from_name"] == "Barak"
    assert '"gold": 5' in unread[0]["effect"]

    db.mail.mark_read(unread[0]["id"])
    assert db.mail.unread_for(hero.id) == []


def test_deleting_a_player_frees_their_spouse_and_mail():
    db = _db()
    hero = db.players.create("Hero", "pw", "M")
    spouse = db.players.create("Spouse", "pw", "F")
    spouse.married_to = hero.id
    db.players.save(spouse)
    db.mail.send(hero.id, "Someone", text="hi")

    with db.transaction() as tx:
        tx.mail.delete_for(hero.id)
        tx.players.delete(hero.id)

    assert db.players.get(hero.id) is None
    assert db.players.get(spouse.id).married_to is None
    assert db.mail.unread_for(hero.id) == []


def test_save_in_transaction_does_not_commit_on_its_own():
    """The whole point of the split: this write belongs to the caller's
    unit of work, so a rollback must take it with it."""
    db = _db()
    hero = db.players.create("Hero", "pw", "M")

    hero.gold = 999_999
    db.players.save_in_transaction(hero)
    db.rollback()

    assert db.players.get(hero.id).gold == 500


def test_transaction_rolls_everything_back_together():
    db = _db()
    hero = db.players.create("Hero", "pw", "M")

    with pytest.raises(RuntimeError), db.transaction() as tx:
        tx.players.save_in_transaction(hero)
        tx.mail.send(hero.id, "Someone", text="hi")
        tx.state.set("day", 5)
        hero.gold = 1
        raise RuntimeError("something went wrong mid-turn")

    assert db.mail.unread_for(hero.id) == []
    assert db.state.get("day") is None
    assert db.players.get(hero.id).gold == 500


def test_clear_online_flags_reports_how_many_it_freed():
    db = _db()
    for name in ("A", "B", "C"):
        player = db.players.create(name, "pw", "M")
        if name != "C":
            player.online = 1
            db.players.save(player)

    with db.transaction() as tx:
        assert tx.players.clear_online_flags() == 2

    assert [p.online for p in db.players.all_players()] == [0, 0, 0]


def test_igm_data_is_namespaced_per_igm():
    db = _db()
    db.igm_data.set_raw("mines", "sift:1", "3")
    db.igm_data.set_raw("latrine", "sift:1", "9")

    assert db.igm_data.get_raw("mines", "sift:1") == "3"
    assert db.igm_data.get_raw("latrine", "sift:1") == "9"
    assert db.igm_data.get_raw("mines", "missing") is None

    db.igm_data.delete("mines", "sift:1")
    assert db.igm_data.get_raw("mines", "sift:1") is None
    assert db.igm_data.get_raw("latrine", "sift:1") == "9"
