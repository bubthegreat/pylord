"""Experience curve and per-level training gains.

Both tables are derived from the same source records as masters.py —
`trainer_stats` in reference/lord.js:44-213 — but are split out here since
they answer different questions (how much exp to level up / what stats you
gain) than master identity (masters.py).

`trainer_stats[i]` (i = 1..11, `i` also being the player level at which you
train with that master) holds, among other fields:

    need        -- exp required to face this master
    hp_gained   -- hp granted on victory
    str_gained  -- strength granted on victory
    def         -- defense granted on victory

lord.js's leveling code (reference/lord.js:15760-15790, inside `turgons()`):

    battle(trainer, false, false);
    ...
    else if (trainer.hp < 1) {
        player.hp_max += trainer.hp_gained;
        player.hp = player.hp_max;
        player.str += trainer.str_gained;
        player.def += trainer.def;
        player.level += 1;
        ...

So defeating `trainer_stats[i]` (while at level i) both grants the gains
above *and* advances `player.level` from i to i+1. That means
`trainer_stats[i].need` is the exp threshold to REACH level i+1 — hence
`EXP_FOR_LEVEL[i + 1] = trainer_stats[i].need` below (checked at
reference/lord.js:15590 and :15683, both `player.exp` compared against
`trainer.need`).

Surprise: `trainer_stats[i].def` is reused for two different purposes in
lord.js — it is both the master's own combat defense stat (used as
`op.def` when you fight them, reference/lord.js:6949) and the amount of
defense the player gains on victory. We preserve that: `LEVEL_STATS[i]`
duplicates the value also present on `MASTERS[i].defense`.
"""

from collections import namedtuple

LevelGain = namedtuple("LevelGain", "hp strength defense")

# level reached -> exp needed to reach it (trainer_stats[level - 1].need)
EXP_FOR_LEVEL: dict[int, int] = {
    2: 100,
    3: 400,
    4: 1000,
    5: 4000,
    6: 10000,
    7: 40000,
    8: 100000,
    9: 400000,
    10: 1000000,
    11: 4000000,
    12: 10000000,
}

# master/level index (1..11) -> gains for defeating that master
LEVEL_STATS: dict[int, LevelGain] = {
    1: LevelGain(hp=10, strength=5, defense=2),
    2: LevelGain(hp=15, strength=7, defense=3),
    3: LevelGain(hp=20, strength=10, defense=5),
    4: LevelGain(hp=30, strength=12, defense=10),
    5: LevelGain(hp=50, strength=20, defense=15),
    6: LevelGain(hp=75, strength=35, defense=22),
    7: LevelGain(hp=125, strength=50, defense=35),
    8: LevelGain(hp=185, strength=75, defense=60),
    9: LevelGain(hp=250, strength=110, defense=80),
    10: LevelGain(hp=350, strength=150, defense=120),
    11: LevelGain(hp=550, strength=200, defense=150),
}
