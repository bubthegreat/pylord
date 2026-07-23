"""Master (trainer) records, transcribed from reference/lord.js:44-213
(`trainer_stats`).

`trainer_stats[0]` is an intentionally-empty placeholder in lord.js (comment:
"You don't need to level up from zero..."); `trainer_stats[1..11]` are the
real masters, indexed by the player level at which you train with them
(fight `trainer_stats[player.level]` to advance to `player.level + 1`; see
`turgons()`/`attack_master()` around reference/lord.js:15649-15790). We keep
that same 1..11 keying for `MASTERS`.

Field mapping from lord.js -> `Master`:
    str -> strength, def -> defense, need -> exp_reward (see naming note
    below), swear -> swear, needstr1/needstr2 -> needstr1/needstr2,
    death -> death. `hp`/`weapon`/`name` unchanged.

Naming note on `exp_reward`: despite the name (required by this project's
downstream interface), `need` is exp the player must have ALREADY EARNED
to face/beat this master -- not exp granted by the fight. It gates the
level-up encounter, it isn't a reward paid out by it. See levels.py for how
this same value feeds `EXP_FOR_LEVEL`.

Surprise: `needstr1` for master 8 (Aladdin) contains a literal `&PWE`
token -- lord.js substitutes it with the player's weapon name at display
time (`trainer.needstr1.replace(/\\&PWE/i, player.weapon)`,
reference/lord.js:15594). We transcribe the raw string as-is; substitution
is a rendering-layer concern for a later task.
"""

from collections import namedtuple

Master = namedtuple(
    "Master",
    "name weapon hp strength defense exp_reward swear needstr1 needstr2 death",
)

MASTERS: dict[int, Master] = {
    1: Master(
        name="Halder",
        weapon="Short Sword",
        hp=30,
        strength=15,
        defense=2,
        exp_reward=100,
        swear="Belar!!! You are truly a great warrior!",
        needstr1="Gee, your muscles are getting bigger than mine...",
        needstr2="",
        death="  You blew your master away!",
    ),
    2: Master(
        name="Barak",
        weapon="Battle Axe",
        hp=40,
        strength=17,
        defense=3,
        exp_reward=400,
        swear="Children of Mara!!! You have bested me??!",
        needstr1="You know, you are actually getting pretty good with",
        needstr2='that thing..."',
        death="  You blew your master away!",
    ),
    3: Master(
        name="Aragorn",
        weapon="Twin Swords",
        hp=70,
        strength=35,
        defense=5,
        exp_reward=1000,
        swear="Torak's Eye!!!  You are a great warrior!",
        needstr1="You have learned everything I can teach you.",
        needstr2="",
        death="  You blew your master away!",
    ),
    4: Master(
        name="Olodrin",
        weapon="Power Axe",
        hp=120,
        strength=70,
        defense=10,
        exp_reward=4000,
        swear="Ye Gods!!  You are a master warrior!",
        needstr1="You are becoming a very skilled warrior.",
        needstr2="",
        death="  You blew your master away!",
    ),
    5: Master(
        name="Sandtiger",
        weapon="Blessed Sword",
        hp=200,
        strength=100,
        defense=15,
        exp_reward=10000,
        swear="Very impressive...Very VERY impressive.",
        needstr1="Gee - You really know how to handle your shaft!",
        needstr2="",
        death="  You blew your master away!",
    ),
    6: Master(
        name="Sparhawk",
        weapon="Double Bladed Sword",
        hp=400,
        strength=150,
        defense=22,
        exp_reward=40000,
        swear="This Battle is yours...You have fought with honor.",
        needstr1="You're getting the hang of it now!",
        needstr2="",
        death="  You blew your master away!",
    ),
    7: Master(
        name="Atsuko Sensei",
        weapon="Huge Curved Blade",
        hp=600,
        strength=250,
        defense=35,
        exp_reward=100000,
        swear="Even though you beat me, I am proud of you.",
        needstr1="You are ready to be tested on the battle field!",
        needstr2="",
        death="  You blew your master away!",
    ),
    8: Master(
        name="Aladdin",
        weapon="Shiny Lamp",
        hp=800,
        strength=350,
        defense=60,
        exp_reward=400000,
        swear="I don't need a genie to see that you beat me, man!",
        needstr1="You REALLY know how to use your &PWE!!!",
        needstr2="",
        death="  You blew your master away!",
    ),
    9: Master(
        name="Prince Caspian",
        weapon="Flashing Rapier",
        hp=1200,
        strength=500,
        defense=80,
        exp_reward=1000000,
        swear="Good show, chap!  Jolly good show!",
        needstr1="Something tells me that you are as good as I am now.",
        needstr2="",
        death="  You blew your master away!",
    ),
    10: Master(
        name="Gandalf",
        weapon="Huge Fireballs",
        hp=1800,
        strength=800,
        defense=120,
        exp_reward=4000000,
        swear="Torak's Tooth!  You are great!",
        needstr1="You are becoming a very skilled warrior",
        needstr2="",
        death="  You blew your master away!",
    ),
    11: Master(
        name="Turgon",
        weapon="Ables Sword",
        hp=2500,
        strength=1200,
        defense=150,
        exp_reward=10000000,
        swear="  You are a master warrior!",
        needstr1="You are truly the BEST warrior in the realm.",
        needstr2="",
        death="  You blew your master away!",
    ),
}
