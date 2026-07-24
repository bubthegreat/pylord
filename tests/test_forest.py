"""Forest scene tests -- see pylord/engine/scenes/forest.py's module
docstring for lord.js line-number citations behind every formula/message
ported here.

Two testing styles are used:

- ``play(keys)`` drives the *full* town -> forest session loop (through
  ``tests/harness.py``), which always seeds ``ctx.rng`` with
  ``random.Random(0)``. Used for a couple of end-to-end sanity checks
  where the exact RNG draw sequence has already been hand-verified (see
  the comments beside each).
- ``_ctx(...)`` builds a ``GameCtx`` directly (mirroring
  ``tests/test_game.py``'s own helper) so individual forest.py functions
  (``_run_fight``, ``_pick_monster``, ``_look_to_kill``) can be exercised
  with a fully-controlled ``Player`` and RNG, sidestepping
  ``tests/harness.py``'s "player must already exist in play()'s own
  throwaway db" limitation (harness.py has no supported way to seed a
  *custom* starting Player through the full session loop).
"""

from __future__ import annotations

import random

from pylord import db
from pylord.engine import data
from pylord.engine.game import GameCtx
from pylord.engine.scenes import forest as forest_mod
from pylord.models import PlayerRepo
from pylord.terminal import FakeIO
from tests.harness import play, screen


class _SeqRNG:
    """Minimal fake RNG: ``randrange(n)`` returns the next value from a
    pre-scripted list, ignoring ``n`` (the caller is responsible for
    scripting values that are valid for whatever ``n`` will actually be
    passed -- used to pin down a specific branch deterministically
    without hunting for a real ``random.Random`` seed)."""

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


# --- End-to-end smoke tests (through the real town -> forest session) --


async def test_forest_menu_shows_expected_letters():
    io, _player = await play(["f", "r", "q"])
    text = screen(io)
    assert "The Forest" in text
    assert "(L)ook for something to kill" in text
    assert "(H)ealer's Hut" in text
    assert "(R)eturn to town" in text
    assert "(V)iew your stats" in text


async def test_kill_flow_grants_exact_gold_and_exp():
    """``play()`` seeds ``ctx.rng = random.Random(0)``. Hand-verified draw
    order for a fresh level-1 "Tester" player pressing F, L, A:

        randrange(5)  -> 3   (event check, != 1: no event, go to fight)
        randrange(10) -> 6   (level-1 monster index -> MONSTERS[1][6],
                               "Large Mosquito": str=2, hp=3, gold=46, exp=2)
        randrange(5)  -> 0   (attack_damage's base roll: half=5, 0+5=5 dmg)
        randrange(10) -> 4   (crit-move roll, 4+1=5, not > 9: no power move)

    5 damage kills the 3-hp Mosquito outright (not an overkill, since
    5 <= player.strength(10), so no death_phrase/loot-bonus roll --
    reference/lord.js:6973 gates that on ``atk > player.str``).
    """
    io, player = await play(["f", "l", "a", "z", "r", "q"])
    text = screen(io)
    assert "You have encountered Large Mosquito`2!!" in text or (
        "You have encountered Large Mosquito" in text
    )
    assert "You have killed Large Mosquito" in text
    assert "You receive 46 gold, and" in text
    assert "2 experience!" in text
    assert player.gold == 500 + 46
    assert player.exp == 1 + 2
    assert player.forest_fights == 15 - 1
    assert player.gems == 0


async def test_healer_option_routes_to_real_healer_scene():
    """Task 11: (H) now routes to the real healer scene, not a stub. A
    fresh player is already at full HP (hp == hp_max == 20), so the
    healer's "you look fine to us" branch fires and bounces straight back
    to town -- see pylord/engine/scenes/healer.py."""
    io, _player = await play(["f", "h", "q"])
    text = screen(io)
    assert "You look fine to us" in text
    assert text.count("Town Square") == 2


