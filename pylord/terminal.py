"""LORD backtick color codes -> ANSI, and a small terminal I/O abstraction.

The color table below is ported from ``reference/lord.js``. lord.js actually
contains *two* independent implementations of backtick-code handling:

1. ``lord_to_ansi(str)`` (reference/lord.js ~line 6482) - already translates
   backtick codes directly to ANSI SGR escape sequences. This is the
   authoritative source for the plain foreground codes (`` `1``-`` `9``,
   `` `0``, `` `!``-`` `%``), the special `` `* `` code, and `` `c``.
2. ``lw(str, ext)`` (reference/lord.js ~line 3784), used by the Synchronet
   front-end, which sets a DOS-style single-byte console attribute via
   ``foreground(col)``/``background(col)`` (reference/lord.js lines
   2138-2152) rather than emitting ANSI directly. This is the source for
   codes that ``lord_to_ansi`` does not implement at all: `` `^`` (black
   foreground), `` `)`` and `` `B1``-`` `B9``/`` `B!``-`` `B%``/`` `B^``
   (blink variants - bit 0x80 of the DOS attribute byte), `` `l`` (green
   "-=-=-" separator line), `` `n`` (conditional newline), double backtick
   (inline "wait for keypress"), `` `.`` (no-op placeholder) and `` `|``
   (mail-queue file cleanup side effect).

Both were ported here into one merged table so `render()` supports every
code either function recognizes.

Divergences from lord.js (all intentional, all documented here per the
task's "document any codes lord.js supports that you map differently"
requirement):

* Background codes `` `r0``-`` `r7``: the literal ``lord_to_ansi`` source has
  a bug - it maps `` `r3``/`` `r6``/`` `r7`` to ANSI 43/47/46 (yellow/white/
  cyan) instead of the correct 46/43/47 (cyan/yellow/white). This is provably
  a transcription bug and not intentional: lord.js's *foreground* table
  deliberately re-orders CGA color indices to their correct ANSI
  equivalents everywhere else (e.g. CGA index 1 = blue -> ANSI 34, not
  ANSI "31+1"), and the separate DOS ``background(col)`` function used by
  ``lw()`` implies the same intended CGA->ANSI order as the foreground
  table. We port the *corrected* mapping (`` `r3``->46 cyan, `` `r6``->43
  yellow, `` `r7``->47 white/gray). Separately, in the original JS the
  `` `r`` sub-switch itself compares against bare numeric literals
  (``case 0:`` instead of ``case '0':``) against a string operand, so with
  strict ``===`` those cases can never match at all - the branch is dead
  code in the reference. We implement the clearly-intended behavior rather
  than replicate that bug.
* Every recognized color code emits a leading ``\\x1b[0m``-style reset as
  part of its own escape (matching ``lord_to_ansi``'s ``\\x1b[0;NNm``
  style) rather than lord.js's persistent single DOS attribute byte, where
  setting the foreground leaves an independently-set background bit alone
  (and vice-versa). Because ANSI SGR state is additive rather than a
  single mutable byte, faithfully reproducing "foreground and background
  persist independently across codes" would require ``render()`` to carry
  state across calls. Each code is self-contained here for simplicity and
  to avoid attribute bleed across separate ``write()`` calls; the
  documented cost is that a background set by an earlier code is cleared
  by a later foreground code (and vice versa), which does not happen in
  the original DOS-attribute model.
* `` `c`` maps only to ``\\x1b[2J\\x1b[H`` (per this project's interface
  spec). In lord.js, `` `c`` *additionally* prints two blank lines after
  clearing (`` `C`` does not). We treat `` `c``/`` `C`` identically.
* `` `n`` always emits ``\\r\\n``. In lord.js it is conditional on the
  current cursor column vs. terminal width, which render() (a pure text
  function with no cursor-position state) cannot know.
* Double backtick ("` `` `") blocks on a keypress in lord.js and prints
  nothing. render() has no I/O access, so it also prints nothing but does
  not block; actual key-waiting belongs to ``TermIO.readkey()``/``pause()``.
* Unknown/unrecognized codes: both lord.js functions silently *drop* any
  backtick code they don't recognize (the character is consumed with no
  output). Per this project's interface spec, ``render()`` instead passes
  unknown codes through literally (backtick + following character
  unchanged), to aid debugging malformed text.
"""

from __future__ import annotations

import asyncio
import re
import time
from abc import ABC

CLEAR_SEQ = "\x1b[2J\x1b[H"

_LINE_TEXT = (
    "  -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-"
)
_LINE_ANSI = "\x1b[0;32m"

