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

from pylord import data
from pylord.engine.game import GameCtx
from pylord.hooks import IGM, ForestEvent, IgmContext, IgmStore, IgmViolation
from pylord.terminal import ConnectionClosed, FakeIO
from tests.harness import query_one
from tests.igm_contract import contract_check

_FIXTURES = Path(__file__).parent / "fixtures"
_IGMS_DIR = _FIXTURES / "igms"
_DUP_DIR = _FIXTURES / "igms_dup"


# --- helpers ----------------------------------------------------------


async def _db():
    database = await data.connect(":memory:")
    return database, database.players


def _ctx(database, repo, player, keys=None, igms=None):
    io = FakeIO(keys or [])
    ctx = GameCtx(player=player, db=database, io=io, rng=random.Random(0))
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


def test_loader_sets_igm_dir_to_the_plugin_directory():
    from pylord import igm_loader

    reg = igm_loader.discover(_FIXTURES / "igms_data", {})
    (igm,) = reg.enabled
    assert igm.dir == _FIXTURES / "igms_data" / "data_igm"


def test_igm_can_read_a_data_file_it_ships_with():
    """The supported way to ship more than one file: relative imports stay
    broken under the synthetic module name, but ``self.dir`` is real."""
    from pylord import igm_loader

    reg = igm_loader.discover(_FIXTURES / "igms_data", {})
    (igm,) = reg.enabled
    assert igm.greeting() == "hello from a plugin data file"


def test_igm_dir_is_none_when_a_plugin_is_constructed_directly():
    """Nothing sets ``dir`` outside the loader, so a hand-built instance
    (contract_check does this) must cope with it being unset."""
    from pylord.hooks import IGM

    class Bare(IGM):
        key = "bare"
        name = "Bare"

        async def enter(self, ctx) -> None:
            pass

    assert Bare().dir is None


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
    # Each entry is (owning IGM, event) -- the forest needs the owner to
    # build that plugin's guardrailed context.
    igm, event = events[0]
    assert igm.key == "ev"
    assert event.weight == 3


async def test_daily_maint_exception_contained(caplog):
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

    database, _repo = await _db()
    reg = igm_loader.IgmRegistry([BadMaint(), GoodMaint()])
    with caplog.at_level("ERROR", logger="pylord.igm"):
        await reg.run_daily_maint(database, {})  # must not raise
    # the good IGM still ran + committed despite the bad one crashing.
    row = await query_one(database, 
        "SELECT v FROM igm_data WHERE igm_key='goodmaint' AND k='ran'"
    )
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

    database, _repo = await _db()
    reg = igm_loader.IgmRegistry([LoopMaint()])
    await reg.run_daily_maint(database, {})  # must not raise
    row = await query_one(database, 
        "SELECT v FROM igm_data WHERE igm_key='loopmaint' AND k='ok'"
    )
    assert row is not None


async def test_daily_maintenance_threads_registry():
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

    database, repo = await _db()
    await repo.create("Hero", "pw", "M")
    reg = igm_loader.IgmRegistry([Tracker()])
    await daily.maintenance(database, {"game": {}}, "2026-07-24", igms=reg)
    row = await query_one(database, 
        "SELECT v FROM igm_data WHERE igm_key='tracker' AND k='day_seen'"
    )
    assert row is not None


# --- PlayerView validation -------------------------------------------


async def test_playerview_blocks_level_write():
    database, repo = await _db()
    p = await repo.create("Hero", "pw", "M")
    ctx = _ctx(database, repo, p)
    igm_ctx = await IgmContext.create(ctx, _StubIGM())
    with pytest.raises(IgmViolation):
        igm_ctx.player.level = 99


async def test_playerview_blocks_name_and_id():
    database, repo = await _db()
    p = await repo.create("Hero", "pw", "M")
    ctx = _ctx(database, repo, p)
    igm_ctx = await IgmContext.create(ctx, _StubIGM())
    with pytest.raises(IgmViolation):
        igm_ctx.player.name = "Cheater"
    with pytest.raises(IgmViolation):
        igm_ctx.player.id = 7