async def test_view_stats_option_routes_to_stats_then_town():
    """See docs/deviations.md: (V) bounces to the shared ``stats`` scene,
    which always returns to Town Square afterward, not back to the
    forest -- ``stats.py`` isn't owned by this task. "Town Square" appears
    twice: once on the initial entry (before `f`), once more after stats
    hands back to `"town"` (mirrors tests/test_town.py's own
    ``test_view_stats_shows_name_level_and_returns_to_town``)."""
    io, player = await play(["f", "v", "q"])
    text = screen(io)
    assert "Experience" in text  # stats.py's own screen
    assert player.name in text
    assert text.count("Town Square") == 2


async def test_no_fights_left_shows_message_and_stays_in_forest():
    ctx = _ctx(overrides={"forest_fights": 0}, keys=["l", "z", "r"])
    result = await forest_mod.forest(ctx)
    text = screen(ctx.io)
    assert "You are too tired." in text
    assert "Try again tomorrow." in text
    assert ctx.player.forest_fights == 0
    assert result == "town"


# --- _run_fight() unit tests (fine-grained RNG control) ----------------


async def test_run_success_ends_fight_with_no_loot():
    """A fresh ``random.Random(0)`` fed straight into ``attempt_run()`` as
    the *first* draw gives ``randrange(9) == 6`` (!= 1 -> not caught)."""
    monster = data.MONSTERS[1][0]  # Small Thief
    ctx = _ctx(rng=random.Random(0), keys=["r", "z"])
    died = await forest_mod._run_fight(ctx, monster)
    assert died is False
    assert ctx.player.hp == ctx.player.hp_max  # untouched -- no counter-attack
    assert ctx.player.gold == 500  # default Player.gold, unchanged
    assert ctx.player.exp == 1  # default Player.exp, unchanged
    text = screen(ctx.io)
    assert "dash into the forest" in text


async def test_run_fail_applies_enemy_counter_attack():
    """Hand-verified with ``pylord.engine.combat`` directly: feeding a
    fresh ``random.Random(6)`` into ``Fight(...).attempt_run()`` against
    ``MONSTERS[1][0]`` (Small Thief, str=6) gives ``randrange(9) == 1``
    (caught) then a counter-attack for exactly 3 damage against a
    defense=1 player. See the module docstring for how ``_run_fight``
    infers this wording from the HP delta (it can't re-read the enemy's
    ``Round`` -- ``attempt_run()`` only returns ``bool``)."""
    monster = data.MONSTERS[1][0]  # Small Thief
    ctx = _ctx(
        overrides={"strength": 10, "defense": 1, "hp": 20, "hp_max": 20},
        rng=random.Random(6),
        keys=["r", "a", "a", "z"],
    )
    died = await forest_mod._run_fight(ctx, monster)
    text = screen(ctx.io)
    assert f"{monster.name} sees you!" in text
    assert f"{monster.name} hits you for 3 damage!" in text
    assert died is False
    # 20 - 3 (caught) - 2 (2nd-round counter, see the follow-on attacks)
    assert ctx.player.hp == 15


async def test_skill_attack_decrements_skill_uses():
    """Hand-verified: with ``random.Random(0)`` (the opening initiative
    roll -- reference/lord.js:7375-7391 -- draws first, then the skill
    attack) a Death Knight skill attack against MONSTERS[1][0] (Small
    Thief, 9 hp) overkills it (damage > player.str(10)), which both kills
    the thief and rolls a "find a gem" loot bonus."""
    monster = data.MONSTERS[1][0]
    ctx = _ctx(
        overrides={
            "class_type": 1,
            "skill_dk": 5,
            "skill_uses": 2,
            "strength": 10,
            "defense": 1,
            "hp": 20,
            "hp_max": 20,
        },
        rng=random.Random(0),
        keys=["s", "z"],
    )
    died = await forest_mod._run_fight(ctx, monster)
    assert died is False
    assert ctx.player.skill_uses == 1
    assert ctx.player.gems == 1
    text = screen(ctx.io)
    assert monster.death_phrase in text


