"""Fixture for ``IGM.dir``: a plugin that ships its own data file.

The loader gives every plugin its directory, which is how an IGM with
tables or ``.ANS`` screens too big to inline reads them. Relative *imports*
are still impossible (the synthetic module name has no parent package), so
this is the supported way to ship more than one file.

Kept in its own fixture directory so it does not disturb the discovery
tests that assert ``igms/`` contains exactly one enabled plugin.
"""

from __future__ import annotations

from pylord.hooks import IGM


class DataIGM(IGM):
    key = "data_igm"
    name = "Data File Reader"
    author = "pylord tests"
    default_enabled = True

    def greeting(self) -> str:
        assert self.dir is not None, "loader did not set IGM.dir"
        return (self.dir / "data" / "greeting.txt").read_text().strip()

    async def enter(self, ctx) -> None:
        await ctx.term.write(f"\n  {self.greeting()}\n")
