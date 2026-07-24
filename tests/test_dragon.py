"""Red Dragon fight tests -- see pylord/engine/scenes/dragon.py's module
docstring for lord.js line-number citations behind every formula/message
ported here, and the field-by-field reset citations in ``_victory``.

Follows tests/test_training.py's/tests/test_forest.py's established style:
a local ``_SeqRNG`` for deterministic combat rolls, and a local ``_ctx()``
helper for a fully-controlled ``Player``."""

from __future__ import annotations

from pylord import db
from pylord.engine.game import GameCtx
from pylord.engine.scenes import dragon as dragon_mod
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
    ctx = GameCtx(player=player, repo=repo, io=io, conn=conn, config=config or {})
    if rng is not None:
        ctx.rng = rng
    return ctx


# --- End-to-end smoke test ---------------------------------------------


async def test_dragon_reachable_from_town():
    io, _player = await play(["x", "x"])
    text = screen(io)
    assert "not yet" in text


# --- Gate: level < 12, and the once-a-day seen_dragon lock --------------


async def test_gate_refuses_level_below_12():
    ctx = _ctx(overrides={"level": 11}, keys=["x"])
    result = await dragon_mod.dragon(ctx)
    assert result == "town"
    assert "not yet" in screen(ctx.io)
    assert ctx.player.seen_dragon == 0  # never even reached the fight


async def test_seen_dragon_blocks_second_attempt_same_day():
    ctx = _ctx(overrides={"level": 12, "seen_dragon": 1}, keys=["x"])
    result = await dragon_mod.dragon(ctx)
    assert result == "town"
    assert "shaking so badly" in screen(ctx.io)


async def test_return_from_pre_fight_menu_does_not_start_a_fight():
    ctx = _ctx(overrides={"level": 12}, keys=["r", "x"])
    result = await dragon_mod.dragon(ctx)
    assert result == "town"
    assert ctx.player.seen_dragon == 0
    assert "wise to depart" in screen(ctx.io)


# --- Seeded win: exact reset field values + king_count+1 + news --------


async def test_dragon_win_resets_every_field_and_increments_king_count():
    """One-shot kill: player str=40000 so attack_damage's floor(str/2)=
    20000 alone exceeds the Dragon's hp (15000), regardless of the roll.
        randrange(20000) -> 0   (attack_damage's base roll -> dmg = 20000)
        randrange(10)    -> 0   (crit-move roll, 0+1=1, not > 9)
    Keys: (A)ttack at the pre-fight menu, (A)ttack in battle, then 6
    more() prompts through the victory/epilogue/reset text (a normal win,
    king_count going 2 -> 3 with the default win_deeds=3 threshold would
    end the session instead -- see the separate quest-over test below, so
    this test starts from king_count=0).
    """
    ctx = _ctx(
        overrides={
            "level": 12, "strength": 40000, "hp": 500, "hp_max": 500,
            "charm": 77, "skill_dk": 15, "kids": 2, "married_to": 999,
            "gold": 12345, "bank": 999, "exp": 54321, "gems": 3,
            "weapon_num": 9, "armor_num": 9, "defense": 88,
        },
        # First draw is the opening initiative roll (0 -> tmp 1, the
        # player strikes first, reference/lord.js:7375-7391).
        rng=_SeqRNG([0, 0, 0]),
        keys=["a", "a", "x", "x", "x", "x", "x", "x"],
    )
    result = await dragon_mod.dragon(ctx)
    assert result == "town"

    p = ctx.player
    assert p.level == 1
    assert p.hp_max == 20
    assert p.hp == 20
    assert p.weapon_num == 1
    assert p.armor_num == 1
    assert p.gold == 500
    assert p.bank == 0
    assert p.defense == 1
    assert p.strength == 10
    assert p.gems == 10
    assert p.alive == 1
    assert p.at_inn == 0
    assert p.exp == 10
    assert p.forest_fights == 15 + 2  # config default (15) + kids (2)
    assert p.player_fights == 3  # config default
    assert p.king_count == 1

    # Explicitly kept, not reset:
    assert p.charm == 77
    assert p.skill_dk == 15
    assert p.kids == 2
    assert p.married_to == 999
    assert p.seen_dragon == 1  # reset only by tomorrow's daily maintenance

    text = screen(ctx.io)
    assert "You have defeated The Red Dragon!" in text
    assert "YOUR QUEST IS NOT OVER" in text

    news_row = ctx.conn.execute("SELECT text FROM daily_news").fetchone()
    assert news_row is not None
    assert "Hero" in news_row["text"]
    assert "slain the" in news_row["text"]
    assert "Red Dragon" in news_row["text"]