async def test_playerview_clamps_negative_gold():
    database, repo = await _db()
    p = await repo.create("Hero", "pw", "M")
    ctx = _ctx(database, repo, p)
    igm_ctx = await IgmContext.create(ctx, _StubIGM())
    igm_ctx.player.gold = -5
    assert p.gold == 0


async def test_playerview_clamps_hp_to_hp_max():
    database, repo = await _db()
    p = await repo.create("Hero", "pw", "M")
    p.hp_max = 30
    ctx = _ctx(database, repo, p)
    igm_ctx = await IgmContext.create(ctx, _StubIGM())
    igm_ctx.player.hp = 999
    assert p.hp == 30
    igm_ctx.player.hp = -50
    assert p.hp == 0


async def test_playerview_stat_floors():
    database, repo = await _db()
    p = await repo.create("Hero", "pw", "M")
    ctx = _ctx(database, repo, p)
    igm_ctx = await IgmContext.create(ctx, _StubIGM())
    igm_ctx.player.strength = -3
    igm_ctx.player.defense = 0
    igm_ctx.player.charm = -1
    igm_ctx.player.hp_max = -9
    # Floors are lord.js check_fields()'s own: 0, not 1
    # (reference/lord.js:16611-16658).
    assert p.strength == 0
    assert p.defense == 0
    assert p.charm == 0
    assert p.hp_max == 0


async def test_playerview_exp_cap():
    database, repo = await _db()
    p = await repo.create("Hero", "pw", "M")
    ctx = _ctx(database, repo, p)
    igm_ctx = await IgmContext.create(ctx, _StubIGM())
    igm_ctx.player.exp = 5_000_000_000
    assert p.exp == 2_000_000_000
    igm_ctx.player.exp = -1
    assert p.exp == 0


async def test_playerview_stat_caps_at_32000():
    """Post-review: PlayerView now shares its bounds with
    pylord.engine.effects.apply_effect (pylord/engine/limits.py), which
    caps hp_max/strength/defense/charm at 32,000 -- previously PlayerView
    floored these but never capped them."""
    database, repo = await _db()
    p = await repo.create("Hero", "pw", "M")
    ctx = _ctx(database, repo, p)
    igm_ctx = await IgmContext.create(ctx, _StubIGM())
    igm_ctx.player.strength = 99_999
    igm_ctx.player.defense = 99_999
    igm_ctx.player.charm = 99_999
    igm_ctx.player.hp_max = 99_999
    assert p.strength == 32_000
    assert p.defense == 32_000
    assert p.charm == 32_000
    assert p.hp_max == 32_000


async def test_playerview_forest_and_player_fights_now_validated():
    """Post-review: forest_fights/player_fights are floored at 0 and
    capped at 32,000 by the shared pylord/engine/limits.py bounds --
    previously PlayerView passed them through completely unvalidated."""
    database, repo = await _db()
    p = await repo.create("Hero", "pw", "M")
    ctx = _ctx(database, repo, p)
    igm_ctx = await IgmContext.create(ctx, _StubIGM())
    igm_ctx.player.forest_fights = -5
    igm_ctx.player.player_fights = 99_999
    assert p.forest_fights == 0
    assert p.player_fights == 32_000


async def test_playerview_reads_pass_through():
    database, repo = await _db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 123
    ctx = _ctx(database, repo, p)
    igm_ctx = await IgmContext.create(ctx, _StubIGM())
    assert igm_ctx.player.gold == 123
    assert igm_ctx.player.name == "Hero"


# --- store ------------------------------------------------------------


