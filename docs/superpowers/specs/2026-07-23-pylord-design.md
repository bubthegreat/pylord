# pylord — Legend of the Red Dragon in Python — Design Spec

Date: 2026-07-23
Status: Approved (sections A/B approved interactively; C fast-tracked by owner)

## Context

Rebuild the classic BBS door game *Legend of the Red Dragon* (Seth Able Robinson, 1989)
in Python as a multiplayer telnet server, consolidating the base game and the classic
IGM (In-Game Module) expansion ecosystem into one project with a modern, modular
plugin system. The original Turbo Pascal source was never released (rights sold to
Metropolis in 1998). The canonical open-source reference is Synchronet's GPL
`xtrn/lord/lord.js` — a behavior-faithful port with exact tables and formulas.

## Decisions (owner-approved)

| Decision | Choice |
|---|---|
| Game model | Faithful door game: daily limits, async PvP, shared persistent world |
| Interface | Telnet server (asyncio), ANSI color; players connect with any telnet/BBS client |
| Fidelity | Exact clone — tables/formulas ported from GPL `lord.js`; project licensed GPL-3.0 |
| Storage | SQLite (WAL), single server process |
| Auth | Character name + password, classic BBS style |
| Plugins | Drop-in `igms/` directory, auto-discovered; per-IGM enable/disable in config |
| Architecture | Hooked core: faithful hardcoded engine + defined hook points for IGMs |
| IGM bundle | Starter six enabled at v1; remaining catalog recreated in later waves, disabled by default |
| Packaging | uv-managed, Python 3.12+ |

## Section A — Architecture & Tech Stack

- **Runtime deps**: `telnetlib3` only. Stdlib `sqlite3`. Dev deps: `pytest`, `ruff`.
- **Process model**: one asyncio process; each telnet connection is a session
  coroutine. All DB writes serialize through the process (SQLite WAL). No node
  numbers, no drop files — the original's `INFO.<node>` / `3RDPARTY.DAT` /
  subprocess mechanism is replaced by in-process Python plugin classes. Fidelity
  target is player-visible behavior, not file formats.
- **Daily reset**: lazy — first activity after local midnight triggers maintenance
  (reset daily counters, bank interest, news rollover), like original LORDBOOT maint.

### Layout

```
pylord/
  server.py        # telnetlib3 entry, session lifecycle, auth
  terminal.py      # ANSI writer, LORD backtick color codes (`1..`0, `%, `\ etc.), input helpers
  engine/
    game.py        # session game loop: town square dispatch
    daily.py       # daily reset / maintenance
    combat.py      # fight engine: forest, master, PvP, dragon (formulas from lord.js)
    data/          # weapons.py, armor.py, masters.py, monsters.py, events.py — ported tables
    scenes/        # town, forest, inn, healer, bank, weapons, armor, training, hall,
                   # mail, flirt, marriage, dark_cloak, other_places ...
  hooks.py         # hook registry + IGM base class + IGM-facing API
  igm_loader.py    # scans igms/, validates, registers enabled IGMs
  models.py        # Player dataclass mirroring player_info record
  db.py            # SQLite repository + numbered migrations
igms/
  baraks_house/    # each IGM: package dir with igm.py exposing one IGM subclass
  ...
config.toml        # sysop settings incl. [igms] enable flags
```

## Section B — Core Game Scope & Data Model

### Core game (v1, exact-clone targets)

- **Character**: 3 skill classes (Death Knight / Mystical / Thieving), 12 levels,
  masters Halder→Turgon (exact stats/quotes), gender, exp thresholds from lord.js.
- **Town Square**: Forest, Inn, Turgon's training, King Arthur's weapons, Abdul's
  armor, healer, bank (interest + robbery), Ye Old Mail, Hall of Honors, warrior
  list, daily news, view stats, Conjugality List (marriage), Dark Cloak Tavern.
- **Forest**: per-level monster tables, exact combat math (attack/skill/run),
  gold/exp drops, base-game forest events (fairy, old man, gems, etc.),
  **Other Places** menu → IGM hook.
- **Inn**: Violet / Seth Able the bard (charm-gated flirt chain through marriage),
  bard songs, room rental, attack players sleeping at the inn.
- **PvP**: attack offline or inn-sleeping players; kills yield gold/exp/news.
- **Dragon**: level-12 + gear gates, dragon fight, victory → game reset cycle,
  king count, children mechanic.
- **Dailies**: forest fights/day, PvP fights/day, flirts, skill uses, bank
  interest, daily news, JENNIE codes.
