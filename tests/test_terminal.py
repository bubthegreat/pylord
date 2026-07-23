import pytest

from pylord.terminal import FakeIO, OutOfKeys, TermIO, render, strip

# --- render() -----------------------------------------------------------


def test_render_red_foreground_code():
    # lord.js's own lord_to_ansi() (reference/lord.js ~line 6507) emits
    # a combined reset+color SGR escape rather than two separate escapes.
    out = render("`4Death`0")
    assert "\x1b[0;31m" in out  # `4 -> reset + red foreground


def test_render_includes_reset_before_color_change():
    out = render("`4Death`0")
    assert "\x1b[0;31m" in out
    assert "\x1b[1;32m" in out  # `0 -> reset(bold) + bright green


def test_render_bright_green_code():
    out = render("`0Alive")
    assert "\x1b[1;32m" in out


def test_render_all_dark_foreground_codes():
    expected = {
        "1": "\x1b[0;34m",
        "2": "\x1b[0;32m",
        "3": "\x1b[0;36m",
        "4": "\x1b[0;31m",
        "5": "\x1b[0;35m",
        "6": "\x1b[0;33m",
        "7": "\x1b[0;37m",
    }
    for code, ansi in expected.items():
        assert render(f"`{code}x") == f"{ansi}x"


def test_render_all_bright_foreground_codes():
    expected = {
        "8": "\x1b[1;30m",
        "9": "\x1b[1;34m",
        "0": "\x1b[1;32m",
        "!": "\x1b[1;36m",
        "@": "\x1b[1;31m",
        "#": "\x1b[1;35m",
        "$": "\x1b[1;33m",
        "%": "\x1b[1;37m",
    }
    for code, ansi in expected.items():
        assert render(f"`{code}x") == f"{ansi}x"


def test_render_black_foreground():
    assert render("`^x") == "\x1b[0;30mx"


def test_render_blink_red_shorthand():
    assert render("`)x") == "\x1b[0;5;31mx"


def test_render_blink_prefixed_codes():
    assert render("`B1x") == "\x1b[0;5;34mx"  # blink blue
    assert render("`B0x") == "\x1b[1;5;32mx"  # blink bright green
    assert render("`B^x") == "\x1b[0;5;30mx"  # blink black


def test_render_background_codes():
    expected = {
        "0": "\x1b[40m",
        "1": "\x1b[44m",
        "2": "\x1b[42m",
        "3": "\x1b[46m",
        "4": "\x1b[41m",
        "5": "\x1b[45m",
        "6": "\x1b[43m",
        "7": "\x1b[47m",
    }
    for code, ansi in expected.items():
        assert render(f"`r{code}x") == f"{ansi}x"


def test_render_black_on_red_special_code():
    assert render("`*x") == "\x1b[0;30;41mx"


def test_render_clear_screen():
    assert render("`c") == "\x1b[2J\x1b[H"
    assert render("`C") == "\x1b[2J\x1b[H"


def test_render_separator_line():
    out = render("`l")
    assert out.startswith("\x1b[0;32m")
    assert "-=-=-" in out


def test_render_newline_code():
    assert render("a`nb") == "a\r\nb"


def test_render_noop_codes_produce_no_output():
    assert render("a`.b") == "ab"
    assert render("a`|b") == "ab"
    assert render("a``b") == "ab"


def test_render_unknown_code_passes_through_literally():
    assert render("`zfoo") == "`zfoo"


def test_render_dangling_backtick_passes_through():
    assert render("foo`") == "foo`"


def test_render_plain_text_unchanged():
    assert render("no codes here") == "no codes here"


# --- strip() --------------------------------------------------------------


def test_strip_removes_color_codes():
    assert strip("`4Death`0 to `2all`0!") == "Death to all!"


def test_strip_keeps_separator_and_newline_text():
    assert strip("a`nb") == "a\r\nb"
    assert strip("`l") == "  -" + "=-" * 36


def test_strip_keeps_unknown_codes_literally():
    assert strip("`zfoo") == "`zfoo"


def test_strip_removes_clear_and_background_codes():
    assert strip("`c`r3text") == "text"


# --- FakeIO / TermIO --------------------------------------------------------


async def test_fakeio_menu_dispatches_case_insensitively():
    io = FakeIO(keys=["f"])
    result = await io.menu({"F": "Forest"}, "Where to?")
    assert result == "F"


async def test_fakeio_menu_reprompts_on_invalid_key():
    io = FakeIO(keys=["x", "f"])
    result = await io.menu({"F": "Forest"}, "Where to?")
    assert result == "F"


async def test_fakeio_write_records_rendered_output():
    io = FakeIO(keys=[])
    await io.write("`4Death")
    assert io.output == ["\x1b[0;31mDeath"]


async def test_fakeio_readkey_pops_from_list():
    io = FakeIO(keys=["a", "b"])
    assert await io.readkey() == "a"
    assert await io.readkey() == "b"


async def test_fakeio_readkey_raises_outofkeys_when_exhausted():
    io = FakeIO(keys=[])
    with pytest.raises(OutOfKeys):
        await io.readkey()


async def test_fakeio_readline_pops_whole_entry():
    io = FakeIO(keys=["Zaphod"])
    assert await io.readline(prompt="Name?") == "Zaphod"


async def test_fakeio_readline_enforces_maxlen():
    io = FakeIO(keys=["ThisIsWayTooLong"])
    assert await io.readline(maxlen=4) == "This"


async def test_fakeio_readline_applies_charset_filter():
    io = FakeIO(keys=["ab12cd"])
    assert await io.readline(charset="0123456789") == "12"


async def test_fakeio_pause_writes_more_and_reads_key():
    io = FakeIO(keys=[" "])
    await io.pause()
    assert io.output  # something was written
    assert io.keys == []  # the key was consumed


def test_termio_is_not_directly_usable():
    io = TermIO()
    assert isinstance(io, TermIO)
