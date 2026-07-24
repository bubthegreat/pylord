"""A minimal, well-formed IGM used as the happy-path discovery fixture.

Exercises the guardrailed surface an IGM actually gets: a player mutation
(gold), a persistent store write, buffered news, and terminal output --
all without reading any input, so ``contract_check`` can run ``enter()``
to completion against a scripted ``FakeIO`` with an empty key queue.
"""

from __future__ import annotations

from pylord.hooks import IGM


class SampleIGM(IGM):
    key = "sample"
    name = "Sample Adventure"
    author = "pylord tests"
    default_enabled = True

    async def enter(self, ctx) -> None:
        await ctx.term.write("\n  You wander into the Sample Adventure.\n")
        visits = ctx.store.get("visits", 0) + 1
        ctx.store.set("visits", visits)
        ctx.player.gold += 10
        ctx.news(f"`0Someone visited the Sample Adventure ({visits} times).")
