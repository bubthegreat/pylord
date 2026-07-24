from __future__ import annotations

from pylord.hooks import IGM


class FirstDup(IGM):
    key = "dup"
    name = "First Dup"
    default_enabled = True

    async def enter(self, ctx) -> None:
        await ctx.term.write("first")