async def test_store_isolation_between_keys():
    database, repo = await _db()
    p = await repo.create("Hero", "pw", "M")
    ctx = _ctx(database, repo, p)
    a = await IgmContext.create(ctx, _StubIGM("aaa"))
    b = await IgmContext.create(ctx, _StubIGM("bbb"))
    a.store.set("shared", "from_a")
    b.store.set("shared", "from_b")
    await a.store.flush(database)
    await b.store.flush(database)
    a2 = await IgmContext.create(ctx, _StubIGM("aaa"))
    b2 = await IgmContext.create(ctx, _StubIGM("bbb"))
    assert a2.store.get("shared") == "from_a"
    assert b2.store.get("shared") == "from_b"


async def test_store_delete():
    database, repo = await _db()
    p = await repo.create("Hero", "pw", "M")
    ctx = _ctx(database, repo, p)
    s = await IgmContext.create(ctx, _StubIGM("zzz"))
    s.store.set("k", {"n": 1})
    await s.store.flush(database)
    s2 = await IgmContext.create(ctx, _StubIGM("zzz"))
    assert s2.store.get("k") == {"n": 1}
    s2.store.delete("k")
    await s2.store.flush(database)
    s3 = await IgmContext.create(ctx, _StubIGM("zzz"))
    assert s3.store.get("k", "gone") == "gone"


# --- mail / other_players --------------------------------------------


async def test_mail_insert():
    database, repo = await _db()
    p = await repo.create("Hero", "pw", "M")
    recipient = await repo.create("Villager", "pw", "M")
    ctx = _ctx(database, repo, p)
    igm_ctx = await IgmContext.create(ctx, _StubIGM())
    igm_ctx.mail("Villager", text="Hello!", effect={"gold": 5})
    # Buffered until the visit ends cleanly, so nothing is on disk yet.
    assert await query_one(database, "SELECT 1 FROM mail") is None
    await igm_ctx.flush(database)

    row = await query_one(
        database,
        "SELECT to_id, from_name, text, effect FROM mail WHERE to_id = :tid",
        tid=recipient.id,
    )
    assert row is not None
    assert row.from_name == _StubIGM().name
    assert row.text == "Hello!"
    assert '"gold": 5' in row.effect


async def test_other_players_excludes_self():
    database, repo = await _db()
    p = await repo.create("Hero", "pw", "M")
    await repo.create("Ally", "pw", "M")
    ctx = _ctx(database, repo, p)
    igm_ctx = await IgmContext.create(ctx, _StubIGM())
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


def _visit_ctx(database, repo, player, igm):
    from pylord import igm_loader

    reg = igm_loader.IgmRegistry([igm])
    ctx = _ctx(database, repo, player, keys=[" "], igms=reg)
    return ctx


async def test_crash_restores_player_and_rolls_back_store():
    database, repo = await _db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 100
    p.hp = 20
    p.hp_max = 20
    await repo.save(p)
    original = p  # the object server.handle_connection would also hold
    ctx = _visit_ctx(database, repo, p, _CrashIGM())

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
        await query_one(database, 
            "SELECT 1 FROM igm_data WHERE igm_key='crash'"
        )
        is None
    )
    # news dropped
    assert (
        await query_one(database, 
            "SELECT 1 FROM daily_news WHERE text LIKE '%dropped%'"
        )
        is None
    )
    # mail rolled back
    assert await query_one(database, "SELECT 1 FROM mail") is None
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

    database, repo = await _db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 100
    await repo.save(p)
    original = p
    ctx = _visit_ctx(database, repo, p, _DisconnectIGM())

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
    await repo.save(original)

    reloaded = await repo.get(p.id)
    assert reloaded.gold == 100  # rollback survived the cleanup save
    assert reloaded.online == 0
    # store write rolled back too
    assert (
        await query_one(database, "SELECT 1 FROM igm_data WHERE igm_key='disconnect'")
        is None
    )


async def test_clean_visit_flushes_everything():
    database, repo = await _db()
    p = await repo.create("Hero", "pw", "M")
    p.gold = 100
    await repo.save(p)
    igm = _CleanIGM()
    ctx = _visit_ctx(database, repo, p, igm)

    from pylord.engine.scenes.other_places import _visit

    await _visit(ctx, igm)

    reloaded = await repo.get(p.id)
    assert reloaded.gold == 150
    assert (
        await query_one(database, 
            "SELECT v FROM igm_data WHERE igm_key='clean' AND k='count'"
        )
        is not None
    )
    assert (
        await query_one(database, 
            "SELECT 1 FROM daily_news WHERE text = 'clean news line'"
        )
        is not None
    )


