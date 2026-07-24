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
    io, _player = await play(["v", "q"])
    text = screen(io)
    assert "Fists" in text
    assert "Nothing!" in text


async def test_unknown_key_reprompts_then_accepts_valid_key():
    _io, player = await play(["z", "q"])
    # No exception raised, and quit still completed the session cleanly.
    assert player.name == "Tester"


async def test_stub_scene_shows_under_construction_and_returns_to_town():
    io, _player = await play(["s", "q"])
    text = screen(io)
    assert "Under construction" in text
    assert text.count("Town Square") == 2


async def test_every_stub_destination_reachable():
    # K/A/H/T/Y are real scenes now (Task 11: shops, healer, bank, training).
    stub_keys = ["s", "i", "l", "w", "d", "c", "o", "x"]
    for key in stub_keys:
        io, _player = await play([key, "q"])
        assert "Under construction" in screen(io)
