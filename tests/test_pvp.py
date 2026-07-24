"""PvP (Slaughter Other Players) scene tests -- see
pylord/engine/scenes/pvp.py's module docstring for lord.js line-number
citations behind every formula/message ported here. Follows
tests/test_training.py's/tests/test_forest.py's established style: a local
``_SeqRNG`` to pin deterministic combat rolls, and direct calls into the
scene module's private helpers (``_slaughter``, ``_list``) alongside its
public engine entry points (``find_attackable``, ``run_attack``)."""

from __future__ import annotations

from pylord import db
from pylord.engine.game import GameCtx
from pylord.engine.scenes import inn as inn_mod
from pylord.engine.scenes import pvp as pvp_mod
from pylord.models import PlayerRepo
from pylord.terminal import FakeIO
from tests.harness import play, screen


class _SeqRNG:
    """See tests/test_forest.py's identical helper for rationale."""

    def __init__(self, values):
        self._values = list(values)

    def randrange(self, _n):
        return self._values.pop(0)


def _two_players(attacker_overrides=None, target_overrides=None):
    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)
    attacker = repo.create("Hero", "pw", "M")
    for key, value in (attacker_overrides or {}).items():
        setattr(attacker, key, value)
    repo.save(attacker)

    target = repo.create("Victim", "pw", "F")
    for key, value in (target_overrides or {}).items():
        setattr(target, key, value)
    repo.save(target)
    return conn, repo, attacker, target


def _ctx(conn, repo, player, keys):
    return GameCtx(player=player, repo=repo, io=FakeIO(keys), conn=conn)


# --- End-to-end smoke test -------------------------------------------------


async def test_pvp_menu_reachable_from_town():
    io, _player = await play(["s", "r"])
    text = screen(io)
    assert "Slaughter Other Players" in text


# --- (L)ist Warriors: excludes self/online/dead/sleeping --------------------


async def test_list_excludes_self_online_dead_and_sleeping():
    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)
    me = repo.create("Hero", "pw", "M")
    online = repo.create("Onliner", "pw", "M")
    online.online = 1
    repo.save(online)
    dead = repo.create("Deadman", "pw", "M")
    dead.alive = 0
    repo.save(dead)
    sleeping = repo.create("Sleeper", "pw", "M")
    sleeping.at_inn = 1
    repo.save(sleeping)
    attackable = repo.create("Attackable", "pw", "M")
    attackable.exp = 500
    repo.save(attackable)

    ctx = _ctx(conn, repo, me, ["x"])
    await pvp_mod._list(ctx)
    text = screen(ctx.io)

    assert "Attackable" in text
    assert "Hero" not in text
    assert "Onliner" not in text
    assert "Deadman" not in text
    assert "Sleeper" not in text


# --- (S)laughter -- field-flow eligibility checks ---------------------------


async def test_slaughter_self_exclusion():
    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)
    me = repo.create("Hero", "pw", "M")
    ctx = _ctx(conn, repo, me, ["Hero", "y", "x"])
    await pvp_mod._slaughter(ctx)
    assert "wish to attack yourself" in screen(ctx.io)


async def test_slaughter_dead_target_refused():
    conn, repo, attacker, _target = _two_players(target_overrides={"alive": 0})
    ctx = _ctx(conn, repo, attacker, ["Victim", "y", "x"])
    died = await pvp_mod._slaughter(ctx)
    assert died is False
    assert "rotting corpse" in screen(ctx.io)


async def test_slaughter_sleeping_target_refused():
    conn, repo, attacker, _target = _two_players(target_overrides={"at_inn": 1})
    ctx = _ctx(conn, repo, attacker, ["Victim", "y", "x"])
    died = await pvp_mod._slaughter(ctx)
    assert died is False
    assert "staying at the Inn" in screen(ctx.io)


async def test_slaughter_no_match_shows_message():
    conn, repo, attacker, _target = _two_players()
    ctx = _ctx(conn, repo, attacker, ["Nobody Here", "x"])
    died = await pvp_mod._slaughter(ctx)
    assert died is False
    assert "No warriors found" in screen(ctx.io)


async def test_slaughter_decline_confirm_does_not_fight():
    conn, repo, attacker, _target = _two_players()
    ctx = _ctx(conn, repo, attacker, ["Victim", "y", "n"])
    died = await pvp_mod._slaughter(ctx)
    assert died is False
    assert conn.execute("SELECT COUNT(*) c FROM mail").fetchone()["c"] == 0


# --- run_attack() -- shared engine checks -----------------------------------


