"""Combat engine, ported from reference/lord.js.

Every formula below is a direct port of a function in ``reference/lord.js``;
each has a docstring/comment citing the exact source line(s) it was taken
from. The three functions this module is built around:

- ``do_attack()``          -- player's basic attack   (lord.js:6931-6997)
- ``enemy_attack()``       -- enemy's counter-attack   (lord.js:6691-6839)
- ``handle_hit()``         -- damage-application tail shared by all three
                               skill attacks below      (lord.js:6893-6929)
- ``try_running()``        -- flee attempt             (lord.js:6999-7030)
- ``use_death_knight()``   -- Death Knight skill attack (lord.js:7032-7108)
- ``use_thief_skill()``    -- Thieving skill attack     (lord.js:7110-7184)
- ``use_mystical_skill()`` -- Mystical spells           (lord.js:7186-7363)

Design notes / deliberate deviations from lord.js (all documented again at
their point of use below):

1. lord.js's ``do_attack``/``handle_hit`` automatically chain into
   ``enemy_attack()`` when the target survives a player hit. This module's
   ``Fight`` interface instead exposes ``player_attack()``/``enemy_attack()``
   as two separate, independently callable actions (per the Task 7 brief's
   required interface) -- the caller (a future game-loop task) is
   responsible for sequencing "player hits, enemy survives, enemy hits
   back", matching lord.js's net behaviour without baking the chaining into
   this engine layer.
2. lord.js's player-vs-player-only bits (``pfight`` honor checks, arena
   no-run rule, ``cant_run``) don't apply to the ``Combatant`` abstraction
   used here (no arena/duel concept) and are omitted.
3. The "child startles your attacker" and "horse intercepts a killing blow"
   side stories in ``enemy_attack`` (lord.js:6731-6758, 6795-6838) depend on
   ``player.kids``/``player.horse`` state that has no equivalent on
   ``Combatant`` and are omitted.
4. lord.js's ``random(n)`` helper isn't defined in this repo's
   ``reference/lord.js`` excerpt (it's supplied by the surrounding BBS
   door-game runtime) but every call site is used as
   ``Math.floor(Math.random() * n)`` -- uniform over ``0..n-1``. We
   reproduce that with ``rng.randrange(n)``, guarding ``n <= 0`` (which
   ``Math.random() * 0`` always resolves to 0 for in JS) by returning 0
   without drawing. See ``_random()``.
5. ``pfight`` (post-review correction): lord.js gates the player-side
   defense subtraction on this flag -- ``do_attack``:6948-6949 and
   ``handle_hit``:6897-6898 both read ``if (pfight) atk -= op.def;``. Every
   monster AND master encounter is started with ``pfight=false`` (masters:
   ``battle(trainer, false, false)``, lord.js:15760); the only caller that
   passes ``pfight=true`` is real player-vs-player combat
   (``battle(op, true, false)``, lord.js:7824). So a Master's ``defense``
   is *never* subtracted from the player's attack in an ordinary encounter
   -- only in PvP. ``Fight.pfight`` defaults to ``False`` accordingly; a
   future PvP task must construct ``Fight(..., pfight=True)`` explicitly.
   ``enemy_attack()``'s ``atk -= player.def`` (lord.js:6726) has no such
   guard and stays unconditional in both modes.
6. ``skill_points`` is never decremented by ``skill_attack()`` -- lord.js
   decrements ``player.levelw``/``levelm``/``levelt`` itself after a
   successful cast (e.g. lord.js:7107, 7183, 7295/7310/7321/7334/7345/7360).
   The caller is responsible for persisting the decremented value back onto
   whichever ``Player`` field the ``kind`` maps to.
"""

from __future__ import annotations

import random
from collections import namedtuple
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pylord.engine.data import weapon

if TYPE_CHECKING:
    from pylord.engine.data import Master, Monster
    from pylord.models import Player

Round = namedtuple("Round", "damage killed text")


def _random(rng: random.Random, n: int) -> int:
    """Port of lord.js's ``random(n)`` (returns 0..n-1). See module docstring
    note 4 for why ``n <= 0`` is special-cased instead of calling
    ``rng.randrange`` directly (which raises on ``n <= 0``)."""
    return 0 if n <= 0 else rng.randrange(n)


