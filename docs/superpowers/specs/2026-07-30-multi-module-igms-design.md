# Multi-module IGMs: load plugins as real Python packages

## Context

`pylord/igm_loader.py` loads exactly one file per plugin. It imports
`igms/<name>/igm.py` with `importlib.util.spec_from_file_location` under a
synthetic module name `igms.<name>` that has no parent package, so
package-relative imports inside a plugin cannot resolve. `igms/README.md`
tells authors to keep all their logic in `igm.py` for that reason.

That is now the binding constraint on the IGM catalogue. Four of the
vendored sources in `reference/igm-sources/` are structurally multi-file
and cannot be ported until a plugin can be more than one module:

| Source | Files | Lines |
|---|---|---|
| `lordts/felicity/` — Felicity's Temple | 12 | 3,236 |
| `lordts/lordcave/` — The L.O.R.D. Cavern | 4 + 11 `.rhp` scripts | 2,275 |
| `lordts/sandbar/` — Sandtiger's Bar v1.02 | 6 | 2,376 |
| `lordts/violet/` — Violet's Cottage | 3 | 1,981 |

The alternative — porting each as one 1,000+ line `igm.py` — trades a
framework limitation for permanently unreadable modules.

A recent change (`IGM.dir`, wave 3) let a plugin read its own *data* and
`.ANS` files. This addresses the other half: its own *code*.

## What exploration established

Three findings shaped the design, and two of them removed work rather than
adding it.

**The plugin directories are already packages.** All 16 have `__init__.py`.
`tests/igms/test_wave3.py:24` already does `from igms.lotto.igm import Lotto`
as an ordinary import. Only the *runtime* loader uses the synthetic path, so
the same files are reached two different ways depending on who is asking.
The original design spec
(`docs/superpowers/specs/2026-07-23-pylord-design.md:65`) called for a
"package dir" from the start.

**There is no `sys.path` problem.** The obvious objection to importing
`igms` by name is that the container puts it at `/app/igms`, beside rather
than inside the installed package. But `uv sync` installs pylord
**editable**, via an `_editable_impl_pylord.pth` holding the project root —
which puts `/app` on `sys.path`. `import igms.lotto.igm` already resolves at
runtime today, verified from outside the repo working directory. The
mechanism the loader was written to avoid needing has been available all
along.

**Only the test fixtures need work.** `pkgutil.iter_modules` finds all 16
real IGMs. The loader's fixtures under `tests/fixtures/` lack `__init__.py`
and do not enumerate. Nine files fix that; no enumeration workaround is
needed.

## Decisions

| Decision | Choice |
|---|---|
| Plugin shape | A real, importable Python package |
| Packaging | One `igms` package, each IGM a subpackage. Not one distribution per IGM |
| Discovery input | Package name (`discover("igms", config)`), not a filesystem path |
| Resolution | Ordinary `__init__.py` hygiene, not synthetic parent packages |
| Wheel | `igms` added to the hatch wheel target |
| Conformance test | Auto-discovered, full contract |

Entry-point plugin distributions (`[project.entry-points."pylord.igms"]`)
were considered and rejected as YAGNI: nothing today installs an IGM from
outside this repo, and the config.toml `[igms]` toggle story would need
rethinking to support it.

## Design

### Plugin shape

`igms/` gains an `__init__.py`, making it a regular package rather than an
implicit namespace package. Every IGM directory is a subpackage, which all
16 already are. Nothing moves and nothing is renamed.

A multi-file plugin is then unremarkable Python:

```
igms/felicity/
  __init__.py
  igm.py          # the single IGM subclass, as always
  statues.py
  prayer.py
  screens/…       # via IGM.dir, unchanged
```

with `igm.py` free to use either `from . import statues` or
`from igms.felicity import statues`. `igms/README.md`'s "use absolute
imports" warning is replaced by guidance on structuring a multi-module
plugin.

### The loader

`pylord/igm_loader.py` stops being an import mechanism and becomes what its
name says — discovery and validation.

- `discover(package: str, config)` replaces
  `discover(igms_dir: Path | Iterable[Path], config)`.
- Enumerate with `pkgutil.iter_modules(import_module(package).__path__)`,
  keeping entries where `ispkg`.
- Load with `import_module(f"{package}.{name}.igm")`.
- Then, unchanged: find exactly one `IGM` subclass, `_validate()` it, set
  `IGM.dir` (now from `Path(module.__file__).parent`), resolve the enabled
  flag from `config["igms"]`.

