"""Mail scene + effect-application tests. See
pylord/engine/scenes/mail.py's and pylord/engine/effects.py's module
docstrings for lord.js line-number citations."""

from __future__ import annotations

from pylord import data
from pylord.engine.effects import apply_effect
from pylord.engine.game import GameCtx
from pylord.engine.scenes import mail as mail_mod
from pylord.terminal import FakeIO
from tests.harness import play, query_one, screen


async def _ctx(overrides=None, keys=None, name="Hero"):
    database = await data.connect(":memory:")
    repo = database.players
    player = await repo.create(name, "pw", "M")
    for key, value in (overrides or {}).items():
        setattr(player, key, value)
    io = FakeIO(keys or [])
    return GameCtx(player=player, db=database, io=io)


# -- apply_effect -----------------------------------------------------------


async def test_apply_effect_gold_and_exp_additive():
    database = await data.connect(":memory:")
    player = await database.players.create("Hero", "pw", "M")
    player.gold = 100
    player.exp = 50
    apply_effect(player, {"gold": 25, "exp": 10})
    assert player.gold == 125
    assert player.exp == 60


async def test_apply_effect_floors_gold_and_gems_at_zero():
    database = await data.connect(":memory:")
    player = await database.players.create("Hero", "pw", "M")
    player.gold = 10
    player.gems = 0
    apply_effect(player, {"gold": -50, "gems": -5})
    assert player.gold == 0
    assert player.gems == 0


async def test_apply_effect_caps_exp_at_2_billion():
    database = await data.connect(":memory:")
    player = await database.players.create("Hero", "pw", "M")
    player.exp = 1_999_999_995
    apply_effect(player, {"exp": 100})
    assert player.exp == 2_000_000_000


async def test_apply_effect_floors_combat_stats_at_zero():
    """lord.js's check_fields() floors str/def/cha/hp_max at 0, not 1
    (reference/lord.js:16641-16658)."""
    database = await data.connect(":memory:")
    player = await database.players.create("Hero", "pw", "M")
    player.strength = 10
    apply_effect(player, {"strength": -50})
    assert player.strength == 0


async def test_apply_effect_ignores_unknown_keys():
    database = await data.connect(":memory:")
    player = await database.players.create("Hero", "pw", "M")
    player.gold = 100
    apply_effect(player, {"hp": 999, "totally_bogus": 1})
    assert player.gold == 100
    assert player.hp == 20  # untouched -- hp isn't a supported key


async def test_apply_effect_supports_every_documented_key():
    database = await data.connect(":memory:")
    player = await database.players.create("Hero", "pw", "M")
    before = {
        f: getattr(player, f)
        for f in (
            "gold", "bank", "gems", "exp", "hp_max", "strength", "defense",
            "charm", "forest_fights", "player_fights", "lays", "kids",
        )
    }
    apply_effect(player, {k: 1 for k in before})
    for field, value in before.items():
        assert getattr(player, field) == value + 1


async def test_apply_effect_caps_gold_and_bank_at_two_billion():
    """reference/lord.js:16630-16640 (check_fields)."""
    database = await data.connect(":memory:")
    player = await database.players.create("Hero", "pw", "M")
    player.gold = 2_000_000_000
    player.bank = 1_999_999_999
    apply_effect(player, {"gold": 5_000, "bank": 5_000})
    assert player.gold == 2_000_000_000
    assert player.bank == 2_000_000_000


# -- (W)rite Mail scene -------------------------------------------------


async def test_mail_reachable_from_town():
    io, _player = await play(["w", "nobody", "x"])
    text = screen(io)
    assert "Write Mail" in text


async def test_write_mail_inserts_row():
    database = await data.connect(":memory:")
    repo = database.players
    sender = await repo.create("Sender", "pw", "M")
    recipient = await repo.create("Recipient", "pw", "F")

    io = FakeIO(["Recipient", "y", "Hello there!", "", "x"])
    ctx = GameCtx(player=sender, db=database, io=io)
    result = await mail_mod.mail(ctx)
    assert result == "town"

    row = await query_one(database, "SELECT to_id, from_name, text, effect, read FROM mail")
    assert row.to_id == recipient.id
    assert row.from_name == "Sender"
    assert "Hello there!" in row.text
    assert row.effect is None
    assert row.read == 0


