"""Shared floor/cap bounds for validated player-stat writes.

Both :class:`pylord.hooks.PlayerView` (IGM writes, Task 12) and
:func:`pylord.engine.effects.apply_effect` (mail "effect" payloads, Task
13a) validate the same handful of ``Player`` fields. They used to carry two
independently-drifted copies of these bounds; this module is the single
source of truth both now import, so a stat can't end up with a different
validated range depending on which channel wrote it (a review finding on
Task 13a -- see ``docs/deviations.md``).

Bounds, and their lord.js citations:

* ``gold``/``gems`` -> floored at 0. Matches lord.js's own "gold on hand
  lost -> 0" combat-death flooring (reference/lord.js:15071).
* ``exp`` -> floored at 0, capped at 2,000,000,000 -- the same ceiling
  ``grant_exp()`` (``pylord/engine/game.py``) applies everywhere exp is
  credited (reference/lord.js:15108-15110).
* ``hp_max``/``strength``/``defense`` -> floored at 1 -- the smallest value
  that keeps a character functional (a 0-strength or 0-hp_max player can
  neither fight nor be healed); no explicit lower bound is discoverable in
  lord.js beyond "a live warrior has a positive combat stat" -- and capped
  at 32,000, matching lord.js's own ``add_hp()``/``add_str()``/
  ``add_def()`` helpers (reference/lord.js:6458-6480).
* ``charm`` -> floored at 1, capped at 32,000. lord.js has no equivalent
  ``add_cha()`` helper; the same ceiling is extrapolated here for
  consistency with the rest of the "small combat stat" family -- an
  explicit, documented guess, not a literal lord.js value.
* ``forest_fights``/``player_fights`` -> floored at 0 (can't have a
  negative fight count), capped at 32,000. lord.js's own forest_fights cap
  (reference/lord.js:5443, 9099-9101) applied to both fields for symmetry;
  lord.js has no explicit ``player_fights`` (``pvp_fights``) cap, so
  32,000 is an extrapolation from the sibling field.
* ``hp`` -> clamped to ``[0, hp_max]`` -- current HP can never exceed
  whatever the (possibly just-changed) max allows. Raise ``hp_max`` first
  for a bigger pool -- documented order dependency.

``level``/``id``/``name``/``password_hash`` are deliberately NOT covered
here -- they're identity/progression fields with their own immutability
rules (see ``PlayerView``), not simple numeric clamps.
"""

from __future__ import annotations

EXP_CAP = 2_000_000_000
STAT_CAP = 32_000

FLOOR_ZERO = frozenset({"gold", "gems"})
FLOOR_ZERO_CAPPED = frozenset({"forest_fights", "player_fights"})
FLOOR_ONE_CAPPED = frozenset({"hp_max", "strength", "defense", "charm"})

# Every field this module knows how to clamp (excluding "hp", handled
# separately below since it needs the live hp_max as a second input).
VALIDATED_FIELDS = FLOOR_ZERO | FLOOR_ZERO_CAPPED | FLOOR_ONE_CAPPED | {"exp"}


def clamp(field: str, value: int) -> int:
    """Clamp ``value`` for ``field`` per this module's documented bounds.
    ``field`` must be one of :data:`VALIDATED_FIELDS` (use
    :func:`clamp_hp` for ``"hp"``, which needs ``hp_max`` too)."""
    value = int(value)
    if field in FLOOR_ZERO:
        return max(0, value)
    if field == "exp":
        return min(max(0, value), EXP_CAP)
    if field in FLOOR_ZERO_CAPPED:
        return max(0, min(value, STAT_CAP))
    if field in FLOOR_ONE_CAPPED:
        return max(1, min(value, STAT_CAP))
    raise ValueError(f"limits.clamp() has no bound for {field!r}")


def clamp_hp(value: int, hp_max: int) -> int:
    """Clamp current HP to ``[0, hp_max]``."""
    return max(0, min(int(value), int(hp_max)))
