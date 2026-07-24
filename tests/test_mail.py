"""Mail scene + effect-application tests. See
pylord/engine/scenes/mail.py's and pylord/engine/effects.py's module
docstrings for lord.js line-number citations."""

from __future__ import annotations

import json

from pylord import db
from pylord.engine.effects import apply_effect
from pylord.engine.game import GameCtx
from pylord.engine.scenes import mail as mail_mod
from pylord.models import PlayerRepo
from pylord.terminal import FakeIO
from tests.harness import play, screen


def _ctx(overrides=None, keys=None, name="Hero"):
    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)
    player = repo.create(name, "pw", "M")
    for key, value in (overrides or {}).items():
        setattr(player, key, value)
    io = FakeIO(keys or [])
    return GameCtx(player=player, repo=repo, io=io, conn=conn)


# -- apply_effect -----------------------------------------------------------


def test_apply_effect_gold_and_exp_additive():
    conn = db.connect(":memory:")
    db.migrate(conn)
    player = PlayerRepo(conn).create("Hero", "pw", "M")
    player.gold = 100
    player.exp = 50
    apply_effect(player, {"gold": 25, "exp": 10})
    assert player.gold == 125
    assert player.exp == 60


def test_apply_effect_floors_gold_and_gems_at_zero():
    conn = db.connect(":memory:")
    db.migrate(conn)
    player = PlayerRepo(conn).create("Hero", "pw", "M")
    player.gold = 10
    player.gems = 0
    apply_effect(player, {"gold": -50, "gems": -5})
    assert player.gold == 0
    assert player.gems == 0


def test_apply_effect_caps_exp_at_2_billion():
    conn = db.connect(":memory:")
    db.migrate(conn)
    player = PlayerRepo(conn).create("Hero", "pw", "M")
    player.exp = 1_999_999_995
    apply_effect(player, {"exp": 100})
    assert player.exp == 2_000_000_000


def test_apply_effect_floors_combat_stats_at_one():
    conn = db.connect(":memory:")
    db.migrate(conn)
    player = PlayerRepo(conn).create("Hero", "pw", "M")
    player.strength = 10
    apply_effect(player, {"strength": -50})
    assert player.strength == 1


def test_apply_effect_ignores_unknown_keys():
    conn = db.connect(":memory:")
    db.migrate(conn)
    player = PlayerRepo(conn).create("Hero", "pw", "M")
    player.gold = 100
    apply_effect(player, {"hp": 999, "totally_bogus": 1})
    assert player.gold == 100
    assert player.hp == 20  # untouched -- hp isn't a supported key


def test_apply_effect_supports_every_documented_key():
    conn = db.connect(":memory:")
    db.migrate(conn)
    player = PlayerRepo(conn).create("Hero", "pw", "M")
    before = {
        f: getattr(player, f)
        for f in (
            "gold", "gems", "exp", "hp_max", "strength", "defense", "charm",
            "forest_fights", "player_fights",
        )
    }
    apply_effect(player, {k: 1 for k in before})
    for field, value in before.items():
        assert getattr(player, field) == value + 1


# -- (W)rite Mail scene -------------------------------------------------


async def test_mail_reachable_from_town():
    io, _player = await play(["w", "nobody", "x"])
    text = screen(io)
    assert "Write Mail" in text


async def test_write_mail_inserts_row():
    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)
    sender = repo.create("Sender", "pw", "M")
    recipient = repo.create("Recipient", "pw", "F")

    io = FakeIO(["Recipient", "y", "Hello there!", "", "x"])
    ctx = GameCtx(player=sender, repo=repo, io=io, conn=conn)
    result = await mail_mod.mail(ctx)
    assert result == "town"

    row = conn.execute(
        "SELECT to_id, from_name, text, effect, read FROM mail"
    ).fetchone()
    assert row["to_id"] == recipient.id
    assert row["from_name"] == "Sender"
    assert "Hello there!" in row["text"]
    assert row["effect"] is None
    assert row["read"] == 0


async def test_write_mail_partial_name_match_confirms():
    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)
    sender = repo.create("Sender", "pw", "M")
    repo.create("Recipient", "pw", "F")

    io = FakeIO(["Rec", "y", "Hi", "", "x"])
    ctx = GameCtx(player=sender, repo=repo, io=io, conn=conn)
    await mail_mod.mail(ctx)
    row = conn.execute("SELECT from_name FROM mail").fetchone()
    assert row is not None


async def test_write_mail_no_match_shows_message_and_inserts_nothing():
    ctx = _ctx(keys=["Nobody Here", "x"])
    await mail_mod.mail(ctx)
    assert "No matching names found" in screen(ctx.io)
    row = ctx.conn.execute("SELECT * FROM mail").fetchone()
    assert row is None


async def test_write_mail_blank_first_line_still_sends_a_note():
    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)
    sender = repo.create("Sender", "pw", "M")
    repo.create("Recipient", "pw", "F")

    io = FakeIO(["Recipient", "y", "", "x"])
    ctx = GameCtx(player=sender, repo=repo, io=io, conn=conn)
    await mail_mod.mail(ctx)
    row = conn.execute("SELECT text FROM mail").fetchone()
    assert row["text"] == "(no message)"


# -- login-time apply_unread_mail ----------------------------------------


async def test_login_applies_effect_exactly_once():
    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)
    player = repo.create("Hero", "pw", "M")
    player.gold = 100
    repo.save(player)

    with conn:
        conn.execute(
            "INSERT INTO mail (to_id, from_name, text, effect, created, read) "
            "VALUES (?, ?, ?, ?, ?, 0)",
            (player.id, "IGM", "A gift!", json.dumps({"gold": 50}), "2026-01-01"),
        )

    io = FakeIO(["x"])
    ctx = GameCtx(player=player, repo=repo, io=io, conn=conn)
    count = await mail_mod.apply_unread_mail(ctx)
    assert count == 1
    assert ctx.player.gold == 150
    assert "A gift!" in screen(ctx.io)

    row = conn.execute("SELECT read FROM mail").fetchone()
    assert row["read"] == 1

    # Re-login: the same mail row must not be applied a second time.
    ctx2 = GameCtx(player=ctx.player, repo=repo, io=FakeIO([]), conn=conn)
    count2 = await mail_mod.apply_unread_mail(ctx2)
    assert count2 == 0
    assert ctx2.player.gold == 150


async def test_apply_unread_mail_no_mail_is_a_silent_no_op():
    ctx = _ctx(keys=[])
    count = await mail_mod.apply_unread_mail(ctx)
    assert count == 0
    assert ctx.io.output == []


async def test_apply_unread_mail_without_effect_shows_text_only():
    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)
    player = repo.create("Hero", "pw", "M")
    with conn:
        conn.execute(
            "INSERT INTO mail (to_id, from_name, text, effect, created, read) "
            "VALUES (?, ?, ?, NULL, ?, 0)",
            (player.id, "Friend", "Just saying hi.", "2026-01-01"),
        )
    ctx = GameCtx(player=player, repo=repo, io=FakeIO(["x"]), conn=conn)
    count = await mail_mod.apply_unread_mail(ctx)
    assert count == 1
    assert "Just saying hi." in screen(ctx.io)
