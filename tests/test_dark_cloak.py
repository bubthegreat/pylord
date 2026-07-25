"""The Dark Cloak Tavern (pylord/engine/scenes/dark_cloak.py).

A port of lord.js's ``darkhorse_tavern()``, so the tests pin the things a
port gets wrong: the odds on each bet, the two-games-per-visit rule, what
Chance charges, and the fact that the old man's memory of a player is
written by that player and read by everyone.
"""

from __future__ import annotations

from pylord import data
from pylord.engine.game import GameCtx
from pylord.engine.scenes import dark_cloak as tavern
from pylord.terminal import FakeIO
from tests.harness import screen


class _SeqRNG:
    """See tests/test_forest.py's identical helper for rationale."""

    def __init__(self, values):
        self._values = list(values)

    def randrange(self, _n=None):
        return self._values.pop(0)


async def _ctx(keys=None, rng=None, database=None, name="Hero", **overrides):
    if database is None:
        database = await data.connect(":memory:")
    player = await database.players.create(name, "pw", "M")
    for key, value in overrides.items():
        setattr(player, key, value)
    await database.players.save(player)
    ctx = GameCtx(player=player, db=database, io=FakeIO(list(keys or [])))
    if rng is not None:
        ctx.rng = rng
    return ctx, database


# --- the bets ------------------------------------------------------------


async def test_the_old_man_guesses_wrong_and_pays_out():
    """lord.js:12340-12349. He only guesses right when the roll is 55 or
    under -- lord.js's own port marks the original, where he always won,
    as a bug."""
    # your number, then his roll (>55 -> he misses), then his wrong guess
    ctx, _db = await _ctx(keys=["", "500", ""], rng=_SeqRNG([41, 90, 7]), gold=1000)
    await tavern._guess_the_number(ctx)
    assert ctx.player.gold == 1500
    assert "grudgingly gives" in screen(ctx.io)


async def test_the_old_man_guesses_right_and_takes_the_gold():
    ctx, _db = await _ctx(keys=["", "500", ""], rng=_SeqRNG([41, 20]), gold=1000)
    await tavern._guess_the_number(ctx)
    assert ctx.player.gold == 500
    assert "dances a jig" in screen(ctx.io)


async def test_betting_nothing_backs_out_without_playing():
    ctx, _db = await _ctx(keys=["", "0"], rng=_SeqRNG([41]), gold=1000)
    await tavern._guess_the_number(ctx)
    assert ctx.player.gold == 1000
    assert "laughs in your face" in screen(ctx.io)


async def test_you_cannot_bet_gold_you_do_not_have():
    """lord.js:12279-12283 re-asks rather than accepting it."""
    ctx, _db = await _ctx(
        keys=["", "99999", "100", ""], rng=_SeqRNG([41, 90, 7]), gold=100
    )
    await tavern._guess_the_number(ctx)
    assert "NOT a good idea" in screen(ctx.io)
    assert ctx.player.gold == 200


async def test_the_mug_game_pays_above_forty_five():
    ctx, _db = await _ctx(keys=["", "200", "", ""], rng=_SeqRNG([0, 46]), gold=1000)
    await tavern._which_mug(ctx)
    assert ctx.player.gold == 1200
    assert "WOODEN TEETH" in screen(ctx.io)


async def test_the_mug_game_takes_at_or_below_forty_five():
    ctx, _db = await _ctx(keys=["", "200", "", ""], rng=_SeqRNG([0, 44]), gold=1000)
    await tavern._which_mug(ctx)
    assert ctx.player.gold == 800
    assert "STALE BEER" in screen(ctx.io)


async def test_the_dagger_throw_pays_above_forty_four():
    ctx, _db = await _ctx(keys=["", "300", "", ""], rng=_SeqRNG([45]), gold=1000)
    await tavern._knock_the_mug(ctx)
    assert ctx.player.gold == 1300
    assert "HIGH AND DRY" in screen(ctx.io)


async def test_winnings_cannot_exceed_the_gold_ceiling():
    """Every payout in lord.js clamps at 2,000,000,000 (:12365)."""
    ctx, _db = await _ctx(
        keys=["", "1000000000", "", ""], rng=_SeqRNG([45]), gold=2_000_000_000
    )
    await tavern._knock_the_mug(ctx)
    assert ctx.player.gold == 2_000_000_000


# --- the two-games rule --------------------------------------------------


async def test_the_third_game_in_one_visit_is_refused():
    """lord.js:12298-12310 -- and the fourth adds the joke about honor."""
    ctx, _db = await _ctx(gold=1000)

    played = await tavern._gamble(ctx, played=2)
    text = screen(ctx.io)
    assert "No one seems too thrilled" in text
    assert "word honor" not in text
    assert played == 3

    ctx.io.output.clear()
    await tavern._gamble(ctx, played=played)
    assert "word honor" in screen(ctx.io)


# --- Chance --------------------------------------------------------------


async def test_chance_wants_two_gems_and_says_so_when_you_are_short():
    ctx, database = await _ctx(keys=["L", "Rival", "Y", "R"], gems=1)
    await database.players.create("Rival", "pw", "F")

    await tavern._chance(ctx)

    text = screen(ctx.io)
    assert "two Gems" in text
    assert "Not having two" in text
    assert ctx.player.gems == 1


