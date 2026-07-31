# Multi-Module IGMs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an IGM ship more than one Python module, by loading plugins as
ordinary Python packages instead of single files opened by hand.

**Architecture:** `igms/` becomes a regular package and each IGM a
subpackage (all 16 already have `__init__.py`). `pylord/igm_loader.py`
stops using `importlib.util.spec_from_file_location` under a synthetic
module name and instead enumerates with `pkgutil.iter_modules` and imports
with `importlib.import_module`. Relative imports inside a plugin then work
because there is a real parent package. Nothing moves and no IGM is
rewritten.

**Tech Stack:** Python 3.12, `importlib`, `pkgutil`, pytest (asyncio auto
mode), ruff, hatchling, uv.

## Global Constraints

- Package manager is **uv** only — `uv run`, `uv add`. Never pip/poetry.
- `uv run ruff check .` must pass. CI runs exactly that (`.github/workflows/ci.yml:28`). It does **not** run `ruff format --check`, and 56 files in the repo are already unformatted — do not reformat files you did not otherwise change.
- The full suite is **644 passing tests** before this work. It must be 644-or-more passing after every task, with no new warnings.
- `discover()` must **never raise**. A broken, missing or duplicate plugin is logged and skipped. This is load-bearing: one bad plugin must never take the game down.
- IGM iteration order must be **deterministic** (sorted), because duplicate-key resolution is first-wins.
- `pylord` must never import `igms.*` at module scope — only inside a function at runtime. That keeps the dependency graph `igms → pylord`, acyclic.
- Branch is `feat/igm-wave3`. Commit after every task.

---

### Task 1: Package hygiene — make every IGM root enumerable

`pkgutil.iter_modules` only reports a subdirectory as a package if it
contains `__init__.py`. All 16 real IGMs already have one; none of the test
fixture roots or their plugin directories do, so they would silently
enumerate as empty. This task adds the missing files and nothing else, so
the loader rewrite in Task 2 lands against a tree that can already be
walked.

**Files:**
- Create: `igms/__init__.py`
- Create: `tests/fixtures/igms/__init__.py`
- Create: `tests/fixtures/igms/sample_igm/__init__.py`
- Create: `tests/fixtures/igms/broken_import/__init__.py`
- Create: `tests/fixtures/igms/no_subclass/__init__.py`
- Create: `tests/fixtures/igms_dup/__init__.py`
- Create: `tests/fixtures/igms_dup/first/__init__.py`
- Create: `tests/fixtures/igms_dup/second/__init__.py`
- Create: `tests/fixtures/igms_data/__init__.py`
- Create: `tests/fixtures/igms_data/data_igm/__init__.py`
- Test: `tests/test_igm_framework.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `igms` and the three `tests.fixtures.igms*` roots are importable regular packages whose subpackages `pkgutil.iter_modules` reports. Task 2 relies on this.

- [ ] **Step 1: Write the failing test**

Add to the end of `tests/test_igm_framework.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_igm_framework.py::test_every_igm_root_enumerates_as_a_package -v`
Expected: FAIL — `tests.fixtures.igms enumerated []` (the fixture roots have no `__init__.py`).

- [ ] **Step 3: Create the package markers**

`igms/__init__.py` gets a docstring, because it is the one a plugin author
may open:

```python
"""Bundled IGMs -- in-game modules the engine loads at startup.

A regular package, not a namespace package, so each IGM below is a real
subpackage and can be split across several modules that import each other.
See ``igms/README.md`` for the plugin contract, and
``pylord/igm_loader.py`` for how these are discovered.
"""
```

The nine files under `tests/fixtures/` are empty (zero bytes). Create them:

```bash
: > tests/fixtures/igms/__init__.py
: > tests/fixtures/igms/sample_igm/__init__.py
: > tests/fixtures/igms/broken_import/__init__.py
: > tests/fixtures/igms/no_subclass/__init__.py
: > tests/fixtures/igms_dup/__init__.py
: > tests/fixtures/igms_dup/first/__init__.py
: > tests/fixtures/igms_dup/second/__init__.py
: > tests/fixtures/igms_data/__init__.py
: > tests/fixtures/igms_data/data_igm/__init__.py
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_igm_framework.py::test_every_igm_root_enumerates_as_a_package -v`
Expected: PASS

- [ ] **Step 5: Run the whole suite — the old loader must be unaffected**

Run: `uv run pytest tests/ -q`
Expected: 645 passed (644 + the new one). Adding `__init__.py` does not
change the path-based loader, which never consulted them.

- [ ] **Step 6: Commit**

```bash
git add igms/__init__.py tests/fixtures tests/test_igm_framework.py
git commit -m "test(igms): give every IGM root an __init__.py so it enumerates