async def test_zero_player_fights_refuses_without_a_fight():
    conn, repo, attacker, target = _two_players(attacker_overrides={"player_fights": 0})
    ctx = _ctx(conn, repo, attacker, ["x"])
    died = await pvp_mod.run_attack(ctx, target, from_inn=False)
    assert died is False
    assert ctx.player.player_fights == 0
    assert "too tired" in screen(ctx.io)


async def test_online_target_blocked_and_costs_no_attempt():
    conn, repo, attacker, target = _two_players(target_overrides={"online": 1})
    ctx = _ctx(conn, repo, attacker, ["x"])
    died = await pvp_mod.run_attack(ctx, target, from_inn=False)
    assert died is False
    assert ctx.player.player_fights == 3  # unchanged -- checked before decrement
    assert "currently online" in screen(ctx.io)


async def test_run_away_costs_a_fight_but_sends_no_mail_or_news():
    conn, repo, attacker, target = _two_players()
    ctx = _ctx(conn, repo, attacker, ["r", "x"])
    ctx.rng = _SeqRNG([0])  # randrange(9) -> 0, != 1: run succeeds
    died = await pvp_mod.run_attack(ctx, target, from_inn=False)
    assert died is False
    assert ctx.player.player_fights == 2  # still decremented once
    assert conn.execute("SELECT COUNT(*) c FROM mail").fetchone()["c"] == 0
    assert conn.execute("SELECT COUNT(*) c FROM daily_news").fetchone()["c"] == 0


# --- run_attack() -- win: exact gold/exp/gem transfer + news + mail --------


async def test_win_transfers_exact_gold_exp_gems_and_writes_news_and_mail():
    """One-shot kill: attacker str=2000 so attack_damage's floor(str/2)=1000
    dominates the 5-hp target regardless of the roll.
        randrange(1000) -> 0   (attack_damage's base roll -> dmg = 1000)
        randrange(10)   -> 0   (crit-move roll, 0+1=1, not > 9)
    """
    conn, repo, attacker, target = _two_players(
        attacker_overrides={"strength": 2000, "gold": 500, "exp": 1},
        target_overrides={
            "hp": 5, "hp_max": 5, "defense": 0,
            "gold": 777, "exp": 1000, "gems": 10,
        },
    )
    ctx = _ctx(conn, repo, attacker, ["a", "x"])
    ctx.rng = _SeqRNG([0, 0])

    died = await pvp_mod.run_attack(ctx, target, from_inn=False)
    assert died is False

    assert ctx.player.gold == 500 + 777
    assert ctx.player.exp == 1 + 500  # + floor(1000 / 2)
    assert ctx.player.gems == 5  # + floor(10 / 2)
    assert ctx.player.player_fights == 2

    reloaded = repo.get(target.id)
    assert reloaded.alive == 0
    assert reloaded.at_inn == 0
    assert reloaded.gold == 0
    assert reloaded.gems == 5  # 10 - floor(10 / 2)
    assert reloaded.exp == 900  # 1000 - floor(1000 / 10)

    news_row = conn.execute("SELECT text FROM daily_news").fetchone()
    assert news_row is not None
    assert "Hero" in news_row["text"]
    assert "has killed" in news_row["text"]
    assert "Victim" in news_row["text"]

    mail_row = conn.execute(
        "SELECT to_id, from_name, text, effect, read FROM mail"
    ).fetchone()
    assert mail_row["to_id"] == target.id
    assert mail_row["from_name"] == "Hero"
    assert "YOU HAVE BEEN ATTACKED" in mail_row["text"]
    assert "has killed you" in mail_row["text"]
    assert mail_row["effect"] is None
    assert mail_row["read"] == 0


async def test_win_gold_capped_at_two_billion():
    conn, repo, attacker, target = _two_players(
        attacker_overrides={"strength": 2000, "gold": 1_999_999_999},
        target_overrides={"hp": 5, "hp_max": 5, "defense": 0, "gold": 50},
    )
    ctx = _ctx(conn, repo, attacker, ["a", "x"])
    ctx.rng = _SeqRNG([0, 0])
    await pvp_mod.run_attack(ctx, target, from_inn=False)
    assert ctx.player.gold == 2_000_000_000


# --- run_attack() -- loss: attacker dies, victim credited synchronously ----


