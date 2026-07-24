"""Daily maintenance: bank interest, resurrection, and daily-counter resets
for every player, run at most once per calendar day.

**Architecture deviation from lord.js (documented, deliberate):** lord.js
resets each player *lazily*, per-player, the moment they log in on a new
day (``wake_up()``, reference/lord.js:5412-5595, called from the login
path once ``player.time != state.days``). This module instead does a
*global batch* pass over every player at once, gated by a single
``game_state`` key (``'last_maint'``) so it only actually runs once per
calendar date no matter how many connections trigger it -- per this
task's explicit brief. The *values and formulas* below are still ported
faithfully from ``wake_up()``; only the "when/how many players at once"
trigger mechanism differs.

Formulas ported from ``wake_up()`` (reference/lord.js:5412-5595):

- **Bank interest, 10%/day**: ``player.bank += parseInt(player.bank / 10,
  10)``, capped at 2,000,000,000 (reference/lord.js:5507-5517).
- **Resurrection + full heal**: ``player.hp = player.hp_max`` (line 5424,
  applied unconditionally -- every player wakes up at full HP, not just
  ones who died) and ``player.dead = false`` (line 5438); ported here as
  ``alive = 1`` for every player.
- **Forest fights**: reset to 15, or ``settings.forest_fights`` if
  configured (lines 5428, 5443-5445) -- ``config["game"]
  ["forest_fights_per_day"]`` here, default 15.
- **Player (PvP) fights**: reset to ``settings.pvp_fights_per_day``
  (line 5432, default 3, reference/lord.js:1856) --
  ``config["game"]["player_fights_per_day"]`` here, default 3.
- **``seen_master``**: reset to false (line 5425).
- **``flirts_today``**: reset to 0 (lord.js's ``player.flirted = false``,
  line 5427).
- **Skill uses**: recomputed daily from the player's own class's skill
  rank (lord.js's ``skillw``/``skillm``/``skillt`` -- this project's
  ``skill_dk``/``skill_my``/``skill_th``, see
  ``pylord/engine/scenes/forest.py``'s module docstring, deviation 3, for
  why those two lord.js concepts are collapsed to one field per class
  here) plus a flat +1 "for being a <class>" bonus
  (reference/lord.js:5448-5469): Death Knight/Thief use
  ``rank // 4 + 1`` (``settings.old_skill_points`` defaults false, so the
  divisor is 4, not 5 -- reference/lord.js:1866); Mystical uses
  ``rank + 1`` (no division at all, line 5454).

Not ported (out of scope for this task, no equivalent field/system here):
the ``player.gone < settings.res_days`` "hasn't abandoned the game"
gate around most of the above (interest/skill-uses apply unconditionally
here instead), ``player.weird``/fairy/horse/spouse/high-spirits/dragon
side effects of waking up. See ``docs/deviations.md``.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from pylord.models import PlayerRepo

_DEFAULT_FOREST_FIGHTS = 15  # reference/lord.js:1857
_DEFAULT_PLAYER_FIGHTS = 3  # reference/lord.js:1856
_BANK_CAP = 2_000_000_000  # reference/lord.js:5507, 5513


def _skill_uses_for(player) -> int:
    """reference/lord.js:5448-5469 -- daily use-point formula for
    whichever class the player actually is (the other two skill_* fields
    are always 0 for a player of a different class, so this only ever
    reads the one that matters)."""
    if player.class_type == 1:  # Death Knight
        return player.skill_dk // 4 + 1
    if player.class_type == 2:  # Mystical
        return player.skill_my + 1
    if player.class_type == 3:  # Thieving
        return player.skill_th // 4 + 1
    return 0


def _set_game_state(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO game_state (key, value) VALUES (:key, :value) "
        "ON CONFLICT(key) DO UPDATE SET value = :value",
        {"key": key, "value": value},
    )


def maintenance(conn: sqlite3.Connection, config: dict[str, Any], today: str) -> None:
    """Run once-per-day global maintenance, idempotently.

    ``today`` is an ISO date string (e.g.
    ``datetime.now(UTC).date().isoformat()`` -- see ``server.py``'s login
    path for the real caller).
    Guarded by the ``game_state`` key ``'last_maint'``: if it already
    equals ``today``, this is a cheap no-op (one SELECT) -- safe to call
    on every login.
    """
    row = conn.execute(
        "SELECT value FROM game_state WHERE key = 'last_maint'"
    ).fetchone()
    if row is not None and row["value"] == today:
        return

    game_cfg = (config or {}).get("game", {})
    forest_fights = game_cfg.get("forest_fights_per_day", _DEFAULT_FOREST_FIGHTS)
    player_fights = game_cfg.get("player_fights_per_day", _DEFAULT_PLAYER_FIGHTS)

    repo = PlayerRepo(conn)

    with conn:
        for player in repo.all_players():
            if player.bank >= _BANK_CAP:  # reference/lord.js:5507-5510
                player.bank = _BANK_CAP
            else:
                player.bank += player.bank // 10  # reference/lord.js:5512
                player.bank = min(player.bank, _BANK_CAP)  # lord.js:5513-5514

            player.hp = player.hp_max  # reference/lord.js:5424
            player.alive = 1  # reference/lord.js:5438 (player.dead = false)

            player.forest_fights = forest_fights  # reference/lord.js:5428, 5443-5445
            player.player_fights = player_fights  # reference/lord.js:5432
            player.flirts_today = 0  # reference/lord.js:5427
            player.seen_master = 0  # reference/lord.js:5425
            player.skill_uses = _skill_uses_for(player)

            repo.save(player)

        day_row = conn.execute(
            "SELECT value FROM game_state WHERE key = 'day'"
        ).fetchone()
        day = int(day_row["value"]) + 1 if day_row is not None else 2
        _set_game_state(conn, "day", str(day))
        _set_game_state(conn, "last_maint", today)
