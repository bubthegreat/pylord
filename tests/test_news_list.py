"""News, List Warriors, Hall of Honors, and Conjugality List tests. See
each scene module's docstring for lord.js line-number citations."""

from __future__ import annotations

from pylord import data
from pylord.engine import npc_state
from pylord.engine.game import GameCtx
from pylord.engine.scenes import conjugality as conjugality_mod
from pylord.engine.scenes import hall as hall_mod
from pylord.engine.scenes import list_warriors as list_mod
from pylord.engine.scenes import news as news_mod
from pylord.terminal import FakeIO
from tests.harness import screen


async def _conn():
    database = await data.connect(":memory:")
    return database


def _ctx(database, player, keys=None):
    return GameCtx(player=player, db=database, io=FakeIO(keys or []))


# -- News -----------------------------------------------------------------


async def test_news_shows_todays_rows():
    database = await _conn()
    repo = database.players
    player = await repo.create("Hero", "pw", "M")
    await database.news.add(1, "A dragon was sighted!")
    ctx = _ctx(database, player, keys=["c"])
    result = await news_mod.news(ctx)
    assert result == "town"
    text = screen(ctx.io)
    assert "A dragon was sighted!" in text
    assert "Daily Happenings" in text


async def test_news_yesterday_shows_prior_day_rows():
    database = await _conn()
    repo = database.players
    player = await repo.create("Hero", "pw", "M")
    await database.state.set("day", 3)
    await database.news.add(2, "Yesterdays event.")
    await database.news.add(3, "Todays event.")
    ctx = _ctx(database, player, keys=["y", "c"])
    await news_mod.news(ctx)
    text = screen(ctx.io)
    assert "Todays event." in text
    assert "Yesterdays event." in text


async def test_news_yesterday_empty_shows_nothing_happened_message():
    database = await _conn()
    repo = database.players
    player = await repo.create("Hero", "pw", "M")
    ctx = _ctx(database, player, keys=["y", "c"])
    await news_mod.news(ctx)
    text = screen(ctx.io)
    assert "nothing of importance happened yesterday" in text


async def test_news_today_again_redisplays():
    database = await _conn()
    repo = database.players
    player = await repo.create("Hero", "pw", "M")
    await database.news.add(1, "Only event.")
    ctx = _ctx(database, player, keys=["t", "c"])
    await news_mod.news(ctx)
    text = screen(ctx.io)
    assert text.count("Only event.") == 2  # shown once at entry, once via T


# -- List Warriors ----------------------------------------------------------


async def test_list_warriors_ranks_by_experience_descending():
    database = await _conn()
    repo = database.players
    low = await repo.create("Low", "pw", "M")
    low.exp = 100
    await repo.save(low)
    high = await repo.create("High", "pw", "M")
    high.exp = 9000
    await repo.save(high)
    mid = await repo.create("Mid", "pw", "M")
    mid.exp = 500
    await repo.save(mid)

    ctx = _ctx(database, await repo.get(low.id), keys=["r"])
    result = await list_mod.list_warriors(ctx)
    assert result == "town"
    text = screen(ctx.io)
    assert text.index("High") < text.index("Mid") < text.index("Low")


async def test_list_warriors_shows_dead_status():
    database = await _conn()
    repo = database.players
    dead = await repo.create("Deadguy", "pw", "M")
    dead.alive = 0
    await repo.save(dead)

    ctx = _ctx(database, await repo.get(dead.id), keys=["r"])
    await list_mod.list_warriors(ctx)
    text = screen(ctx.io)
    assert "Dead" in text


async def test_list_warriors_hall_submenu_routes_to_hall():
    database = await _conn()
    repo = database.players
    player = await repo.create("Hero", "pw", "M")
    ctx = _ctx(database, player, keys=["h"])
    result = await list_mod.list_warriors(ctx)
    assert result == "hall"


# -- Hall of Honors -----------------------------------------------------


async def test_hall_of_honors_empty_shows_no_heroes_message():
    database = await _conn()
    repo = database.players
    player = await repo.create("Hero", "pw", "M")
    ctx = _ctx(database, player, keys=["x"])
    result = await hall_mod.hall(ctx)
    assert result == "town"
    text = screen(ctx.io)
    assert "no heroes in this realm" in text


async def test_hall_of_honors_lists_dragon_slayers_ranked():
    database = await _conn()
    repo = database.players
    one_kill = await repo.create("OneKill", "pw", "M")
    one_kill.king_count = 1
    await repo.save(one_kill)
    two_kills = await repo.create("TwoKills", "pw", "M")
    two_kills.king_count = 2
    await repo.save(two_kills)
    no_kills = await repo.create("NoKills", "pw", "M")
    await repo.save(no_kills)

    ctx = _ctx(database, await repo.get(one_kill.id), keys=["x"])
    await hall_mod.hall(ctx)
    text = screen(ctx.io)
    assert "NoKills" not in text
    assert text.index("TwoKills") < text.index("OneKill")


# -- Conjugality List -----------------------------------------------------


async def test_conjugality_shows_married_pair():
    database = await _conn()
    repo = database.players
    a = await repo.create("Alice", "pw", "F")
    b = await repo.create("Bob", "pw", "M")
    a.married_to = b.id
    b.married_to = a.id
    await repo.save(a)
    await repo.save(b)

    ctx = _ctx(database, await repo.get(a.id), keys=["x"])
    result = await conjugality_mod.conjugality(ctx)
    assert result == "town"
    text = screen(ctx.io)
    assert "Alice" in text
    assert "Bob" in text


async def test_conjugality_no_one_married_shows_message():
    database = await _conn()
    repo = database.players
    player = await repo.create("Hero", "pw", "M")
    ctx = _ctx(database, player, keys=["x"])
    await conjugality_mod.conjugality(ctx)
    text = screen(ctx.io)
    assert "No one is married in this realm" in text


async def test_conjugality_shows_violet_and_seth_marriages():
    database = await _conn()
    repo = database.players
    violet_husband = await repo.create("VioletsHusband", "pw", "M")
    seth_wife = await repo.create("SethsWife", "pw", "F")
    await npc_state.set_married_to_violet(database, violet_husband.id)
    await npc_state.set_married_to_seth(database, seth_wife.id)

    ctx = _ctx(database, await repo.get(violet_husband.id), keys=["x"])
    await conjugality_mod.conjugality(ctx)
    text = screen(ctx.io)
    assert "VioletsHusband" in text
    assert "belongs to" in text
    assert "Violet" in text
    assert "SethsWife" in text
    assert "property of" in text
    assert "Seth Able" in text