async def test_other_places_empty_registry_returns_to_town():
    database, repo = await _db()
    p = await repo.create("Hero", "pw", "M")
    ctx = _ctx(database, repo, p, keys=[" "], igms=None)

    from pylord.engine.scenes.other_places import other_places

    nxt = await other_places(ctx)
    assert nxt == "town"
    assert "overgrown" in "".join(ctx.io.output)


async def test_other_places_lists_and_visits():
    from pylord import igm_loader

    database, repo = await _db()
    p = await repo.create("Hero", "pw", "M")
    reg = igm_loader.IgmRegistry([_CleanIGM()])
    # lord.js numbers the places (reference/lord.js:17020-17064): "1"
    # selects the single IGM, " " answers the visit's internal pause, then
    # "Q" leaves the (looping) hub.
    ctx = _ctx(database, repo, p, keys=["1", " ", "Q"], igms=reg)

    from pylord.engine.scenes.other_places import other_places

    nxt = await other_places(ctx)
    assert nxt == "town"
    assert "Other Places" in "".join(ctx.io.output)


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


def test_town_menu_has_other_places_and_the_forest_does_not():
    """reference/lord.js has Other Places only in main() (:17003); the
    forest switch (:15258-15420) has no such key."""
    from pylord.engine.scenes import forest as forest_mod
    from pylord.engine.scenes import town as town_mod

    assert town_mod._DESTINATIONS["O"] == "other_places"
    assert "ther places" in town_mod._MENU
    assert "O" not in forest_mod._MENU_OPTIONS


class _StubIGM(IGM):
    """A do-nothing IGM for building bare IgmContexts in unit tests."""

    name = "Stub IGM"

    def __init__(self, key="stub"):
        self.key = key

    async def enter(self, ctx):
        pass


async def test_maint_repo_save_does_not_commit_the_registrys_transaction():
    """A plugin saving a player inside daily_maint must not end the
    registry's transaction early.

    ``ctx.repo`` hands the hook a buffered roster rather than the live
    repository, so a ``save()`` marks the player dirty and the maintenance
    pass writes it at the end -- one transaction, still able to roll back
    as a unit if a later IGM crashes."""
    from pylord import igm_loader

    database, repo = await _db()
    player = await repo.create("Hero", "pw", "M")

    class _Greedy(IGM):
        key = "greedy"
        name = "Greedy"

        async def enter(self, ctx):  # pragma: no cover -- unused here
            pass

        async def daily_maint(self, ctx):
            victim = await ctx.repo.get_by_name("Hero")
            victim.gold = 999_999
            await ctx.repo.save(victim)
            raise RuntimeError("boom, after the write")

    registry = igm_loader.IgmRegistry([_Greedy()])
    registry.run_daily_maint(database, {})

    assert (await repo.get(player.id)).gold == 500  # rolled back, not committed


# --- The two event hooks are actually consumed ----------------------------


async def test_igm_forest_event_can_fire_in_the_forest():
    """The hook used to be collected and never consulted: forest.py rolled
    only its own table, while README/igms/README advertised the hook."""
    from pylord import igm_loader
    from pylord.engine.scenes import forest as forest_mod

    fired = []

    async def _run(ctx):
        fired.append(ctx.player.name)
        await ctx.term.write("\n  A plugin event fires!\n")

    class EventIGM(IGM):
        key = "ev"
        name = "Eventful"

        async def enter(self, ctx):  # pragma: no cover -- unused here
            pass

        def forest_event(self, rng):
            return ForestEvent(weight=100, run=_run)

    database, repo = await _db()
    p = await repo.create("Hero", "pw", "M")
    ctx = _ctx(database, repo, p, keys=[" "])
    ctx.igms = igm_loader.IgmRegistry([EventIGM()])
    # weight 100 against 15 base slots: pick a roll inside the plugin range.
    ctx.rng = random.Random(3)
    for _ in range(20):
        await forest_mod._forest_event(ctx)
        if fired:
            break
    assert fired == ["Hero"]


