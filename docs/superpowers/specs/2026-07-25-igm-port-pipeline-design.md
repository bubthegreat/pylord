# IGM Port Pipeline — Design

**Date:** 2026-07-25
**Status:** Approved

## Goal

Work through the 683 archived DOS-era LORD IGM zips in `igms_to_port/` and
port the famous LORD1 classics to pylord's IGM plugin system, slowly and
informally, favouring archives whose behaviour we can reproduce from real
evidence over ones we would have to invent.

## Decisions (from brainstorming)

- **Curation:** famous classics first; no catalogue machinery or scoring.
- **Fidelity:** split the archive into *direct-portable* (readable logic)
  and *infer-from-docs* shelves. Port direct-portable first. For the rest,
  prefer archives whose docs record menus, prices, and formulas; reproduce
  those verbatim and invent only what is unrecorded.
- **Scope:** LORD1-targeted IGMs only. LORD2 `.REF` world scripts stay
  archived until pylord ever grows LORD2-ish features.
- **Cadence:** no fixed unit of work. Ports land as ordinary commits to
  main; no branches, PRs, or queue documents required.
- **Triage:** one-time shelf scan whose output lives in
  `igms_to_port/README.md`; the scan script itself is throwaway.

## Archive facts that shaped the design

Scanned 2026-07-24/25:

| Contents | Count | Consequence |
|---|---|---|
| Real source (`.pas`/`.bas`) | 4 | `barsrc.zip` is Pascal source of the already-ported Barak's House; the other three are dev kits/utilities, not IGMs |
| WildCat wcCODE | 41 | all compiled `.wcx`, zero `.wcc` source — **not** readable |
| LORD2 `.REF` scripts | 170 | readable but out of scope (LORD2) — except some are LORD1 script-host sets misfiled by extension (see below) |
| EXE-only | 338 | infer-from-docs tier |
| No exe/source | 129 | mostly utilities, ANSI packs, patches, data — mostly Shelf D |
| Unreadable | 1 | `tense100.zip`, damaged on the mirror itself |

Key nuance: some `.ref`-bearing zips are **LORD1** script-driven IGMs
(LORD Cavern / ANGEL-toolkit hosts, e.g. `caverhp1.zip`, `cave14a.zip`,
`gate10.zip`, `outs13.zip`). Their scripts are readable logic targeting
LORD1. The shelf scan must separate these from true LORD2 material by
reading the docs (LORD2 / "LORD ]["), not just the file extension.

## Design

### 1. Shelf scan (one-time)

A throwaway script (run from the scratchpad, not committed) walks every
zip, reads `FILE_ID.DIZ` and doc files, and classifies each archive:

- **Shelf A — direct-portable:** readable logic targeting LORD1: true
  source, plus LORD1 script-host sets (Cavern/ANGEL style).
- **Shelf B — documented recreations:** LORD1, EXE-only, docs describe
  gameplay. Each gets its DIZ one-liner. Famous classics starred.
- **Shelf C — LORD2:** parked, listed by name only.
- **Shelf D — not portable / not an IGM:** utilities, ANSI/text packs,
  patches, data files, damaged archives.

Output: shelf sections appended to `igms_to_port/README.md`. That README
is the only persistent triage artifact.

Classification heuristics (best-effort, corrected by hand at port time):
docs mentioning "LORD II"/"LORD2"/"LORD ][" → Shelf C; `.ref`/script files
plus LORD 3.x references → Shelf A; keywords like "editor", "utility",
"ANSI", "patch", "help" with no game loop → Shelf D; otherwise Shelf B.
Misclassification is cheap — a wrong shelf is a wrong line in a README.

### 2. Port loop (informal)

Pick from Shelf A first, then starred Shelf B entries. Per IGM:

1. Unzip into the scratchpad; read the logic (Shelf A) or the docs
   (Shelf B).
2. Write `igms/<key>/igm.py` following the wave-2 conventions already in
   the tree: `default_enabled = False`, entries in `config.toml` and
   `deploy/values/*.yaml`, LORD colour codes, `ctx` facade only.
3. The module docstring states the provenance tier: **direct port**
   (from readable logic), or **documented recreation** (verbatim numbers
   from docs) — and lists exactly what was invented to fill gaps.
4. Tests beside the existing IGM tests: at minimum enter/leave plus one
   mechanic assertion; add a smoke-walk hook when cheap.
5. `uv run pytest` and `uv run pylord smoke` green before commit.
6. Commit straight to main. `docs/deviations.md` gains an entry only when
   we knowingly diverge from recorded original behaviour.

An external automation pushes commits to main (health-check fixes), so
**always `git pull --rebase` immediately before any push.**

### 3. First unit of work: Barak audit

`barsrc.zip` contains the real Pascal source of Barak's House, which was
ported in wave 1 as a recreation. First "port" is therefore an audit:
diff `igms/baraks_house/igm.py` against `BARAK.PAS`, adopt the recorded
numbers and flows verbatim, and record any deliberate deviations in
`docs/deviations.md`.

### 4. Error handling and testing

- The engine already contains IGM crashes (visit rolls back, player
  returns to town); ports rely on that rather than their own guards.
- Player-writes go through the validated `ctx.player` facade, so a bad
  formula cannot corrupt a character.
- Out of scope: `tense100.zip` (damaged), Shelf C, Shelf D, and the 8
  index entries that 404 on the mirror.

## Success criteria

- `igms_to_port/README.md` lists every archive on a shelf with a
  one-liner for Shelf A/B.
- Barak's House matches its real source, deviations documented.
- At least the first few Shelf A/B classics ported, each green under
  `pytest` + `smoke`, toggleable in config, off by default.