async def test_mystical_multi_point_spell_decrements_exact_cost():
    """Regression test for review Important-1: Mystical casts must
    decrement ``skill_uses`` by the *chosen tier's* real cost
    (1/4/8/12/16/20 -- reference/lord.js:7286-7362), not a flat 1.

    ``skill_uses=4`` (passed in as ``skill_attack()``'s ``skill_points``,
    per module docstring deviation 3) auto-selects the highest affordable
    tier -- "D" (Disappear, cost 4). "D" is damage-free and RNG-independent
    (it only draws the discarded flavor-text roll, ``:7225``), so the
    seed here is arbitrary and the outcome is fully deterministic:
    ``fight.ran_away`` is set unconditionally (``:7311-7312``).
    """
    monster = data.MONSTERS[1][0]  # Small Thief
    ctx = _ctx(
        overrides={"class_type": 2, "skill_my": 4, "skill_uses": 4},
        rng=random.Random(0),
        keys=["s", "z"],
    )
    died = await forest_mod._run_fight(ctx, monster)
    assert died is False
    assert ctx.player.skill_uses == 0  # 4 - cost('D')=4, not 4 - 1
    text = screen(ctx.io)
    assert "You disappear into a cool glade" in text


async def test_mystical_cast_fails_when_uses_below_cheapest_tier():
    """``skill_uses=0`` reaching ``skill_attack()`` (which cannot happen
    through the real battle menu -- ``_can_skill()`` already hides `S` in
    that case, see the next test) still refuses to cast and costs
    nothing, via ``_mystical_attack``'s own ``skill_points < cost`` guard
    (reference/lord.js's menu never offers a tier it can't afford)."""
    fight_rng = random.Random(0)
    from pylord.engine.combat import Combatant, Fight, skill_attack

    player_side = Combatant(
        name="Hero", hp=20, hp_max=20, strength=10, defense=1, weapon_name="Fists"
    )
    enemy = Combatant.from_monster(data.MONSTERS[1][0])
    fight = Fight(player_side, enemy, fight_rng, pfight=False)
    round_ = skill_attack(fight, "my", 0)
    assert round_.damage == 0
    assert fight.last_spell_cost == 0


async def test_skill_option_hidden_when_no_uses_left():
    ctx = _ctx(
        overrides={"class_type": 1, "skill_dk": 5, "skill_uses": 0},
    )
    options = forest_mod._battle_options(ctx.player)
    assert "S" not in options


async def test_death_zeroes_gold_loses_ten_percent_exp_and_marks_dead():
    """Hand-verified: ``random.Random(0)`` fed to a 5/5-hp, 0-defense
    player's ``Fight.player_attack()`` (vs. a 200-str/1000-hp dummy
    monster) does 8 damage without killing it, then
    ``Fight.enemy_attack()`` hits back for 105 -- lethal."""
    monster = data.Monster("Big Bear", "Claws", 200, 1000, 999, 50, "The bear wins.")
    ctx = _ctx(
        overrides={
            "strength": 10,
            "defense": 0,
            "hp": 5,
            "hp_max": 5,
            "gold": 1000,
            "exp": 250,
        },
        rng=random.Random(0),
        keys=["a", "z"],
    )
    died = await forest_mod._run_fight(ctx, monster)
    assert died is True
    assert ctx.player.alive == 0
    assert ctx.player.gold == 0
    assert ctx.player.exp == 250 - 25  # 10% of 250, reference/lord.js:15072
    text = screen(ctx.io)
    assert "You have been killed by Big Bear" in text
    assert "GOLD ON HAND WAS LOST." in text
    assert "TEN PERCENT OF EXPERIENCE LOST." in text
    row = ctx.conn.execute("SELECT text FROM daily_news").fetchone()
    assert "has been killed by" in row["text"]
    assert "Big Bear" in row["text"]


