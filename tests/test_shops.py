"""King Arthur's Weapons + Abdul's Armour tests. See
pylord/engine/scenes/shops.py's module docstring for lord.js line-number
citations behind every formula/message ported here.

Follows tests/test_forest.py's established style: ``play(keys)`` for
end-to-end smoke tests through the full town -> shop session, and a local
``await _ctx()`` helper (mirroring test_forest.py's own) to drive individual
private helpers (``_buy_weapon``, ``_sell_weapon``, ...) with a
fully-controlled ``Player`` and RNG for exact-value assertions.
"""

from __future__ import annotations

from pylord import data
from pylord.engine.game import GameCtx
from pylord.engine.scenes import shops as shops_mod
from pylord.terminal import FakeIO
from tests.harness import play, screen


class _SeqRNG:
    """See tests/test_forest.py's identical helper for rationale."""

    def __init__(self, values):
        self._values = list(values)

    def randrange(self, _n):
        return self._values.pop(0)


async def _ctx(overrides=None, rng=None, keys=None, config=None):
    database = await data.connect(":memory:")
    repo = database.players
    player = await repo.create("Hero", "pw", "M")
    for key, value in (overrides or {}).items():
        setattr(player, key, value)
    io = FakeIO(keys or [])
    ctx = GameCtx(player=player, db=database, io=io, config=config)
    if rng is not None:
        ctx.rng = rng
    return ctx


# --- End-to-end smoke test (through the real town -> weapons session) ----


async def test_buy_stick_full_flow_through_town():
    """K -> weapon shop, B -> buy, "1" -> Stick, Y -> confirm, <pause>,
    R -> town, Q -> quit."""
    io, player = await play(
        ["k", "b", "1", "y", "x", "r", "q"], overrides={"weapon_num": 0}
    )
    text = screen(io)
    assert "King Arthur's Weapons" in text
    assert "Stick" in text
    assert player.gold == 500 - 200
    assert player.weapon_num == 1
    assert player.strength == 10 + 5


# --- _buy_weapon() unit tests --------------------------------------------


async def test_buy_stick_decrements_gold_and_sets_weapon():
    ctx = await _ctx(overrides={"weapon_num": 0}, keys=["1", "y", "x"])
    await shops_mod._buy_weapon(ctx)
    assert ctx.player.gold == 500 - 200
    assert ctx.player.weapon_num == 1
    assert ctx.player.strength == 10 + 5


async def test_buy_refused_when_gold_insufficient():
    """Weapon 2 (Dagger, 1000 gold) needs no strength (n < 3), so this
    isolates the gold check: default Player.gold is 500."""
    ctx = await _ctx(overrides={"weapon_num": 0}, keys=["2", "y", "x"])
    await shops_mod._buy_weapon(ctx)
    text = screen(ctx.io)
    assert "You don't have that much gold" in text
    assert ctx.player.gold == 500
    assert ctx.player.weapon_num == 0


async def test_buy_refused_when_strength_insufficient():
    """Weapon 3 (Short Sword) needs str_needed(3) = 10 + LEVEL_STATS[1].str
    = 15 (shop_limit defaults True); a fresh player only has 10."""
    ctx = await _ctx(overrides={"weapon_num": 0}, keys=["3", "y", "x"])
    await shops_mod._buy_weapon(ctx)
    text = screen(ctx.io)
    assert "aren't strong enough to carry" in text
    assert ctx.player.weapon_num == 0
    assert ctx.player.strength == 10


async def test_shop_limit_disabled_skips_strength_gate():
    ctx = await _ctx(
        overrides={"gold": 5000, "weapon_num": 0},
        keys=["3", "y", "x"],
        # GameCtx.config is the [game] table itself -- pylord/server.py
        # passes config["game"] in, so knobs are read flat.
        config={"shop_limit": False},
    )
    await shops_mod._buy_weapon(ctx)
    assert ctx.player.weapon_num == 3
    assert ctx.player.strength == 10 + 20  # Short Sword power


async def test_buying_while_armed_trades_the_old_weapon_in():
    """You can only carry one, so the shop takes the old one in
    part-exchange rather than sending you away to sell it first."""
    ctx = await _ctx(
        overrides={"weapon_num": 1, "strength": 15, "gold": 1_000},
        rng=_SeqRNG([1]),  # pins the trade-in roll: 200 // 2 + 1 = 101
        keys=["2", "y", "x"],
    )
    await shops_mod._buy_weapon(ctx)
    p = ctx.player
    assert p.weapon_num == 2  # Dagger
    assert p.gold == 1_000 + 101 - 1_000
    # Stick's +5 handed back, Dagger's +10 gained.
    assert p.strength == 15 - 5 + 10
    assert "I'll take that Stick" in screen(ctx.io)


async def test_trade_in_counts_toward_the_price():
    """1000 gold short on paper, but the trade-in covers it."""
    ctx = await _ctx(
        overrides={"weapon_num": 1, "strength": 15, "gold": 950},
        rng=_SeqRNG([1]),
        keys=["2", "y", "x"],
    )
    await shops_mod._buy_weapon(ctx)
    assert ctx.player.weapon_num == 2
    assert ctx.player.gold == 950 + 101 - 1_000


