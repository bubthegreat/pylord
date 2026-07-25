import pytest

from pylord import data
from pylord.models import Player, hash_password, verify_password


@pytest.fixture
async def database(tmp_path):
    return await data.connect(str(tmp_path / "g.db"))


@pytest.fixture
async def repo(database):
    return database.players


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


async def test_create_and_get_by_name_roundtrip(repo):
    created = await repo.create("Zaphod", "hunter2", "M")
    assert isinstance(created, Player)
    assert created.id is not None
    assert created.name == "Zaphod"
    assert created.gender == "M"

    fetched = await repo.get_by_name("zaphod")  # case-insensitive
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.name == "Zaphod"


async def test_get_by_id_roundtrip(repo):
    created = await repo.create("Ford", "towel", "M")
    fetched = await repo.get(created.id)
    assert fetched is not None
    assert fetched.name == "Ford"


async def test_get_returns_none_for_missing_id(repo):
    assert await repo.get(9999) is None


async def test_get_by_name_returns_none_for_missing_name(repo):
    assert await repo.get_by_name("nobody") is None


async def test_check_password_wrong_password_returns_none(repo):
    await repo.create("Trillian", "correcthorse", "F")
    assert await repo.check_password("Trillian", "wrongpassword") is None


async def test_check_password_correct_password_returns_player(repo):
    await repo.create("Trillian", "correcthorse", "F")
    result = await repo.check_password("Trillian", "correcthorse")
    assert result is not None
    assert result.name == "Trillian"


async def test_check_password_unknown_name_returns_none(repo):
    assert await repo.check_password("Nobody", "whatever") is None


async def test_save_persists_gold_change(repo):
    created = await repo.create("Arthur", "dontpanic", "M")
    created.gold = 12345
    await repo.save(created)

    fetched = await repo.get(created.id)
    assert fetched.gold == 12345


async def test_create_duplicate_name_case_insensitive_raises_value_error(repo):
    await repo.create("Marvin", "paranoid", "M")
    with pytest.raises(ValueError):
        await repo.create("marvin", "otherpassword", "M")


async def test_all_players_returns_all(repo):
    await repo.create("A", "pw1", "M")
    await repo.create("B", "pw2", "F")
    players = await repo.all_players()
    names = {p.name for p in players}
    assert names == {"A", "B"}
