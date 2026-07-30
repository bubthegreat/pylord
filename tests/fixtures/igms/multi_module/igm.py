"""Fixture: a plugin split across two modules.

Relative and absolute intra-plugin imports both have to resolve. Under the
old loader neither did: ``igm.py`` was executed under a synthetic module
name with no parent package, so a relative import had nothing to resolve
against and the absolute name pointed at a package that was never imported.
"""

from __future__ import annotations

from pylord.hooks import IGM
from tests.fixtures.igms.multi_module import helpers as absolute_helpers

from . import helpers as relative_helpers


class MultiModule(IGM):
    key = "multi_module"
    name = "Multi Module"
    default_enabled = True

    def proof(self) -> tuple[str, str]:
        """Both import styles reached the same module."""
        return (relative_helpers.GREETING, absolute_helpers.shout("ok"))

    async def enter(self, ctx) -> None:
        await ctx.term.write(f"\n  {relative_helpers.GREETING}\n")
