"""Import every scene module so ``@scene(...)`` registration runs.

Anything that needs the full ``SCENES`` registry populated (the telnet
server entrypoint, tests/harness.py) should ``import pylord.engine.scenes``
before calling ``run_session``.
"""

from pylord.engine.scenes import (
    bank,
    conjugality,
    dragon,
    forest,
    hall,
    healer,
    inn,
    jennie,
    list_warriors,
    mail,
    news,
    other_places,
    pvp,
    shops,
    stats,
    town,
    town_extras,
    training,
)

__all__ = [
    "bank",
    "conjugality",
    "dragon",
    "forest",
    "hall",
    "healer",
    "inn",
    "jennie",
    "list_warriors",
    "mail",
    "news",
    "other_places",
    "pvp",
    "shops",
    "stats",
    "town",
    "town_extras",
    "training",
]