pkgutil.iter_modules reports a subdirectory as a package only when it has
an __init__.py. The 16 bundled IGMs already had one; none of the test
fixture roots did, so a loader that walks packages rather than paths would
have found nothing in them and passed by loading zero plugins."
```

---

### Task 2: Load plugins as packages

The behaviour change that unblocks `felicity`, `lordcave`, `sandbar` and
`violet`. Driven by a fixture that is a genuinely multi-module plugin, so
the test fails for the real reason before the loader changes.

`discover()` splits into two functions: `load_all()` returns every valid
IGM regardless of its enable flag, and `discover()` filters that by the
config toggles. Task 4's conformance test needs every IGM including the
disabled ten, and a first-pass-to-build-a-toggle-dict would be worse than
a named function.

**Files:**
- Create: `tests/fixtures/igms/multi_module/__init__.py`
- Create: `tests/fixtures/igms/multi_module/igm.py`
- Create: `tests/fixtures/igms/multi_module/helpers.py`
- Modify: `pylord/igm_loader.py` (module docstring, `_load_one`, `discover`, delete `_load_dir`)
- Test: `tests/test_igm_framework.py`

**Interfaces:**
- Consumes: enumerable package roots from Task 1.
- Produces:
  - `igm_loader.load_all(package: str) -> list[IGM]` — every valid IGM in `package`, sorted by subpackage name, duplicates by `key` dropped after the first. Never raises.
  - `igm_loader.discover(package: str, config: dict[str, Any]) -> IgmRegistry` — `load_all` filtered by `config["igms"]`. Never raises. **Signature change: takes a dotted package name, not a `Path`.**
  - `IGM.dir` continues to be the plugin's directory.

- [ ] **Step 1: Write the multi-module fixture**

`tests/fixtures/igms/multi_module/__init__.py` — empty.

`tests/fixtures/igms/multi_module/helpers.py`:

```python
"""A second module in the same plugin. The point of the whole change."""

GREETING = "helpers module reached"


def shout(text: str) -> str:
    return text.upper()
```

`tests/fixtures/igms/multi_module/igm.py` — exercises **both** import
styles, because they fail for different reasons and a plugin author will
reach for either:

```python
"""Fixture: a plugin split across two modules.

Relative and absolute intra-plugin imports both have to resolve. Under the
old loader neither did: ``igm.py`` was executed under a synthetic module
name with no parent package, so a relative import had nothing to resolve
against and the absolute name pointed at a package that was never imported.
"""

from __future__ import annotations

from tests.fixtures.igms.multi_module import helpers as absolute_helpers

from pylord.hooks import IGM

from . import helpers as relative_helpers


class MultiModule(IGM):
    key = "multi_module"
    name = "Multi Module"
    default_enabled = True

    def proof(self) -> tuple[str, str]:
        """Both import styles reached the same module."""
        return (relative_helpers.GREETING, absolute_helpers.shout("ok"))

    async def enter(self, ctx) -> None:
        await ctx.term.write(f"\n  {relative_helpers.GREETING}\n")