async def test_loss_kills_attacker_and_credits_victim_directly():
    """Attacker deals 0 damage (str=0 -> attack_damage's base roll floors at
    0, guaranteed miss, no rng draw) while the target (str=2000) one-shots a
    5-hp attacker back. Draw order for a single "a" press:
        randrange(10) -> 0   (attacker's crit-move roll on the miss)
        randrange(1000) -> 0 (target's base roll, half=1000 -> 1000 damage)
        randrange(30) -> 0   (target's power-move check, != 1: no boost)
    """
    conn, repo, attacker, target = _two_players(
        attacker_overrides={
            "strength": 0, "defense": 0, "hp": 5, "hp_max": 5,
            "gold": 500, "exp": 1000,
        },
        target_overrides={"strength": 2000, "defense": 0, "hp": 50, "hp_max": 50, "exp": 20},
    )
    ctx = _ctx(conn, repo, attacker, ["a", "x"])
    ctx.rng = _SeqRNG([0, 0, 0])

    died = await pvp_mod.run_attack(ctx, target, from_inn=False)
    assert died is True

    assert ctx.player.gold == 0
    assert ctx.player.exp == 900  # 1000 - floor(1000/10)
    assert ctx.player.alive == 0
    assert ctx.player.player_fights == 2

    reloaded = repo.get(target.id)
    assert reloaded.exp == 20 + 450  # + floor(900 / 2), using attacker's *post*-penalty exp
    assert reloaded.hp == 50  # attacker's swing missed outright

    news_row = conn.execute("SELECT text FROM daily_news").fetchone()
    assert news_row is not None
    assert "Victim" in news_row["text"]
    assert "self defence" in news_row["text"]

    mail_row = conn.execute("SELECT text, effect FROM mail").fetchone()
    assert "YOU HAVE BEEN ATTACKED" in mail_row["text"]
    assert "self defense" in mail_row["text"]
    assert "450" in mail_row["text"]
    assert mail_row["effect"] is None

    assert "You have been killed by Victim" in screen(ctx.io)
    assert "GOLD ON HAND WAS" in screen(ctx.io)


# --- Inn bribe-attack path (inn.py's TODO from Task 13a) --------------------


async def test_inn_sneak_attack_kills_sleeping_target_and_spends_bribe():
    conn, repo, attacker, target = _two_players(
        attacker_overrides={"level": 5, "strength": 2000, "gold": 100_000},
        target_overrides={
            "level": 5, "at_inn": 1, "hp": 5, "hp_max": 5,
            "strength": 0, "defense": 0, "gold": 250, "exp": 40,
        },
    )
    keys = ["y", "s", "Victim", "y", "y", "x", "a", "x"]
    ctx = _ctx(conn, repo, attacker, keys)
    ctx.rng = _SeqRNG([0, 0, 0])  # 2 combat draws + 1 weapon-steal-chance draw (misses)

    died = await inn_mod._bribe_attack(ctx)
    assert died is False

    bribe_cost = 5 * 1600
    assert ctx.player.gold == 100_000 - bribe_cost + 250

    reloaded = repo.get(target.id)
    assert reloaded.alive == 0
    assert reloaded.at_inn == 0

    rows = conn.execute(
        "SELECT text FROM mail WHERE to_id = ? ORDER BY id", (target.id,)
    ).fetchall()
    assert len(rows) == 2
    assert "broken into your room" in rows[0]["text"]
    assert "has killed you" in rows[1]["text"]


async def test_inn_bribe_declined_refunds_nothing_and_costs_nothing():
    conn, repo, attacker, _target = _two_players(attacker_overrides={"gold": 5000})
    ctx = _ctx(conn, repo, attacker, ["n", "x"])
    died = await inn_mod._bribe_attack(ctx)
    assert died is False
    assert ctx.player.gold == 5000


async def test_inn_bribe_insufficient_gold_refused():
    conn, repo, attacker, _target = _two_players(attacker_overrides={"level": 5, "gold": 1})
    ctx = _ctx(conn, repo, attacker, ["y", "x"])
    died = await inn_mod._bribe_attack(ctx)
    assert died is False
    assert ctx.player.gold == 1
    assert "don't have that much gold" in screen(ctx.io)


async def test_inn_bribe_level_gate_refuses_much_weaker_target():
    conn, repo, attacker, _target = _two_players(
        attacker_overrides={"level": 10, "gold": 100_000},
        target_overrides={"level": 5, "at_inn": 1},
    )
    ctx = _ctx(conn, repo, attacker, ["y", "s", "Victim", "y", "x", "r", "x"])
    died = await inn_mod._bribe_attack(ctx)
    assert died is False
    assert "A child could beat that wimp" in screen(ctx.io)


async def test_inn_bribe_return_refunds_half():
    conn, repo, attacker, _target = _two_players(
        attacker_overrides={"level": 2, "gold": 100_000}
    )
    ctx = _ctx(conn, repo, attacker, ["y", "r", "x"])
    died = await inn_mod._bribe_attack(ctx)
    assert died is False
    cost = 2 * 1600
    refund = 800 * (2 * 2)
    assert ctx.player.gold == 100_000 - cost + refund