- **Sysop**: config.toml knobs (fights/day, clean mode, IGM toggles), player
  editor CLI (`pylord edit`).

**Out of scope v1**: RIP graphics, inter-BBS play, LADY script interpreter,
original .DAT import/export.

### Data model (SQLite)

- `players` — mirrors `player_info`: stats, gear ids, gold/bank, flags
  (seen_dragon, married_to, king count…), skill points/uses, daily counters,
  password hash (scrypt via stdlib `hashlib`).
- `game_state` — current game day, dragon status, current king.
- `daily_news` — append-only rows rendered as the news screen.
- `mail` — player mail plus **async effect events**: typed records
  (`{"type": "gold", "amount": n}`) applied at login — the modern equivalent of
  the original backtick mail-codes (`` `b `` gold, `` `E `` exp, …).
- `igm_data` — namespaced per-IGM key/value JSON store; IGMs never touch core
  tables directly except through the API.

Migrations: numbered SQL files applied at boot.

## Section C — IGM Plugin API

Original interface (from Seth Able's spec in LORDSTRC.PAS): 2-line
`3RDPARTY.DAT` registration, `INFO.<node>` drop file, direct PLAYER.DAT record
writes, mail backtick-codes. Modern equivalent, strictly broader:

```python
class IGM:                      # subclass in igms/<name>/igm.py
    key: str                    # unique slug, storage namespace
    name: str                   # shown in Other Places menu
    author: str
    # hook methods (all optional except enter):
    async def enter(self, ctx): ...          # player enters from Other Places
    async def daily_maint(self, ctx): ...    # once per game day
    def forest_event(self) -> Event | None   # weighted random forest event
    def inn_event(self) -> Event | None      # weighted random inn event
```

`ctx` (IgmContext) exposes:
- `ctx.player` — live Player record; mutations validated (floors/caps enforced,
  e.g. gold ≥ 0, no level > 12) and saved on exit — the PLAYER.DAT contract.
- `ctx.term` — screen I/O: write with LORD color codes, menus, prompts, pauses.
- `ctx.store` — per-IGM KV storage (igm_data).
- `ctx.mail(player_name_or_id, text=None, effect=None)` — mail + async effects
  on other players (the backtick-code replacement).
- `ctx.news(text)` — append to daily news.
- `ctx.players` — read-only roster queries (for casinos/graveyards that
  reference other warriors).

Discovery: `igm_loader` scans `igms/*/igm.py`, imports, validates class,
registers if enabled in `config.toml` `[igms]` (unknown IGMs default disabled;
starter six default enabled). A broken IGM logs and is skipped — never takes
the server down.

### Bundled IGM waves

- **Wave 1 (v1, enabled)**: Barak's House, Sandtiger's Bar, Violet's Cottage,
  Turgon's House, The Warrior's Graveyard, LORD Gambling Casino.
- **Wave 2+**: recreate remaining documented catalog (~40: Apothecary, Gem
  Trader, Old Skull Inn, Abandoned Mines, Arena of Lords, The Latrine, Love
  Shack, Anastasia's, LORDopoly, Caves of Despair, Purple Haze, WereWolf II,
  Fairy IGMs, Vanadia series, …) roughly six per wave, shipped disabled by
  default. Full catalog + sources documented in research notes.

## Error Handling

- Session coroutine wrapped: disconnect mid-anything → player state saved at
  last transaction boundary; combat in progress resolves as flee-with-penalty
  (matches original carrier-drop handling).
- IGM exceptions: caught at hook boundary, logged, player returned to Forest
  with a flavor message; IGM data rolled back for that visit.
- DB: every player mutation in a transaction; WAL + busy timeout.
- Input: all prompts through validated helpers (length caps, charset, timeout →
  idle disconnect).

## Testing

- **Unit**: combat math, level/exp tables, charm gates, bank interest — pinned
  against values derived from lord.js (golden tables in test fixtures).
- **Engine**: scripted-session harness — feed keystroke sequences to a fake
  terminal, assert screens/state. Covers every town menu path, forest loop,
  dragon win cycle, daily reset.
- **IGM API**: contract tests any bundled IGM must pass (enter/exit safety,
  storage isolation, validation of stat mutations).
- **Integration**: spin real server on ephemeral port, drive with telnetlib3
  client, full login→forest→logoff smoke.

## Verification (end-to-end)

`uv run pylord serve` → telnet localhost 2323 → create character, fight in
forest, visit Other Places → Barak's House, check news next day. `uv run pytest`
green.
