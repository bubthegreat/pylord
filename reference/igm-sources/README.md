# IGM source, for porting

Until now every IGM in `igms/` was a **recreation from the historical
premise** — nobody had the code, so the behaviour was rebuilt from
descriptions. These are the real sources, so those can become actual ports
and the recreations can be deleted.

## Where this came from, and under what licence

| Directory | Upstream | Licence |
|---|---|---|
| `synchronet/` | [SynchronetBBS/sbbs](https://github.com/SynchronetBBS/sbbs) `xtrn/lord` | GPL ([synchro.net/copyright.html](http://synchro.net/copyright.html)) |
| `lordts/` | [talisto/LORD.ts](https://github.com/talisto/LORD.ts) `igm/` | GPL-3.0 |
| `../assets/` | SynchronetBBS/sbbs `xtrn/lord/*.lrd` | GPL |

Both are GPL, so both are compatible with this project's GPL-3.0. That is
the reason only these two are vendored.

**Two other sources were looked at and deliberately not vendored:**

* [castlecamelot.sourceforge.net](https://castlecamelot.sourceforge.net/camelot6.htm)
  catalogues ~241 IGMs but hosts **compiled binaries only** — several
  entries say outright that the source is lost. Useful as a catalogue of
  what existed and how it behaved; nothing to port.
* [archives.thebbs.org](https://mirrors.archeobits.com/bbs/archives.thebbs.org/ra98c.htm)
  has a handful of Pascal source archives (`ARTIME11.ZIP`, `BARSRC.ZIP`,
  `SANDSRC.ZIP`, `SLOTTO10.ZIP`, `RTSGEM11.ZIP`). These are 1990s shareware
  with **no stated licence** — abandonware whose authors are largely
  uncontactable. Vendoring unlicensed code into a GPL-3.0 repository is a
  licensing problem, not a formality, and the two GPL sources above already
  cover most of the same IGMs (SandBar and Seth's Lotto among them). Left
  out pending a decision.

`../assets/lordtxt.lrd` is a separate win: it is the `lrdfile()` asset the
base game draws its screens from, which this repo never had. Every menu in
`pylord/` currently carries a comment saying its body is *reconstructed*
because that file was missing — MAIN, HEAL, ARTHUR, BT, CLOAK, OLDMAN,
CHANCE, TURGON, BANK, BUYWEP, BUYARM and about 50 more are all in there,
as `@#NAME` sections.

## What we have source for

**Replaces an existing recreation** — port, then delete `igms/<ours>/`:

| Ours | Real source | Where | Lines |
|---|---|---|---|
| `sandtigers_bar` | Sandtiger's Bar v1.02, Joseph Masters (1995) | `lordts/sandbar` | 2376 |
| `violets_cottage` | Violet's Cottage | `lordts/violet` | 1981 |
| `warriors_graveyard` | The Warrior's Graveyard v1.1, Lloyd Hannesson | `lordts/gravyard`, `synchronet/gravyard` | 1845 |
| `baraks_house` | Barak's House | `lordts/barak`, `synchronet/barak` | 1393 |
| `the_latrine` | The Outhouse v1.0, Lloyd Hannesson | `lordts/outhouse`, `synchronet/outhouse` | 678 |
| `abandoned_mines` | The L.O.R.D. Cavern v1.7, Jason Brown | `lordts/lordcave` | 2275 |

**New — no equivalent in `igms/` yet:**

| IGM | Where | Lines |
|---|---|---|
| The Grab Bag v1.1, Mortifis | `synchronet/grabbag` | 3191 |
| Felicity's Temple, Lloyd Hannesson | `lordts/felicity` | 3236 |
| TeamLord v2.0, Masters / Preslar | `lordts/teamlord` | 3220 |
| The FreeWorld II, Martino / Preslar | `lordts/freeworld2` | 734 |
| Olodrin's Orphanage | `lordts/oorphans`, `synchronet/oorphans` | 528 |
| Seth's Tribute Lotto, Joseph Masters | `lordts/lotto` | 258 |
| Pickle's | `synchronet/pickle` | 152 |

**Not places** — maintenance hooks rather than somewhere to visit:
`lordts/aratime` + `synchronet/aratime` (Aragorn's Timer), `lordts/lrdevent`
(event scheduler), `lordts/npclord` (NPC bots).

**No source found**, so these stay recreations for now: `turgons_house`,
`lord_casino`, `apothecary`, `gem_trader`, `old_skull_inn`,
`arena_of_lords`. (`gem_trader` has a possible match in the unvendored
`RTSGEM11.ZIP`.)

## The clones

`reference/upstream/` holds the sparse clones these were extracted from.
It is gitignored — 25 MB of two repositories, of which the 2 MB here is
everything actually needed. Recreate it with the clone commands in this
file's history if a fresh extract is wanted.
