"""Fixture: a plugin whose registered class subclasses a base class defined
in a sibling module (``base.py``), imported into this one.

This is the shape the loader's subclass scan used to break on: it walked
``vars(module).values()``, which includes *imported* names, so importing
``SharedBase`` here made it a second candidate alongside ``SharedIGM``
below -- "expected exactly one IGM subclass, found 2" -- and the plugin
was skipped even though only one class is actually defined in this
module. The fix filters candidates to ``obj.__module__ == module.__name__``,
so only ``SharedIGM`` is registered; ``SharedBase`` is just a base class.

This is exactly the shape a large multi-module plugin (Felicity's Temple,
a future port) wants: shared logic in one file, subclassed per screen.
"""

from __future__ import annotations

from .base import SharedBase


class SharedIGM(SharedBase):
    key = "shared_base"
    name = "Shared Base"
    default_enabled = True

    async def enter(self, ctx) -> None:
        await ctx.term.write(f"\n  {self.greeting()}\n")
