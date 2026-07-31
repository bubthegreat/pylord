"""Fixture for ``IGM.dir``: a plugin that ships its own data file.

The loader gives every plugin its directory, which is how an IGM with
tables or ``.ANS`` screens too big to inline reads them -- for
non-Python files. A plugin can *also* split its Python across modules and
import between them, relatively or absolutely; see
``tests/fixtures/igms/multi_module/`` for that.

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
