# IGM Port Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Triage the 683 archived LORD IGM zips onto shelves in `igms_to_port/README.md`, audit Barak's House against its real Pascal source, and land the first documented-recreation port.

**Architecture:** A throwaway scratchpad script classifies every zip (LORD1 direct-portable / documented / LORD2 / non-IGM) into README sections. Ports are ordinary `igms/<key>/` plugins following the wave-2 conventions, tested with `tests/igms/_harness.py`, committed straight to main.

**Tech Stack:** Python 3.12, stdlib `zipfile`, pylord IGM plugin API (`pylord.hooks.IGM`), pytest via `uv run pytest`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-25-igm-port-pipeline-design.md`.
- All new IGMs: `default_enabled = False`, toggles added to `config.toml` `[igms]` and BOTH `deploy/values/prod.yaml` and `deploy/values/local.yaml` `igms:` maps (prod may enable; local mirrors config).
- Module docstring must state provenance tier (direct port / documented recreation) and list everything invented.
- LORD2-targeted archives are out of scope; so are `tense100.zip` and the 8 dead-link files.
- Commit author: pass `-c user.name='Bub Taylor' -c user.email='bubthegreat@gmail.com'` (repo has no local identity).
- **An external script pushes health-check fixes to main. Before ANY `git push`, run `git pull --rebase origin main`.** Commits themselves are safe; only pushes race.
- Verification before any "done" claim: `uv run pytest` and `uv run pylord smoke` both green.

---

### Task 1: Shelf scan into `igms_to_port/README.md`

**Files:**
- Create (scratchpad, NOT committed): `<scratchpad>/shelf_scan.py`
- Modify: `igms_to_port/README.md` (append shelf sections)

**Interfaces:**
- Produces: README sections `## Shelf A — direct-portable (LORD1, readable logic)`, `## Shelf B — documented recreations (LORD1, EXE-only)`, `## Shelf C — LORD2 (parked)`, `## Shelf D — not portable / not an IGM`. Task 3 reads Shelf A/B to pick ports.

- [ ] **Step 1: Write the scan script in the scratchpad**

```python
"""Classify every igms_to_port zip onto a shelf; emit markdown sections."""
import re, zipfile, pathlib, collections

ROOT = pathlib.Path("igms_to_port")
# Names (stem prefixes) known famous from the historical IGM catalogue.
FAMOUS = {
    "sfairy", "ww", "fair", "faire", "grave", "dapit", "barak", "arena",
    "wall", "wl-", "stone", "kaldor", "keep", "camel", "jester", "witch",
    "wizard", "prison", "mafia", "avalon", "xenon", "phan",
}
LORD2_PAT = re.compile(r"lord\s*(ii|2|\]\[)|for\s+l(\.o\.r\.d\.)?\s*(ii|2)", re.I)
SCRIPT_HOST_PAT = re.compile(r"lordcave|outlands|angel toolkit|skeleton", re.I)
UTIL_PAT = re.compile(
    r"editor|utility|utilit|patch|convert|ansi\s+set|help file|faq|"
    r"top.?ten|html|maint|manager|reset|backup", re.I)

def docs_text(z):
    out = []
    for n in z.namelist():
        if re.search(r"file_id\.diz|\.diz$|read.?me|\.doc$|\.txt$", n, re.I):
            try:
                out.append(z.read(n)[:6000].decode("cp437", errors="replace"))
            except Exception:
                pass
    return "\n".join(out)

def diz_line(z):
    for n in z.namelist():
        if n.lower().endswith("file_id.diz"):
            try:
                raw = z.read(n)[:400].decode("cp437", errors="replace")
                return re.sub(r"\s+", " ", raw).strip()[:120]
            except Exception:
                pass
    return ""

shelves = collections.defaultdict(list)
for zp in sorted(ROOT.glob("*.zip")):
    try:
        z = zipfile.ZipFile(zp)
    except Exception:
        shelves["D"].append((zp.name, "unreadable archive"))
        continue
    names = [n.lower() for n in z.namelist()]
    exts = {pathlib.Path(n).suffix for n in names}
    text = docs_text(z)
    one = diz_line(z)
    star = "★ " if any(zp.stem.lower().startswith(f) for f in FAMOUS) else ""
    if LORD2_PAT.search(text):
        shelves["C"].append((zp.name, one))
    elif {".pas", ".bas"} & exts or (".ref" in exts and SCRIPT_HOST_PAT.search(text)):
        shelves["A"].append((zp.name, star + one))
    elif UTIL_PAT.search(one) or not ({".exe", ".com", ".ref", ".wcx"} & exts):
        shelves["D"].append((zp.name, one))
    else:
        shelves["B"].append((zp.name, star + one))

TITLES = {
    "A": "Shelf A — direct-portable (LORD1, readable logic)",
    "B": "Shelf B — documented recreations (LORD1, EXE-only)",
    "C": "Shelf C — LORD2 (parked)",
    "D": "Shelf D — not portable / not an IGM",
}
for shelf in "ABCD":
    print(f"\n## {TITLES[shelf]}\n")
    print(f"{len(shelves[shelf])} archives. ★ = famous classic, port first.\n"
          if shelf in "AB" else f"{len(shelves[shelf])} archives.\n")
    for name, line in shelves[shelf]:
        print(f"- `{name}` — {line}" if line else f"- `{name}`")
```