```

- [ ] **Step 2: Write the failing test**

Add to `tests/test_igm_framework.py`, next to the other discovery tests
(after `test_discover_missing_dir_returns_empty`):

```python
def test_a_plugin_can_be_split_across_modules():
    """The capability this whole change exists for: igm.py importing a
    sibling module in its own package, both relatively and absolutely."""
    from pylord import igm_loader

    reg = igm_loader.discover("tests.fixtures.igms", {})
    igm = next(i for i in reg.enabled if i.key == "multi_module")
    assert igm.proof() == ("helpers module reached", "OK")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_igm_framework.py::test_a_plugin_can_be_split_across_modules -v`
Expected: FAIL. `discover()` still takes a `Path`, so it treats the string
as a directory name, finds nothing, and `next()` raises `StopIteration`.

- [ ] **Step 4: Rewrite the loader**

In `pylord/igm_loader.py`, replace the module docstring's "Module import
strategy" paragraph (lines 13-21) with:

```
**Module import strategy.** A plugin is an ordinary Python package:
``igms/<name>/`` with an ``__init__.py`` and an ``igm.py``. Discovery
enumerates subpackages with :func:`pkgutil.iter_modules` and imports
``<package>.<name>.igm`` with :func:`importlib.import_module`, which means
a plugin's own modules can import each other -- relatively or absolutely --
like any other Python code.

This replaces an earlier scheme that executed ``igm.py`` alone via
``spec_from_file_location`` under a synthetic module name with no parent
package. That made relative imports impossible and confined every IGM to
one file. It also meant a second ``discover()`` re-executed the module;
now the second call gets the same module object out of ``sys.modules``,
which is simply what importing twice means in Python.
```

Replace the imports block:

```python
from __future__ import annotations

import importlib
import logging
import pkgutil
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pylord.hooks import IGM, ForestEvent, IgmMaintContext, InnEvent

if TYPE_CHECKING:
    import random
```

Replace `_load_one` (currently lines 46-79) with:

```python
def _load_one(package: str, name: str) -> IGM:
    """Import ``<package>.<name>.igm`` and return its validated IGM instance.

    Raises on any problem (import error, wrong subclass count, validation
    failure); the caller is responsible for catching + logging.
    """
    module = importlib.import_module(f"{package}.{name}.igm")

    subclasses = [
        obj
        for obj in vars(module).values()
        if isinstance(obj, type) and issubclass(obj, IGM) and obj is not IGM
    ]
    if len(subclasses) != 1:
        raise ValueError(
            f"expected exactly one IGM subclass in {package}.{name}.igm, "
            f"found {len(subclasses)}"
        )
    instance = subclasses[0]()
    # Relative imports work now, but a plugin still needs its directory to
    # reach non-Python files it ships -- data tables, .ANS screens.
    instance.dir = Path(module.__file__).parent
    _validate(instance)
    return instance
```

Replace `discover` and delete `_load_dir` entirely (currently lines 92-148):

```python
def load_all(package: str) -> list[IGM]:
    """Every valid IGM in ``package``, whether or not it is enabled.

    Sorted by subpackage name so duplicate-key resolution is deterministic:
    the first to claim a key wins and later claimants are logged and
    skipped. Never raises -- an unimportable root or a broken plugin is
    logged and skipped, because one bad plugin must never take the game
    down.
    """
    try:
        root = importlib.import_module(package)
    except BaseException:
        logger.warning("no IGMs loaded: cannot import %r", package, exc_info=True)
        return []

    loaded: list[IGM] = []
    seen_keys: set[str] = set()
    names = sorted(n for _, n, ispkg in pkgutil.iter_modules(root.__path__) if ispkg)

    for name in names:
        try:
            instance = _load_one(package, name)
        except BaseException:
            logger.warning("skipping broken IGM %s.%s", package, name, exc_info=True)
            continue
        if instance.key in seen_keys:
            logger.info(
                "ignoring %s.%s: key %r is already taken", package, name, instance.key
            )
            continue
        seen_keys.add(instance.key)
        loaded.append(instance)
    return loaded


