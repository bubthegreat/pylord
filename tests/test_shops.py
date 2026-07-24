"""King Arthur's Weapons + Abdul's Armour tests. See
pylord/engine/scenes/shops.py's module docstring for lord.js line-number
citations behind every formula/message ported here.

Follows tests/test_forest.py's established style: ``play(keys)`` for
end-to-end smoke tests through the full town -> shop session, and a local
``_ctx()`` helper (mirroring test_forest.py's own) to drive individual
private helpers (``_buy_weapon``, ``_sell_weapon``, ...) with a
fully-controlled ``Player`` and RNG for exact-value assertions.
"""

from __future__ import annotations

from pylord import db
from pylord.engine.game import GameCtx
from pylord.engine.scenes import shops as shops_mod
from pylord.models import PlayerRepo
from pylord.terminal import FakeIO
from tests.harness import play, screen


class _SeqRNG:
    """See tests/test_forest.py's identical helper for rationale."""

    def __init__(self, values):
        self._values = list(values)

    def randrange(self, _n):
        return self._values.pop(0)


def _ctx(overrides=None, rng=None, keys=None, config=None):
    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)
    player = repo.create("Hero", "pw", "M")
    for key, value in (overrides or {}).items():
        setattr(player, key, value)
    io = FakeIO(keys or [])
    ctx = GameCtx(player=player, repo=repo, io=io, conn=conn, config=config)
    if rng is not None:
        ctx.rng = rng
    return ctx


# --- End-to-end smoke test (through the real town -> weapons session) ----


async def test_buy_stick_full_flow_through_town():
    """K -> weapon shop, B -> buy, "1" -> Stick, Y -> confirm, <pause>,
    R -> town, Q -> quit."""
    io, player = await play(["k", "b", "1", "y", "x", "r", "q"])
    text = screen(io)
    assert "King Arthur's Weapons" in text
    assert "Stick" in text
    assert player.gold == 500 - 200
    assert player.weapon_num == 1
    assert player.strength == 10 + 5


# --- _buy_weapon() unit tests --------------------------------------------


async def test_buy_stick_decrements_gold_and_sets_weapon():
    ctx = _ctx(keys=["1", "y", "x"])
    await shops_mod._buy_weapon(ctx)
    assert ctx.player.gold == 500 - 200
    assert ctx.player.weapon_num == 1
    assert ctx.player.strength == 10 + 5


async def test_buy_refused_when_gold_insufficient():
    """Weapon 2 (Dagger, 1000 gold) needs no strength (n < 3), so this
    isolates the gold check: default Player.gold is 500."""
    ctx = _ctx(keys=["2", "y", "x"])
    await shops_mod._buy_weapon(ctx)
    text = screen(ctx.io)
    assert "You don't have that much gold" in text
    assert ctx.player.gold == 500
    assert ctx.player.weapon_num == 0


async def test_buy_refused_when_strength_insufficient():
    """Weapon 3 (Short Sword) needs str_needed(3) = 10 + LEVEL_STATS[1].str
    = 15 (shop_limit defaults True); a fresh player only has 10."""
    ctx = _ctx(keys=["3", "y", "x"])
    await shops_mod._buy_weapon(ctx)
    text = screen(ctx.io)
    assert "aren't strong enough to carry" in text
    assert ctx.player.weapon_num == 0
    assert ctx.player.strength == 10


async def test_shop_limit_disabled_skips_strength_gate():
    ctx = _ctx(
        overrides={"gold": 5000},
        keys=["3", "y", "x"],
        config={"game": {"shop_limit": False}},
    )
    await shops_mod._buy_weapon(ctx)
    assert ctx.player.weapon_num == 3
    assert ctx.player.strength == 10 + 20  # Short Sword power


async def test_buy_refused_when_already_armed():
    ctx = _ctx(overrides={"weapon_num": 1, "strength": 15}, keys=["2", "y", "x"])
    await shops_mod._buy_weapon(ctx)
    text = screen(ctx.io)
    assert "already have a weapon" in text
    assert ctx.player.weapon_num == 1


async def test_buy_declined_at_confirm_prompt_changes_nothing():
    ctx = _ctx(keys=["1", "n", "x"])
    await shops_mod._buy_weapon(ctx)
    assert ctx.player.weapon_num == 0
    assert ctx.player.gold == 500


