"""Forest-fight capacity and real-time regeneration.

**Both mechanics here are deliberate departures from lord.js**, added for a
persistent server where players drop in and out through the day rather than
calling a BBS once. See ``docs/deviations.md``; every other number in the
engine is a port, these two are ours.

**Capacity.** lord.js hands every player the same flat allowance each
morning (``settings.forest_fights``, reference/lord.js:5428/5443-5445). Here
that allowance is a *floor*: a player's maximum is

    forest_fights_per_day  +  fight_bonus  (+ kids, + horse, at daily reset)

and ``fight_bonus`` is earned two ways -- one free point every time you beat
your master (so the cap tracks progression), and as many extra as you care
to buy from Turgon's endurance training, each costing more than the last.
Both survive the Dragon reset, like the class skill ranks do.

**Regeneration.** lord.js's allowance only refills at the daily rollover.
Here one fight comes back every ``fight_regen_minutes`` of real time (15 by
default; 0 disables), up to the player's maximum -- so someone who burns
their fights at breakfast has a few again by lunch.

The clock lives on the player (``fights_regen_at``) rather than in memory,
so it keeps running while they're logged off, and it advances in whole
intervals so partial progress is never rounded away. A player at or over
their maximum banks nothing: their clock resets to now, so the first fight
after a spending spree is always a full interval away.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pylord.models import Player

DEFAULT_REGEN_MINUTES = 15
DEFAULT_FOREST_FIGHTS = 15  # reference/lord.js:1857, the base allowance
#: What the first bought endurance point costs; each one after costs another
#: multiple of this (2x, 3x, ...), scaled by the buyer's level.
DEFAULT_ENDURANCE_COST = 1_000
STAT_CAP = 32_000  # reference/lord.js:16617-16621


def max_forest_fights(player: Player, config: dict[str, Any] | None = None) -> int:
    """The player's current ceiling: the configured daily allowance plus
    everything they have trained."""
    base = (config or {}).get("forest_fights_per_day", DEFAULT_FOREST_FIGHTS)
    return min(base + max(0, player.fight_bonus), STAT_CAP)


def endurance_cost(player: Player, config: dict[str, Any] | None = None) -> int:
    """Price of the *next* bought point: ``base x (bought + 1) x level``.

    Only purchases count toward the multiplier -- the free point a master
    hands out on a win doesn't make the next one dearer.
    """
    base = (config or {}).get("endurance_cost", DEFAULT_ENDURANCE_COST)
    return base * (player.endurance_bought + 1) * max(1, player.level)


def grant_bonus(player: Player, amount: int = 1) -> None:
    """Raise the ceiling permanently (a master win, or a purchase)."""
    player.fight_bonus = min(max(0, player.fight_bonus + amount), STAT_CAP)


def regen_minutes(config: dict[str, Any] | None = None) -> int:
    return (config or {}).get("fight_regen_minutes", DEFAULT_REGEN_MINUTES)


def _parse(stamp: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def apply_regen(
    player: Player,
    config: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> int:
    """Credit any fights the passage of real time has earned.

    Returns how many were added (0 if none, or if regeneration is off).
    Safe to call as often as you like -- it is driven entirely by the
    stored clock, so extra calls simply find nothing to grant.
    """
    minutes = regen_minutes(config)
    now = datetime.now(UTC) if now is None else now
    if minutes <= 0:
        player.fights_regen_at = now.isoformat()
        return 0

    interval = timedelta(minutes=minutes)
    last = _parse(player.fights_regen_at)
    ceiling = max_forest_fights(player, config)

    # No clock yet (a fresh character, or the column's first day), or the
    # player is already topped up: start counting from now.
    if last is None or player.forest_fights >= ceiling:
        player.fights_regen_at = now.isoformat()
        return 0

    elapsed = now - last
    if elapsed < interval:
        return 0

    earned = int(elapsed // interval)
    before = player.forest_fights
    player.forest_fights = min(before + earned, ceiling)
    gained = player.forest_fights - before

    if player.forest_fights >= ceiling:
        # Topped up -- don't bank the leftover time.
        player.fights_regen_at = now.isoformat()
    else:
        # Advance by whole intervals so the remainder carries forward.
        player.fights_regen_at = (last + interval * earned).isoformat()
    return gained