async def test_chance_sells_the_dossier_for_two_gems():
    ctx, database = await _ctx(keys=["L", "Rival", "Y", "Y", "", "", "R"], gems=5)
    rival = await database.players.create("Rival", "pw", "F")
    rival.strength, rival.defense, rival.gold, rival.bank = 250, 90, 700, 300
    rival.gems, rival.kids, rival.charm = 4, 2, 60
    await database.players.save(rival)

    await tavern._chance(ctx)

    text = screen(ctx.io)
    assert ctx.player.gems == 3
    assert "total Strength of 250" in text
    assert "total Defense of 90" in text
    assert "Total worth in gold is 1,000" in text  # gold + bank
    assert "very good looking woman" in text  # charm 60, her gender not yours
    assert "2 offspring" in text


async def test_chance_will_not_sell_you_yourself():
    ctx, _db = await _ctx(keys=["L", "Hero", "Y", "R"], gems=5)
    await tavern._chance(ctx)
    assert "favorite customer" in screen(ctx.io)
    assert ctx.player.gems == 5


# --- the old man's memory ------------------------------------------------


async def test_you_write_the_two_lines_the_realm_remembers():
    ctx, _db = await _ctx(keys=["E", "Slayer of rats.", "Feared by none.", "R"])

    await tavern._old_man(ctx)

    assert ctx.player.description1 == "Slayer of rats."
    assert ctx.player.description2 == "Feared by none."
    assert "It has been noted" in screen(ctx.io)


async def test_the_old_man_repeats_what_someone_wrote_about_themselves():
    ctx, database = await _ctx(keys=["V", "Rival", "Y", "R"])
    rival = await database.players.create("Rival", "pw", "F")
    rival.description1 = "Bathes in dragon blood."
    rival.description2 = "Owes me money."
    await database.players.save(rival)

    await tavern._old_man(ctx)

    text = screen(ctx.io)
    assert "Bathes in dragon blood." in text
    assert "Owes me money." in text


async def test_the_old_man_has_heard_nothing_about_a_silent_player():
    ctx, database = await _ctx(keys=["V", "Rival", "Y", "R"])
    await database.players.create("Rival", "pw", "F")

    await tavern._old_man(ctx)

    assert "haven't heard anything about her" in screen(ctx.io)


# --- the conversation wall ----------------------------------------------


async def test_the_bar_starts_quiet_and_remembers_what_is_said():
    ctx, database = await _ctx(keys=["A", "The dragon is a liar."])
    await tavern._conversation(ctx)
    assert "The bar is quiet" in screen(ctx.io)

    # A second drinker, in the same realm, sees what the first said.
    ctx2, _ = await _ctx(keys=["C"], database=database, name="Other")
    await tavern._conversation(ctx2)
    text = screen(ctx2.io)
    assert "The dragon is a liar." in text
    assert "Hero" in text


async def test_a_grunt_is_not_worth_recording():
    """lord.js:8525-8528 -- under two characters and nothing is entered."""
    ctx, database = await _ctx(keys=["A", "x"])
    await tavern._conversation(ctx)
    assert "ENTRY NOT ENTERED" in screen(ctx.io)
    assert await database.igm_data.get_raw("dark_cloak", "conversation") is None


# --- the ranking ---------------------------------------------------------


async def test_the_ranking_orders_by_lays_then_charm():
    ctx, database = await _ctx(keys=[""], lays=3, charm=5)
    for name, lays, charm in (("Casanova", 9, 1), ("Tied", 3, 99), ("Chaste", 0, 50)):
        other = await database.players.create(name, "pw", "M")
        other.lays, other.charm = lays, charm
        await database.players.save(other)

    await tavern._rankings(ctx)

    text = screen(ctx.io)
    assert "Chaste" not in text  # nobody with zero makes the list
    order = [text.index(n) for n in ("Casanova", "Tied", "Hero")]
    assert order == sorted(order)


async def test_clean_mode_renames_the_column():
    ctx, _db = await _ctx(keys=[""])
    ctx.config = {"clean_mode": True}
    await tavern._rankings(ctx)
    assert "Evil Deeds" in screen(ctx.io)


# --- reachable from the forest -------------------------------------------


async def test_only_a_mounted_player_ever_finds_the_tavern():
    """lord.js rolls ``random(15 + (player.horse ? 1 : 0))`` (:14482), so
    slot 15 -- the tavern -- does not exist for a player on foot."""
    from pylord.engine.scenes import forest

    class _OnlyFirst:
        def __init__(self, first):
            self.first, self.used = first, False

        def randrange(self, _n=None):
            if not self.used:
                self.used = True
                return self.first
            return 0

    ctx, _db = await _ctx(keys=["R"], horse=1)
    ctx.rng = _OnlyFirst(15)
    await forest._forest_event(ctx)
    assert "The Dark Cloak Tavern" in screen(ctx.io)

    on_foot, _db2 = await _ctx(keys=["R"], horse=0)
    on_foot.rng = _OnlyFirst(15)  # clamped to 15 slots, so this can't come up
    await forest._forest_event(on_foot)
    assert "The Dark Cloak Tavern" not in screen(on_foot.io)
