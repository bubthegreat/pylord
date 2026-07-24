# pylord

A Python remake of **Legend of the Red Dragon** (LORD), the classic BBS
door game by Seth Able Robinson — playable over plain telnet, with the
original In-Game Module (IGM) spirit intact as a drop-in plugin system.

Forest fights, the Red Dragon, Turgon's warrior training, Violet and Seth
at the inn, player-vs-player combat, mail, daily news, and a starter set
of six IGMs are all here, ported from the original game logic.

Two things work differently on purpose, for a server people drop into
through the day rather than call once: your forest-fight maximum is
**trainable** (a free point per master beaten, more for sale at Turgon's),
and one fight **comes back every 15 minutes** of real time. Both are
documented in `docs/deviations.md` and configurable below.

## License and provenance

pylord is licensed under the **GPL-3.0-or-later** (see `LICENSE`).

Game formulas, data tables, and screen flows are ported from the GPL
JavaScript implementation of LORD (`lord.js`) distributed with
[Synchronet BBS](https://github.com/SynchronetBBS/sbbs) — a copy lives in
`reference/` with provenance notes. It is reference material only; nothing
in `reference/` is imported at runtime. Intentional differences from the
original are logged in `docs/deviations.md`.

## Quick start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run pylord serve
```

Then, from another terminal:

```sh
telnet localhost 2323
```

Enter a name that doesn't exist yet and you'll be walked through
character creation.

## Sysop configuration

Everything is configured in `config.toml`:

```toml
[server]
host = "0.0.0.0"
port = 2323
# db = "lord.db"   # optional; defaults to lord.db next to config.toml

[game]
forest_fights_per_day = 15
player_fights_per_day = 3
flirts_per_day = 1        # reserved; the romantic-mail flow it gates isn't ported
clean_mode = false        # hides the Inn's adult options
win_deeds = 3             # dragon kills that end the realm (0 = never)
shop_limit = true         # require the strength/defense to carry what you buy
fight_regen_minutes = 15  # real minutes per recovered forest fight (0 = off)
endurance_cost = 1000     # gold for the first bought forest fight at Turgon's

[igms]
# true = enabled; omitted IGMs fall back to their own default
baraks_house = true
sandtigers_bar = true
violets_cottage = true
turgons_house = true
warriors_graveyard = true
lord_casino = true
```

The sysop CLI works against the same database (`--config` points at your
`config.toml`, default `./config.toml`):

```sh
uv run pylord players                          # list everyone
uv run pylord edit Zaphod --gold 5000          # also: --gems, --level,
                                               # --alive 0|1, --reset-password
```

Daily maintenance (fight resets, bank interest, IGM daily hooks) runs
automatically on the first connection of each UTC day.

## Writing your own IGM

IGMs are drop-in plugins discovered from the `igms/` directory next to
your database. Each one is a folder containing an `igm.py` that defines
exactly one subclass of `pylord.hooks.IGM`:

```
igms/
  crystal_cave/
    igm.py
```

```python
# igms/crystal_cave/igm.py
from pylord.hooks import IGM, IgmContext


class CrystalCave(IGM):
    key = "crystal_cave"          # unique id; also the config.toml toggle name
    name = "The Crystal Cave"     # shown in the Other Places menu
    author = "You"
    default_enabled = True

    async def enter(self, ctx: IgmContext) -> None:
        await ctx.term.write("\n  `5You step into a shimmering cave...\n")
        if not ctx.store.get(f"visited:{ctx.player.id}", False):
            ctx.store.set(f"visited:{ctx.player.id}", True)
            ctx.player.gold += 100
            ctx.news(f"`0{ctx.player.name} `2discovered the Crystal Cave!")
            await ctx.term.write("  `2A first-visit gift: `0100 `2gold!\n")
        await ctx.term.pause()
```

Enable it with `crystal_cave = true` under `[igms]` in `config.toml` and
it appears under **(O)ther places** on the Town Square.

The `ctx` façade gives you:

- `ctx.player` — the visiting player; writes are validated (gold/hp/stat
  caps enforced, level and identity immutable), so a bug can't corrupt a
  character.
- `ctx.term` — terminal I/O: `write()` (with LORD `` `color `` codes),
  `menu()`, `readline()`, `pause()`.
- `ctx.store` — persistent per-IGM key/value storage.
- `ctx.news(text)` — add a line to today's news.
- `ctx.mail(to_name, text=..., effect=...)` — send in-game mail, including
  async stat effects applied at the recipient's next login.
- `ctx.other_players()` / `ctx.rng` — everyone else, and the session RNG.

Optional overrides: `daily_maint()` (once per game day), `forest_event()`
(contribute a random forest encounter) and `inn_event()` (add a key to the
Inn's menu). A crashing IGM is contained — its visit rolls back and the
player returns to where they were.

The six bundled IGMs in `igms/` are working examples, from small
(`baraks_house`) to a full mini-game (`lord_casino`).

## Running it for real

`deploy/` holds a Helm chart, per-environment values and an ArgoCD
Application; `deploy/README.md` covers the homelab setup end to end. In
short:

```sh
tilt up                                   # local cluster, port 2323
helm template pylord deploy/helm/pylord \
  -f deploy/values/prod.yaml              # what the homelab runs
```

Characters live on a retained volume at `/data`, config comes from a
ConfigMap, and CI builds `bubthegreat/pylord` and points production at the
new tag — ArgoCD does the rest.

The pod also runs a `ttyd` sidecar so the realm is playable in a browser
over HTTPS (an HTTP Ingress can't carry telnet); telnet clients connect
straight to the service's own address on 2323.

## Development

```sh
uv run pytest        # full suite, including the telnet end-to-end harness
uv run ruff check .
```

### End-to-end harness

`uv run pylord smoke` starts a throwaway server on an ephemeral port,
connects over real telnet, and plays through every base feature —
character creation, both shops, bank, healer, Turgon's, the inn, the
listings, mail, a forest fight, and an IGM visit — checking what each
screen says:

```sh
uv run pylord smoke              # one pass/fail line per feature
uv run pylord smoke --verbose    # also print every screen it saw
uv run pylord smoke --dir /tmp/x # keep the throwaway db/igms around
```

The same walkthrough runs in CI as `tests/test_e2e_features.py`. The thin
client behind it (`pylord/e2e.py`) is reusable for one-off scripted
sessions:

```python
from pylord.e2e import LordClient

client = await LordClient.connect("127.0.0.1", 2323)
await client.login("Zaphod", "hunter2")
client.key("F")
print(await client.expect("ook for something to kill"))
```