@dataclass
class Combatant:
    """One side of a Fight. Mutable so hp can be drained in place."""

    name: str
    hp: int
    hp_max: int
    strength: int
    defense: int
    weapon_name: str

    @classmethod
    def from_player(cls, p: Player) -> Combatant:
        """weapon_num 0 means unarmed -- lord.js's ``weapon_stats[0]``
        placeholder is named "Fists" (see engine/data/weapons.py docstring);
        WEAPONS excludes that placeholder, so it's special-cased here rather
        than looked up."""
        wname = weapon(p.weapon_num).name if p.weapon_num else "Fists"
        return cls(
            name=p.name,
            hp=p.hp,
            hp_max=p.hp_max,
            strength=p.strength,
            defense=p.defense,
            weapon_name=wname,
        )

    @classmethod
    def from_monster(cls, m: Monster) -> Combatant:
        """Monster has no defense field at all in lord.js (see
        engine/data/monsters.py docstring) -- defense=0 here reproduces that
        exactly, since do_attack()/handle_hit() only ever subtract op.def
        when ``pfight`` is true (never for a plain monster encounter);
        subtracting a defense of 0 is a no-op with the same net effect."""
        return cls(
            name=m.name,
            hp=m.hp,
            hp_max=m.hp,
            strength=m.strength,
            defense=0,
            weapon_name=m.weapon,
        )

    @classmethod
    def from_master(cls, m: Master) -> Combatant:
        """Masters carry a real ``def`` in lord.js's trainer_stats (it also
        doubles as the level-up stat grant -- see engine/data/masters.py
        docstring), so it's used here, unlike Monster."""
        return cls(
            name=m.name,
            hp=m.hp,
            hp_max=m.hp,
            strength=m.strength,
            defense=m.defense,
            weapon_name=m.weapon,
        )


def attack_damage(
    attacker: Combatant,
    defender: Combatant,
    rng: random.Random,
    pfight: bool = False,
) -> int:
    """Base damage roll for a **player-side** attack, per lord.js:

        atk = random(parseInt(str / 2, 10)) + parseInt(str / 2, 10)
        if (pfight) atk -= defender.def

    seen (with identical shape, different variable names) at:
      - do_attack (player's basic attack): lord.js:6943 (roll), 6948-6949 (pfight-gated defense subtract)
      - use_death_knight / use_thief_skill (skill roll): lord.js:7099 / 7180
      - handle_hit (skill's pfight-gated defense subtract): lord.js:6897-6898

    **``pfight`` gating (post-review correction):** lord.js only subtracts
    the defender's defense when ``pfight`` is true -- i.e. real
    player-vs-player combat (``battle(op, true, false)``, lord.js:7824).
    Every monster and master encounter uses ``pfight=false``
    (``battle(trainer, false, false)``, lord.js:15760), so a Master's
    ``defense`` is never subtracted from the player's attack in an ordinary
    fight. Defaults to ``False`` to match that. See module docstring note 5.

    This is the **player-side** formula only -- do not use it for the
    enemy's attack. ``Fight.enemy_attack()`` subtracts ``player.defense``
    unconditionally (lord.js:6726 has no ``pfight`` guard at all); that
    asymmetry is correct per lord.js and is implemented separately.

    Result is floored at 0 -- never negative, per the Task 7 TDD
    requirement. ``Fight.player_attack()`` treats a 0 result as a miss
    (lord.js's do_attack does the same: ``if (atk < 1)`` at 6954), while
    skill attacks routed through ``handle_hit`` instead clamp a
    non-positive result *up* to a guaranteed 1 (lord.js:6900-6902) -- that
    clamp-up is applied by the caller (``_handle_hit`` below), not by this
    shared primitive, since the two behaviours diverge here.

    Consumes exactly one rng draw (the base roll) -- defense subtraction is
    not random -- so callers that need a further draw afterward (e.g.
    ``player_attack()``'s crit roll) stay aligned with lord.js's draw order.
    """
    half = attacker.strength // 2
    raw = _random(rng, half) + half
    if pfight:
        raw -= defender.defense
    return max(raw, 0)


