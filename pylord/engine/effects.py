"""Applying async mail "effects" to a player.

This is the general-purpose channel behind lord.js's mail-embedded escape
codes -- e.g. `` `E123`` ("you receive 123 exp", reference/lord.js:3857-3858)
or `` `b500`` ("bank gains 500 gold", lord.js:5460ish) -- which
``lord_to_ansi()``/mail-reading code interprets inline as it displays a
message. This project generalizes that into a single JSON dict stored on
the ``mail.effect`` column (``pylord/db.py``) and applied by
:func:`apply_effect` the moment the mail is read, rather than parsing
escape codes out of message text. Both ``IgmContext.mail()`` (Task 12,
``pylord/hooks.py``) and this task's Mail scene use the same channel.

Supported keys (additive deltas, per this task's brief): ``gold``, ``gems``,
``exp``, ``hp_max``, ``strength``, ``defense``, ``charm``, ``forest_fights``,
``player_fights``. Unknown keys are ignored (a forward-compatible, rather
than an error-raising, channel -- an IGM author's typo shouldn't crash a
player's login). Floors/caps mirror the two existing "validated player
write" conventions already in this codebase:

* ``gold``/``gems`` floored at 0 -- matches lord.js's own "gold on hand
  lost -> 0" combat-death flooring (reference/lord.js:15071) and
  ``PlayerView``'s identical floor (``pylord/hooks.py``).
* ``exp`` floored at 0, capped at 2,000,000,000 -- the same ceiling
  ``grant_exp()`` (``pylord/engine/game.py``) and ``PlayerView`` apply
  everywhere exp is credited (reference/lord.js:15108-15110).
* ``hp_max``/``strength``/``defense``/``charm`` floored at 1 -- matches
  ``PlayerView``'s "never below a newborn warrior's minimum" floor
  (``pylord/hooks.py``'s module docstring explains the reasoning). Also
  capped at 32,000, mirroring lord.js's own ``add_hp()``/``add_str()``/
  ``add_def()`` helpers (reference/lord.js:6458-6480), which every
  positive stat-gain code path in lord.js (bard songs, training) routes
  through. lord.js has no equivalent ``add_cha()`` helper, but the same
  32,000 ceiling is used here for ``charm`` too, for consistency with the
  rest of the "small combat stat" family -- an explicit, documented
  extrapolation, not a literal lord.js value.
* ``forest_fights``/``player_fights`` floored at 0 (can't have a negative
  fight count) and capped at 32,000 -- lord.js's own forest_fights cap
  (reference/lord.js:5443, 9099-9101) applied here to both fields for
  symmetry; lord.js has no explicit player_fights (pvp_fights) cap, so 32,000
  is an extrapolation from the sibling field, documented here.

``hp`` is deliberately **not** a supported key: lord.js's mail effects never
touch current HP directly (only ``hp_max``, which the player's next heal/
Turgon's visit/daily reset reconciles ``hp`` against); allowing an
un-clamped direct ``hp`` write here would risk a stale value above the
(possibly since-changed) ``hp_max``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pylord.models import Player

_EXP_CAP = 2_000_000_000
_STAT_CAP = 32_000

_FLOOR_ZERO = frozenset({"gold", "gems"})
_FLOOR_ZERO_CAPPED = frozenset({"forest_fights", "player_fights"})
_FLOOR_ONE_CAPPED = frozenset({"hp_max", "strength", "defense", "charm"})

_SUPPORTED = _FLOOR_ZERO | _FLOOR_ZERO_CAPPED | _FLOOR_ONE_CAPPED | {"exp"}


def apply_effect(player: Player, effect: dict) -> None:
    """Apply an additive ``{stat: delta}`` effect dict to ``player`` in
    place. Unknown keys are silently ignored; every supported key is
    floored/capped per this module's docstring."""
    for key, delta in effect.items():
        if key not in _SUPPORTED:
            continue
        current = getattr(player, key)
        new_value = current + int(delta)
        if key in _FLOOR_ZERO:
            new_value = max(0, new_value)
        elif key == "exp":
            new_value = min(max(0, new_value), _EXP_CAP)
        elif key in _FLOOR_ZERO_CAPPED:
            new_value = max(0, min(new_value, _STAT_CAP))
        elif key in _FLOOR_ONE_CAPPED:
            new_value = max(1, min(new_value, _STAT_CAP))
        setattr(player, key, new_value)
