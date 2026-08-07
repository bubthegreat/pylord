# Armor Rebalance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rescale armor defense powers (~×2.5, top tiers compressed) and reprice tiers 12–15 so armor always beats fairyland's 35k gold/defense-point, level-appropriate armor makes same-level monsters survivable without nullifying them, and existing characters are migrated by delta.

**Architecture:** Data-table change in `pylord/engine/data/armor.py` plus a one-time versioned data migration in `pylord/data.py` (`CURRENT_VERSION` 5 → 6 in `pylord/schema.py`). Combat, shops, monsters, dragon, weapons, and fairyland are untouched — shops and combat read powers from the table at runtime.

**Tech Stack:** Python 3.12, SQLAlchemy async core, pytest (async tests run under the repo's existing pytest config). Everything runs via `uv run`.

**Spec:** `docs/superpowers/specs/2026-08-07-armor-rebalance-design.md`

## Global Constraints

- New powers by tier 1–15: `3, 8, 25, 38, 63, 88, 125, 188, 250, 375, 560, 750, 950, 1150, 1350`.
- New prices: tiers 1–11 unchanged; tier 12 `7_000_000`, tier 13 `10_000_000`, tier 14 `11_000_000`, tier 15 `12_000_000`.
- Value invariant for every tier n ≥ 2: `(price[n] - price[n-1] // 2) / (power[n] - power[n-1]) < 35_000`.
- Migration is a **delta** (`defense += new_power - old_power`), clamped to `[0, 32000]` (`STAT_CAP` in `pylord/engine/limits.py`), never a recompute — fairyland-bought defense must survive.
- Old powers frozen in the migration: `1, 3, 10, 15, 25, 35, 50, 75, 100, 150, 225, 300, 400, 600, 1000` (tiers 1–15).
- Commit messages: Conventional Commits, end with the Claude co-author trailer.

---

### Task 1: Rescale the armor table

**Files:**
- Modify: `pylord/engine/data/armor.py`
- Test: `tests/test_data.py`

**Interfaces:**
- Consumes: `Item = namedtuple("Item", "num name price power")` from `pylord/engine/data/weapons.py` (unchanged).
- Produces: `ARMOR: list[Item]` with the new powers/prices; `armor(num)` 1-based lookup (signature unchanged). Task 2's `_ARMOR_POWERS_V6` and Task 3's simulation both depend on these exact values.

- [ ] **Step 1: Update/extend tests (they must fail against the old table)**

In `tests/test_data.py`, replace `test_armor_table_shape_and_endpoints` and add two tests:

```python
def test_armor_table_shape_and_endpoints():
    assert len(data.ARMOR) == 15
    first = data.ARMOR[0]
    assert first.num == 1
    assert first.name == "Coat"
    assert first.price == 200
    assert first.power == 3

    last = data.ARMOR[14]
    assert last.num == 15
    assert last.name == "Armour Of Lore"
    assert last.price == 12_000_000
    assert last.power == 1350


def test_armor_powers_and_prices_strictly_increase():
    for prev, cur in zip(data.ARMOR, data.ARMOR[1:]):
        assert cur.power > prev.power, (prev, cur)
        assert cur.price > prev.price, (prev, cur)


def test_armor_upgrades_beat_fairyland_defense_price():
    """Net upgrade cost per defense point stays under SunShines' Fairy
    Land's flat 35,000 gold/point (igms/sunshines_fairy_land/igm.py,
    PRICE_DEFENSE). Trade-in floor: half the old armor's price."""
    for prev, cur in zip(data.ARMOR, data.ARMOR[1:]):
        net_cost = cur.price - prev.price // 2
        per_point = net_cost / (cur.power - prev.power)
        assert per_point < 35_000, (cur.name, per_point)
```

- [ ] **Step 2: Run tests to verify the right ones fail**

Run: `uv run pytest tests/test_data.py -v`
Expected: `test_armor_table_shape_and_endpoints` FAILS (power 1 ≠ 3), `test_armor_upgrades_beat_fairyland_defense_price` FAILS (tier 12+ over 35k). Monotonicity may pass — fine.

- [ ] **Step 3: Rewrite `pylord/engine/data/armor.py`**

Replace the whole file with:

```python
"""Armor shop table.

Transcribed from reference/lord.js:1397-1414 (`armour_stats`), then
**deliberately rebalanced** -- the powers and the tier 12-15 prices below
diverge from lord.js on purpose (DIFF), per
docs/superpowers/specs/2026-08-07-armor-rebalance-design.md:

* The original powers (1, 3, 10, 15, 25, 35, 50, 75, 100, 150, 225, 300,
  400, 600, 1000) left a player in level-appropriate armor near-certain to
  die to same-level forest monsters (a level-10 player in Full Body Armour
  faced ~26% death odds per fight), and made armor a worse deal per
  defense point than SunShines' Fairy Land's flat 35,000-gold price from
  tier 11 up. Powers are rescaled ~x2.5, with tiers 13-15 compressed so
  endgame armor blocks the Red Dragon's claws but never blunts its
  Flaming Breath.
* The original tier 12-15 prices (10M, 40M, 100M, 400M) are cut so every
  upgrade's net cost (price minus a half-price trade-in) stays under
  35,000 gold per defense point; tests/test_data.py locks that invariant.

`armour_stats[0]` ("Nothing!", price 0) is the unarmored placeholder
returned by `get_armour()` (lord.js:1837-1840) when `player.arm_num === 0`;
excluded from `ARMOR` for the same reason `weapon_stats[0]` is excluded
from `WEAPONS` (see weapons.py).

Semantics of the `num` field mirror weapons but apply to defense instead of
strength -- lord.js adds it directly onto `player.def`:

    player.def += newa.num;   // buy armor, lord.js:10424
    player.def -= olda.num;   // sell armor, lord.js:10499

We name that field `power` on `Item`, consistent with weapons.py.

The pre-rebalance powers also live, frozen, in pylord/data.py's
`_ARMOR_POWERS_V5`, which migrates old realms onto this curve. Rescaling
this table again means adding a new migration constant + version bump
there -- never editing the frozen one.
"""

from pylord.engine.data.weapons import Item

ARMOR: list[Item] = [
    Item(1, "Coat", 200, 3),
    Item(2, "Heavy Coat", 1000, 8),
    Item(3, "Leather Vest", 3000, 25),
    Item(4, "Bronze Armour", 10000, 38),
    Item(5, "Iron Armour", 30000, 63),
    Item(6, "Graphite Armour", 100000, 88),
    Item(7, "Erdricks Armour", 150000, 125),
    Item(8, "Armour Of Death", 200000, 188),
    Item(9, "Able's Armour", 400000, 250),
    Item(10, "Full Body Armour", 1000000, 375),
    Item(11, "Blood Armour", 4000000, 560),
    Item(12, "Magic Protection", 7000000, 750),
    Item(13, "Belars's Mail", 10000000, 950),
    Item(14, "Golden Armour", 11000000, 1150),
    Item(15, "Armour Of Lore", 12000000, 1350),
]


def armor(num: int) -> Item:
    """1-based lookup into ARMOR (num 1..15)."""
    if not 1 <= num <= len(ARMOR):
        raise ValueError(f"armor num out of range 1..{len(ARMOR)}: {num}")
    return ARMOR[num - 1]
```

- [ ] **Step 4: Run the data tests, then the full suite**

Run: `uv run pytest tests/test_data.py -v` — expected: all PASS.
Run: `uv run pytest` — expected: PASS. If a shop/e2e test asserts an old armor price/power, update that assertion to the new table value (that is the only acceptable kind of failure; anything else is a regression — stop and investigate).

- [ ] **Step 5: Commit**

```bash
git add pylord/engine/data/armor.py tests/test_data.py
git commit -m "feat(balance): rescale armor powers and late-tier prices

Powers ~x2.5 (top tiers compressed to keep the Red Dragon dangerous);
tier 12-15 prices cut so every upgrade beats SunShines' Fairy Land's
35k gold per defense point. Spec:
docs/superpowers/specs/2026-08-07-armor-rebalance-design.md

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Version-6 delta migration for existing characters

**Files:**
- Modify: `pylord/schema.py` (line ~161, `CURRENT_VERSION`)
- Modify: `pylord/data.py` (module constants near `logger`; `create_schema`, lines ~387–404; new method on `Database`)
- Test: `tests/test_datalayer.py`

**Interfaces:**
- Consumes: `Database.players` (`PlayersRepo.all_players() -> list[Player]`, `save(player)`, `get(id)`, `create(name, password)`), `schema.schema_version.c.applied_count`, `STAT_CAP` from `pylord/engine/limits.py`, `Player.armor_num` / `Player.defense` (defaults 0 / 1).
- Produces: `Database._rebalance_armor_defense()` (private, called only from `create_schema`), module constants `_ARMOR_POWERS_V5` / `_ARMOR_POWERS_V6`, `schema.CURRENT_VERSION == 6`.

- [ ] **Step 1: Write failing migration tests**

Append to `tests/test_datalayer.py` (it already defines `_db()` returning `await data.connect(":memory:")`; extend the imports at the top with `from sqlalchemy import update` and `from pylord import schema`):

```python
async def _set_version(db: Database, version: int) -> None:
    await db.execute(
        update(schema.schema_version).values(applied_count=version)
    )


async def test_v6_migration_rebases_armored_defense_by_delta():
    db = await _db()
    p = await db.players.create("Armored", "pw")
    p.armor_num = 11  # Blood Armour: old power 225, new power 560
    p.defense = 233 + 225 + 50  # base + old armor + 50 fairyland points
    await db.players.save(p)

    await _set_version(db, 5)
    await db.create_schema()

    migrated = await db.players.get(p.id)
    # Delta (+335) applied; the 50 bought points survive.
    assert migrated.defense == 233 + 560 + 50
    row = await db.fetch_one(
        schema.schema_version.select()
    )
    assert row.applied_count == schema.CURRENT_VERSION


async def test_v6_migration_skips_unarmored_and_corrupt_rows():
    db = await _db()
    bare = await db.players.create("Bare", "pw")  # armor_num 0
    corrupt = await db.players.create("Corrupt", "pw")
    corrupt.armor_num = 99
    corrupt.defense = 123
    await db.players.save(corrupt)

    await _set_version(db, 5)
    await db.create_schema()

    assert (await db.players.get(bare.id)).defense == 1  # model default
    assert (await db.players.get(corrupt.id)).defense == 123


async def test_v6_migration_is_idempotent_and_clamps():
    db = await _db()
    p = await db.players.create("Capped", "pw")
    p.armor_num = 15  # delta +350
    p.defense = 31_900
    await db.players.save(p)

    await _set_version(db, 5)
    await db.create_schema()
    assert (await db.players.get(p.id)).defense == 32_000  # clamped

    # Second startup: version is already current, no second delta.
    await db.create_schema()
    assert (await db.players.get(p.id)).defense == 32_000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_datalayer.py -k v6 -v`
Expected: FAIL — defense unchanged (no migration exists yet).

- [ ] **Step 3: Implement the migration**

In `pylord/schema.py`, change:

```python
CURRENT_VERSION = 6
```

In `pylord/data.py`, add below the `logger = ...` line:

```python
#: Armor defense powers by armor_num (index 0 = unarmored) before and
#: after the schema-version-6 rebalance
#: (docs/superpowers/specs/2026-08-07-armor-rebalance-design.md). V5 is
#: frozen history -- it must match what players actually bought under
#: version 5, not the live table in pylord/engine/data/armor.py, which
#: may drift again behind a future migration.
_ARMOR_POWERS_V5 = (0, 1, 3, 10, 15, 25, 35, 50, 75, 100, 150, 225, 300, 400, 600, 1000)
_ARMOR_POWERS_V6 = (0, 3, 8, 25, 38, 63, 88, 125, 188, 250, 375, 560, 750, 950, 1150, 1350)
```

In `create_schema`, insert the migration between reading the stored version and writing the current one:

```python
        existing = await self.fetch_one(select(schema.schema_version.c.applied_count))
        if existing is not None and existing.applied_count < 6:
            await self._rebalance_armor_defense()
        if existing is None:
```

(the `if existing is None: insert ... else: update ...` tail stays as is).

Add the method to `Database` (next to `_add_missing_columns`):

```python
    async def _rebalance_armor_defense(self) -> None:
        """Schema-version-6 data migration: armor powers were rescaled
        (see _ARMOR_POWERS_V5/_V6), so re-base every armored player's
        defense by the delta for their equipped armor. A delta rather
        than a recompute, so defense bought at SunShines' Fairy Land or
        granted by IGMs survives."""
        from pylord.engine.limits import STAT_CAP

        for player in await self.players.all_players():
            if player.armor_num == 0:
                continue
            if not 1 <= player.armor_num < len(_ARMOR_POWERS_V5):
                logger.warning(
                    "player %s has armor_num %s outside 1..15; "
                    "skipping armor rebalance for them",
                    player.id,
                    player.armor_num,
                )
                continue
            delta = (
                _ARMOR_POWERS_V6[player.armor_num]
                - _ARMOR_POWERS_V5[player.armor_num]
            )
            player.defense = max(0, min(player.defense + delta, STAT_CAP))
            await self.players.save(player)
```

(Function-local import: `pylord/data.py` is the layer under the engine; keeping the engine import out of module scope avoids any future import-cycle surprise.)

- [ ] **Step 4: Run the migration tests, then the full suite**

Run: `uv run pytest tests/test_datalayer.py -k v6 -v` — expected: PASS.
Run: `uv run pytest` — expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pylord/schema.py pylord/data.py tests/test_datalayer.py
git commit -m "feat(balance): migrate existing realms onto the new armor curve

Schema version 5 -> 6: re-base each armored player's defense by the
per-tier power delta (clamped to the 32k stat cap), preserving defense
bought at the fairyland store. Unarmored and corrupt rows are skipped.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Survivability guard test

**Files:**
- Create: `tests/test_balance.py`

**Interfaces:**
- Consumes: `Combatant` (constructor fields `name, hp, hp_max, strength, defense, weapon_name`) and `Fight(player_side, enemy, rng)` with `player_attack() -> Round`, `enemy_attack() -> Round`, `over`, `winner` from `pylord/engine/combat.py`; `MONSTERS[10]` (list of 10 level-10 monsters) from `pylord/engine/data/monsters.py`; `WEAPONS` from `pylord/engine/data/weapons.py`; `armor(10)` from Task 1; `LEVEL_STATS` from `pylord/engine/data/levels.py`.
- Produces: nothing downstream — a regression guard locking in the spec's survivability window.

- [ ] **Step 1: Write the test**

Create `tests/test_balance.py`:

```python
"""Balance regression guards for the armor rebalance.

Locks in the spec's survivability window
(docs/superpowers/specs/2026-08-07-armor-rebalance-design.md): a level-10
player in tier-10 gear survives level-10 forest monsters except on
genuinely unlucky rolls, while monsters still land a meaningful share of
their swings. Seeded rng -- deterministic. If a future data edit (armor,
monsters, level grants) breaks either bound, this test is the tripwire.
"""

import random

from pylord.engine.combat import Combatant, Fight
from pylord.engine.data.armor import armor
from pylord.engine.data.levels import LEVEL_STATS
from pylord.engine.data.monsters import MONSTERS
from pylord.engine.data.weapons import WEAPONS


def _level10_player() -> Combatant:
    """Fresh level-10 build: starting stats (20 hp / 10 str / 1 def) plus
    every level-up grant through level 9, tier-10 weapon and armor."""
    hp = 20 + sum(LEVEL_STATS[i].hp for i in range(1, 10))
    strength = (
        10
        + sum(LEVEL_STATS[i].strength for i in range(1, 10))
        + WEAPONS[9].power
    )
    defense = (
        1
        + sum(LEVEL_STATS[i].defense for i in range(1, 10))
        + armor(10).power
    )
    return Combatant(
        name="Hero",
        hp=hp,
        hp_max=hp,
        strength=strength,
        defense=defense,
        weapon_name="Wans' Weapon",
    )


def test_level10_in_full_body_survives_level10_forest():
    rng = random.Random(1234)
    trials = 2000
    deaths = 0
    blocked = 0
    swings = 0

    for _ in range(trials):
        monster = MONSTERS[10][rng.randrange(10)]
        fight = Fight(_level10_player(), Combatant.from_monster(monster), rng)
        while not fight.over:
            fight.player_attack()
            if fight.over:
                break
            round_ = fight.enemy_attack()
            swings += 1
            if round_.damage == 0:
                blocked += 1
        if fight.winner == "enemy":
            deaths += 1

    death_rate = deaths / trials
    blocked_rate = blocked / swings
    # Survivable: dying to a same-level monster takes real bad luck.
    assert death_rate < 0.05, f"death rate {death_rate:.1%}"
    # ... but not nullified: monsters still land a meaningful share.
    assert 0.50 < blocked_rate < 0.90, f"blocked rate {blocked_rate:.1%}"
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/test_balance.py -v`
Expected: PASS (design-sim values with these stats: death ≈ 1%, blocked ≈ 70%). If it fails, the armor table from Task 1 doesn't match the spec — fix the table, not the bounds.

- [ ] **Step 3: Sanity-check the guard actually guards**

Temporarily change `armor(10).power`'s use to `150` in the test's defense sum (i.e. replace `+ armor(10).power` with `+ 150`), rerun, and confirm the death-rate assertion FAILS. Revert the edit. Do not commit the temporary change.

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_balance.py
git commit -m "test(balance): guard level-10 armor survivability window

Seeded simulation: death rate < 5% and 50-90% of enemy swings blocked
for a level-10 build in tier-10 gear vs level-10 monsters.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