@dataclass
class Fight:
    """One combat encounter between the player and an enemy Combatant."""

    player_side: Combatant
    enemy: Combatant
    rng: random.Random
    pfight: bool = False
    ran_away: bool = False
    light_shield: bool = False
    gem_found: bool = False
    bonus_gold: bool = False

    @property
    def over(self) -> bool:
        return self.player_side.hp <= 0 or self.enemy.hp <= 0 or self.ran_away

    @property
    def winner(self) -> str | None:
        if self.enemy.hp <= 0:
            return "player"
        if self.player_side.hp <= 0:
            return "enemy"
        return None

    def _loot_bonus(self, dmg: int, killed: bool) -> str:
        """Overkill loot roll shared by do_attack() and handle_hit():

            if (atk > player.str && op.hp < 1) {
                switch (random(3)) {
                    case 0: /* find a gem */ break;
                    case 1: /* enemy's gold doubles */ break;
                }
            }

        (do_attack:6973-6991, handle_hit:6905-6924; case 2 and the implicit
        default do nothing). Effects beyond Round's shape are recorded on
        Fight state per the Task 7 brief's guidance.
        """
        if not (killed and dmg > self.player_side.strength):
            return ""
        roll = _random(self.rng, 3)
        if roll == 0:
            self.gem_found = True
            return " You find a gem!"
        if roll == 1:
            self.bonus_gold = True
            return " You find more gold than expected!"
        return ""

    def player_attack(self) -> Round:
        """Port of do_attack(). reference/lord.js:6931-6997.

        Delegates the base roll + ``pfight``-gated defense subtraction to
        ``attack_damage()`` (single source of truth, no duplicated formula
        -- see module docstring note 5 for the ``pfight`` correction).
        Amulet handling (6945-6946, 6951-6952) is omitted -- Player
        (pylord/models.py) has no amulet field. Draw order matches lord.js
        exactly: base roll first (6943, inside ``attack_damage()``), then
        the power-move-chance roll (6944, drawn unconditionally, before the
        miss check), so seeded rng sequences stay aligned with the source
        even though the multiply itself only applies on a hit.
        """
        dmg = attack_damage(
            self.player_side, self.enemy, self.rng, self.pfight
        )  # lord.js:6943, 6948-6949
        crit_roll = _random(self.rng, 10) + 1  # lord.js:6944
        if dmg < 1:  # lord.js:6954
            return Round(
                damage=0, killed=False, text=f"You miss {self.enemy.name} completely!"
            )
        if crit_roll > 9:  # lord.js:6961 (`c > 9`), a 1-in-10 chance
            dmg *= 3  # lord.js:6962, "POWER MOVE"
        self.enemy.hp -= dmg  # lord.js:6972
        killed = self.enemy.hp <= 0
        text = f"You hit {self.enemy.name} for {dmg} damage!"
        text += self._loot_bonus(dmg, killed)
        return Round(damage=dmg, killed=killed, text=text)

    def enemy_attack(self) -> Round:
        """Port of enemy_attack() for a plain (non-pfight, non-dragon)
        encounter. reference/lord.js:6691-6839.

        Dragon weapon-switching (6704-6720) and the kids/horse side stories
        (6731-6758, 6795-6838) are omitted -- see module docstring notes 2-3.
        ``light_shield``'s halving (6767-6769) is kept, since it's driven
        purely by Fight/skill_attack state modeled here.
        """
        half = self.enemy.strength // 2
        raw = _random(self.rng, half) + half  # lord.js:6703
        if _random(self.rng, 30) == 1:  # lord.js:6721, 1-in-30 power move
            raw += raw // 2  # lord.js:6722
        atk = raw - self.player_side.defense  # lord.js:6726
        if atk < 1:  # lord.js:6727
            return Round(
                damage=0, killed=False, text=f"{self.enemy.name} misses you completely!"
            )
        if self.light_shield:  # lord.js:6767-6769
            atk //= 2
        self.player_side.hp -= atk  # lord.js:6770
        killed = self.player_side.hp <= 0
        return Round(
            damage=atk,
            killed=killed,
            text=f"{self.enemy.name} hits you for {atk} damage!",
        )

    def attempt_run(self) -> bool:
        """Port of try_running() for a plain encounter.
        reference/lord.js:6999-7030.

        The arena no-run rule (7001-7006) and ``cant_run`` override don't
        apply to a bare Combatant fight and are omitted. On a failed
        attempt the enemy gets a free attack, exactly as lord.js does
        (``enemy_attack(op, pfight)`` at 7011).
        """
        if _random(self.rng, 9) == 1:  # lord.js:7008, 1-in-9 chance to be caught
            self.enemy_attack()
            return False
        self.ran_away = True  # lord.js:7015
        return True


def _handle_hit(fight: Fight, atk: int, verb: str) -> Round:
    """Port of handle_hit() -- the damage-application tail shared by every
    skill attack (Death Knight, Thieving, and 3 of the 6 Mystical spells).
    reference/lord.js:6893-6929.

    Unlike do_attack(), this never misses: defense is subtracted (gated on
    ``fight.pfight``, per module docstring note 5), then the result is
    clamped *up* to a guaranteed minimum of 1
    (lord.js:6900-6902: ``if (atk < 1) atk = 1;``).
    """
    if fight.pfight:  # lord.js:6897-6898 `if (pfight) atk -= op.def;`
        atk -= fight.enemy.defense
    atk = max(atk, 1)  # lord.js:6900-6902
    fight.enemy.hp -= atk  # lord.js:6904
    killed = fight.enemy.hp <= 0
    text = f"{verb} {fight.enemy.name} for {atk} damage!"
    text += fight._loot_bonus(atk, killed)
    return Round(damage=atk, killed=killed, text=text)