def discover(package: str, config: dict[str, Any]) -> IgmRegistry:
    """Discover, validate, and enable the IGMs in ``package``.

    IGMs are *code*: they ship inside the image alongside the engine, and a
    new one arrives the way any other change does -- a folder in ``igms/``,
    a pull request, the next release.

    Returns an :class:`IgmRegistry` of the enabled instances. Enable state
    for each IGM key is ``config["igms"].get(key, instance.default_enabled)``.
    Never raises.
    """
    toggles: dict[str, Any] = (config or {}).get("igms", {}) or {}
    enabled = [
        igm for igm in load_all(package) if toggles.get(igm.key, igm.default_enabled)
    ]
    return IgmRegistry(enabled)
```

- [ ] **Step 5: Run the new test to verify it passes**

Run: `uv run pytest tests/test_igm_framework.py::test_a_plugin_can_be_split_across_modules -v`
Expected: PASS

- [ ] **Step 6: Update the existing discovery tests to pass package names**

In `tests/test_igm_framework.py`, replace the three path constants (lines
24-26) with package names:

```python
_IGMS_PKG = "tests.fixtures.igms"
_DUP_PKG = "tests.fixtures.igms_dup"
_DATA_PKG = "tests.fixtures.igms_data"
```

Then update each call site:

- line ~50 `discover(_IGMS_DIR, {})` → `discover(_IGMS_PKG, {})`
- line ~59 (in `test_discover_skips_broken_modules`) → `discover(_IGMS_PKG, {})`. **Also relax its assertion**: it currently reads `assert all(i.key == "sample" for i in reg.enabled)`, which the new `multi_module` fixture breaks. Change to `assert {i.key for i in reg.enabled} == {"sample", "multi_module"}` — still proving `broken_import` and `no_subclass` never make it in.
- line ~69 `discover(_FIXTURES / "does_not_exist", {})` → `discover("tests.fixtures.does_not_exist", {})`, and rename the test to `test_discover_unknown_package_returns_empty`.
- lines ~76 and ~86 `discover(_FIXTURES / "igms_data", {})` → `discover(_DATA_PKG, {})`.
- line ~109 → `discover(_IGMS_PKG, {"igms": {"sample": False}})`
- line ~116 → `discover(_DUP_PKG, {})`
- line ~123 → `discover(_IGMS_PKG, {})`

Also update `test_loader_sets_igm_dir_to_the_plugin_directory` (~line 76),
whose assertion still names a path:

```python
def test_loader_sets_igm_dir_to_the_plugin_directory():
    from pylord import igm_loader

    reg = igm_loader.discover(_DATA_PKG, {})
    (igm,) = reg.enabled
    assert igm.dir == Path(__file__).parent / "fixtures" / "igms_data" / "data_igm"
```

- [ ] **Step 7: Delete the two tests whose feature is gone**

`test_discover_prefers_the_first_directory_for_a_duplicate_key` (~lines
782-809) and `test_discover_still_accepts_a_single_directory` (~lines
812-815) both test multi-directory discovery. That existed so a
volume-seeded copy of an IGM could not shadow the shipped one; commit
`d53c20c` removed volume seeding, and a package name cannot name two roots.
Delete both. `test_duplicate_key_second_skipped` still covers first-wins
via the `igms_dup` fixture, and the unknown-package test covers the
nothing-found case.

- [ ] **Step 8: Check the remaining discover() calls for re-exec dependence**

Run: `uv run pytest tests/test_igm_framework.py -q`

`import_module` caches, so a second `discover()` in one process now returns
the same module objects rather than re-executing them. Read any failure in
that light before changing anything: if a test depended on a fresh module
per call, say so in its docstring and rewrite it to construct the IGM
directly instead of re-discovering.

Expected: all pass. The bundled IGMs are side-effect-free at module level,
so caching changes nothing observable for them.

- [ ] **Step 9: Run the whole suite**

Run: `uv run pytest tests/ -q 2>&1 | tail -5`
Expected: pass. `tests/test_server.py` and `tests/test_e2e_features.py`
will fail here if Task 3 has not landed — `server.py` still passes a
`Path`. If they do, that is expected; complete Task 3 before judging.

- [ ] **Step 10: Commit**

```bash
git add pylord/igm_loader.py tests/test_igm_framework.py tests/fixtures/igms/multi_module
git commit -m "feat(igms): load plugins as packages, so an IGM can span modules

