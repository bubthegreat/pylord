"""Game data tables ported verbatim from reference/lord.js.

See the individual modules for the exact lord.js line ranges and any
transcription notes:

- weapons.py  -- weapon shop table (lord.js:1416-1433)
- armor.py    -- armor shop table (lord.js:1397-1414)
- levels.py   -- exp curve + per-level training gains (lord.js:44-213)
- masters.py  -- master/trainer records (lord.js:44-213)
- monsters.py -- forest monster records (lord.js:215-1395)
"""

from pylord.engine.data.armor import ARMOR, armor
from pylord.engine.data.levels import EXP_FOR_LEVEL, LEVEL_STATS, LevelGain
from pylord.engine.data.masters import MASTERS, Master
from pylord.engine.data.monsters import MONSTERS, Monster
from pylord.engine.data.weapons import WEAPONS, Item, weapon

__all__ = [
    "ARMOR",
    "EXP_FOR_LEVEL",
    "LEVEL_STATS",
    "MASTERS",
    "MONSTERS",
    "WEAPONS",
    "Item",
    "LevelGain",
    "Master",
    "Monster",
    "armor",
    "weapon",
]