async def test_write_mail_partial_name_match_confirms():
    database = await data.connect(":memory:")
    repo = database.players
    sender = await repo.create("Sender", "pw", "M")
    await repo.create("Recipient", "pw", "F")

    io = FakeIO(["Rec", "y", "Hi", "", "x"])
    ctx = GameCtx(player=sender, db=database, io=io)
    await mail_mod.mail(ctx)
    assert await query_one(database, "SELECT from_name FROM mail") is not None


async def test_write_mail_no_match_shows_message_and_inserts_nothing():
    ctx = await _ctx(keys=["Nobody Here", "x"])
    await mail_mod.mail(ctx)
    assert "No matching names found" in screen(ctx.io)
    assert await query_one(ctx.db, "SELECT * FROM mail") is None


async def test_write_mail_blank_first_line_still_sends_a_note():
    database = await data.connect(":memory:")
    repo = database.players
    sender = await repo.create("Sender", "pw", "M")
    await repo.create("Recipient", "pw", "F")

    io = FakeIO(["Recipient", "y", "", "x"])
    ctx = GameCtx(player=sender, db=database, io=io)
    await mail_mod.mail(ctx)
    row = await query_one(database, "SELECT text FROM mail")
    assert row.text == "(no message)"


# -- login-time apply_unread_mail ----------------------------------------


async def test_login_applies_effect_exactly_once():
    database = await data.connect(":memory:")
    repo = database.players
    player = await repo.create("Hero", "pw", "M")
    player.gold = 100
    await repo.save(player)

    await database.mail.send(player.id, "IGM", text="A gift!", effect={"gold": 50})

    io = FakeIO(["x"])
    ctx = GameCtx(player=player, db=database, io=io)
    count = await mail_mod.apply_unread_mail(ctx)
    assert count == 1
    assert ctx.player.gold == 150
    assert "A gift!" in screen(ctx.io)

    row = await query_one(database, "SELECT read FROM mail")
    assert row.read == 1

    # Re-login: the same mail row must not be applied a second time.
    ctx2 = GameCtx(player=ctx.player, db=database, io=FakeIO([]))
    count2 = await mail_mod.apply_unread_mail(ctx2)
    assert count2 == 0
    assert ctx2.player.gold == 150


async def test_apply_unread_mail_effect_survives_crash_without_session_save():
    """Post-review durability fix: apply_unread_mail's DB write (marking
    the row read) and the player's mutated stats must land in the SAME
    transaction. Simulates a crash by calling apply_unread_mail and then
    reloading the player straight from the DB via a *fresh* PlayerRepo.get
    -- never calling ctx.save()/GameCtx.save()/repo.save() at all -- the
    old "mark read now, persist player only at session end" version would
    lose the gold here."""
    database = await data.connect(":memory:")
    repo = database.players
    player = await repo.create("Hero", "pw", "M")
    player.gold = 100
    await repo.save(player)

    await database.mail.send(player.id, "IGM", text="A gift!", effect={"gold": 50})

    ctx = GameCtx(player=player, db=database, io=FakeIO(["x"]))
    count = await mail_mod.apply_unread_mail(ctx)
    assert count == 1
    # No ctx.save()/repo.save() call here on purpose -- simulating a crash
    # (process kill, connection drop) that skips server.py's own cleanup
    # save entirely.

    reloaded = await database.players.get(player.id)
    assert reloaded.gold == 150
    reloaded_row = await query_one(database, "SELECT read FROM mail")
    assert reloaded_row.read == 1


async def test_apply_unread_mail_no_mail_is_a_silent_no_op():
    ctx = await _ctx(keys=[])
    count = await mail_mod.apply_unread_mail(ctx)
    assert count == 0
    assert ctx.io.output == []


async def test_apply_unread_mail_without_effect_shows_text_only():
    database = await data.connect(":memory:")
    repo = database.players
    player = await repo.create("Hero", "pw", "M")
    await database.mail.send(player.id, "Friend", text="Just saying hi.")
    ctx = GameCtx(player=player, db=database, io=FakeIO(["x"]))
    count = await mail_mod.apply_unread_mail(ctx)
    assert count == 1
    assert "Just saying hi." in screen(ctx.io)
