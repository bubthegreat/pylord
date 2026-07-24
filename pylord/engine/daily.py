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
- **``seen_violet``/``seen_bard``**: reset to 0/false (lines 5437, 5429) --
  the once-a-day gates for the Inn's Violet/Seth Able flirt chain and bard
  song (``pylord/engine/scenes/inn.py``).
- **``seen_dragon``**: reset to false (line 5436) -- without this the
  Dragon is a once-per-*character* event rather than once per day.
- **Kids/horse forest-fight bonuses**: ``forest_fights += kids``
  (lines 5490-5505) and ``+= forest_fights / 4`` while mounted
  (lines 5575-5582), both capped at 32,000.
- **``high_spirits``**: ``random(3) + 1 > 1`` (lines 5565-5573) -- the
  gate on the forest's JENNIE codeword.
- **``weird``**: ``random(5) === 1`` (lines 5433-5435) -- the gate on the
  forest's "weird event" gem find.
- **Pregnancy**: the ``have_baby()`` trigger (lines 5595-5597); see
  ``_pregnancy`` for what this batch pass keeps of lord.js's interactive
  birth scene.
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

Each player's reset is guarded on ``last_played != today`` so a session
that was already open when the day rolled over can't revert another
connection's reset when it saves on disconnect.

Not ported (no equivalent field/system here): the
``player.gone < settings.res_days`` "hasn't abandoned the game" gate
around most of the above (interest/skill-uses apply unconditionally
instead), and the spouse/marriage side effects of waking up. See
``docs/deviations.md``.
"""

from __future__ import annotations

import random as _random_module
import sqlite3
from typing import Any

from pylord.engine.persist import save_player_raw
from pylord.models import PlayerRepo

_DEFAULT_FOREST_FIGHTS = 15  # reference/lord.js:1857
_DEFAULT_PLAYER_FIGHTS = 3  # reference/lord.js:1856
_BANK_CAP = 2_000_000_000  # reference/lord.js:5507, 5513
_STAT_CAP = 32_000  # reference/lord.js:5499-5501, 5578-5583


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


def _pregnancy(player, rng) -> str | None:
    """Port of ``wake_up()``'s pregnancy trigger + ``have_baby()``.
    reference/lord.js:5595-5597 (the roll) and :5180-5312 (the outcome).

    lord.js runs ``have_baby()`` inline during a login, so it can narrate
    the birth over several ``more()`` prompts; this project's maintenance
    is a terminal-less batch pass (see the module docstring), so only the
    mechanical outcome happens here and the news line stands in for the
    prose. Returns a news line, or ``None`` when nothing happened.
    """
    if player.gender != "F":
        return None
    if rng.randrange(34) + 1 != 11:  # reference/lord.js:5595
        return None
    if player.lays * 5 <= player.kids:  # reference/lord.js:5595
        return None
    if rng.randrange(20) + 1 == 20:  # reference/lord.js:5215, stillborn
        return f"  `0{player.name} `2is grief stricken over a great loss."
    player.kids = min(player.kids + 1, _STAT_CAP)  # reference/lord.js:5245
    child = "boy" if rng.randrange(2) == 0 else "girl"
    return f"  `0{player.name} `2gives birth to a {child}!"


def maintenance(
    conn: sqlite3.Connection,
    config: dict[str, Any],
    today: str,
    igms=None,
    rng: _random_module.Random | None = None,
) -> None:
    """Run once-per-day global maintenance, idempotently.

    ``today`` is an ISO date string (e.g.
    ``datetime.now(UTC).date().isoformat()`` -- see ``server.py``'s login
    path for the real caller).
    Guarded by the ``game_state`` key ``'last_maint'``: if it already
    equals ``today``, this is a cheap no-op (one SELECT) -- safe to call
    on every login.

    ``igms`` (an optional IgmRegistry) runs each enabled plugin's
    ``daily_maint`` hook *after* the core per-player pass has committed;
    each plugin's failure is contained (see
    ``IgmRegistry.run_daily_maint``), so a bad IGM can't abort the daily
    reset.
    """
    row = conn.execute(
        "SELECT value FROM game_state WHERE key = 'last_maint'"
    ).fetchone()
    if row is not None and row["value"] == today:
        return

    game_cfg = (config or {}).get("game", {})
    forest_fights = game_cfg.get("forest_fights_per_day", _DEFAULT_FOREST_FIGHTS)
    player_fights = game_cfg.get("player_fights_per_day", _DEFAULT_PLAYER_FIGHTS)
    rng = _random_module.Random() if rng is None else rng

    repo = PlayerRepo(conn)
    news: list[str] = []

    # One transaction for the whole pass. Every write below goes through
    # save_player_raw (pylord/engine/persist.py) rather than
    # PlayerRepo.save, which opens a ``with self.conn`` block of its own --
    # sqlite3 connections are not re-entrant context managers, so the
    # nested commit would end this transaction early and a failure
    # mid-pass could re-apply bank interest to everyone on the retry.
    with conn:
        for player in repo.all_players():
            if player.last_played == today:
                # Already reset today by an earlier pass (or by a session
                # that spanned the rollover) -- don't pay interest twice.
                continue

            if player.bank >= _BANK_CAP:  # reference/lord.js:5507-5510
                player.bank = _BANK_CAP
            else:
                player.bank += player.bank // 10  # reference/lord.js:5512
                player.bank = min(player.bank, _BANK_CAP)  # lord.js:5513-5514

            player.hp = player.hp_max  # reference/lord.js:5424
            player.alive = 1  # reference/lord.js:5438 (player.dead = false)

            player.forest_fights = forest_fights  # reference/lord.js:5428, 5443-5445
            if player.kids:  # reference/lord.js:5490-5505
                player.forest_fights = min(
                    player.forest_fights + player.kids, _STAT_CAP
                )
            if player.horse:  # reference/lord.js:5575-5582
                player.forest_fights = min(
                    player.forest_fights + player.forest_fights // 4, _STAT_CAP
                )
            player.player_fights = player_fights  # reference/lord.js:5432
            player.flirts_today = 0  # reference/lord.js:5427
            player.seen_master = 0  # reference/lord.js:5425
            player.seen_dragon = 0  # reference/lord.js:5436
            player.seen_violet = 0  # reference/lord.js:5437
            player.seen_bard = 0  # reference/lord.js:5429
            player.skill_uses = _skill_uses_for(player)
            # 2-in-3 chance of high spirits, which is what unlocks the
            # forest's JENNIE codeword (reference/lord.js:5565-5573).
            player.high_spirits = 1 if rng.randrange(3) + 1 > 1 else 0
            # 1-in-5 chance of the forest's "weird event" gem find
            # (reference/lord.js:5433-5435).
            player.weird = 1 if rng.randrange(5) == 1 else 0

            born = _pregnancy(player, rng)
            if born is not None:
                news.append(born)

            player.last_played = today

            save_player_raw(conn, player)

        day_row = conn.execute(
            "SELECT value FROM game_state WHERE key = 'day'"
        ).fetchone()
        day = int(day_row["value"]) + 1 if day_row is not None else 2
        _set_game_state(conn, "day", str(day))
        _set_game_state(conn, "last_maint", today)
        for line in news:
            conn.execute(
                "INSERT INTO daily_news (day, text) VALUES (?, ?)", (str(day), line)
            )

    # After the core reset has committed, let enabled IGMs run their own
    # daily hook (each contained; see IgmRegistry.run_daily_maint).
    if igms is not None:
        igms.run_daily_maint(conn, config)