An IGM was one file because the loader made it one: igm.py was executed
via spec_from_file_location under a synthetic module name with no parent
package, so a relative import had nothing to resolve against. Four vendored
sources -- felicity, lordcave, sandbar, violet -- are structurally
multi-file and could not be ported at all.

They are ordinary Python packages now, enumerated with pkgutil and
imported with import_module, so a plugin's modules import each other like
any other code. The synthetic names, the sys.modules juggling and the
multi-directory first-wins loop all go; discover() takes a package name.

Multi-directory discovery existed so a volume-seeded copy could not shadow
a shipped IGM, and d042da2's successor d53c20c removed volume seeding.
Duplicate keys are still first-wins, now by sorted subpackage name."
```

---

### Task 3: Point the call sites at the package, and ship it in the wheel

`server.py` still derives a filesystem path, which only ever worked because
of where the package happens to sit on disk. The wheel ships `pylord` only —
verified by building one — so a non-editable install has no IGMs at all.
The Dockerfile comment describes volume seeding that no longer exists.

**Files:**
- Modify: `pylord/server.py:432-437` (the only `discover()` caller in `pylord/` — verified)
- Modify: `pyproject.toml` (add hatch wheel target)
- Modify: `Dockerfile:56-57` (stale comment)
- Modify: `igms/README.md` (multi-module guidance)
- Test: `tests/test_igm_framework.py`

**Interfaces:**
- Consumes: `discover(package, config)` from Task 2.
- Produces: `pylord.server.start()` loads IGMs from the `"igms"` package. A built wheel contains both `pylord/` and `igms/`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_igm_framework.py`:

```python
def test_the_bundled_igms_load_by_package_name():
    """server.start() names the package rather than deriving a path from
    where pylord happens to sit on disk."""
    from pylord import igm_loader

    keys = {i.key for i in igm_loader.load_all("igms")}
    assert len(keys) == 16
    assert {"lotto", "pickle", "oorphans", "freeworld2"} <= keys
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/test_igm_framework.py::test_the_bundled_igms_load_by_package_name -v`
Expected: PASS already (Task 2 made `load_all` work). This test pins the
bundled set so a later packaging mistake that empties `igms/` fails loudly
rather than silently loading zero IGMs.

- [ ] **Step 3: Update `pylord/server.py`**

Replace lines 432-437:

```python
    # Discover the IGMs shipped with this build, once at startup; the
    # registry is shared (read-only after discovery) by every connection.
    # IGMs are code -- they arrive with a release, not by being copied onto
    # a volume, so the data directory holds nothing but the database.
    igms = igm_loader.discover("igms", config)
    logger.info("loaded %d enabled IGM(s)", len(igms.enabled))
```

Then remove the now-unused `Path` import from `pylord/server.py` **only if
nothing else in the file uses it** — check with
`grep -n "Path" pylord/server.py` first.

- [ ] **Step 4: Confirm no other caller was missed**

Run: `grep -rn "discover(" pylord/ tests/ --include=*.py | grep -v igm_loader.py`

`pylord/server.py` was the only caller in `pylord/` when this plan was
written, and Task 2 already updated the ones in `tests/`. Every remaining
hit must pass a dotted package name; if a `Path` survives anywhere, fix it
now rather than letting it fail at runtime, where `discover()` swallows the
error and loads zero IGMs.

- [ ] **Step 5: Add igms to the wheel**

Append to `pyproject.toml`, after the `[build-system]` block:

