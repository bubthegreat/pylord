"""Inn tests. See pylord/engine/scenes/inn.py's module docstring for
lord.js line-number citations."""

from __future__ import annotations

from pylord import db
from pylord.engine import npc_state
from pylord.engine.game import GameCtx
from pylord.engine.scenes import inn as inn_mod
from pylord.models import PlayerRepo
from pylord.terminal import FakeIO
from tests.harness import play, screen


class _FixedRng:
    """A stand-in for ``random.Random`` that returns a scripted sequence of
    ``randrange()`` results -- deterministic tests for the carry/seduce and
    bard-song probability rolls."""

    def __init__(self, values):
        self._values = list(values)

    def randrange(self, _n):
        return self._values.pop(0)


def _ctx(overrides=None, keys=None, rng=None):
    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)
    player = repo.create("Hero", "pw", "M")
    for key, value in (overrides or {}).items():
        setattr(player, key, value)
    io = FakeIO(keys or [])
    ctx = GameCtx(player=player, repo=repo, io=io, conn=conn)
    if rng is not None:
        ctx.rng = rng
    return ctx


def _female_ctx(overrides=None, keys=None, rng=None):
    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)
    player = repo.create("Heroine", "pw", "F")
    for key, value in (overrides or {}).items():
        setattr(player, key, value)
    io = FakeIO(keys or [])
    ctx = GameCtx(player=player, repo=repo, io=io, conn=conn)
    if rng is not None:
        ctx.rng = rng
    return ctx


async def test_inn_reachable_from_town():
    io, _player = await play(["i", "r", "q"])
    text = screen(io)
    assert "Red Dragon Inn" in text


# -- Violet flirt tiers: exact charm thresholds -----------------------------
# Every tier action ends with a single pause() -- "x" below is just a
# throwaway keypress to satisfy it; "r" is the outer Inn menu's return.


async def test_wink_success_at_threshold_charm_1():
    ctx = _ctx(overrides={"charm": 1, "level": 1, "exp": 0}, keys=["f", "w", "x", "r"])
    await inn_mod.inn(ctx)
    assert ctx.player.exp == 5  # 5 * level(1)
    assert ctx.player.seen_violet == 1


async def test_wink_fails_below_threshold_charm_0_no_penalty():
    ctx = _ctx(
        overrides={"charm": 0, "level": 1, "exp": 0, "hp": 20},
        keys=["f", "w", "x", "r"],
    )
    await inn_mod.inn(ctx)
    assert ctx.player.exp == 0
    assert ctx.player.hp == 20  # wink failure has no HP penalty


async def test_kiss_success_at_threshold_charm_2():
    ctx = _ctx(overrides={"charm": 2, "level": 3, "exp": 0}, keys=["f", "k", "x", "r"])
    await inn_mod.inn(ctx)
    assert ctx.player.exp == 30  # 10 * level(3)


async def test_kiss_fails_below_threshold_loses_hp():
    ctx = _ctx(
        overrides={"charm": 1, "level": 2, "hp": 20, "hp_max": 20},
        keys=["f", "k", "x", "r"],
    )
    await inn_mod.inn(ctx)
    assert ctx.player.hp == 20 - 2  # level(2) * penalty_mult(1)


async def test_peck_threshold_charm_4():
    below = _ctx(overrides={"charm": 3, "level": 1, "hp": 20}, keys=["f", "p", "x", "r"])
    await inn_mod.inn(below)
    assert below.player.hp == 20 - 3  # level(1) * penalty_mult(3)

    at = _ctx(overrides={"charm": 4, "level": 1, "exp": 0}, keys=["f", "p", "x", "r"])
    await inn_mod.inn(at)
    assert at.player.exp == 20


async def test_sit_threshold_charm_8():
    below = _ctx(overrides={"charm": 7, "level": 1, "hp": 20}, keys=["f", "s", "x", "r"])
    await inn_mod.inn(below)
    assert below.player.hp == 20 - 5  # level(1) * penalty_mult(5)

    at = _ctx(overrides={"charm": 8, "level": 1, "exp": 0}, keys=["f", "s", "x", "r"])
    await inn_mod.inn(at)
    assert at.player.exp == 30


async def test_grab_threshold_charm_16():
    below = _ctx(overrides={"charm": 15, "level": 1, "hp": 20}, keys=["f", "g", "x", "r"])
    await inn_mod.inn(below)
    assert below.player.hp == 20 - 10  # level(1) * penalty_mult(10)

    at = _ctx(overrides={"charm": 16, "level": 1, "exp": 0}, keys=["f", "g", "x", "r"])
    await inn_mod.inn(at)
    assert at.player.exp == 40


async def test_hp_never_drops_below_1_on_penalty():
    ctx = _ctx(overrides={"charm": 0, "level": 50, "hp": 5}, keys=["f", "g", "x", "r"])
    await inn_mod.inn(ctx)
    assert ctx.player.hp == 1


# -- Daily flirt gate ---------------------------------------------------


