# Reference Source Files

## Provenance

This directory contains reference source files from the Synchronet BBS door game project.

**Repository:** https://github.com/SynchronetBBS/sbbs  
**Source Directory:** `xtrn/lord/`  
**Fetched:** 2026-07-23  
**Upstream License:** GPL-3.0

## Files

- `lord.js` - Main game logic and implementation
- `recorddefs.js` - Record file format definitions and data structures
- `assets/` - `.lrd` screen and text assets the base game displays

## IGM sources (`igm-sources/`)

The base game above never modelled an IGM's internals -- IGMs were separate
DOS executables reached through the `3RDPARTY.DAT` handshake. Real source for
a number of them is vendored under `igm-sources/`, in two GPL trees
(`lordts/` and `synchronet/`).

**See `igm-sources/README.md`** for the full inventory: upstream provenance
and licence per tree, which bundled `igms/` recreations have a real original,
which IGMs have source but no port yet, which modules are maintenance hooks
rather than places to visit, and which sources were deliberately not vendored.

`igms/README.md` records the same ports-vs-recreations split from the
`igms/` side.

## Usage

These files are **reference only** and are not imported at runtime by pylord. They serve as authoritative sources for validating gameplay mechanics, table structures, and formulas during the porting process from the original LORD implementation.

See `/docs/deviations.md` for gameplay deviations from the reference implementation.
