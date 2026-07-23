import pytest

from pylord import db
from pylord.models import Player, PlayerRepo, hash_password, verify_password


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "g.db")
    db.migrate(c)
    return c


@pytest.fixture
def repo(conn):
    return PlayerRepo(conn)


def test_hash_and_verify_password_roundtrip():
    hashed = hash_password("hunter2")
    assert hashed.startswith("scrypt$")
    parts = hashed.split("$")
    assert len(parts) == 3
    assert verify_password("hunter2", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_hash_password_uses_random_salt():
    a = hash_password("hunter2")
    b = hash_password("hunter2")
    assert a != b  # different salts -> different hashes


def test_create_and_get_by_name_roundtrip(repo):
    created = repo.create("Zaphod", "hunter2", "M")
    assert isinstance(created, Player)
    assert created.id is not None
    assert created.name == "Zaphod"
    assert created.gender == "M"

    fetched = repo.get_by_name("zaphod")  # case-insensitive
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.name == "Zaphod"


def test_get_by_id_roundtrip(repo):
    created = repo.create("Ford", "towel", "M")
    fetched = repo.get(created.id)
    assert fetched is not None
    assert fetched.name == "Ford"


def test_get_returns_none_for_missing_id(repo):
    assert repo.get(9999) is None


def test_get_by_name_returns_none_for_missing_name(repo):
    assert repo.get_by_name("nobody") is None


def test_check_password_wrong_password_returns_none(repo):
    repo.create("Trillian", "correcthorse", "F")
    assert repo.check_password("Trillian", "wrongpassword") is None


def test_check_password_correct_password_returns_player(repo):
    repo.create("Trillian", "correcthorse", "F")
    result = repo.check_password("Trillian", "correcthorse")
    assert result is not None
    assert result.name == "Trillian"


def test_check_password_unknown_name_returns_none(repo):
    assert repo.check_password("Nobody", "whatever") is None


def test_save_persists_gold_change(repo):
    created = repo.create("Arthur", "dontpanic", "M")
    created.gold = 12345
    repo.save(created)

    fetched = repo.get(created.id)
    assert fetched.gold == 12345


def test_create_duplicate_name_case_insensitive_raises_value_error(repo):
    repo.create("Marvin", "paranoid", "M")
    with pytest.raises(ValueError):
        repo.create("marvin", "otherpassword", "M")


def test_all_players_returns_all(repo):
    repo.create("A", "pw1", "M")
    repo.create("B", "pw2", "F")
    players = repo.all_players()
    names = {p.name for p in players}
    assert names == {"A", "B"}