async def test_one_flirt_per_day_gate():
    """After one flirt, seen_violet is set; a second attempt is refused and
    grants no further exp."""
    ctx = _ctx(
        overrides={"charm": 1, "level": 1, "exp": 0}, keys=["f", "w", "x", "f", "r"]
    )
    await inn_mod.inn(ctx)
    assert ctx.player.exp == 5
    assert ctx.player.seen_violet == 1
    text = screen(ctx.io)
    assert "better not go too fast" in text


async def test_female_player_redirected_to_seth_and_gate_untouched():
    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)
    player = repo.create("Heroine", "pw", "F")
    io = FakeIO(["f", "r"])
    ctx = GameCtx(player=player, repo=repo, io=io, conn=conn)
    await inn_mod.inn(ctx)
    text = screen(ctx.io)
    assert "rather flirt with Seth Able" in text
    assert ctx.player.seen_violet == 0


# -- Carry / marriage, and the singleton NPC-marriage race -----------------


async def test_carry_violet_success_grants_exp_and_lays():
    ctx = _ctx(
        overrides={"charm": 40, "level": 1, "exp": 0, "lays": 0},
        keys=["f", "c", "x", "r"],
        rng=_FixedRng([1]),  # randrange(3) == 1 -> success branch
    )
    await inn_mod.inn(ctx)
    assert ctx.player.exp == 40
    assert ctx.player.lays == 1


async def test_carry_violet_below_charm_threshold_drops_hp_to_1():
    ctx = _ctx(overrides={"charm": 10, "level": 5, "hp": 50}, keys=["f", "c", "x", "r"])
    await inn_mod.inn(ctx)
    assert ctx.player.hp == 1


async def test_carry_violet_success_writes_news_row():
    """Post-review: reference/lord.js:9578 (`log_line('...Got laid by
    Violet!')`) was missing from the success branch's port."""
    ctx = _ctx(
        overrides={"charm": 40, "level": 1},
        keys=["f", "c", "x", "r"],
        rng=_FixedRng([1]),  # success branch
    )
    await inn_mod.inn(ctx)
    row = ctx.conn.execute("SELECT text FROM daily_news").fetchone()
    assert row is not None
    assert "Got laid by" in row["text"]
    assert "Violet" in row["text"]


async def test_carry_violet_appalled_when_married_writes_news_row():
    """Post-review: reference/lord.js:9564 (`log_line('...calls X a dirty
    old man/bastard!')`) was missing from the "married" branch's port."""
    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)
    spouse = repo.create("Spouse", "pw", "F")
    player = repo.create("Married", "pw", "M")
    player.married_to = spouse.id
    ctx = GameCtx(player=player, repo=repo, io=FakeIO(["f", "c", "x", "r"]), conn=conn)
    await inn_mod.inn(ctx)
    row = ctx.conn.execute("SELECT text FROM daily_news").fetchone()
    assert row is not None
    assert "Violet" in row["text"]
    assert "calls" in row["text"]


async def test_seduce_seth_success_writes_news_row():
    """Post-review: reference/lord.js:8612 (`log_line('...got laid by Seth
    Able!')`) was missing from the success branch's port."""
    ctx = _female_ctx(
        overrides={"charm": 40, "level": 1},
        keys=["h", "f", "c", "x", "r", "r"],
        rng=_FixedRng([2]),  # randrange(4) == 2 -> success branch
    )
    await inn_mod.inn(ctx)
    row = ctx.conn.execute("SELECT text FROM daily_news").fetchone()
    assert row is not None
    assert "got laid by" in row["text"]
    assert "Seth Able" in row["text"]


async def test_seduce_seth_appalled_when_married_writes_news_row():
    """Post-review: reference/lord.js:8596 (`log_line('...calls X a filthy
    harlot/slut!')`) was missing from the "married" branch's port."""
    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)
    spouse = repo.create("Spouse", "pw", "M")
    player = repo.create("Married", "pw", "F")
    player.married_to = spouse.id
    ctx = GameCtx(
        player=player, repo=repo, io=FakeIO(["h", "f", "c", "x", "r", "r"]), conn=conn
    )
    await inn_mod.inn(ctx)
    row = ctx.conn.execute("SELECT text FROM daily_news").fetchone()
    assert row is not None
    assert "Seth Able" in row["text"]
    assert "calls" in row["text"]


async def test_marriage_below_charm_100_refused():
    ctx = _ctx(overrides={"charm": 50}, keys=["f", "m", "x", "r"])
    await inn_mod.inn(ctx)
    assert npc_state.married_to_violet(ctx.conn) == npc_state.NONE
    assert ctx.player.seen_violet == 1


async def test_marriage_at_charm_100_succeeds_and_grants_exp():
    ctx = _ctx(overrides={"charm": 100, "level": 2, "exp": 0}, keys=["f", "m", "x", "r"])
    await inn_mod.inn(ctx)
    assert npc_state.married_to_violet(ctx.conn) == ctx.player.id
    assert ctx.player.exp == 2000  # 1000 * level(2)
    assert ctx.player.seen_violet == 0  # marriage resets the daily gate