- [ ] **Step 2: Run it, sanity-check the classification**

Run: `python3 <scratchpad>/shelf_scan.py > <scratchpad>/shelves.md; head -50 <scratchpad>/shelves.md`
Expected: Shelf A small (single digits — `barsrc.zip`, `caverhp1.zip`, cavern/script sets); Shelf C large (~170); spot-check 5 names per shelf against their DIZ lines. Known checks: `ww301.zip` on B starred, `lordhtm.zip` on D, `cnw-1361.zip` on C. Adjust patterns and re-run until those three land right.

- [ ] **Step 3: Append the sections to `igms_to_port/README.md`**

Append `shelves.md` under the existing content (after "Known oddities"), keeping the header block intact. Add one intro line: `Shelves generated by a one-time scan (2026-07-25); classifications are best-effort and corrected at port time.`

- [ ] **Step 4: Commit**

```bash
git add igms_to_port/README.md
git -c user.name='Bub Taylor' -c user.email='bubthegreat@gmail.com' \
  commit -m "docs: shelve the IGM archive for porting"
```

---

### Task 2: Barak's House source audit

**Files:**
- Read: `barsrc.zip` → extract to scratchpad; primary source `BARAK.PAS` (+ `BAR_VAR.PAS`)
- Modify: `igms/baraks_house/igm.py`, `tests/igms/test_baraks_house.py` (or wherever `git grep -l baraks_house tests/` points)
- Modify: `docs/deviations.md`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `igms/baraks_house/igm.py` with numbers matching `BARAK.PAS`; docstring updated from "recreation" to "verified against original Pascal source".

- [ ] **Step 1: Extract and read the source**

```bash
python3 -c "import zipfile; zipfile.ZipFile('igms_to_port/barsrc.zip').extractall('<scratchpad>/barsrc')"
```
Read `BARAK.PAS` and `BAR_VAR.PAS` fully. Inventory every player-visible mechanic: menu options, prices, stat deltas, probabilities, daily limits, strings.

- [ ] **Step 2: Diff against our recreation**

Read `igms/baraks_house/igm.py`. Produce a table (in the eventual commit message / deviations entry): mechanic → Pascal value → pylord value → action (adopt / keep-as-deviation).

- [ ] **Step 3: Write failing tests for each adopted verbatim number**

For every mechanic whose value changes, pin the Pascal value in the existing test module first. Follow the house pattern:

```python
async def test_price_matches_original_source():
    gctx, ictx, player, db = await _visit(BaraksHouse, keys=[...], gold=1000)
    await BaraksHouse().enter(ictx)
    assert player.gold == 1000 - PASCAL_PRICE  # value read from BARAK.PAS
```

Run: `uv run pytest tests/igms -k barak -v` — new assertions FAIL against current invented numbers.

- [ ] **Step 4: Adopt the verbatim values in `igm.py`; docstring update**

Change constants/flows to the Pascal values. Docstring: provenance becomes "direct-port-verified: numbers from BARAK.PAS (barsrc.zip)"; anything deliberately kept different moves to `docs/deviations.md` with a reason.

- [ ] **Step 5: Verify**

Run: `uv run pytest && uv run pylord smoke`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add igms/baraks_house tests docs/deviations.md
git -c user.name='Bub Taylor' -c user.email='bubthegreat@gmail.com' \
  commit -m "feat(igms): verify Barak's House against original Pascal source"