# Plain, single-character foreground/special codes. Ported from
# lord_to_ansi() plus `^`/`)`/`*` from lw()'s foreground()/DOS-attribute
# translation (see module docstring).
_SIMPLE_CODES: dict[str, str] = {
    "1": "\x1b[0;34m",  # blue
    "2": "\x1b[0;32m",  # green
    "3": "\x1b[0;36m",  # cyan
    "4": "\x1b[0;31m",  # red
    "5": "\x1b[0;35m",  # magenta
    "6": "\x1b[0;33m",  # yellow / brown
    "7": "\x1b[0;37m",  # white / light grey
    "8": "\x1b[1;30m",  # dark grey (bright black)
    "9": "\x1b[1;34m",  # bright blue
    "0": "\x1b[1;32m",  # bright green
    "!": "\x1b[1;36m",  # bright cyan
    "@": "\x1b[1;31m",  # bright red
    "#": "\x1b[1;35m",  # bright magenta
    "$": "\x1b[1;33m",  # bright yellow
    "%": "\x1b[1;37m",  # bright white
    "^": "\x1b[0;30m",  # black
    ")": "\x1b[0;5;31m",  # blink red (shorthand for `B4)
    "*": "\x1b[0;30;41m",  # black on red
}

# Two-char `Bx codes: blink variants of the foreground table above.
# Ported from lw()'s foreground(17..31) branch (0x80 blink bit + color).
_BLINK_CODES: dict[str, str] = {
    "1": "\x1b[0;5;34m",
    "2": "\x1b[0;5;32m",
    "3": "\x1b[0;5;36m",
    "4": "\x1b[0;5;31m",
    "5": "\x1b[0;5;35m",
    "6": "\x1b[0;5;33m",
    "7": "\x1b[0;5;37m",
    "8": "\x1b[1;5;30m",
    "9": "\x1b[1;5;34m",
    "0": "\x1b[1;5;32m",
    "!": "\x1b[1;5;36m",
    "@": "\x1b[1;5;31m",
    "#": "\x1b[1;5;35m",
    "$": "\x1b[1;5;33m",
    "%": "\x1b[1;5;37m",
    "^": "\x1b[0;5;30m",
}

# Two-char `rx codes: background colors. Corrected order - see module
# docstring for the bug in lord.js's literal lord_to_ansi() r-switch.
_BG_CODES: dict[str, str] = {
    "0": "\x1b[40m",
    "1": "\x1b[44m",
    "2": "\x1b[42m",
    "3": "\x1b[46m",
    "4": "\x1b[41m",
    "5": "\x1b[45m",
    "6": "\x1b[43m",
    "7": "\x1b[47m",
}


def _tokens(text: str) -> list[tuple[str, str, str]]:
    """Parse text into (kind, ansi, literal) tuples.

    kind is one of:
      "text"    - literal, non-code text; ansi is '', literal is the run.
      "code"    - recognized backtick code; ansi is the escape sequence
                  (may be ''), literal is the displayed text (may be '').
      "unknown" - unrecognized/dangling backtick code; ansi is '', literal
                  is the raw source text to pass through unchanged.
    """
    out: list[tuple[str, str, str]] = []
    buf: list[str] = []
    i = 0
    n = len(text)

    def flush() -> None:
        if buf:
            out.append(("text", "", "".join(buf)))
            buf.clear()

    while i < n:
        ch = text[i]
        if ch != "`":
            buf.append(ch)
            i += 1
            continue

        flush()

        if i + 1 >= n:
            out.append(("unknown", "", "`"))
            i += 1
            continue

        code = text[i + 1]

        if code == "B" and i + 2 < n and text[i + 2] in _BLINK_CODES:
            out.append(("code", _BLINK_CODES[text[i + 2]], ""))
            i += 3
            continue

        if code == "r" and i + 2 < n and text[i + 2] in _BG_CODES:
            out.append(("code", _BG_CODES[text[i + 2]], ""))
            i += 3
            continue

        if code in _SIMPLE_CODES:
            out.append(("code", _SIMPLE_CODES[code], ""))
            i += 2
            continue

        if code in ("c", "C"):
            out.append(("code", CLEAR_SEQ, ""))
            i += 2
            continue

        if code == "l":
            out.append(("code", _LINE_ANSI, _LINE_TEXT))
            i += 2
            continue

        if code == "n":
            out.append(("code", "", "\r\n"))
            i += 2
            continue

        if code in ("`", ".", "|"):
            out.append(("code", "", ""))
            i += 2
            continue

        out.append(("unknown", "", "`" + code))
        i += 2

    flush()
    return out


