"""News, List Warriors, Hall of Honors, and Conjugality List tests. See
each scene module's docstring for lord.js line-number citations."""

from __future__ import annotations

from pylord import db
from pylord.engine import npc_state
from pylord.engine.game import GameCtx
from pylord.engine.scenes import conjugality as conjugality_mod
from pylord.engine.scenes import hall as hall_mod
from pylord.engine.scenes import list_warriors as list_mod
from pylord.engine.scenes import news as news_mod
from pylord.models import PlayerRepo
from pylord.terminal import FakeIO
from tests.harness import screen


def _conn():
    conn = db.connect(":memory:")
    db.migrate(conn)
    return conn


def _ctx(conn, player, keys=None):
    repo = PlayerRepo(conn)
    return GameCtx(player=player, repo=repo, io=FakeIO(keys or []), conn=conn)


# -- News -----------------------------------------------------------------


async def test_news_shows_todays_rows():
    conn = _conn()
    repo = PlayerRepo(conn)
    player = repo.create("Hero", "pw", "M")
    with conn:
        conn.execute(
            "INSERT INTO daily_news (day, text) VALUES ('1', 'A dragon was sighted!')"
        )
    ctx = _ctx(conn, player, keys=["c"])
    result = await news_mod.news(ctx)
    assert result == "town"
    text = screen(ctx.io)
    assert "A dragon was sighted!" in text
    assert "Daily Happenings" in text


async def test_news_yesterday_shows_prior_day_rows():
    conn = _conn()
    repo = PlayerRepo(conn)
    player = repo.create("Hero", "pw", "M")
    with conn:
        conn.execute("INSERT INTO game_state (key, value) VALUES ('day', '3')")
        conn.execute(
            "INSERT INTO daily_news (day, text) VALUES ('2', 'Yesterdays event.')"
        )
        conn.execute(
            "INSERT INTO daily_news (day, text) VALUES ('3', 'Todays event.')"
        )
    ctx = _ctx(conn, player, keys=["y", "c"])
    await news_mod.news(ctx)
    text = screen(ctx.io)
    assert "Todays event." in text
    assert "Yesterdays event." in text


async def test_news_yesterday_empty_shows_nothing_happened_message():
    conn = _conn()
    repo = PlayerRepo(conn)
    player = repo.create("Hero", "pw", "M")
    ctx = _ctx(conn, player, keys=["y", "c"])
    await news_mod.news(ctx)
    text = screen(ctx.io)
    assert "nothing of importance happened yesterday" in text


async def test_news_today_again_redisplays():
    conn = _conn()
    repo = PlayerRepo(conn)
    player = repo.create("Hero", "pw", "M")
    with conn:
        conn.execute(
            "INSERT INTO daily_news (day, text) VALUES ('1', 'Only event.')"
        )
    ctx = _ctx(conn, player, keys=["t", "c"])
    await news_mod.news(ctx)
    text = screen(ctx.io)
    assert text.count("Only event.") == 2  # shown once at entry, once via T


# -- List Warriors ----------------------------------------------------------


async def test_list_warriors_ranks_by_experience_descending():
    conn = _conn()
    repo = PlayerRepo(conn)
    low = repo.create("Low", "pw", "M")
    low.exp = 100
    repo.save(low)
    high = repo.create("High", "pw", "M")
    high.exp = 9000
    repo.save(high)
    mid = repo.create("Mid", "pw", "M")
    mid.exp = 500
    repo.save(mid)

    ctx = _ctx(conn, repo.get(low.id), keys=["r"])
    result = await list_mod.list_warriors(ctx)
    assert result == "town"
    text = screen(ctx.io)
    assert text.index("High") < text.index("Mid") < text.index("Low")


async def test_list_warriors_shows_dead_status():
    conn = _conn()
    repo = PlayerRepo(conn)
    dead = repo.create("Deadguy", "pw", "M")
    dead.alive = 0
    repo.save(dead)

    ctx = _ctx(conn, repo.get(dead.id), keys=["r"])
    await list_mod.list_warriors(ctx)
    text = screen(ctx.io)
    assert "Dead" in text


async def test_list_warriors_hall_submenu_routes_to_hall():
    conn = _conn()
    repo = PlayerRepo(conn)
    player = repo.create("Hero", "pw", "M")
    ctx = _ctx(conn, player, keys=["h"])
    result = await list_mod.list_warriors(ctx)
    assert result == "hall"


# -- Hall of Honors -----------------------------------------------------


async def test_hall_of_honors_empty_shows_no_heroes_message():
    conn = _conn()
    repo = PlayerRepo(conn)
    player = repo.create("Hero", "pw", "M")
    ctx = _ctx(conn, player, keys=["x"])
    result = await hall_mod.hall(ctx)
    assert result == "town"
    text = screen(ctx.io)
    assert "no heroes in this realm" in text


async def test_hall_of_honors_lists_dragon_slayers_ranked():
    conn = _conn()
    repo = PlayerRepo(conn)
    one_kill = repo.create("OneKill", "pw", "M")
    one_kill.king_count = 1
    repo.save(one_kill)
    two_kills = repo.create("TwoKills", "pw", "M")
    two_kills.king_count = 2
    repo.save(two_kills)
    no_kills = repo.create("NoKills", "pw", "M")
    repo.save(no_kills)

    ctx = _ctx(conn, repo.get(one_kill.id), keys=["x"])
    await hall_mod.hall(ctx)
    text = screen(ctx.io)
    assert "NoKills" not in text
    assert text.index("TwoKills") < text.index("OneKill")


# -- Conjugality List -----------------------------------------------------


async def test_conjugality_shows_married_pair():
    conn = _conn()
    repo = PlayerRepo(conn)
    a = repo.create("Alice", "pw", "F")
    b = repo.create("Bob", "pw", "M")
    a.married_to = b.id
    b.married_to = a.id
    repo.save(a)
    repo.save(b)

    ctx = _ctx(conn, repo.get(a.id), keys=["x"])
    result = await conjugality_mod.conjugality(ctx)
    assert result == "town"
    text = screen(ctx.io)
    assert "Alice" in text
    assert "Bob" in text


async def test_conjugality_no_one_married_shows_message():
    conn = _conn()
    repo = PlayerRepo(conn)
    player = repo.create("Hero", "pw", "M")
    ctx = _ctx(conn, player, keys=["x"])
    await conjugality_mod.conjugality(ctx)
    text = screen(ctx.io)
    assert "No one is married in this realm" in text


async def test_conjugality_shows_violet_and_seth_marriages():
    conn = _conn()
    repo = PlayerRepo(conn)
    violet_husband = repo.create("VioletsHusband", "pw", "M")
    seth_wife = repo.create("SethsWife", "pw", "F")
    npc_state.set_married_to_violet(conn, violet_husband.id)
    npc_state.set_married_to_seth(conn, seth_wife.id)

    ctx = _ctx(conn, repo.get(violet_husband.id), keys=["x"])
    await conjugality_mod.conjugality(ctx)
    text = screen(ctx.io)
    assert "VioletsHusband" in text
    assert "belongs to" in text
    assert "Violet" in text
    assert "SethsWife" in text
    assert "property of" in text
    assert "Seth Able" in text