```

---

### Task 3: First documented-recreation port — WereWolf (ww301)

If Step 1 shows `ww301.zip`'s docs record too little (no concrete mechanics beyond the DIZ), substitute the starred Shelf B entry with the richest docs and follow the same steps; note the substitution in the commit message.

**Files:**
- Read: `ww301.zip` → scratchpad
- Create: `igms/werewolf/igm.py`
- Create: `tests/igms/test_werewolf.py`
- Modify: `config.toml` (`[igms]` add `werewolf = false`), `deploy/values/prod.yaml`, `deploy/values/local.yaml` (`igms:` maps)

**Interfaces:**
- Consumes: wave-2 conventions (`pylord.hooks.IGM`, `IgmContext`), test plumbing from `tests/igms/_harness.py` (`make_db`, `make_ctx`, `make_igm_ctx`, `SeqRandom`), `tests/igm_contract.contract_check`.
- Produces: `class WereWolf(IGM)` with `key = "werewolf"`.

- [ ] **Step 1: Extract, read every doc file, inventory recorded mechanics**

```bash
python3 -c "import zipfile; zipfile.ZipFile('igms_to_port/ww301.zip').extractall('<scratchpad>/ww301')"
```
List what the docs actually record: menu layout, transformation rules, costs, PvP interaction ("kill other players and desecrate their dead bodies"), sysop-configurable knobs. Write the inventory into the module docstring draft: **recorded** list vs **invented** list.

- [ ] **Step 2: Write the failing test module**

```python
"""WereWolf (ww301) -- documented recreation."""
from igms.werewolf.igm import WereWolf
from tests.igm_contract import contract_check
from tests.igms._harness import make_ctx, make_db, make_igm_ctx


async def _visit(keys, rng=None, **overrides):
    database, repo = await make_db()
    player = await repo.create("Hero", "pw", "M")
    for key, value in overrides.items():
        setattr(player, key, value)
    gctx = make_ctx(database, repo, player, keys=keys, rng=rng)
    return gctx, await make_igm_ctx(gctx, WereWolf), player, database


async def test_contract():
    await contract_check(WereWolf)


def test_ships_disabled():
    assert WereWolf.default_enabled is False
    assert WereWolf.key == "werewolf"
```
Plus one failing test per mechanic recorded in Step 1 (exact assertions come from the archive docs — pin every number the docs state, `SeqRandom` for any probability roll).

Run: `uv run pytest tests/igms/test_werewolf.py -v` — FAIL (module doesn't exist).

- [ ] **Step 3: Implement `igms/werewolf/igm.py`**

Skeleton per house style (see `igms/apothecary/igm.py`): module docstring with provenance tier + recorded/invented split, `_MENU` string in LORD colour codes, constants for every number, `class WereWolf(IGM)` with `key/name/author/default_enabled=False` and `async def enter(self, ctx)` menu loop via `ctx.term.menu`. Mechanics exactly as recorded; gaps filled minimally and listed in the docstring.

- [ ] **Step 4: Wire the toggles**

`config.toml` `[igms]`: `werewolf = false`. `deploy/values/local.yaml` and `deploy/values/prod.yaml` `igms:` maps: `werewolf: false` (sysop flips prod when ready).

- [ ] **Step 5: Verify**

Run: `uv run pytest && uv run pylord smoke`
Expected: green, including discovery picking up the new folder (`test_igm_framework` loader tests unaffected; `smoke` still passes with the IGM disabled).

- [ ] **Step 6: Commit, then push everything with rebase**

```bash
git add igms/werewolf tests/igms/test_werewolf.py config.toml deploy/values
git -c user.name='Bub Taylor' -c user.email='bubthegreat@gmail.com' \
  commit -m "feat(igms): port WereWolf (ww301) as a documented recreation"
git pull --rebase origin main   # health-check fixer pushes to main
uv run pytest                    # re-verify post-rebase
git push origin main
```

---

## Self-review notes

- Spec coverage: shelf scan → Task 1; Barak audit → Task 2; first classic port + port-loop conventions → Task 3; LORD2/damaged exclusions are constraints, not tasks. The ongoing churn beyond the first port is intentionally outside this plan (spec: "no fixed unit").
- Exact mechanics in Tasks 2–3 come from reading the archive at execution time; the plan pins the process, files, verification, and every convention instead — that is the nature of an audit/port against primary sources.
- Type consistency: `_visit` helper signature matches `tests/igms/test_wave2.py`'s established pattern; `WereWolf.key = "werewolf"` used consistently across igm.py, config, values, tests.