def render(text: str) -> str:
    """Render LORD backtick codes in ``text`` to ANSI escape sequences."""
    pieces = []
    for kind, ansi, literal in _tokens(text):
        pieces.append(ansi + literal if kind == "code" else literal)
    return "".join(pieces)


def strip(text: str) -> str:
    """Remove all LORD backtick codes from ``text``, leaving plain text."""
    return "".join(literal for _kind, _ansi, literal in _tokens(text))


_DEFAULT_RE = re.compile(r"\[([A-Za-z0-9])\]")


def _default_from_prompt(prompt: str) -> str | None:
    """The key a prompt advertises as its default: the last ``[X]`` in it,
    read after colour codes are stripped (screens write ``[`0Y`2]``)."""
    matches = _DEFAULT_RE.findall(strip(prompt))
    return matches[-1] if matches else None


class OutOfKeys(Exception):
    """Raised by FakeIO when a scripted input queue is exhausted."""


class ConnectionClosed(Exception):
    """Raised by TelnetIO when the peer has disconnected mid-read.

    This is TelnetIO's counterpart to FakeIO's ``OutOfKeys``: both signal
    "no more input is coming" to callers (menu()/pause()/scene code) rather
    than silently synthesizing a blank line or keypress.
    """


class TermIO(ABC):
    """Abstract-ish base for terminal I/O. Concrete subclasses implement
    write/readkey/readline; pause() and menu() are built from those."""

    async def write(self, text: str) -> None:
        raise NotImplementedError

    async def readline(
        self, prompt: str = "", maxlen: int = 40, charset: str | None = None
    ) -> str:
        raise NotImplementedError

    async def readkey(self) -> str:
        raise NotImplementedError

    async def pause(self) -> None:
        """Show a "MORE" prompt and wait for a keypress."""
        await self.write("`2<`0MORE`2>")
        await self.readkey()

    #: True when the client is character-at-a-time, so a CR really is the
    #: player pressing Enter (see TelnetIO.char_mode).
    char_mode = True

    async def menu(
        self, options: dict[str, str], prompt: str, default: str | None = None
    ) -> str:
        """Single-key, case-insensitive dispatch. Re-prompts on invalid keys.

        Returns the matching key exactly as given in ``options`` (not the
        raw pressed key, which may differ in case).

        **Enter takes the default.** lord.js writes the default into the
        prompt in brackets and maps anything else onto it (e.g.
        ``ch = getkey(); if (ch !== 'N') ch = 'Y';`` behind ``[Y]``,
        reference/lord.js:16856-16863). ``default`` names the key
        explicitly; when omitted it is read from the last ``[X]`` in the
        prompt, which is where every ported screen already advertises it.

        A CR from a *line-mode* client is not a keypress -- it's the tail
        of the line whose first character answered the previous prompt
        (Mudlet sends "t\r\n") -- so Enter is only honoured when the
        client negotiated character-at-a-time. Otherwise it is swallowed,
        as before, or every prompt would fire its own default.
        """
        lookup = {key.upper(): key for key in options}
        if default is None:
            default = _default_from_prompt(prompt)
        default_key = lookup.get(default.upper()) if default else None

        if prompt:
            await self.write(prompt)
        while True:
            pressed = (await self.readkey()).upper()
            if pressed in lookup:
                return lookup[pressed]
            if pressed in ("\r", "\n"):
                if default_key is not None and self.char_mode:
                    return default_key
                continue
            if prompt:
                await self.write(prompt)


class FakeIO(TermIO):
    """Scripted TermIO for tests. Pops from ``keys`` for both readkey() and
    readline(); records every write() call's RENDERED text in ``output``."""

    def __init__(self, keys: list[str]):
        self.keys: list[str] = list(keys)
        self.output: list[str] = []

    async def write(self, text: str) -> None:
        self.output.append(render(text))

    async def readkey(self) -> str:
        if not self.keys:
            raise OutOfKeys("FakeIO ran out of scripted keys")
        return self.keys.pop(0)

    async def readline(
        self, prompt: str = "", maxlen: int = 40, charset: str | None = None
    ) -> str:
        if prompt:
            await self.write(prompt)
        if not self.keys:
            raise OutOfKeys("FakeIO ran out of scripted keys")
        value = self.keys.pop(0)
        if charset is not None:
            value = "".join(c for c in value if c in charset)
        return value[:maxlen]


