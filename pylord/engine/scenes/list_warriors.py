"""List Warriors -- port of ``reference/lord.js``'s ``list_players()``
(``:16349-16361``), which just calls ``generate_rankings(f, true, true,
false)`` (``:6580-6689``) and displays the resulting file.

**Sort order**: lord.js's actual sort key is experience, descending
(``a.sort(function(a,b) { return b.exp - a.exp; })``, reference/lord.js:6612)
-- **not** level, despite this task's own brief describing the listing as
"ranked (level desc)". Per this project's established convention of lord.js
winning over an earlier brief's paraphrase (see e.g. ``docs/deviations.md``'s
several "An earlier draft of this task's brief guessed X -- lord.js's actual
behavior Y wins" rows), this port sorts by ``exp`` descending, exactly like
``generate_rankings()``. Noted again in ``docs/deviations.md``.

**Columns**: name (with `` `F` ``/class-letter prefix), experience, level,
"Mastered" (D/M/T flags for skill ranks over 19/39 -- reference/lord.js:
6651-6674, using this project's ``skill_dk``/``skill_my``/``skill_th`` in
place of lord.js's ``skillw``/``skillm``/``skillt``, same field mapping
established by ``forest.py``), and status (Dead/Alive, plus "On" if
currently ``online`` -- reference/lord.js:6676-6684).

**Hall of Honors submenu**: lord.js's own dragon-kill leaderboard
(``rank_king()``, reference/lord.js:15612-15647) is nested inside Turgon's
Training's `` `V`iew rankings`` (lord.js:15870-15881) -- a key this project's
``training.py`` deliberately doesn't implement (see its own module
docstring / ``docs/deviations.md``, "no (V)iew rankings"). That leaves no
existing town-square letter that reaches it, so per this task's brief
("expose via List Warriors submenu") this scene offers `` `H`all of
Honors`` as an extra key, routing to the standalone ``hall`` scene
(``hall.py``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylord.engine.game import scene

if TYPE_CHECKING:
    from pylord.engine.game import GameCtx
    from pylord.models import Player

_HEADER = (
    "\n\n  `%Legend Of The Red Dragon - Player Rankings`2\n"
    "  Name                    Experience    Level    Mastered    Status\n"
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
)

_CLASS_LETTER = {1: "D", 2: "M", 3: "T"}


def _mastery_flags(p: Player) -> str:
    out = []
    for field, letter in (
        ("skill_dk", "D"), ("skill_my", "M"), ("skill_th", "T"),
    ):
        rank = getattr(p, field)
        out.append(letter if rank > 19 else " ")
    return "".join(out)


def _row(p: Player) -> str:
    sex = "F" if p.gender == "F" else " "
    cls = _CLASS_LETTER.get(p.class_type, " ")
    status = "Dead " if not p.alive else "Alive"
    if p.online:
        status += "  On"
    return (
        f"  {sex} {cls} `2{p.name:<22}`2{p.exp:>13}    `%{p.level:>2}`2        "
        f"{_mastery_flags(p)}     `0{status}"
    )


@scene("list_warriors")
async def list_warriors(ctx: GameCtx) -> str:
    players = sorted(ctx.repo.all_players(), key=lambda p: p.exp, reverse=True)
    await ctx.io.write(_HEADER)
    for p in players:
        await ctx.io.write(_row(p) + "\n")
    choice = await ctx.io.menu(
        {"H": "hall", "R": "town"}, "\n  `2(`0H`2)all of Honors   (`0R`2)eturn : "
    )
    if choice == "H":
        return "hall"
    return "town"
