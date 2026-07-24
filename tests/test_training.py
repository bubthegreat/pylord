"""Turgon's Warrior Training tests. See
pylord/engine/scenes/training.py's module docstring for lord.js
line-number citations behind every formula/message ported here, and for
the post-review correction on which key (`Q` vs `A`) actually shows
``needstr1``/``needstr2`` under vs. over the exp threshold.

Follows tests/test_forest.py's established style: ``play(keys)`` for a
smoke test through the full town -> training session, and a local
``_ctx()`` helper to drive ``training()``/its private helpers directly
with a fully-controlled ``Player`` and RNG.
"""

from __future__ import annotations

from pylord import db
from pylord.engine import data
from pylord.engine.game import GameCtx
from pylord.engine.scenes import training as training_mod
from pylord.models import PlayerRepo
from pylord.terminal import FakeIO
from tests.harness import play, screen


class _SeqRNG:
    """See tests/test_forest.py's identical helper for rationale."""

    def __init__(self, values):
        self._values = list(values)

    def randrange(self, _n):
        return self._values.pop(0)


def _ctx(overrides=None, rng=None, keys=None):
    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)
    player = repo.create("Hero", "pw", "M")
    for key, value in (overrides or {}).items():
        setattr(player, key, value)
    io = FakeIO(keys or [])
    ctx = GameCtx(player=player, repo=repo, io=io, conn=conn)
    if rng is not None:
        ctx.rng = rng
    return ctx


# --- End-to-end smoke test (through the real town -> training session) ---


async def test_training_menu_reachable_from_town():
    io, _player = await play(["t", "r", "q"])
    text = screen(io)
    assert "Turgon's Warrior Training" in text
    assert "Your master is Halder" in text


# --- Q (ask) -- exp threshold gates needstr1/needstr2 vs. generic notice --


async def test_ask_under_threshold_shows_generic_need_more_exp():
    """A fresh level-1 player has exp=1, well under Halder's
    exp_reward=100. lord.js's ask() (needstr1 is NOT shown here -- see
    module docstring's post-review correction)."""
    trainer = data.MASTERS[1]
    ctx = _ctx(keys=["x"])
    await training_mod._ask(ctx, trainer)
    text = screen(ctx.io)
    assert "more experience" in text
    assert trainer.needstr1 not in text


async def test_ask_over_threshold_shows_needstr1_quote():
    trainer = data.MASTERS[1]
    ctx = _ctx(overrides={"exp": trainer.exp_reward + 1}, keys=["x"])
    await training_mod._ask(ctx, trainer)
    text = screen(ctx.io)
    assert trainer.needstr1 in text


# --- A (attack) -- under threshold: comedic refusal, no fight ------------


async def test_attack_under_threshold_refuses_without_a_fight():
    trainer = data.MASTERS[1]
    ctx = _ctx(keys=["x", "x", "x", "x"])  # 4 pauses in the comedic sequence
    await training_mod._attack_master(ctx, trainer)
    text = screen(ctx.io)
    assert "not ready for your testing" in text
    assert ctx.player.seen_master == 1
    assert ctx.player.level == 1


async def test_attack_seen_master_gate_refuses_second_attempt_same_day():
    trainer = data.MASTERS[1]
    ctx = _ctx(overrides={"seen_master": 1}, keys=["x"])
    await training_mod._attack_master(ctx, trainer)
    text = screen(ctx.io)
    assert "too late" in text
    assert ctx.player.level == 1


# --- A (attack) -- over threshold: real fight, win grants level + stats --


async def test_master_win_grants_level_and_exact_stat_gains():
    """A one-shot kill: player str=1000 (so attack_damage's floor(str/2)=
    500 dominates Halder's hp=30 regardless of the roll), and the crit
    roll must land <= 9 (no power-move multiplier needed to one-shot
    anyway). ``_SeqRNG`` pins both draws deterministically:
        randrange(500) -> 0   (attack_damage's base roll -> dmg = 500)
        randrange(10)  -> 0   (crit-move roll, 0+1=1, not > 9)
    500 damage one-shots Halder (hp=30) on the very first swing.
    """
    trainer = data.MASTERS[1]
    ctx = _ctx(
        overrides={
            "exp": trainer.exp_reward + 1,
            "strength": 1000,
            "hp": 200,
            "hp_max": 200,
        },
        rng=_SeqRNG([0, 0]),
        keys=["a", "x"],
    )
    await training_mod._attack_master(ctx, trainer)
    text = screen(ctx.io)
    assert "You have bested Halder" in text
    assert trainer.swear in text
    assert "YOU ARE NOW LEVEL 2" in text

    gain = data.LEVEL_STATS[1]
    assert ctx.player.level == 2
    assert ctx.player.hp_max == 200 + gain.hp
    assert ctx.player.hp == ctx.player.hp_max
    assert ctx.player.strength == 1000 + gain.strength
    assert ctx.player.defense == 1 + trainer.defense
    assert ctx.player.seen_master == 0  # reset on a win


async def test_master_loss_heals_and_shows_mercy_no_death():
    """Player deals 0 damage (strength=0 -> attack_damage's base roll
    floors at 0, a guaranteed miss that costs no rng draw -- ``half=0``
    short-circuits ``_random()``) while Halder (str=15) one-shots a
    5-hp player back. Draw order for a single "a" press:
        randrange(10) -> 0   (crit-move roll on the miss, 0+1=1: no power move)
        randrange(7)  -> 0   (enemy's base roll, half=7 -> 0+7=7 damage)
        randrange(30) -> 0   (enemy power-move check, != 1: no power move)
    7 damage kills a 5-hp player outright. No death penalty applies --
    the master resurrects and fully heals instead.
    """
    trainer = data.MASTERS[1]
    ctx = _ctx(
        overrides={
            "exp": trainer.exp_reward + 1,
            "strength": 0,
            "defense": 0,
            "hp": 5,
            "hp_max": 5,
        },
        rng=_SeqRNG([0, 0, 0]),
        keys=["a", "x", "x"],
    )
    await training_mod._attack_master(ctx, trainer)
    text = screen(ctx.io)
    assert "raises his" in text
    assert ctx.player.hp == ctx.player.hp_max
    assert ctx.player.alive == 1
    assert ctx.player.level == 1
    assert ctx.player.gold == 500  # no gold penalty, unlike a forest death


# --- Level 12: no more masters --------------------------------------------


async def test_level_12_shows_dragon_message_and_returns_to_town():
    ctx = _ctx(overrides={"level": 12}, keys=["x"])
    result = await training_mod.training(ctx)
    text = screen(ctx.io)
    assert "Your master is Turgon" in text
    assert "Red Dragon" in text
    assert result == "town"
