"""IGM plugin framework tests (Task 12).

Covers loader discovery + skip/toggle behavior, the guardrailed
``IgmContext`` surface (PlayerView validation, per-key store isolation,
buffered news/mail), the forest "Other Places" visit protocol's
transactional rollback on a crashing IGM, registry collection helpers, and
daily-maintenance exception containment.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from pylord import db
from pylord.engine.game import GameCtx
from pylord.hooks import IGM, ForestEvent, IgmContext, IgmViolation
from pylord.models import PlayerRepo
from pylord.terminal import ConnectionClosed, FakeIO
from tests.igm_contract import contract_check

_FIXTURES = Path(__file__).parent / "fixtures"
_IGMS_DIR = _FIXTURES / "igms"
_DUP_DIR = _FIXTURES / "igms_dup"


# --- helpers ----------------------------------------------------------


def _db():
    conn = db.connect(":memory:")
    db.migrate(conn)
    return conn, PlayerRepo(conn)


def _ctx(conn, repo, player, keys=None, igms=None):
    io = FakeIO(keys or [])
    ctx = GameCtx(player=player, repo=repo, io=io, conn=conn, rng=random.Random(0))
    ctx.igms = igms
    return ctx


# --- discovery / registry --------------------------------------------


def test_discover_finds_sample_igm():
    from pylord import igm_loader

    reg = igm_loader.discover(_IGMS_DIR, {})
    keys = {i.key for i in reg.enabled}
    assert "sample" in keys


def test_discover_skips_broken_modules(caplog):
    from pylord import igm_loader

    with caplog.at_level("WARNING", logger="pylord.igm"):
        reg = igm_loader.discover(_IGMS_DIR, {})
    # broken_import + no_subclass never make it into the registry ...
    assert all(i.key == "sample" for i in reg.enabled)
    # ... and the loader survived and logged rather than raising.
    assert caplog.records


def test_discover_missing_dir_returns_empty():
    from pylord import igm_loader

    reg = igm_loader.discover(_FIXTURES / "does_not_exist", {})
    assert reg.enabled == []


def test_config_disables_igm_absent_from_other_places():
    from pylord import igm_loader

    reg = igm_loader.discover(_IGMS_DIR, {"igms": {"sample": False}})
    assert all(i.key != "sample" for i in reg.other_places())


def test_duplicate_key_second_skipped():
    from pylord import igm_loader

    reg = igm_loader.discover(_DUP_DIR, {})
    assert len([i for i in reg.enabled if i.key == "dup"]) == 1


def test_other_places_sorted_by_name():
    from pylord import igm_loader

    reg = igm_loader.discover(_IGMS_DIR, {})
    names = [i.name for i in reg.other_places()]
    assert names == sorted(names)


def test_registry_forest_events_collection():
    from pylord import igm_loader

    async def _run(ctx):
        return None

    class EventIGM(IGM):
        key = "ev"
        name = "Eventful"
        default_enabled = True

        async def enter(self, ctx):
            pass

        def forest_event(self, rng):
            return ForestEvent(weight=3, run=_run)

    reg = igm_loader.IgmRegistry([EventIGM()])
    events = reg.forest_events(random.Random(0))
    assert len(events) == 1
    assert events[0].weight == 3


def test_daily_maint_exception_contained(caplog):
    from pylord import igm_loader

    class BadMaint(IGM):
        key = "badmaint"
        name = "Bad Maint"
        default_enabled = True

        async def enter(self, ctx):
            pass

        async def daily_maint(self, ctx):
            raise RuntimeError("boom in maintenance")

    class GoodMaint(IGM):
        key = "goodmaint"
        name = "Good Maint"
        default_enabled = True

        async def enter(self, ctx):
            pass

        async def daily_maint(self, ctx):
            ctx.store.set("ran", True)

    conn, _repo = _db()
    reg = igm_loader.IgmRegistry([BadMaint(), GoodMaint()])
    with caplog.at_level("ERROR", logger="pylord.igm"):
        reg.run_daily_maint(conn, {})  # must not raise
    # the good IGM still ran + committed despite the bad one crashing.
    row = conn.execute(
        "SELECT v FROM igm_data WHERE igm_key='goodmaint' AND k='ran'"
    ).fetchone()
    assert row is not None
    assert caplog.records


async def test_daily_maint_runs_inside_event_loop():
    # This async test *is* a running event loop -- the same situation as the
    # telnet server's shell callback. run_daily_maint must not blow up with
    # "asyncio.run() cannot be called from a running event loop".
    from pylord import igm_loader

    class LoopMaint(IGM):
        key = "loopmaint"
        name = "Loop Maint"
        default_enabled = True

        async def enter(self, ctx):
            pass

        async def daily_maint(self, ctx):
            ctx.store.set("ok", 1)

    conn, _repo = _db()
    reg = igm_loader.IgmRegistry([LoopMaint()])
    reg.run_daily_maint(conn, {})  # must not raise
    row = conn.execute(
        "SELECT v FROM igm_data WHERE igm_key='loopmaint' AND k='ok'"
    ).fetchone()
    assert row is not None


def test_daily_maintenance_threads_registry():
    # daily.maintenance should invoke registry.run_daily_maint after the
    # core per-player reset.
    from pylord import igm_loader
    from pylord.engine import daily

    class Tracker(IGM):
        key = "tracker"
        name = "Tracker"
        default_enabled = True

        async def enter(self, ctx):
            pass

        async def daily_maint(self, ctx):
            ctx.store.set("day_seen", True)

    conn, repo = _db()
    repo.create("Hero", "pw", "M")
    reg = igm_loader.IgmRegistry([Tracker()])
    daily.maintenance(conn, {"game": {}}, "2026-07-24", igms=reg)
    row = conn.execute(
        "SELECT v FROM igm_data WHERE igm_key='tracker' AND k='day_seen'"
    ).fetchone()
    assert row is not None


# --- PlayerView validation -------------------------------------------


def test_playerview_blocks_level_write():
    conn, repo = _db()
    p = repo.create("Hero", "pw", "M")
    ctx = _ctx(conn, repo, p)
    igm_ctx = IgmContext(ctx, _StubIGM())
    with pytest.raises(IgmViolation):
        igm_ctx.player.level = 99


def test_playerview_blocks_name_and_id():
    conn, repo = _db()
    p = repo.create("Hero", "pw", "M")
    ctx = _ctx(conn, repo, p)
    igm_ctx = IgmContext(ctx, _StubIGM())
    with pytest.raises(IgmViolation):
        igm_ctx.player.name = "Cheater"
    with pytest.raises(IgmViolation):
        igm_ctx.player.id = 7


def test_playerview_clamps_negative_gold():
    conn, repo = _db()
    p = repo.create("Hero", "pw", "M")
    ctx = _ctx(conn, repo, p)
    igm_ctx = IgmContext(ctx, _StubIGM())
    igm_ctx.player.gold = -5
    assert p.gold == 0


def test_playerview_clamps_hp_to_hp_max():
    conn, repo = _db()
    p = repo.create("Hero", "pw", "M")
    p.hp_max = 30
    ctx = _ctx(conn, repo, p)
    igm_ctx = IgmContext(ctx, _StubIGM())
    igm_ctx.player.hp = 999
    assert p.hp == 30
    igm_ctx.player.hp = -50
    assert p.hp == 0


def test_playerview_stat_floors():
    conn, repo = _db()
    p = repo.create("Hero", "pw", "M")
    ctx = _ctx(conn, repo, p)
    igm_ctx = IgmContext(ctx, _StubIGM())
    igm_ctx.player.strength = -3
    igm_ctx.player.defense = 0
    igm_ctx.player.charm = -1
    igm_ctx.player.hp_max = 0
    assert p.strength == 1
    assert p.defense == 1
    assert p.charm == 1
    assert p.hp_max == 1


def test_playerview_exp_cap():
    conn, repo = _db()
    p = repo.create("Hero", "pw", "M")
    ctx = _ctx(conn, repo, p)
    igm_ctx = IgmContext(ctx, _StubIGM())
    igm_ctx.player.exp = 5_000_000_000
    assert p.exp == 2_000_000_000
    igm_ctx.player.exp = -1
    assert p.exp == 0


def test_playerview_stat_caps_at_32000():
    """Post-review: PlayerView now shares its bounds with
    pylord.engine.effects.apply_effect (pylord/engine/limits.py), which
    caps hp_max/strength/defense/charm at 32,000 -- previously PlayerView
    floored these but never capped them."""
    conn, repo = _db()
    p = repo.create("Hero", "pw", "M")
    ctx = _ctx(conn, repo, p)
    igm_ctx = IgmContext(ctx, _StubIGM())
    igm_ctx.player.strength = 99_999
    igm_ctx.player.defense = 99_999
    igm_ctx.player.charm = 99_999
    igm_ctx.player.hp_max = 99_999
    assert p.strength == 32_000
    assert p.defense == 32_000
    assert p.charm == 32_000
    assert p.hp_max == 32_000


def test_playerview_forest_and_player_fights_now_validated():
    """Post-review: forest_fights/player_fights are floored at 0 and
    capped at 32,000 by the shared pylord/engine/limits.py bounds --
    previously PlayerView passed them through completely unvalidated."""
    conn, repo = _db()
    p = repo.create("Hero", "pw", "M")
    ctx = _ctx(conn, repo, p)
    igm_ctx = IgmContext(ctx, _StubIGM())
    igm_ctx.player.forest_fights = -5
    igm_ctx.player.player_fights = 99_999
    assert p.forest_fights == 0
    assert p.player_fights == 32_000


def test_playerview_reads_pass_through():
    conn, repo = _db()
    p = repo.create("Hero", "pw", "M")
    p.gold = 123
    ctx = _ctx(conn, repo, p)
    igm_ctx = IgmContext(ctx, _StubIGM())
    assert igm_ctx.player.gold == 123
    assert igm_ctx.player.name == "Hero"


# --- store ------------------------------------------------------------


def test_store_isolation_between_keys():
    conn, repo = _db()
    p = repo.create("Hero", "pw", "M")
    ctx = _ctx(conn, repo, p)
    a = IgmContext(ctx, _StubIGM("aaa"))
    b = IgmContext(ctx, _StubIGM("bbb"))
    a.store.set("shared", "from_a")
    b.store.set("shared", "from_b")
    a.store.flush()
    b.store.flush()
    conn.commit()
    a2 = IgmContext(ctx, _StubIGM("aaa"))
    b2 = IgmContext(ctx, _StubIGM("bbb"))
    assert a2.store.get("shared") == "from_a"
    assert b2.store.get("shared") == "from_b"


def test_store_delete():
    conn, repo = _db()
    p = repo.create("Hero", "pw", "M")
    ctx = _ctx(conn, repo, p)
    s = IgmContext(ctx, _StubIGM("zzz"))
    s.store.set("k", {"n": 1})
    s.store.flush()
    conn.commit()
    s2 = IgmContext(ctx, _StubIGM("zzz"))
    assert s2.store.get("k") == {"n": 1}
    s2.store.delete("k")
    s2.store.flush()
    conn.commit()
    s3 = IgmContext(ctx, _StubIGM("zzz"))
    assert s3.store.get("k", "gone") == "gone"


# --- mail / other_players --------------------------------------------


def test_mail_insert():
    conn, repo = _db()
    p = repo.create("Hero", "pw", "M")
    recipient = repo.create("Villager", "pw", "M")
    ctx = _ctx(conn, repo, p)
    igm_ctx = IgmContext(ctx, _StubIGM())
    igm_ctx.mail("Villager", text="Hello!", effect={"gold": 5})
    conn.commit()
    row = conn.execute(
        "SELECT to_id, from_name, text, effect FROM mail WHERE to_id=?",
        (recipient.id,),
    ).fetchone()
    assert row is not None
    assert row["from_name"] == _StubIGM().name
    assert row["text"] == "Hello!"
    assert '"gold": 5' in row["effect"]


def test_other_players_excludes_self():
    conn, repo = _db()
    p = repo.create("Hero", "pw", "M")
    repo.create("Ally", "pw", "M")
    ctx = _ctx(conn, repo, p)
    igm_ctx = IgmContext(ctx, _StubIGM())
    summaries = igm_ctx.other_players()
    names = {s.name for s in summaries}
    assert "Ally" in names
    assert "Hero" not in names


# --- visit protocol: rollback + news flush ----------------------------


class _CrashIGM(IGM):
    key = "crash"
    name = "Crash Test"
    default_enabled = True

    async def enter(self, ctx):
        ctx.player.gold = 999999
        ctx.player.hp = 1
        ctx.store.set("should_not_persist", "x")
        ctx.news("this news should be dropped")
        ctx.mail("Hero", text="dropped mail")
        raise RuntimeError("kaboom inside enter()")


class _CleanIGM(IGM):
    key = "clean"
    name = "Clean Visit"
    default_enabled = True

    async def enter(self, ctx):
        ctx.player.gold += 50
        ctx.store.set("count", 1)
        ctx.news("clean news line")


def _visit_ctx(conn, repo, player, igm):
    from pylord import igm_loader

    reg = igm_loader.IgmRegistry([igm])
    ctx = _ctx(conn, repo, player, keys=[" "], igms=reg)
    return ctx


async def test_crash_restores_player_and_rolls_back_store():
    conn, repo = _db()
    p = repo.create("Hero", "pw", "M")
    p.gold = 100
    p.hp = 20
    p.hp_max = 20
    repo.save(p)
    original = p  # the object server.handle_connection would also hold
    ctx = _visit_ctx(conn, repo, p, _CrashIGM())

    from pylord.engine.scenes.other_places import _visit

    await _visit(ctx, _CrashIGM())

    # CRITICAL: restore must be in place -- the SAME object identity the
    # rest of the session (and the server's cleanup save) holds, restored
    # to pre-visit values (not a rebound snapshot copy leaving the original
    # carrying the IGM's mutations).
    assert ctx.player is original
    assert original.gold == 100
    assert original.hp == 20
    # player object restored to pre-visit values
    assert ctx.player.gold == 100
    assert ctx.player.hp == 20
    # store write rolled back
    assert (
        conn.execute(
            "SELECT 1 FROM igm_data WHERE igm_key='crash'"
        ).fetchone()
        is None
    )
    # news dropped
    assert (
        conn.execute(
            "SELECT 1 FROM daily_news WHERE text LIKE '%dropped%'"
        ).fetchone()
        is None
    )
    # mail rolled back
    assert conn.execute("SELECT 1 FROM mail").fetchone() is None
    # flavor message shown
    out = "".join(ctx.io.output)
    assert "strange force" in out


class _DisconnectIGM(IGM):
    key = "disconnect"
    name = "Disconnect Test"
    default_enabled = True

    async def enter(self, ctx):
        # Mutate, then the player disconnects mid-visit (the common case).
        ctx.player.gold = 999999
        ctx.store.set("nope", "x")
        raise ConnectionClosed("peer vanished mid-IGM")


async def test_disconnect_midvisit_restores_before_reraise_and_cleanup_save():
    from pylord.terminal import ConnectionClosed as _CC

    conn, repo = _db()
    p = repo.create("Hero", "pw", "M")
    p.gold = 100
    repo.save(p)
    original = p
    ctx = _visit_ctx(conn, repo, p, _DisconnectIGM())

    from pylord.engine.scenes.other_places import _visit

    # ConnectionClosed must re-raise (session teardown needs the signal) ...
    with pytest.raises(_CC):
        await _visit(ctx, _DisconnectIGM())

    # ... but the in-place restore must already have happened on the SAME
    # object, so the server's finally-block cleanup save (which holds this
    # very object) can't re-persist the IGM's mutation.
    assert ctx.player is original
    assert original.gold == 100

    # Simulate server.handle_connection's cleanup: online = 0; repo.save.
    original.online = 0
    repo.save(original)

    reloaded = repo.get(p.id)
    assert reloaded.gold == 100  # rollback survived the cleanup save
    assert reloaded.online == 0
    # store write rolled back too
    assert (
        conn.execute("SELECT 1 FROM igm_data WHERE igm_key='disconnect'").fetchone()
        is None
    )


async def test_clean_visit_flushes_everything():
    conn, repo = _db()
    p = repo.create("Hero", "pw", "M")
    p.gold = 100
    repo.save(p)
    igm = _CleanIGM()
    ctx = _visit_ctx(conn, repo, p, igm)

    from pylord.engine.scenes.other_places import _visit

    await _visit(ctx, igm)

    reloaded = repo.get(p.id)
    assert reloaded.gold == 150
    assert (
        conn.execute(
            "SELECT v FROM igm_data WHERE igm_key='clean' AND k='count'"
        ).fetchone()
        is not None
    )
    assert (
        conn.execute(
            "SELECT 1 FROM daily_news WHERE text = 'clean news line'"
        ).fetchone()
        is not None
    )


async def test_other_places_empty_registry_returns_forest():
    conn, repo = _db()
    p = repo.create("Hero", "pw", "M")
    ctx = _ctx(conn, repo, p, keys=[" "], igms=None)

    from pylord.engine.scenes.other_places import other_places

    nxt = await other_places(ctx)
    assert nxt == "forest"
    assert "overgrown" in "".join(ctx.io.output)


async def test_other_places_lists_and_visits():
    from pylord import igm_loader

    conn, repo = _db()
    p = repo.create("Hero", "pw", "M")
    reg = igm_loader.IgmRegistry([_CleanIGM()])
    # 'A' selects the single IGM, then a key for the visit's internal pause
    ctx = _ctx(conn, repo, p, keys=["A", " "], igms=reg)

    from pylord.engine.scenes.other_places import other_places

    nxt = await other_places(ctx)
    assert nxt == "forest"


# --- contract check runs against the sample fixture -------------------


async def test_sample_igm_passes_contract():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "igms._sample_fixture", _IGMS_DIR / "sample_igm" / "igm.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    await contract_check(mod.SampleIGM)


# --- forest menu wiring ----------------------------------------------


def test_forest_menu_has_other_places():
    from pylord.engine.scenes import forest as forest_mod

    assert "O" in forest_mod._MENU_OPTIONS
    assert forest_mod._MENU_OPTIONS["O"] == "other_places"
    assert "Other places" in forest_mod._MENU or "ther places" in forest_mod._MENU


class _StubIGM(IGM):
    """A do-nothing IGM for building bare IgmContexts in unit tests."""

    name = "Stub IGM"

    def __init__(self, key="stub"):
        self.key = key

    async def enter(self, ctx):
        pass