async def test_dragon_win_reset_honors_configured_forest_and_player_fights():
    ctx = _ctx(
        overrides={"level": 12, "strength": 40000, "hp": 500, "hp_max": 500},
        # First draw is the opening initiative roll (0 -> tmp 1, the
        # player strikes first, reference/lord.js:7375-7391).
        rng=_SeqRNG([0, 0, 0]),
        keys=["a", "a", "x", "x", "x", "x", "x", "x"],
        config={"game": {"forest_fights_per_day": 20, "player_fights_per_day": 5}},
    )
    await dragon_mod.dragon(ctx)
    assert ctx.player.forest_fights == 20
    assert ctx.player.player_fights == 5


async def test_dragon_win_at_win_deeds_threshold_ends_session():
    """A third dragon kill (default win_deeds=3) ends the session
    immediately instead of showing "quest not over" -- reference/lord.js
    :12183-12196. One fewer more() prompt than a normal win (no "YOU FEEL
    STRANGE" epilogue tail)."""
    ctx = _ctx(
        overrides={
            "level": 12, "strength": 40000, "hp": 500, "hp_max": 500,
            "king_count": 2,
        },
        # First draw is the opening initiative roll (0 -> tmp 1, the
        # player strikes first, reference/lord.js:7375-7391).
        rng=_SeqRNG([0, 0, 0]),
        keys=["a", "a", "x", "x", "x", "x", "x"],
    )
    result = await dragon_mod.dragon(ctx)
    assert result is None
    assert ctx.player.king_count == 3
    text = screen(ctx.io)
    assert "YOUR QUEST IS OVER" in text
    assert "YOUR QUEST IS NOT OVER" not in text

    row = ctx.conn.execute(
        "SELECT value FROM game_state WHERE key = 'won_by'"
    ).fetchone()
    assert row is not None
    assert row["value"] == str(ctx.player.id)


# --- Seeded loss: death, no exp penalty (unlike forest/PvP) -------------


async def test_dragon_loss_kills_player_with_no_experience_penalty():
    """Player deals 0 damage (str=0 -> guaranteed miss, no rng draw for the
    base roll) while the Dragon (str=2000) one-shots a 5-hp player. Draw
    order, opening roll first:
        randrange(99) -> 0   (opening initiative: the player strikes first)
        randrange(10) -> 0   (player's crit-move roll on the miss)
        randrange(1000) -> 0 (Dragon's base roll, half=1000 -> 1000 damage)
        randrange(4) -> 0    (Dragon's weapon pick: Huge Claw, no doubling
                              -- reference/lord.js:6704-6720)
        randrange(30) -> 0   (Dragon's power-move check, != 1: no boost)
    """
    ctx = _ctx(
        overrides={
            "level": 12, "strength": 0, "defense": 0, "hp": 5, "hp_max": 5,
            "gold": 999, "exp": 555,
        },
        rng=_SeqRNG([0, 0, 0, 0, 0]),
        keys=["a", "a", "x"],
    )
    result = await dragon_mod.dragon(ctx)
    assert result is None

    p = ctx.player
    assert p.hp == 0
    assert p.alive == 0
    assert p.gold == 0
    assert p.exp == 555  # unchanged -- no experience penalty on a dragon loss

    news_row = ctx.conn.execute("SELECT text FROM daily_news").fetchone()
    assert news_row is not None
    assert "Red Dragon" in news_row["text"]
    assert "has killed" in news_row["text"]
    assert "Hero" in news_row["text"]

    text = screen(ctx.io)
    assert "rips your head off" in text
