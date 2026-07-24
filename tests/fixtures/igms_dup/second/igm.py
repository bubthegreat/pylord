from __future__ import annotations

from pylord.hooks import IGM


class SecondDup(IGM):
    key = "dup"
    name = "Second Dup"
    default_enabled = True

    async def enter(self, ctx) -> None:
        await ctx.term.write("second")