Removed: `spec_from_file_location`, the `sys.modules` insert-before-exec /
pop-on-failure juggling, and the multi-directory first-wins loop. The
multi-directory support existed for volume-seeded IGMs, which `d53c20c`
removed, and for test isolation, which package names now provide.

Retained exactly as-is: a broken plugin is logged and skipped, and
`discover()` never raises. Two IGMs declaring the same `key` keep
first-wins by iteration order, with the loser logged.

### Call sites

- `pylord/server.py:435` — `Path(__file__).resolve().parent.parent / "igms"`
  becomes `discover("igms", config)`, deleting a path derivation that only
  worked because of where the package happens to sit on disk.
- Tests pass `"tests.fixtures.igms"` and friends.
- `Dockerfile:56-57` — the comment claims the bundled IGMs are seeded into
  the data volume and that the loader resolves `igms/` next to the
  database. `d53c20c` removed that; the comment describes behaviour that no
  longer exists and is corrected here.
- `pyproject.toml` — add `[tool.hatch.build.targets.wheel] packages =
  ["pylord", "igms"]`. Today only `pylord/` would ship in a wheel; the
  container works solely because the install is editable. That is a latent
  gap this change is the right moment to close.

### Accepted behaviour change

`import_module` caches in `sys.modules`. A second `discover()` returns the
already-imported module rather than re-executing a fresh one, which
`igm_loader.py:13-21` currently documents as deliberate.

This is the more correct semantic — importing a module twice giving you the
same module is simply how Python works — but it is a real change, and
`tests/test_igm_framework.py` calls `discover` ten times. Those tests are
reviewed as part of the work and the loader docstring's re-exec paragraph
is rewritten. Any test that genuinely depends on re-execution states why.

### Conformance test

`tests/igms/test_conformance.py`, new. Its purpose is that a change to
pylord's IGM-facing API fails loudly across every bundled plugin at once,
rather than silently in whichever IGM someone next happens to run.

It discovers IGMs through the *real* loader with every toggle forced on, so
there is no hand-maintained class list and a new IGM is covered the moment
its directory lands. For each discovered IGM:

- `contract_check()` (`tests/igm_contract.py`) — imports cleanly, `enter()`
  runs to completion or degrades gracefully on `OutOfKeys`, the player
  guardrails hold, the store round-trips through the database.
- Every *overridden* optional hook is actually invoked: `daily_maint`
  against a real `IgmMaintContext`, and `forest_event` / `inn_event` called
  with their return types checked. Those two hooks exist in
  `pylord/hooks.py:101,110` and have had **zero** users across 16 IGMs, so
  this is their first exercise.
- Static checks across the set: `key` values unique, `default_enabled`
  agrees with `config.toml`'s `[igms]` table, `IGM.dir` resolves, and any
  `data/` or `screens/` file a plugin reads exists.

The hand-listed `_WAVE2` / `_WAVE3` contract parametrisations in
`tests/igms/test_wave2.py` and `test_wave3.py` are retired in its favour.
Their per-IGM mechanics tests stay — those assert behaviour, not contract.

### Loader tests

- A new `tests/fixtures/igms/multi_module/` plugin with `igm.py` plus a
  `helpers.py`, exercising **both** a relative (`from . import helpers`)
  and an absolute (`from tests.fixtures.igms.multi_module import helpers`)
  intra-plugin import. This is the regression test for the whole change.
- Existing `sample_igm` / `broken_import` / `no_subclass` / `igms_dup`
  fixtures keep their meaning, retargeted at package names, and gain the
  nine `__init__.py` files that make them enumerable.

## Out of scope

- **TeamLord** (`lordts/teamlord/`, 3,220 lines) and cross-player party
  state. Team play is a separate evaluation with its own design; this work
  neither enables nor prepares for it.
- Entry-point plugin distributions, and third-party IGMs installed from
  outside this repo.
- Formalizing pylord's IGM-facing public API beyond what `pylord.hooks`
  already exposes. The conformance test above will make drift in that API
  visible, which is the prerequisite for formalizing it later.
- Porting any IGM. This change unblocks `felicity`, `lordcave`, `sandbar`
  and `violet`; each port is separate work.

## Verification

1. `uv run pytest tests/ -q` — the full suite, including the new
   conformance and multi-module tests.
2. `uv run ruff check .`
3. Start the server with every IGM enabled and walk Town Square →
   `(O)ther places`, confirming all 16 list and enter.
4. `uv build`, then confirm the wheel contains both `pylord/` and `igms/`.
5. Build the image and run it, confirming the loader logs 16 discovered
   IGMs — this is what proves the package import works in the container and
   not only under the repo's editable install.
