# Armor Rebalance — Design

**Date:** 2026-08-07
**Status:** Proposed

## Problem

The armor table is a faithful transcription of original LORD
(`pylord/engine/data/armor.py`, from `reference/lord.js:1397-1414`), and the
original curve is broken in two ways that modern play makes obvious:

1. **Survivability.** A level-10 player wearing the level-appropriate armor
   (Full Body, +150 defense) dies to level-10 monsters with near certainty:
   Monte-Carlo simulation (level-10 stats, tier-10 weapon and armor, heal
   between fights) gives a **26% chance of dying in any single forest
   fight** — the armor blocks only ~15% of enemy swings, and a single fight
   averages 527 damage against 780 max hp. Damage per hit swings 0–900+
   because monster rolls (`str/2 .. str-1`, strength 565–989 at level 10)
   dwarf total defense (383).

2. **Value.** Buying defense points outright at SunShines' Fairy Land's
   general store costs a flat 35,000 gold/point
   (`igms/sunshines_fairy_land/igm.py`, `PRICE_DEFENSE`). Armor upgrades are
   *worse* than that from tier 11 up — Blood Armour nets ~47k/point after
   trade-in, and tiers 13–15 run 350k–875k/point — despite requiring a huge
   lump-sum save. Armor should never be a worse deal than buying points.

This is a **deliberate balance deviation** from lord.js, in the same spirit
as the existing `_DEF_CAP` "DIFF:" deviation in
`pylord/engine/scenes/shops.py`.

## Goals

- At level *L* wearing tier-*L* armor, a player survives same-level forest
  monsters except when genuinely unlucky (~1% per-fight death at level 10),
  without **nullifying** monsters (a meaningful share of swings still land).
- Net armor upgrade cost (price − trade-in) stays **under 35k gold per
  defense point** at every tier, so armor always beats buying raw points.
- The Red Dragon (str 2000, Flaming Breath doubles the roll) **stays
  dangerous** for an endgame player in top armor.
- Monsters, masters, the dragon, weapons, combat formulas, and the
  fairyland store are **unchanged**.

## Design

### 1. New armor powers (~×2.5, top tiers compressed)

| # | Armor | Power old → new | Price old → new |
|---|-------|----------------|-----------------|
| 1 | Coat | 1 → 3 | 200 |
| 2 | Heavy Coat | 3 → 8 | 1,000 |
| 3 | Leather Vest | 10 → 25 | 3,000 |
| 4 | Bronze Armour | 15 → 38 | 10,000 |
| 5 | Iron Armour | 25 → 63 | 30,000 |
| 6 | Graphite Armour | 35 → 88 | 100,000 |
| 7 | Erdricks Armour | 50 → 125 | 150,000 |
| 8 | Armour Of Death | 75 → 188 | 200,000 |
| 9 | Able's Armour | 100 → 250 | 400,000 |
| 10 | Full Body Armour | 150 → 375 | 1,000,000 |
| 11 | Blood Armour | 225 → 560 | 4,000,000 |
| 12 | Magic Protection | 300 → 750 | 10,000,000 → **7,000,000** |
| 13 | Belars's Mail | 400 → 950 | 40,000,000 → **10,000,000** |
| 14 | Golden Armour | 600 → 1,150 | 100,000,000 → **11,000,000** |
| 15 | Armour Of Lore | 1000 → 1,350 | 400,000,000 → **12,000,000** |

Rationale:

- ×2.5 puts level-10 per-fight death at **0.9%** (30k-trial sim), average
  damage taken per fight at 128, and typical-monster hits in a 0–86 band
  instead of 0–312 — while ~30% of swings still land, so monsters are not
  nullified. Rare power-move spikes (1-in-30, ×1.5) still hurt.
- Tiers 13–15 are compressed (not a straight ×2.5) so endgame defense
  (level-12 base 503 + Lore 1350 = 1853) blocks the dragon's ordinary claw
  swings but leaves **Flaming Breath** (1-in-4 swings, roll doubled:
  150–2,100 damage vs 1,680 max hp) fully lethal. Dragon stays a fight.