# --- _pick_monster() -- normal + wildcard selection ---------------------


def test_pick_monster_level_one_is_always_the_level_one_block():
    ctx = _ctx(overrides={"level": 1}, rng=_SeqRNG([5]))
    monster = forest_mod._pick_monster(ctx)
    assert monster == data.MONSTERS[1][5]


def test_pick_monster_normal_case_uses_own_level_block():
    # randrange(6) -> 0 (!= 2: normal branch), randrange(10) -> 7
    ctx = _ctx(overrides={"level": 3}, rng=_SeqRNG([0, 7]))
    monster = forest_mod._pick_monster(ctx)
    assert monster == data.MONSTERS[3][7]


def test_pick_monster_wildcard_case_reaches_a_lower_level_block():
    # randrange(6) -> 2 (wildcard branch), randrange(player.level=5) -> 0
    # (-> level 1), randrange(10) -> 3
    ctx = _ctx(overrides={"level": 5}, rng=_SeqRNG([2, 0, 3]))
    monster = forest_mod._pick_monster(ctx)
    assert monster == data.MONSTERS[1][3]


# --- Post-audit forest keys: (B)ank, (J)ENNIE, flavor, status line --------


async def test_vulture_banks_all_gold():
    """reference/lord.js:15260-15272 -- the hidden `B` key."""
    ctx = _ctx(overrides={"gold": 750, "bank": 100}, keys=["b", "r"])
    await forest_mod.forest(ctx)
    assert ctx.player.gold == 0
    assert ctx.player.bank == 850
    assert "UGLY VULTURE" in screen(ctx.io)


async def test_forest_menu_shows_the_status_line():
    """reference/lord.js:15227-15246."""
    ctx = _ctx(overrides={"gold": 42, "gems": 7}, keys=["r"])
    await forest_mod.forest(ctx)
    text = screen(ctx.io)
    assert "HitPoints: (" in text
    assert "Gold: 42" in text
    assert "Gems: 7" in text


async def test_class_flavor_keys_just_print_a_line():
    """reference/lord.js:15319-15352."""
    ctx = _ctx(keys=["t", "r"])
    await forest_mod.forest(ctx)
    assert "Thieving skills cannot help you here" in screen(ctx.io)


async def test_jennie_codeword_grants_an_extra_forest_fight():
    """reference/lord.js:15396-15419 -- J, then E-N-N-I-E, then BABE."""
    ctx = _ctx(
        overrides={"high_spirits": 1, "forest_fights": 5},
        keys=["j", "e", "n", "n", "i", "e", "BABE", " ", "r"],
    )
    await forest_mod.forest(ctx)
    assert ctx.player.forest_fights == 6
    assert ctx.player.high_spirits == 0  # spent for the day
    assert "EXTRA FOREST FIGHT" in screen(ctx.io)


async def test_jennie_needs_high_spirits():
    """reference/lord.js:15397 -- a low-spirits player gets nothing."""
    ctx = _ctx(overrides={"high_spirits": 0, "forest_fights": 5}, keys=["j", "r"])
    await forest_mod.forest(ctx)
    assert ctx.player.forest_fights == 5
    assert "Jennie" not in screen(ctx.io)


async def test_jennie_wrong_answer_gets_the_shrug():
    ctx = _ctx(
        overrides={"high_spirits": 1},
        keys=["j", "e", "n", "n", "i", "e", "ZZZZ", " ", "r"],
    )
    await forest_mod.forest(ctx)
    assert "You do not understand her" in screen(ctx.io)


async def test_jennie_ugly_answer_ends_the_session():
    """reference/lord.js:15488-15497."""
    ctx = _ctx(
        overrides={"high_spirits": 1, "hp": 20, "hp_max": 20},
        keys=["j", "e", "n", "n", "i", "e", "UGLY", " "],
    )
    result = await forest_mod.forest(ctx)
    assert result is None
    assert ctx.player.hp == 1
    assert ctx.player.alive == 0