```toml
[tool.hatch.build.targets.wheel]
# Both, explicitly: hatchling would otherwise infer only the package named
# after the project, and a wheel without igms/ is a realm with no Other
# Places at all. The container has not noticed because uv installs the
# project editable, which puts the source root on sys.path.
packages = ["pylord", "igms"]
```

- [ ] **Step 6: Verify the wheel**

```bash
uv build --wheel --out-dir /tmp/pylord-wheel
uv run python -c "
import zipfile, glob
w = sorted(glob.glob('/tmp/pylord-wheel/*.whl'))[-1]
tops = {n.split('/')[0] for n in zipfile.ZipFile(w).namelist()}
print(sorted(tops))
assert 'igms' in tops and 'pylord' in tops, tops
print('OK')
"
rm -rf /tmp/pylord-wheel
```

Expected: `['igms', 'pylord', 'pylord-0.1.1.dist-info']` then `OK`.

- [ ] **Step 7: Fix the stale Dockerfile comment**

Replace `Dockerfile` lines 56-57:

```dockerfile
# IGMs are code and ship with the image, next to the package that loads
# them by name. The data volume holds nothing but the database.
COPY --chown=pylord:pylord igms/ ./igms/
```

- [ ] **Step 8: Update the plugin contract in `igms/README.md`**

Replace the "Use absolute imports" blockquote (~lines 91-95) with:

````markdown
### Splitting a plugin across modules

An IGM is a real Python package, so a big one does not have to live in a
single `igm.py`. Put whatever you like beside it and import it normally:

```
igms/felicity/
  __init__.py
  igm.py          # still exactly one IGM subclass
  statues.py
  prayer.py
```

```python
from . import statues                  # relative
from igms.felicity import prayer       # or absolute -- both work
```

The loader imports `igms.<your_igm>.igm` and looks for the single `IGM`
subclass there; the other modules are yours to arrange. Keep them
side-effect-free at import: the loader imports every plugin at startup.
````

- [ ] **Step 9: Run the whole suite**

Run: `uv run pytest tests/ -q 2>&1 | tail -5`
Expected: all pass, including `tests/test_server.py` and
`tests/test_e2e_features.py`, which exercise `start()` for real.

- [ ] **Step 10: Lint**

Run: `uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 11: Commit**

```bash
git add pylord/server.py pyproject.toml Dockerfile igms/README.md tests/test_igm_framework.py
git commit -m "feat(igms): load the bundled set by package name, and ship it

server.start() derived igms/ from where pylord sat on disk, which worked
only because the two happen to be siblings. It names the package now.

The wheel shipped pylord/ alone, so a non-editable install had no IGMs --
masked entirely because uv installs the project editable and the .pth puts
the source root on sys.path. Both packages ship now.

The Dockerfile still claimed the IGMs were seeded into the data volume;
d53c20c ended that."
```

---

### Task 4: Conformance test — every IGM, every hook, no hand-maintained list

The point is that a change to pylord's IGM-facing API fails across all 16
bundled plugins at once, rather than silently in whichever one someone
happens to run next. It also gives `forest_event` and `inn_event` their
first exercise: both hooks exist in `pylord/hooks.py:101,110` and have
**zero** users across 16 IGMs.

**Files:**
- Create: `tests/igms/test_conformance.py`
- Modify: `tests/igms/test_wave2.py` (retire the contract parametrisation)
- Modify: `tests/igms/test_wave3.py` (same)

**Interfaces:**
- Consumes: `igm_loader.load_all("igms")` from Task 2; `contract_check` from `tests/igm_contract.py`; `make_db`, `make_maint_ctx` from `tests/igms/_harness.py`.
- Produces: nothing other tasks depend on. This is the last task.

- [ ] **Step 1: Write the conformance test**

Create `tests/igms/test_conformance.py`:

```python
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


