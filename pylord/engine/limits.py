"""Shared floor/cap bounds for validated player-stat writes.

Both :class:`pylord.hooks.PlayerView` (IGM writes, Task 12) and
:func:`pylord.engine.effects.apply_effect` (mail "effect" payloads, Task
13a) validate the same handful of ``Player`` fields. They used to carry two
independently-drifted copies of these bounds; this module is the single
source of truth both now import, so a stat can't end up with a different
validated range depending on which channel wrote it (a review finding on
Task 13a -- see ``docs/deviations.md``).

Every bound is a literal port of lord.js's own ``check_fields()``
(reference/lord.js:16603-16679) -- the field-by-field floor/cap normalizer
lord.js runs immediately after an IGM returns (called at :16727), i.e.
exactly the role this module plays for ``PlayerView`` and
``apply_effect``. (An earlier version of this module was ported against
``add_hp()``/``add_str()``/``add_def()`` (:6458-6480) instead, which only
covers three stats, and guessed floors of 1 where ``check_fields()``
floors at 0.)

Bounds, and their ``check_fields()`` lines:

* ``gold`` -> floored at 0 (:16630-16631), capped at 2,000,000,000
  (:16632-16634).
* ``bank`` -> floored at 0, capped at 2,000,000,000 (:16635-16640).
* ``gems`` -> floored at 0, capped at 32,000. ``check_fields()`` doesn't
  cover ``gem``, but every site that credits gems caps it there
  (reference/lord.js:3722-3723, 14858-14859, 15478-15479) and the record
  field is a ``SignedInteger16`` (reference/recorddefs.js:155-159).
* ``exp`` -> floored at 0, capped at 2,000,000,000 (:16659-16663). Same
  ceiling ``grant_exp()`` (``pylord/engine/game.py``) applies.
* ``hp_max`` -> floored at 0, capped at 32,000 (:16611-16616).
* ``strength``/``defense``/``charm`` -> floored at 0, capped at 32,000
  (:16641-16658).
* ``forest_fights``/``player_fights`` -> floored at 0, capped at 32,000
  (:16617-16627; the player-side forest-fight cap is also applied at
  :5503-5504 -- note :5443 is a *settings* bound, not a player one).
* ``lays``/``kids`` -> floored at 0, capped at 32,000 (:16665-16674;
  lord.js's ``laid``/``kids``).
* ``hp`` -> clamped to ``[0, hp_max]``. ``check_fields()`` uses a flat
  ``[0, 32000]`` (:16605-16610) because lord.js reconciles hp against
  hp_max elsewhere; clamping to the live max here is strictly safer and
  keeps ``PlayerView`` from parking a stale hp above a lowered max. Raise
  ``hp_max`` first for a bigger pool -- documented order dependency.

``level``/``id``/``name``/``password_hash`` are deliberately NOT covered
here -- they're identity/progression fields with their own immutability
rules (see ``PlayerView``), not simple numeric clamps.
"""

from __future__ import annotations

EXP_CAP = 2_000_000_000
GOLD_CAP = 2_000_000_000
STAT_CAP = 32_000

FLOOR_ZERO_BIG_CAPPED = frozenset({"gold", "bank"})
FLOOR_ZERO_CAPPED = frozenset(
    {
        "gems",
        "forest_fights",
        "player_fights",
        "hp_max",
        "strength",
        "defense",
        "charm",
        "lays",
        "kids",
    }
)

# Every field this module knows how to clamp (excluding "hp", handled
# separately below since it needs the live hp_max as a second input).
VALIDATED_FIELDS = FLOOR_ZERO_BIG_CAPPED | FLOOR_ZERO_CAPPED | {"exp"}


def clamp(field: str, value: int) -> int:
    """Clamp ``value`` for ``field`` per this module's documented bounds.
    ``field`` must be one of :data:`VALIDATED_FIELDS` (use
    :func:`clamp_hp` for ``"hp"``, which needs ``hp_max`` too)."""
    value = int(value)
    if field in FLOOR_ZERO_BIG_CAPPED:
        return max(0, min(value, GOLD_CAP))
    if field == "exp":
        return min(max(0, value), EXP_CAP)
    if field in FLOOR_ZERO_CAPPED:
        return max(0, min(value, STAT_CAP))
    raise ValueError(f"limits.clamp() has no bound for {field!r}")


def clamp_hp(value: int, hp_max: int) -> int:
    """Clamp current HP to ``[0, hp_max]``."""
    return max(0, min(int(value), int(hp_max)))