async def test_already_married_to_violet_blocks_second_players_flirt():
    """Once anyone marries Violet, *every* subsequent flirt attempt (even
    from a different player) hits the "Grizelda" gate before ever reaching
    the marriage ladder -- reference/lord.js:9832-9877 checks
    ``state.married_to_violet`` unconditionally, before any per-player
    identity check."""
    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)
    first = repo.create("First", "pw", "M")
    first.charm = 100
    second = repo.create("Second", "pw", "M")
    second.charm = 100

    ctx1 = GameCtx(player=first, repo=repo, io=FakeIO(["f", "m", "x", "r"]), conn=conn)
    await inn_mod.inn(ctx1)
    assert npc_state.married_to_violet(conn) == first.id

    ctx2 = GameCtx(player=second, repo=repo, io=FakeIO(["f", "x", "r"]), conn=conn)
    await inn_mod.inn(ctx2)
    assert npc_state.married_to_violet(conn) == first.id  # unchanged
    assert "Grizelda" in screen(ctx2.io)


async def test_marry_npc_race_someone_else_wins_meanwhile():
    """Direct test of the race-condition branch inside ``_marry_npc``
    (reference/lord.js:9459-9468) -- unreachable through ``_flirt``'s own
    call path in a single-threaded test (its own married-NPC gate always
    intercepts first, see the test above), so exercised at the function
    level exactly like a genuine multi-connection race would."""
    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)
    winner = repo.create("Winner", "pw", "M")
    loser = repo.create("Loser", "pw", "M")
    loser.charm = 100
    npc_state.set_married_to_violet(conn, winner.id)

    ctx = GameCtx(player=loser, repo=repo, io=FakeIO(["x"]), conn=conn)
    await inn_mod._marriage_violet(ctx)
    assert npc_state.married_to_violet(conn) == winner.id  # unchanged
    assert "walking out" in screen(ctx.io)


async def test_flirt_blocked_while_someone_else_married_to_violet():
    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)
    first = repo.create("First", "pw", "M")
    npc_state.set_married_to_violet(conn, first.id)
    second = repo.create("Second", "pw", "M")

    ctx = GameCtx(player=second, repo=repo, io=FakeIO(["f", "x", "r"]), conn=conn)
    await inn_mod.inn(ctx)
    assert "Grizelda" in screen(ctx.io)
    assert ctx.player.seen_violet == 1


# -- Room rental --------------------------------------------------------


async def test_rent_room_costs_400_per_level_and_sets_at_inn():
    ctx = _ctx(overrides={"level": 3, "gold": 5000, "at_inn": 0}, keys=["g", "y"])
    result = await inn_mod.inn(ctx)
    assert result is None  # ends the session, like lord.js's exit(0)
    assert ctx.player.at_inn == 1
    assert ctx.player.gold == 5000 - 1200  # 400 * level(3)


async def test_rent_room_declined_leaves_gold_and_at_inn_untouched():
    ctx = _ctx(
        overrides={"level": 1, "gold": 500, "at_inn": 0}, keys=["g", "n", "r"]
    )
    await inn_mod.inn(ctx)
    assert ctx.player.at_inn == 0
    assert ctx.player.gold == 500


async def test_rent_room_refused_when_gold_insufficient():
    ctx = _ctx(
        overrides={"level": 5, "gold": 10, "at_inn": 0}, keys=["g", "y", "r"]
    )
    await inn_mod.inn(ctx)
    assert ctx.player.at_inn == 0
    assert ctx.player.gold == 10


async def test_rent_room_free_above_charm_99():
    ctx = _ctx(
        overrides={"level": 5, "gold": 100, "charm": 100, "at_inn": 0},
        keys=["g", "y"],
    )
    result = await inn_mod.inn(ctx)
    assert result is None
    assert ctx.player.gold == 100  # unchanged -- free room
    assert ctx.player.at_inn == 1


async def test_entering_inn_clears_at_inn():
    ctx = _ctx(overrides={"at_inn": 1}, keys=["r"])
    await inn_mod.inn(ctx)
    assert ctx.player.at_inn == 0


# -- Bard song ------------------------------------------------------------


async def test_bard_song_once_per_day_gate():
    ctx = _ctx(
        overrides={"seen_bard": 0, "forest_fights": 10},
        keys=["h", "a", "x", "r", "q"],
        rng=_FixedRng([0, 3]),  # odd branch skipped (0 != 1); gender-M outcome 3
    )
    await inn_mod.inn(ctx)
    assert ctx.player.seen_bard == 1
    assert ctx.player.forest_fights == 12  # +2, "glad you are male" outcome
    text = screen(ctx.io)
    assert "throat is too dry" not in text


async def test_bard_song_refuses_second_time_same_day():
    ctx = _ctx(overrides={"seen_bard": 1}, keys=["h", "a", "x", "r", "q"])
    await inn_mod.inn(ctx)
    assert "throat is too dry" in screen(ctx.io)