def test_the_bundled_set_is_not_empty():
    """A packaging mistake that stops IGMs loading would otherwise turn
    every parametrised test below into a silent no-op."""
    assert len(ALL_IGMS) == 16


@pytest.mark.parametrize("igm", ALL_IGMS, ids=IDS)
async def test_contract(igm: IGM):
    await contract_check(type(igm))


@pytest.mark.parametrize("igm", ALL_IGMS, ids=IDS)
async def test_daily_maint_runs_if_overridden(igm: IGM):
    """Ten of the sixteen override daily_maint. It runs during global
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
    config = tomllib.loads(Path("config.toml").read_text())
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
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/igms/test_conformance.py -v 2>&1 | tail -30`

Expected: all pass. If `test_config_lists_every_igm_with_its_default`
fails, that is a real finding — fix `config.toml` rather than the test.
If a `contract_check` fails for one IGM, that is also real; fix the IGM.

- [ ] **Step 3: Retire the hand-maintained contract lists**

In `tests/igms/test_wave2.py`, delete `test_contract` and
`test_ships_disabled` and the `_WAVE2` list feeding them, plus the now-unused
`contract_check` import. Keep every mechanics test.

In `tests/igms/test_wave3.py`, do the same for `test_contract`,
`test_ships_disabled` and `_WAVE3`.

Both are now covered for **all sixteen** IGMs by `test_conformance.py`,
not just the twelve someone remembered to list.

- [ ] **Step 4: Check the starter-six test modules too**

Run: `grep -ln "contract_check" tests/igms/`

For each hit other than `test_conformance.py`, delete its `contract_check`
call and the import if unused. Leave all behavioural tests alone.

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest tests/ -q 2>&1 | tail -5`
Expected: all pass. The count will differ from 644 — conformance adds
roughly 16×5 parametrised cases while the retired lists remove about 24.
Confirm the *number of failures* is zero; do not chase the total.

- [ ] **Step 6: Lint**

Run: `uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add tests/igms/
git commit -m "test(igms): hold every IGM to the contract, without a list

The contract check ran against a hand-maintained list of twelve classes
across two modules, so a new IGM was covered only if someone remembered to
add it. It discovers all sixteen through the real loader now.

It also invokes every hook a plugin actually overrides, which gives
forest_event and inn_event their first exercise -- both have existed since
28f83d0 with zero users -- and pins each IGM's config.toml entry against
its declared default, so the sysop's switchboard cannot drift from the
code."
```

---

## Verification

After all four tasks:

1. `uv run pytest tests/ -q` — zero failures, no new warnings.
2. `uv run ruff check .` — clean.
3. Enable everything and walk the menu for real:
   ```bash
   uv run python -c "
   import asyncio, tomllib, random
   from pathlib import Path
   from pylord import igm_loader, data
   from pylord.engine.game import GameCtx
   from pylord.engine.scenes.other_places import other_places
   from pylord.terminal import FakeIO, strip
   cfg = tomllib.loads(Path('config.toml').read_text())
   cfg['igms'] = {k: True for k in cfg['igms']}
   reg = igm_loader.discover('igms', cfg)
   print(len(reg.enabled), 'enabled:', [i.key for i in reg.other_places()])
   assert len(reg.enabled) == 16
   "
   ```
   Expected: 16 enabled, listed in display-name order.
4. `uv build --wheel` and confirm the wheel holds both `pylord/` and `igms/`.
5. Build the image and run it, confirming the startup log reports the
   discovered IGM count. **This is the step that actually proves the
   package import works in the container** rather than only under the
   repo's editable install — everything above passes either way.

## Follow-on work this unblocks

Not part of this plan. Recorded so the next session does not have to
rediscover it:

- Port `felicity` (12 files), `lordcave` (4 + 11 scripts), `sandbar` (6)
  and `violet` (3) — the four that needed this.
- `grabbag` (3,191 lines, one file) was never blocked and is portable now.
- TeamLord and cross-player party state remain out of scope, pending a
  separate team-play evaluation.