- Tier 12–15 prices drop so the net upgrade cost per point lands at
  ~26k–33k, under the 35k fairyland floor. Tiers ≤ 11 already beat 35k
  with the new powers; their prices are untouched.

### 2. Files changed

- `pylord/engine/data/armor.py` — new `power` values for all 15 rows, new
  `price` for rows 12–15. Rewrite the module docstring: it currently claims
  a faithful lord.js transcription; it must now document the original
  values, the new curve, and why (this section's rationale, briefly), in
  the repo's existing "DIFF:" style.
- `pylord/schema.py` — `CURRENT_VERSION` 5 → 6.
- `pylord/data.py` (`create_schema`) — one-time data migration, see below.
- `tests/test_data.py` — update asserted armor values.
- New tests — see Testing.

Explicitly unchanged: `monsters.py`, `masters.py`, `weapons.py`,
`combat.py`, `levels.py`, dragon stats, fairyland prices, shop buy/sell
logic (`shops.py` reads powers from the table; the defense-prerequisite
`_need_sum` uses `LEVEL_STATS`, not armor powers, so wear requirements are
untouched).

### 3. Migration (existing characters)

`create_schema` already reads `schema_version.applied_count` before
writing `CURRENT_VERSION` back. Add: when the stored version is `< 6`,
apply a **delta** to every player with `armor_num > 0`:

```
defense = clamp(defense - OLD_POWER[armor_num] + NEW_POWER[armor_num], 0, 32000)
```

- Delta, not recompute-from-scratch: defense points bought at fairyland or
  granted by IGMs are preserved.
- `OLD_POWER` (the 15 original values) lives as a frozen constant next to
  the migration step — the live table can drift later without corrupting
  the migration.
- Runs inside the same startup path; fresh databases (no stored version
  row) skip it.
- No compensation for the tier 12–15 price cuts (a past buyer overpaid in
  gold terms); acceptable for a balance patch.
- The new-player and dragon-reset defense baseline moves from 1 to 3 in
  lockstep with Coat's power, so `defense = base (0) + armor_power` holds
  for freshly created characters exactly as it does for migrated ones.

### 4. Error handling

- Migration clamps to the existing `[0, 32000]` stat bounds
  (`pylord/engine/limits.py`).
- `armor_num` outside 1–15 (corrupt row): skip the row, log a warning.

## Testing

1. **Table sanity** (`tests/test_data.py`): update the endpoint assertions
   in `test_armor_table_shape_and_endpoints` (Coat 200/3, Lore 12M/1350);
   add a monotonicity check (powers and prices strictly increase).
2. **Value invariant** (new): for every tier n ≥ 2, assert
   `(price[n] - price[n-1] // 2) / (power[n] - power[n-1]) < 35_000` —
   armor always beats fairyland's per-point price. (Trade-in is
   charm/level-dependent and can exceed half price; half is the
   conservative floor.)
3. **Migration** (new, `tests/test_migrate.py` or `test_datalayer.py`):
   seed a version-5 database with players (armored, unarmored,
   fairyland-boosted defense, corrupt `armor_num`), run `create_schema`,
   assert deltas applied exactly once (idempotent on second startup) and
   clamped.
4. **Survivability guard** (new, seeded-rng simulation test): level-10
   build vs level-10 monster table, assert per-fight death rate < 5% and
   blocked-swing rate < 90% — locks in "survivable but not nullified"
   against future data edits.
5. Full suite (`uv run pytest`) — combat/shop/e2e tests must pass
   unchanged except for asserted table values.

## Out of scope

- Weapon curve rebalance (same structural issue may exist; separate pass).
- Fairyland price changes.
- Combat formula changes (damage variance is addressed indirectly: higher
  defense truncates the roll range).