class TelnetIO(TermIO):
    """TermIO backed by a telnetlib3 (reader, writer) pair.

    **Input pacing.** A held-down key sends a continuous stream, and every
    keypress here can mean a database write (a fight, a dig, a purchase).
    A token bucket paces reads: a burst is free, then input is admitted at
    ``INPUT_RATE`` keys a second. It costs an idle player nothing -- the
    bucket is always full when you are reading the screen -- but it stops
    one session monopolising the process, which matters on a realm open to
    the internet.
    """

    #: Sustained keypresses per second once the burst allowance is spent.
    #: Comfortably above a held key's repeat rate (~30/s) so holding Enter
    #: to keep hunting is never slowed; it exists to bound a script that
    #: floods thousands a second.
    INPUT_RATE = 60.0
    #: Keys that may be sent instantly before pacing applies.
    INPUT_BURST = 90.0

    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self._tokens = self.INPUT_BURST
        self._last_refill = time.monotonic()
        # Set right after a raw read returns "\r": a CRLF-style Enter
        # arrives over the wire as two separate reads ("\r" then "\n"), so
        # the very next raw read must swallow a leading "\n" instead of
        # misreading it as an already-terminated blank line/keypress. See
        # _raw_read()'s docstring for the bug this fixes.
        self._swallow_lf = False

    async def _throttle(self) -> None:
        """Spend one token, waiting for it if the bucket has run dry."""
        now = time.monotonic()
        self._tokens = min(
            self.INPUT_BURST,
            self._tokens + (now - self._last_refill) * self.INPUT_RATE,
        )
        self._last_refill = now
        if self._tokens < 1.0:
            await asyncio.sleep((1.0 - self._tokens) / self.INPUT_RATE)
            self._tokens = 1.0
        self._tokens -= 1.0

    async def _raw_read(self) -> str:
        """Read one character, applying CRLF-swallowing and EOF handling.

        Bug fixed here (found while writing this task's integration tests --
        TelnetIO was previously untested against a real telnetlib3 reader):
        a client's Enter key normally arrives as two bytes, "\\r\\n". The old
        code read only one byte per readline()/readkey() call, so the "\\n"
        left over from an Enter was seen as the *start* of the next
        readline()/readkey() call and immediately treated as "nothing
        typed" -- every other line of input from a real telnet client was
        silently swallowed. This also compounds with a second bug: on a
        genuine disconnect, ``reader.read(1)`` returns ``""`` forever
        without blocking, so the old ``readline()``/``menu()`` treated EOF
        as an ordinary terminator/keypress and ``menu()`` would spin in a
        tight, non-blocking infinite loop re-reading "" forever. Both are
        fixed here: a lone "\\n" immediately following a "\\r" is consumed
        and not returned, and "" now raises ``ConnectionClosed`` so callers
        (readline/readkey/menu/pause and ultimately the server's
        connection handler) can unwind and clean up instead of spinning.
        """
        await self._throttle()
        ch = await self.reader.read(1)
        if self._swallow_lf:
            self._swallow_lf = False
            if ch == "\n":
                ch = await self.reader.read(1)
        if ch == "":
            raise ConnectionClosed("telnet connection closed by peer")
        if ch == "\r":
            self._swallow_lf = True
        return ch

    async def write(self, text: str) -> None:
        # Telnet requires CRLF line endings: a bare LF moves the cursor
        # down without returning to column 0, stair-stepping all output in
        # real clients. Normalize first so an already-CRLF string isn't
        # doubled into CR CR LF.
        self.writer.write(render(text).replace("\r\n", "\n").replace("\n", "\r\n"))

    @property
    def char_mode(self) -> bool:
        """True once the client has acknowledged WILL ECHO + WILL SGA, which
        telnetlib3 reports as "kludge" mode -- the character-at-a-time
        arrangement every BBS door expects (ttyd and real telnet clients do
        this; Mudlet-style line-mode clients stay "local")."""
        return getattr(self.writer, "mode", "local") == "kludge"

    async def readkey(self) -> str:
        return await self._raw_read()

    async def readline(
        self, prompt: str = "", maxlen: int = 40, charset: str | None = None
    ) -> str:
        if prompt:
            await self.write(prompt)
        chars: list[str] = []
        while True:
            ch = await self._raw_read()
            if ch in ("\r", "\n"):
                break
            if ch in ("\x08", "\x7f"):  # backspace / delete
                if chars:
                    chars.pop()
                    self.writer.write("\x08 \x08")
                continue
            if charset is not None and ch not in charset:
                continue
            if len(chars) >= maxlen:
                continue
            chars.append(ch)
            self.writer.write(ch)  # local echo
        return "".join(chars)
