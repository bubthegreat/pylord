"""Town Square + stats screen tests, driven through the full session loop
via tests/harness.py's play()."""

from __future__ import annotations

from tests.harness import play, screen


async def test_town_square_shows_menu_and_letters():
    io, _player = await play(["q"])
    text = screen(io)
    assert "Town Square" in text
    assert "(F)orest" in text
    assert "(Q)uit to fields" in text


async def test_quit_logs_off_without_error():
    _io, player = await play(["q"])
    assert player.name == "Tester"


async def test_view_stats_shows_name_level_and_returns_to_town():
    io, player = await play(["v", "q"])
    text = screen(io)
    assert player.name in text
    assert "Level" in text
    assert "Experience" in text
    # After stats + pause, control returns to the town square a 2nd time.
    assert text.count("Town Square") == 2


async def test_stats_shows_fists_and_nothing_for_unequipped_player():
    """A *new* character starts with a Stick and a Coat (reference/
    recorddefs.js:47-51, 136-141), so the unarmed display has to be set up
    explicitly (e.g. a player who sold their gear back to the shops)."""
    io, _player = await play(
        ["v", "q"], overrides={"weapon_num": 0, "armor_num": 0}
    )
    text = screen(io)
    assert "Fists" in text
    assert "Nothing!" in text


async def test_new_character_starts_with_stick_and_coat():
    """reference/recorddefs.js:46-56 (weapon_num def:1 / 'Stick') and
    :131-141 (arm_num def:1 / 'Coat')."""
    io, player = await play(["v", "q"])
    text = screen(io)
    assert player.weapon_num == 1 and player.armor_num == 1
    assert "Stick" in text
    assert "Coat" in text


async def test_unknown_key_reprompts_then_accepts_valid_key():
    _io, player = await play(["z", "q"])
    # No exception raised, and quit still completed the session cleanly.
    assert player.name == "Tester"


async def test_other_places_is_reachable_from_town():
    """reference/lord.js:17003-17077 -- Other Places is a Town Square key
    (it used to route to an "Under construction" stub here, leaving the
    IGM hub reachable only from a forest key lord.js doesn't have)."""
    io, _player = await play(["o", "x", "q", "y"])
    # No IGMs are wired into this session, so the hub says so and returns
    # to town rather than the old "Under construction" stub.
    assert "path is overgrown" in screen(io)


async def test_quit_asks_for_confirmation_and_says_goodbye():
    """reference/lord.js:16853-16871 (do_quit) and :16832-16841 (goodbye)."""
    io, _player = await play(["q", "n", "q", "y"])
    text = screen(io)
    assert "Quit game?" in text
    assert "Quitting To The Fields" in text
    assert text.count("Town Square") == 2  # the "n" put us back


async def test_new_town_keys_reach_their_scenes():
    """M/P/1/R -- reference/lord.js:17110, :17113, :17120, :16950."""
    io, _player = await play(["m", "n", "q", "y"])
    assert "Make Announcement?" in screen(io)

    io, _player = await play(["p", "x", "q", "y"])
    assert "Warriors in the Realm Now" in screen(io)

    io, _player = await play(["1", "x", "q", "y"])
    assert "GAME STATISTICS" in screen(io)

    io, _player = await play(["r", "x", "q", "y"])
    assert "You have no mail" in screen(io)


async def test_every_task_13b_destination_reachable():
    """S/X route to real scenes (not KeyError'ing on an unregistered name)
    and eventually land back at the Town Square."""
    io, _player = await play(["s", "r"])
    assert "Slaughter Other Players" in screen(io)

    io, _player = await play(["x", "x"])
    assert "not yet\n  strong enough" in screen(io)


async def test_every_task_13a_destination_reachable():
    """I/L/W/D/C route to real scenes (not KeyError'ing on an unregistered
    name) and eventually land back at the Town Square."""
    io, _player = await play(["i", "q"])
    assert "Red Dragon Inn" in screen(io)

    io, _player = await play(["l", "r"])
    assert "Player Rankings" in screen(io)

    io, _player = await play(["w", "nobody-matches", "x"])
    assert "No matching names found" in screen(io)

    io, _player = await play(["d", "c"])
    assert "Daily Happenings" in screen(io)

    io, _player = await play(["c", "x"])
    assert "CONJUGALITY LIST" in screen(io)


# --- Stats screen: the second half of show_stats() -------------------------


async def test_stats_shows_skills_class_and_family():
    """reference/lord.js:5842-5919 -- marriage, kids, horse, fairy, the
    per-track skill block, the class-interest line and the amulet."""
    io, _player = await play(
        ["v", "x", "q", "y"],
        overrides={
            "class_type": 2,
            "skill_my": 40,
            "skill_uses": 6,
            "kids": 2,
            "horse": 1,
            "has_fairy": 1,
            "amulet": 1,
        },
    )
    text = screen(io)
    assert "The Mystical Skills: MASTERED" in text
    assert "Uses Today: (6)" in text
    assert "You have 2 children." in text
    assert "You are on horseback." in text
    assert "fairy in your pocket" in text
    assert "currently interested in The Mystical" in text
    assert "Amulet of Accuracy" in text


async def test_stats_shows_npc_marriage():
    """reference/lord.js:5843-5852 -- the NPC marriages live in shared
    game state (pylord/engine/npc_state.py)."""
    from pylord import db
    from pylord.engine import npc_state
    from pylord.engine.game import GameCtx
    from pylord.engine.scenes.stats import stats as stats_scene
    from pylord.models import PlayerRepo
    from pylord.terminal import FakeIO

    conn = db.connect(":memory:")
    db.migrate(conn)
    repo = PlayerRepo(conn)
    player = repo.create("Hero", "pw", "M")
    npc_state.set_married_to_violet(conn, player.id)

    io = FakeIO([" "])
    await stats_scene(GameCtx(player=player, repo=repo, io=io, conn=conn))
    assert "married to Violet" in screen(io)