async def test_buy_zero_or_out_of_range_silently_cancels():
    """``n == 0`` (or out of 1..15) is lord.js's own "cancel" shortcut --
    no message at all, no state change, and no extra keys consumed
    (nothing left in the queue after the item-number prompt)."""
    ctx = _ctx(keys=["0"])
    await shops_mod._buy_weapon(ctx)
    assert ctx.player.weapon_num == 0
    assert ctx.player.gold == 500


# --- _sell_weapon() -- exact resale rate ----------------------------------


async def test_sell_weapon_exact_price_and_stat_rollback():
    """level=1, charm=2 (defaults) -> mult=2, weapon branch rolls
    random(2); ``_SeqRNG([1])`` pins that roll to 1 regardless of ``n``.
    price = 200 // 2 + 1 = 101 (well under the price-cap clause)."""
    ctx = _ctx(
        overrides={"weapon_num": 1, "strength": 15},
        rng=_SeqRNG([1]),
        keys=["y", "x"],
    )
    await shops_mod._sell_weapon(ctx)
    text = screen(ctx.io)
    assert "101" in text
    assert ctx.player.weapon_num == 0
    assert ctx.player.gold == 500 + 101
    assert ctx.player.strength == 15 - 5


async def test_sell_weapon_with_nothing_equipped_refused():
    ctx = _ctx(keys=["x"])
    await shops_mod._sell_weapon(ctx)
    text = screen(ctx.io)
    assert "don't have" in text
    assert ctx.player.gold == 500


async def test_sell_weapon_gold_cap_shows_lot_of_money_flavor():
    """Post-review Minor 2: reference/lord.js:10099-10103. gold starts 50
    under the 2,000,000,000 cap; selling for 101 (same pinned roll as
    ``test_sell_weapon_exact_price_and_stat_rollback``) pushes it over."""
    ctx = _ctx(
        overrides={"weapon_num": 1, "strength": 15, "gold": 2_000_000_000 - 50},
        rng=_SeqRNG([1]),
        keys=["y", "x"],
    )
    await shops_mod._sell_weapon(ctx)
    text = screen(ctx.io)
    assert "Wow, you have a lot of money!" in text
    assert ctx.player.gold == 2_000_000_000


# --- Armor: buy/sell mirror the weapon tests ------------------------------


async def test_buy_coat_decrements_gold_and_sets_armor():
    ctx = _ctx(keys=["1", "y", "x"])
    await shops_mod._buy_armor(ctx)
    assert ctx.player.gold == 500 - 200
    assert ctx.player.armor_num == 1
    assert ctx.player.defense == 1 + 1


async def test_buy_armor_refused_when_gold_insufficient():
    ctx = _ctx(keys=["2", "y", "x"])  # Heavy Coat, 1000 gold, no def gate
    await shops_mod._buy_armor(ctx)
    text = screen(ctx.io)
    assert "lacking funds" in text
    assert ctx.player.gold == 500
    assert ctx.player.armor_num == 0


async def test_sell_armor_exact_price_and_stat_rollback():
    """level=1, charm=2 -> mult=2, armor branch (inclusive 0<=mult<=65530)
    also rolls random(2); pinned to 1. price = 200 // 2 + 1 = 101."""
    ctx = _ctx(
        overrides={"armor_num": 1, "defense": 2},
        rng=_SeqRNG([1]),
        keys=["y", "x"],
    )
    await shops_mod._sell_armor(ctx)
    text = screen(ctx.io)
    assert "101" in text
    assert ctx.player.armor_num == 0
    assert ctx.player.gold == 500 + 101
    assert ctx.player.defense == 2 - 1


async def test_sell_armor_gold_cap_shows_lot_of_money_flavor():
    """Post-review Minor 2: reference/lord.js:10494-10498."""
    ctx = _ctx(
        overrides={"armor_num": 1, "defense": 2, "gold": 2_000_000_000 - 50},
        rng=_SeqRNG([1]),
        keys=["y", "x"],
    )
    await shops_mod._sell_armor(ctx)
    text = screen(ctx.io)
    assert "Wow, you have a lot of money!" in text
    assert ctx.player.gold == 2_000_000_000


async def test_sell_armor_with_nothing_equipped_refused():
    ctx = _ctx(keys=["x"])
    await shops_mod._sell_armor(ctx)
    text = screen(ctx.io)
    assert "don't have" in text
    assert ctx.player.gold == 500
