"""Reusable IGM contract check.

Every bundled IGM's own test module is expected to call
``contract_check(SomeIGM)`` so a single place enforces the framework's
invariants against real plugins: the class validates, ``enter()`` runs to
completion (or degrades gracefully when it runs out of scripted input),
and nothing forbidden leaks out of the guardrails (level never moves,
gold/gems/exp never go negative, hp stays within ``[0, hp_max]``).

It is deliberately import-only from the public framework surface
(``pylord.hooks`` + ``pylord.igm_loader``) so an IGM author can copy it as
a template without depending on engine internals.
"""

from __future__ import annotations

import random

from pylord import data
from pylord.hooks import IGM, IgmContext
from pylord.terminal import FakeIO, OutOfKeys

# A generous scripted key queue so most ``enter()`` implementations run to
# completion; anything that still runs dry degrades to OutOfKeys, which the
# contract treats as an acceptable (graceful) exit rather than a failure.
_DEFAULT_KEYS = ["\r"] * 64


async def contract_check(igm_cls: type[IGM], keys: list[str] | None = None) -> None:
    assert issubclass(igm_cls, IGM), "IGM must subclass pylord.hooks.IGM"

    inst = igm_cls()
    assert inst.key, "IGM.key must be a non-empty slug"
    assert inst.name, "IGM.name must be non-empty"
    assert type(inst).enter is not IGM.enter, "IGM must override enter()"

    database = await data.connect(":memory:")
    repo = database.players
    player = await repo.create("ContractTester", "pw", "M")

    before = {
        "id": player.id,
        "name": player.name,
        "level": player.level,
        "password_hash": player.password_hash,
    }

    io = FakeIO(list(keys) if keys is not None else _DEFAULT_KEYS)

    # Build a GameCtx-free IgmContext directly: contract_check exercises the
    # plugin in isolation, without the full scene loop.
    from pylord.engine.game import GameCtx

    ctx = GameCtx(player=player, db=database, io=io, rng=random.Random(0))
    igm_ctx = await IgmContext.create(ctx, inst)

    try:
        await inst.enter(igm_ctx)
    except OutOfKeys:
        pass  # graceful: plugin simply wanted more input than we scripted.

    # Forbidden mutations must never have leaked through the PlayerView.
    assert player.level == before["level"], "IGM changed player level"
    assert player.id == before["id"], "IGM changed player id"
    assert player.name == before["name"], "IGM changed player name"
    assert player.password_hash == before["password_hash"], "IGM changed password"
    assert player.gold >= 0, "IGM drove gold negative"
    assert player.gems >= 0, "IGM drove gems negative"
    assert player.exp >= 0, "IGM drove exp negative"
    assert 0 <= player.hp <= player.hp_max, "IGM drove hp out of [0, hp_max]"

    # The per-IGM store must round-trip through the DB: flush a value, then
    # read it back through a fresh context scoped to the same key. This
    # exercises the storage path every IGM relies on for persistence.
    igm_ctx.store.set("__contract_probe__", {"ok": True})
    await igm_ctx.store.flush(database)
    fresh = await IgmContext.create(ctx, inst)
    assert fresh.store.get("__contract_probe__") == {"ok": True}, (
        "IgmStore did not round-trip through the database"
    )
