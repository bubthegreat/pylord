# IGMs -- In-Game Modules (pylord plugins)

An **IGM** is a mini-game or feature that a player reaches from the Town
Square's **(O)ther places** menu. This is pylord's replacement for the
original LORD's `3RDPARTY.DAT` / `INFO.<node>` handshake: instead of shelling
out to a separate `.EXE` and swapping stats through a flat file, a pylord IGM
is just a Python class the engine runs in-process behind a safety fence.

Sixteen bundled IGMs ship here, all **enabled by default** -- `baraks_house`,
`sandtigers_bar`, `violets_cottage`, `turgons_house`, `warriors_graveyard`,
`lord_casino`, `apothecary`, `gem_trader`, `old_skull_inn`, `abandoned_mines`,
`arena_of_lords`, `the_latrine`, `werewolf`, `outlands_tavern`,
`sunshines_fairy_land`, and `kaldors_court` -- from a few screens each to a
full mini-game. A
sysop who doesn't want one turns it off in `config.toml` under `[igms]`.
Add your own alongside them -- IGMs ship with the build, so a new one
arrives with the next release rather than being copied onto a server.

Most of the classic third-party IGMs have no surviving source -- they were
separate DOS executables, and `reference/lord.js` models only the base
game -- so most of these are a recreation from the historical premise with
its invented parts flagged in its module docstring. `outlands_tavern` is a
partial exception: its archive ships two real `.RHP` "Random Happening"
scripts in readable source, one of which is ported verbatim -- see its
module docstring for the direct-port/recreation split.

## Writing an IGM

Create `igms/<your_igm>/igm.py` containing exactly **one** subclass of
`pylord.hooks.IGM`:

```python
from pylord.hooks import IGM


class DragonLottery(IGM):
    key = "dragon_lottery"          # unique lowercase slug (a-z 0-9 _ -)
    name = "The Dragon's Lottery"   # shown in the Other Places menu
    author = "you@example.com"      # optional
    default_enabled = False         # loaded but off unless config enables it

    async def enter(self, ctx):
        # ctx is an IgmContext -- a guardrailed view of the session.
        await ctx.term.write("\n  `%Welcome to the lottery!`0\n")

        ticket = await ctx.term.menu(
            {"Y": "buy", "N": "no"}, "  Buy a ticket for 100 gold? [`0Y`2] "
        )
        if ticket == "Y" and ctx.player.gold >= 100:
            ctx.player.gold -= 100
            if ctx.rng.randrange(10) == 0:
                ctx.player.gold += 1000
                await ctx.term.write("\n  `%You WON 1000 gold!`0\n")
                ctx.news(f"`0{ctx.player.name} won the Dragon's Lottery!")
            else:
                await ctx.term.write("\n  `2No luck this time.`0\n")
        await ctx.term.pause()
```

> **Use absolute imports.** Each `igm.py` is loaded as a standalone module
> (`igms.<dir>`) without a parent package, so package-relative imports
> (`from . import helpers`) will fail. Import from installed/absolute paths
> instead (`from pylord.hooks import IGM`). If you need helper modules, keep
> your logic inside `igm.py` or import them by absolute name.

Then enable it in `config.toml`:

```toml
[igms]
dragon_lottery = true
```

## The `IgmContext` your `enter()` receives

You never touch the raw game context. `ctx` gives you a safe subset:

| Member | What it is |
| --- | --- |
| `ctx.player` | A **validated** view of the visiting player. Reads pass through; writes are clamped (see below). |
| `ctx.term` | The terminal (`write`, `readkey`, `readline`, `menu`, `pause`). |
| `ctx.store` | Per-IGM persistent storage: `get(k, default)`, `set(k, v)`, `delete(k)`. JSON values, scoped to your `key`. |
| `ctx.rng` | The session's random generator. |
| `ctx.mail(to_name, text=None, effect=None)` | Send in-game mail (from your IGM's name). |
| `ctx.news(text)` | Add a line to today's news (flushed only if your visit finishes cleanly). |
| `ctx.other_players()` | Read-only summaries of other warriors (`name, level, alive, class_type`). |

### Player-write guardrails

Writes through `ctx.player` are validated so a bug can't corrupt a character:

- `gold`, `bank` -> floored at `0`, capped at `2,000,000,000`
- `exp` -> floored at `0`, capped at `2,000,000,000`
- `hp` -> clamped to `[0, hp_max]` (raise `hp_max` first if you want a bigger pool)
- `hp_max`, `strength`, `defense`, `charm`, `gems`, `lays`, `kids`,
  `forest_fights`, `player_fights` -> floored at `0`, capped at `32,000`
- `level` -> **forbidden** (raises `IgmViolation`; grant `exp` instead)
- `id`, `name`, `password_hash` -> **forbidden** (identity is immutable)

These are lord.js's own bounds, ported from its `check_fields()`
normaliser (`reference/lord.js:16603-16679`).

Any other field passes through unvalidated -- IGMs are semi-trusted.

### The visit is transactional

The whole visit runs inside one database transaction. If your `enter()`
raises **any** exception, the engine rolls everything back -- player stats,
store writes, mail, and news are all undone -- and bounces the player back to
the forest with a "strange force pushes you back" message. So a crashing IGM
can never leave a character in a broken half-state. A clean return commits
everything at once.

## Optional hooks

```python
    async def daily_maint(self, ctx):
        # Runs once per game-day during global maintenance. ctx here is an
        # IgmMaintContext: ctx.conn, ctx.config, ctx.repo, ctx.store.
        # Do DB-only work -- there is no terminal and no awaiting here.
        ...

    def forest_event(self, rng):
        # Return a pylord.hooks.ForestEvent(weight, run) to inject a random
        # forest encounter, or None. `run` is an async (IgmContext) -> None.
        # `weight` buys that many slots alongside the base game's own 15
        # forest events.
        return None

    def inn_event(self, rng):
        # Return a pylord.hooks.InnEvent(label, run) to add a numbered key
        # to the Inn's menu, or None.
        return None
```

Both event hooks run behind the same sandbox as `enter()`: one transaction,
and the player restored in place if your code raises.

## Testing your IGM

Call the shared contract check so your plugin is held to the framework's
invariants:

```python
from tests.igm_contract import contract_check
from igms.dragon_lottery.igm import DragonLottery

async def test_contract():
    await contract_check(DragonLottery)
```

Broken plugins (import errors, no/multiple `IGM` subclass, bad `key`) are
logged and skipped at startup -- one bad plugin never takes the game down.