def _death_knight_attack(fight: Fight, skill_points: int) -> Round:
    """Port of use_death_knight(). reference/lord.js:7032-7108.

    Costs 1 use point; requires at least 1 (lord.js has no explicit "not
    enough points" guard for this skill -- the menu simply hides the option
    when ``player.levelw`` is 0 -- so we add an equivalent guard here since
    this module has no menu to hide options from). Damage: base roll
    tripled (``atk *= 3``, lord.js:7104). The ``settings.dk_boost`` x3.3
    server-config variant (7100-7101) is a deployment toggle, not modeled.
    The pfight honor-check (7038-7051) is player-vs-player-only and omitted.
    """
    if skill_points < 1:
        # Equivalent to lord.js's menu hiding this option entirely
        # (battle_prompt only shows it when player.levelw > 0) -- the
        # underlying function is never invoked, so zero rng draws here
        # matches lord.js exactly (no draw happens either).
        return Round(
            damage=0, killed=False, text="You don't have the strength for that."
        )
    _random(
        fight.rng, 7
    )  # lord.js:7059, flavor-text switch(random(7)) -- discarded, draw-order only
    half = fight.player_side.strength // 2
    atk = _random(fight.rng, half) + half  # lord.js:7099
    atk *= 3  # lord.js:7104 (non-dk_boost branch)
    return _handle_hit(fight, atk, "In a brutal display, you tear into")


def _thief_attack(fight: Fight, skill_points: int) -> Round:
    """Port of use_thief_skill(). reference/lord.js:7110-7184.

    The formula is identical to the Death Knight attack -- same roll, same
    x3 multiplier, same handle_hit tail -- only the flavor text differs in
    lord.js. The Task 7 brief anticipated a thief-specific "steal gold"
    mechanic ("Thieving death-blow/gold effects"); no such mechanic exists
    in ``use_thief_skill`` -- it has no ``op.gold``/``player.gold``
    interaction at all. The *only* gold/gem effect present anywhere along
    the skill-attack code path is the generic overkill loot bonus shared by
    every attack type (``handle_hit``:6905-6924, ``do_attack``:6973-6991).
    Per "lord.js wins" over the brief's guess, that shared bonus is what's
    surfaced here via ``fight.gem_found`` / ``fight.bonus_gold``.
    """
    if skill_points < 1:
        # See _death_knight_attack's identical guard note: equivalent to
        # the menu hiding this option, zero draws.
        return Round(damage=0, killed=False, text="You don't have the skill for that.")
    _random(
        fight.rng, 7
    )  # lord.js:7137, flavor-text switch(random(7)) -- discarded, draw-order only
    half = fight.player_side.strength // 2
    atk = _random(fight.rng, half) + half  # lord.js:7180
    atk *= 3  # lord.js:7181
    return _handle_hit(fight, atk, "With a sneaky strike, you stab")


# (letter -> use-point cost), highest tier first for auto-selection below.
_MYSTICAL_COST = {"P": 1, "D": 4, "H": 8, "L": 12, "S": 16, "M": 20}
_MYSTICAL_TIERS_HIGH_TO_LOW = ("M", "S", "L", "H", "D", "P")


