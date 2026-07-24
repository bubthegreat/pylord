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
player's login). Floors/caps are the shared bounds in
``pylord/engine/limits.py`` -- the same module ``PlayerView``
(``pylord/hooks.py``) validates IGM writes against, so a stat can't end up
with a different validated range depending on which channel wrote it (a
review finding on this task -- previously each module carried its own,
independently-drifted copy of these bounds; see ``docs/deviations.md``).

``hp`` is deliberately **not** a supported key: lord.js's mail effects never
touch current HP directly (only ``hp_max``, which the player's next heal/
Turgon's visit/daily reset reconciles ``hp`` against); allowing an
un-clamped direct ``hp`` write here would risk a stale value above the
(possibly since-changed) ``hp_max``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylord.engine import limits

if TYPE_CHECKING:
    from pylord.models import Player


def apply_effect(player: Player, effect: dict) -> None:
    """Apply an additive ``{stat: delta}`` effect dict to ``player`` in
    place. Unknown keys are silently ignored; every supported key is
    floored/capped per ``pylord/engine/limits.py``."""
    for key, delta in effect.items():
        if key not in limits.VALIDATED_FIELDS:
            continue
        new_value = getattr(player, key) + int(delta)
        setattr(player, key, limits.clamp(key, new_value))