async def test_igm_inn_event_appears_on_the_inn_menu():
    from pylord import igm_loader
    from pylord.engine.scenes import inn as inn_mod
    from pylord.hooks import InnEvent

    visited = []

    async def _run(ctx):
        visited.append(True)
        await ctx.term.write("\n  You slip into the back room.\n")

    class InnIGM(IGM):
        key = "backroom"
        name = "Back Room"

        async def enter(self, ctx):  # pragma: no cover -- unused here
            pass

        def inn_event(self, rng):
            return InnEvent(label="Slip into the back room", run=_run)

    database, repo = await _db()
    p = await repo.create("Hero", "pw", "M")
    ctx = _ctx(database, repo, p, keys=["1", "R"])
    ctx.igms = igm_loader.IgmRegistry([InnIGM()])

    await inn_mod.inn(ctx)

    text = "".join(ctx.io.output)
    assert "Slip into the back room" in text
    assert visited == [True]


async def test_store_reads_its_own_writes_after_a_flush():
    """flush() used to leave the read cache saying "missing", so a get()
    after it reported a value that was already on disk as absent."""
    database, _repo = await _db()
    store = IgmStore("cache")

    assert store.get("rate") is None
    store.set("rate", 175)
    await store.flush(database)

    assert store.get("rate") == 175
    # ... and it really persisted, so the next visit's snapshot sees it.
    reloaded = IgmStore("cache", await database.igm_data.all_for("cache"))
    assert reloaded.get("rate") == 175

    store.delete("rate")
    await store.flush(database)
    assert store.get("rate") is None
    assert IgmStore("cache", await database.igm_data.all_for("cache")).get("rate") is None


def test_discover_prefers_the_first_directory_for_a_duplicate_key(tmp_path):
    """A realm seeded with an old copy of a bundled IGM must still get the
    shipped one: bundled directories are searched first, and a later copy
    of the same key is ignored rather than shadowing it."""
    from pylord import igm_loader

    def _write(root, key, marker):
        d = root / key
        d.mkdir(parents=True)
        (d / "igm.py").write_text(
            "from pylord.hooks import IGM\n"
            f"class X(IGM):\n"
            f"    key = {key!r}\n"
            f"    name = {marker!r}\n"
            f"    default_enabled = True\n"
            "    async def enter(self, ctx):\n        pass\n"
        )

    bundled, local = tmp_path / "bundled", tmp_path / "local"
    _write(bundled, "mines", "shipped")
    _write(local, "mines", "stale copy")
    _write(local, "sysops_own", "custom")

    reg = igm_loader.discover([bundled, local], {})
    by_key = {igm.key: igm.name for igm in reg.enabled}

    assert by_key["mines"] == "shipped"      # not the stale volume copy
    assert by_key["sysops_own"] == "custom"  # a sysop's own still loads


def test_discover_still_accepts_a_single_directory(tmp_path):
    from pylord import igm_loader

    assert igm_loader.discover(tmp_path, {}).enabled == []


def test_every_igm_root_enumerates_as_a_package():
    """pkgutil.iter_modules only reports a subdirectory as a package when it
    has an __init__.py. The loader walks these roots, so a root that does
    not enumerate would silently load nothing at all."""
    import importlib
    import pkgutil

    expected = {
        "igms": 16,
        "tests.fixtures.igms": 3,
        "tests.fixtures.igms_dup": 2,
        "tests.fixtures.igms_data": 1,
    }
    for name, count in expected.items():
        pkg = importlib.import_module(name)
        found = [n for _, n, ispkg in pkgutil.iter_modules(pkg.__path__) if ispkg]
        assert len(found) == count, f"{name} enumerated {found}"