async def test_nothing_is_sold_when_you_cannot_afford_the_new_one():
    """The old weapon must survive a refusal -- validate, then trade."""
    ctx = await _ctx(
        overrides={"weapon_num": 1, "strength": 15, "gold": 10},
        rng=_SeqRNG([1]),
        keys=["2", "y", "x"],
    )
    await shops_mod._buy_weapon(ctx)
    p = ctx.player
    assert (p.weapon_num, p.gold, p.strength) == (1, 10, 15)
    assert "don't have that much gold" in screen(ctx.io)


async def test_nothing_is_sold_when_you_cannot_wield_the_new_one():
    """Strength is judged *without* the old weapon's bonus, since you are
    handing it over -- and a refusal leaves you holding it."""
    ctx = await _ctx(
        overrides={"weapon_num": 1, "strength": 15, "gold": 100_000},
        rng=_SeqRNG([1]),
        keys=["3", "y", "x"],  # Short Sword needs 15 bare strength; we have 10
    )
    await shops_mod._buy_weapon(ctx)
    p = ctx.player
    assert (p.weapon_num, p.strength) == (1, 15)
    assert p.gold == 100_000
    assert "aren't strong enough" in screen(ctx.io)


async def test_buy_declined_at_confirm_prompt_changes_nothing():
    ctx = await _ctx(overrides={"weapon_num": 0}, keys=["1", "n", "x"])
    await shops_mod._buy_weapon(ctx)
    assert ctx.player.weapon_num == 0
    assert ctx.player.gold == 500


async def test_buy_zero_or_out_of_range_silently_cancels():
    """``n == 0`` (or out of 1..15) is lord.js's own "cancel" shortcut --
    no message at all, no state change, and no extra keys consumed
    (nothing left in the queue after the item-number prompt)."""
    ctx = await _ctx(overrides={"weapon_num": 0}, keys=["0"])
    await shops_mod._buy_weapon(ctx)
    assert ctx.player.weapon_num == 0
    assert ctx.player.gold == 500


# --- _sell_weapon() -- exact resale rate ----------------------------------


async def test_sell_weapon_exact_price_and_stat_rollback():
    """level=1, charm=1 (defaults) -> mult=1, weapon branch rolls
    random(1); ``_SeqRNG([1])`` pins that roll to 1 regardless of ``n``.
    price = 200 // 2 + 1 = 101 (well under the price-cap clause)."""
    ctx = await _ctx(
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
    ctx = await _ctx(overrides={"weapon_num": 0}, keys=["x"])
    await shops_mod._sell_weapon(ctx)
    text = screen(ctx.io)
    assert "don't have" in text
    assert ctx.player.gold == 500


async def test_sell_weapon_gold_cap_shows_lot_of_money_flavor():
    """Post-review Minor 2: reference/lord.js:10099-10103. gold starts 50
    under the 2,000,000,000 cap; selling for 101 (same pinned roll as
    ``test_sell_weapon_exact_price_and_stat_rollback``) pushes it over."""
    ctx = await _ctx(
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
    ctx = await _ctx(overrides={"armor_num": 0}, keys=["1", "y", "x"])
    await shops_mod._buy_armor(ctx)
    assert ctx.player.gold == 500 - 200
    assert ctx.player.armor_num == 1
    assert ctx.player.defense == 3 + 3  # model default (bare) + Coat's power


async def test_buy_armor_refused_when_gold_insufficient():
    ctx = await _ctx(
        overrides={"armor_num": 0}, keys=["2", "y", "x"]
    )  # Heavy Coat, 1000 gold, no def gate
    await shops_mod._buy_armor(ctx)
    text = screen(ctx.io)
    assert "lacking funds" in text
    assert ctx.player.gold == 500
    assert ctx.player.armor_num == 0


async def test_sell_armor_exact_price_and_stat_rollback():
    """level=1, charm=1 -> mult=1, armor branch (inclusive 0<=mult<=65530)
    also rolls random(1); pinned to 1. price = 200 // 2 + 1 = 101."""
    ctx = await _ctx(
        overrides={"armor_num": 1, "defense": 10},
        rng=_SeqRNG([1]),
        keys=["y", "x"],
    )
    await shops_mod._sell_armor(ctx)
    text = screen(ctx.io)
    assert "101" in text
    assert ctx.player.armor_num == 0
    assert ctx.player.gold == 500 + 101
    assert ctx.player.defense == 7


async def test_sell_armor_gold_cap_shows_lot_of_money_flavor():
    """Post-review Minor 2: reference/lord.js:10494-10498."""
    ctx = await _ctx(
        overrides={"armor_num": 1, "defense": 10, "gold": 2_000_000_000 - 50},
        rng=_SeqRNG([1]),
        keys=["y", "x"],
    )
    await shops_mod._sell_armor(ctx)
    text = screen(ctx.io)
    assert "Wow, you have a lot of money!" in text
    assert ctx.player.gold == 2_000_000_000


async def test_sell_armor_with_nothing_equipped_refused():
    ctx = await _ctx(overrides={"armor_num": 0}, keys=["x"])
    await shops_mod._sell_armor(ctx)
    text = screen(ctx.io)
    assert "don't have" in text
    assert ctx.player.gold == 500
