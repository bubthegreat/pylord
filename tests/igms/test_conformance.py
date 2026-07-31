"""Every bundled IGM, held to the framework's contract automatically.

Discovery is done by the real loader, so there is no list here to forget to
update: an IGM is covered the moment its directory lands in ``igms/``. The
point is that a change to pylord's IGM-facing API -- ``IgmContext``,
``PlayerView``, the hook signatures -- fails across all of them at once
instead of silently in whichever plugin someone next happens to run.

Behaviour specific to one IGM belongs in that IGM's own test module. What
lives here is only what every IGM must satisfy.
"""

from __future__ import annotations

import random
import tomllib
from pathlib import Path

import pytest

from pylord import igm_loader
from pylord.hooks import IGM, ForestEvent, InnEvent
from tests.igm_contract import contract_check
from tests.igms._harness import make_db, make_maint_ctx

#: Every bundled IGM, enabled or not. Collected once at import so the
#: parametrised tests below get readable ids.
ALL_IGMS = igm_loader.load_all("igms")
IDS = [igm.key for igm in ALL_IGMS]

#: Derived from this file's location, not cwd -- the suite must pass no
#: matter where pytest is invoked from.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_TOML = _REPO_ROOT / "config.toml"

#: Every IGM key `config.toml` lists. Used as the expected bundled set:
#: deriving it means adding an IGM does not require editing a count here,
#: while still catching a packaging mistake that discovers nothing.
CONFIGURED_KEYS = frozenset(tomllib.loads(_CONFIG_TOML.read_text())["igms"])


def test_the_bundled_set_matches_config():
    """A packaging mistake that stops IGMs loading would otherwise turn
    every parametrised test below into a silent no-op -- pytest collects
    zero cases from an empty parametrize list and reports success.

    Checked against `config.toml`'s `[igms]` table rather than a hardcoded
    number, so this stays true as the catalogue grows but still fails loudly
    if discovery returns nothing, or if an IGM lands without its toggle.
    """
    assert set(IDS) == CONFIGURED_KEYS, {
        "discovered but unconfigured": sorted(set(IDS) - CONFIGURED_KEYS),
        "configured but not discovered": sorted(CONFIGURED_KEYS - set(IDS)),
    }


@pytest.mark.parametrize("igm", ALL_IGMS, ids=IDS)
def test_every_bundled_igm_ships_enabled(igm: IGM):
    """The product policy the old per-wave ``test_ships_*`` lists pinned:
    a shipped IGM is on, and the sysop turns off what they don't want.

    Spelled out here rather than inferred, because
    ``test_config_lists_every_igm_with_its_default`` below only proves
    ``config.toml`` and the class agree with each other -- it would happily
    agree on the wrong value.
    """
    assert igm.default_enabled is True, (
        f"{igm.key}.default_enabled is False; bundled IGMs ship on"
    )


@pytest.mark.parametrize("igm", ALL_IGMS, ids=IDS)
async def test_contract(igm: IGM):
    """Checks the loaded instance itself, not a freshly built one, so
    ``igm.dir`` is the real plugin directory the loader set it to -- a
    data-reading IGM (pickle, oorphans, freeworld2) is exercised on its
    real data-file path, not only the ``dir is None`` fallback."""
    await contract_check(igm)


@pytest.mark.parametrize("igm", ALL_IGMS, ids=IDS)
async def test_daily_maint_runs_if_overridden(igm: IGM):
    """Twelve of the sixteen override daily_maint. It runs during global
    maintenance with no terminal and no player, so a plugin that reaches
    for either breaks the whole nightly pass rather than one visit."""
    if type(igm).daily_maint is IGM.daily_maint:
        pytest.skip(f"{igm.key} does not override daily_maint")
    database, repo = await make_db()
    await repo.create("MaintTester", "pw", "M")
    ctx = await make_maint_ctx(database, {}, igm.key)
    await igm.daily_maint(ctx)
    await ctx.store.flush(database)


@pytest.mark.parametrize("igm", ALL_IGMS, ids=IDS)
def test_event_hooks_return_the_right_type(igm: IGM):
    """forest_event and inn_event are collected by IgmRegistry and their
    results are called by the Forest and the Inn. Nothing bundled uses them
    yet, so this is the first thing that has ever checked their shape."""
    rng = random.Random(0)

    forest = igm.forest_event(rng)
    assert forest is None or isinstance(forest, ForestEvent), (
        f"{igm.key}.forest_event returned {type(forest).__name__}"
    )
    if forest is not None:
        assert forest.weight > 0, f"{igm.key} contributed a zero-weight event"
        assert callable(forest.run)

    inn = igm.inn_event(rng)
    assert inn is None or isinstance(inn, InnEvent), (
        f"{igm.key}.inn_event returned {type(inn).__name__}"
    )
    if inn is not None:
        assert inn.label and callable(inn.run)


def test_keys_are_unique():
    keys = [igm.key for igm in ALL_IGMS]
    assert len(keys) == len(set(keys)), sorted(keys)


@pytest.mark.parametrize("igm", ALL_IGMS, ids=IDS)
def test_config_lists_every_igm_with_its_default(igm: IGM):
    """config.toml's [igms] table is the sysop's switchboard. An IGM
    missing from it still loads -- discover() falls back to
    default_enabled -- but a sysop reading the file would never learn it
    exists."""
    config = tomllib.loads(_CONFIG_TOML.read_text())
    toggles = config["igms"]
    assert igm.key in toggles, f"{igm.key} is not listed in config.toml [igms]"
    assert toggles[igm.key] == igm.default_enabled, (
        f"config.toml sets {igm.key}={toggles[igm.key]} but the class "
        f"declares default_enabled={igm.default_enabled}"
    )


@pytest.mark.parametrize("igm", ALL_IGMS, ids=IDS)
def test_shipped_data_and_screen_files_exist(igm: IGM):
    """IGM.dir is how a plugin reaches its own data tables and .ANS art.
    A missing directory means the plugin silently degrades -- oorphans
    falls back to a generic orphan, pickle draws no garden -- so check the
    files are actually there rather than waiting to notice."""
    assert igm.dir is not None and igm.dir.is_dir()
    for subdir in ("data", "screens"):
        path = igm.dir / subdir
        if path.exists():
            assert any(path.iterdir()), f"{igm.key}/{subdir} is empty"
