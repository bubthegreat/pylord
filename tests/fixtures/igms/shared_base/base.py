"""A base class for a plugin split across ``base.py`` + ``igm.py``.

Deliberately leaves ``key``/``name`` unset and does not override
``enter()`` -- it is never meant to be registered on its own, only
subclassed by the concrete IGM in the sibling ``igm.py``. See that
module's docstring for what this fixture proves.
"""

from __future__ import annotations

from pylord.hooks import IGM


class SharedBase(IGM):
    """Shared behaviour a multi-module plugin (e.g. Felicity's Temple)
    could hang off a base class instead of repeating in every screen."""

    author = "pylord tests"

    def greeting(self) -> str:
        return "shared base reached"