def _mystical_attack(fight: Fight, skill_points: int, choice: str | None) -> Round:
    """Port of use_mystical_skill(). reference/lord.js:7186-7363.

    **Skill-mapping decision (see also the Task 7 report):** lord.js gates
    its interactive 6-option menu on *two* independent counters --
    ``player.levelm`` (spendable use-points, decremented on cast) AND
    ``player.skillm`` (a separate permanent rank), e.g. Heat Wave requires
    ``player.levelm > 7 && player.skillm > 7`` (lord.js:7255). This
    project's ``Player`` model (pylord/models.py) collapses that to a
    single field, ``skill_my``; the caller passes it in as ``skill_points``
    and gating here uses that one value only: ``skill_points >= cost``.
    (lord.js's threshold constants -- 1, 4, 8, 12, 16, 20 -- are each
    exactly the true cost, checked with a strict `<` "too tired" guard, e.g.
    ``if (player.levelm < 1)`` for Pinch which costs 1 -- so `>=` here is
    the faithful non-strict equivalent.)

    lord.js's menu is interactive (the player picks a letter); this engine
    layer has no I/O. ``choice`` lets a caller (a future UI/game-loop task)
    pick a spell letter explicitly (``P``/``D``/``H``/``L``/``S``/``M``);
    when omitted (the default used by ``skill_attack``), the highest-tier
    spell ``skill_points`` can afford is auto-selected. This auto-selection
    is a judgment call documented here because lord.js has no
    non-interactive equivalent to port -- there is no "AI" opponent logic
    for mystical skills anywhere in the source.

    Spell formulas (``roll = random(str // 2) + str // 2``, the same base
    roll used everywhere else in combat):

    =====  ====  ==========================================================
    Letter Cost  Effect (lord.js lines)
    =====  ====  ==========================================================
    P      1     atk = roll*2 - (roll*2)//4  (net x1.5), handle_hit (7286-7299)
    D      4     no damage; sets fight.ran_away                  (7301-7312)
    H      8     atk = roll*2 + (roll*2)//4  (net x2.5), handle_hit (7313-7325)
    L      12    no damage; sets fight.light_shield               (7326-7336)
    S      16    atk = roll*4 + (roll*4)//4  (net x5),   handle_hit (7337-7349)
    M      20    no damage; heals player to hp_max                (7350-7362)
    =====  ====  ==========================================================
    """
    if choice is not None:
        if choice not in _MYSTICAL_COST or skill_points < _MYSTICAL_COST[choice]:
            return Round(
                damage=0,
                killed=False,
                text="You reach for the power, but it just isn't there.",
            )
    else:
        choice = next(
            (
                c
                for c in _MYSTICAL_TIERS_HIGH_TO_LOW
                if skill_points >= _MYSTICAL_COST[c]
            ),
            None,
        )
        if choice is None:
            return Round(
                damage=0,
                killed=False,
                text="You reach for the power, but it just isn't there.",
            )

    # lord.js:7225, flavor-text switch(random(7)) -- drawn unconditionally
    # once per cast, before the menu/spell dispatch, regardless of which
    # letter is eventually chosen. Discarded, draw-order only.
    _random(fight.rng, 7)

    half = fight.player_side.strength // 2

    if choice == "P":
        atk = _random(fight.rng, half) + half  # lord.js:7292
        atk = atk * 2 - (atk * 2) // 4  # lord.js:7293
        return _handle_hit(fight, atk, "You whisper the word of pain into")

    if choice == "D":
        fight.ran_away = True  # lord.js:7311-7312
        return Round(
            damage=0,
            killed=False,
            text="You disappear into a cool glade, far from your enemy.",
        )

    if choice == "H":
        atk = _random(fight.rng, half) + half  # lord.js:7322
        atk = atk * 2 + (atk * 2) // 4  # lord.js:7323
        return _handle_hit(fight, atk, "Flames engulf")

    if choice == "L":
        fight.light_shield = True  # lord.js:7335
        return Round(
            damage=0,
            killed=False,
            text="A beam of light covers you. You are still glowing.",
        )

    if choice == "S":
        atk = _random(fight.rng, half) + half  # lord.js:7346
        atk = atk * 4 + (atk * 4) // 4  # lord.js:7347
        return _handle_hit(fight, atk, "You imagine the bones shattering inside")

    # choice == "M"
    fight.player_side.hp = fight.player_side.hp_max  # lord.js:7361
    return Round(
        damage=0,
        killed=False,
        text="Missing pieces of your flesh crawl back into place. You are healed.",
    )


def skill_attack(
    fight: Fight,
    kind: Literal["dk", "my", "th"],
    skill_points: int,
    mystical_choice: str | None = None,
) -> Round:
    """Dispatch to the three skill-attack ports:
    ``dk`` -> use_death_knight() (lord.js:7032-7108)
    ``th`` -> use_thief_skill()  (lord.js:7110-7184)
    ``my`` -> use_mystical_skill() (lord.js:7186-7363)

    ``mystical_choice`` is ``my``-only; see ``_mystical_attack`` docstring
    for why it exists and what it defaults to.
    """
    if kind == "dk":
        return _death_knight_attack(fight, skill_points)
    if kind == "th":
        return _thief_attack(fight, skill_points)
    if kind == "my":
        return _mystical_attack(fight, skill_points, mystical_choice)
    raise ValueError(f"unknown skill kind: {kind!r}")
