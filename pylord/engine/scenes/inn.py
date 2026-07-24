"""The Red Dragon Inn -- port of ``reference/lord.js``'s ``red_dragon_inn()``
(``:9894-10014``): flirting with Violet/Seth Able, the bard's song, room
rental, and the bartender.

**Top-level menu mapping** (lord.js:9930, ``(C,D,F,T,G,V,H,M,R)``\\ -- this
port keeps ``F``/``H``/``G``/``T``/``R`` and routes ``W``/``D``/``V`` to the
already-standalone ``mail``/``news``/``stats`` scenes (ending this Inn visit,
the same "detour scene always returns to town" simplification already
established by ``healer.py``/``stats.py`` -- see ``docs/deviations.md``).
``C`` (``converse()``, the "Dark Horse Tavern" gambling mini-game,
lord.js:8459-8574) and ``M`` (``announce()``, a free-text everyone-sees
broadcast, lord.js:9397-9432) are dropped entirely -- out of scope for this
task, no test coverage requested; ``C`` mirrors the same-spirit skip already
recorded for the Forest's ``darkhorse_tavern()`` random event
(``docs/deviations.md``).

**Daily gates, exactly**: this scene uses **two** separate daily-reset
booleans (both reset by ``pylord/engine/daily.py``, reference/lord.js:5437/
5429), not one. ``player.seen_violet`` gates the Violet/Seth Able flirt
*tiers* -- a single shared field lord.js reuses for both NPCs (male players
flirt with Violet, female players with Seth Able, see ``_flirt``/
``_bard_menu`` below). ``player.seen_bard`` is a wholly independent gate for
the bard *song* specifically (``_bard_song`` below, reference/lord.js's own
``bard_song()`` checks ``player.seen_bard``, never ``seen_violet``) -- a
player can hear today's song and still have their once-a-day flirt attempt
available, or vice versa. Neither is ``player.flirts_today``
(lord.js's ``player.flirted``), which gates a *different*, unrelated lord.js
mechanic -- the player-to-player "send romantic mail" flow inside
``compose_mail()`` (reference/lord.js:5012-5177) -- which this task's Mail
scene does not implement (see ``mail.py``'s module docstring); it is left
untouched here.

**NPC marriage** is global game state (one Violet, one Seth Able, shared by
every player), not a per-player field -- see ``pylord/engine/npc_state.py``.

**Bug fix, not a deviation**: lord.js's Violet ``kiss()`` success branch
assigns the exp reward to ``player.ext`` (reference/lord.js:9647), a
property that doesn't exist anywhere else in the codebase -- almost
certainly a `` `exp` `` typo, since the very same line's message text
promises "You receive N experience!" and every sibling tier (wink/peck/
sit/grab) correctly credits ``player.exp``. This port credits ``player.exp``
(via ``grant_exp``) as the text says it does.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pylord.engine import npc_state
from pylord.engine.game import grant_exp, scene

if TYPE_CHECKING:
    from pylord.engine.game import GameCtx

_ROOM_COST_PER_LEVEL = 400  # reference/lord.js:6395
_FREE_ROOM_CHARM = 99  # reference/lord.js:6410 (`player.cha > 99`)

_MENU = (
    "\n"
    "  `5The Red Dragon Inn   `8(? for menu)\n"
    "  `2(`0F`2)lirt   (`0H`2)ear The Bard   (`0G`2)et A Room   (`0T`2)alk To Barkeep\n"
    "  `2(`0W`2)rite Mail   (`0D`2)aily News   (`0V`2)iew Stats   (`0R`2)eturn\n"
)


@dataclass(frozen=True)
class _Tier:
    key: str
    label: str
    threshold: int
    exp_mult: int
    penalty_mult: int  # 0 == no HP penalty on failure (wink tier)
    action: str
    success: str
    fail: str


# reference/lord.js:9618-9739 (Violet, male players).
_VIOLET_TIERS = (
    _Tier(
        "W", "Wink", 1, 5, 0,
        "`%You wink at Violet seductively..",
        "`2She blushes and smiles!!  You are making progress with her!",
        "`4She dumps a tankard of ale on your head!!  The entire bar laughs "
        "at your misfortune!!",
    ),
    _Tier(
        "K", "Kiss", 2, 10, 1,
        "`%You take Violet's hand and kiss it!",
        "`2She pulls her hand away and laughs merrily!!  Your relationship "
        "with her is taking off!",
        "`2She pulls her hand away and slaps your face!  The entire bar "
        "laughs at your misfortune!!",
    ),
    _Tier(
        "P", "Peck", 4, 20, 3,
        "`%You attempt to meekly kiss her on the lips, but...",
        "`2She pulls you into a rough embrace, and kisses you soundly!!  "
        "You are elated!",
        "`2She pushes you away and kicks you in the shin!  The entire bar "
        "laughs at your misfortune!!",
    ),
    _Tier(
        "S", "Sit On Lap", 8, 30, 5,
        "`%You grab her and throw her on your lap...",
        "`2She laughs and hugs you around the neck!!  You cherish her "
        "warmth!!",
        "She jumps off your lap, and punches you hard!  Your chair tips "
        "over backwards!  The entire bar laughs at your misfortune!!",
    ),
    _Tier(
        "G", "Grab", 16, 40, 10,
        "`%You palm her shapely cheeks...`2",
        "She doesn't object!  You become over excited and force your hand "
        "away!",
        "She breaks a tankard over your head!  You swoon and fall on your "
        "face!  The entire bar laughs at your misfortune!!",
    ),
)

# reference/lord.js:8646-8788 (Seth Able, female players).
_SETH_TIERS = (
    _Tier(
        "W", "Wink", 1, 5, 0,
        "`%You wink at Seth Able seductively..",
        "`2He blushes and smiles!!  You are making progress with him!",
        "`4He looks the other way!  You nearly die of embarrassment!",
    ),
    _Tier(
        "F", "Flutter Eyelashes", 2, 10, 1,
        "`%You turn to Seth Able and flutter your eyelashes violently..",
        "`2He smiles broadly and winks back!  Your relationship with him "
        "is taking off!",
        "`2He doesn't seem interested and starts talking to Violet!  You "
        "nearly faint from embarresment!",
    ),
    _Tier(
        "D", "Drop Hanky", 4, 20, 3,
        "`%You innocently drop your lace hanky on the ground..",
        "`2Seth sees it, picks it up and offers it to you!  He smiles "
        "hugely!  You are elated!",
        "`2He ignores your plea for attention, and looks away!  You "
        "nearly faint from embarresment!",
    ),
    _Tier(
        "A", "Ask For A Drink", 8, 30, 5,
        "`%You wave Seth over and ask him to buy you a drink..",
        "`2He buys you the most expensive drink in the house, and gives "
        "you a hug!  You cherish his warmth!",
        "`2He looks startled at your advances and mumbles a lame excuse!  "
        "You nearly die of embarresment!",
    ),
    _Tier(
        "K", "Kiss", 16, 40, 10,
        "`%You reach over his mandolin, and kiss him soundly...",
        "`2He doesn't object!  He kisses you back!  You become over "
        "excited and force yourself away!",
        "`2He pushes your face away, and says he is just not ready for "
        "that kind of relationship!",
    ),
)


async def _run_tier(ctx: GameCtx, tier: _Tier) -> None:
    """Shared engine for one wink/kiss/peck/.../grab (or flutter/hanky/...)
    attempt. Sets the shared daily gate unconditionally, exactly like every
    lord.js tier function does at its own top (e.g. reference/lord.js:9619,
    9639, 8647...)."""
    p = ctx.player
    p.seen_violet = 1
    await ctx.io.write(f"\n  {tier.action}\n\n")
    if p.charm >= tier.threshold:
        gain = tier.exp_mult * p.level
        await grant_exp(ctx, gain)
        await ctx.io.write(
            f"  {tier.success}\n\n  `%You receive {gain} experience!\n"
        )
    elif tier.penalty_mult:
        dmg = tier.penalty_mult * p.level
        p.hp = max(1, p.hp - dmg)
        await ctx.io.write(f"  {tier.fail}\n\n  `4YOU LOSE {dmg} HIT POINTS!\n")
    else:
        await ctx.io.write(f"  {tier.fail}\n")
    await ctx.io.pause()


async def _run_carry_violet(ctx: GameCtx) -> None:
    """Port of ``carry()``. reference/lord.js:9552-9616."""
    p = ctx.player
    await ctx.io.write(
        "\n  You pick Violet up and roughly carry her upstairs and throw "
        "her on the bed...\n\n"
    )
    p.seen_violet = 1
    if p.married_to is not None and p.married_to > -1:
        await ctx.io.write(
            "  `#Violet `0is appalled that you would even suggest such a "
            "thing!\n\n  She calls you a dirty old man!\n"
        )
        insult = "dirty old man" if ctx.rng.randrange(2) else "bastard"
        ctx.news(f"`#  Violet `2calls `0{p.name} `2a `){insult}`2!")
    elif p.charm > 32:
        if ctx.rng.randrange(3) == 1:
            await grant_exp(ctx, p.level * 40)
            p.lays += 1
            await ctx.io.write(
                "  She smiles invitingly...\n\n  Half an hour later....You "
                "saunter downstairs.  The drunks are mystified!\n\n"
                f"  `0YOU GET `%{p.level * 40}`0 EXPERIENCE!\n"
            )
            ctx.news(f"`5  {p.name} `%Got laid by `#Violet`%!")
        else:
            await ctx.io.write(
                "  She tells you she's just too busy today.  You saunter "
                "down to the bar disappointed.\n"
            )
    else:
        p.hp = 1
        await ctx.io.write(
            "  She jumps off the bed screaming at you!  She savagely "
            "kicks you in the groin!  The entire bar laughs at your "
            "misfortune!!\n\n  `4YOUR HITPOINTS GO DOWN TO 1!\n"
        )
        ctx.news(f"`0  {p.name} `2got kicked in the groin by `#Violet`2!")
    await ctx.io.pause()


async def _run_seduce_seth(ctx: GameCtx) -> None:
    """Port of ``seduce()``. reference/lord.js:8581-8644."""
    p = ctx.player
    await ctx.io.write(
        "\n  You turn on the charm, moving your body seductively against "
        "him, you ask him to come upstairs with you...\n\n"
    )
    p.seen_violet = 1
    if p.married_to is not None and p.married_to > -1:
        await ctx.io.write(
            "  Seth Able is appalled that you would even suggest such a "
            "thing!\n\n  He calls you a filthy harlot!\n"
        )
        insult = ("filthy harlot", "slut")[ctx.rng.randrange(2)]
        ctx.news(f"`%  Seth Able `2calls `0{p.name} `2a `){insult}`2!")
    elif p.charm >= 32:
        if ctx.rng.randrange(4) == 2:
            await grant_exp(ctx, p.level * 40)
            p.lays += 1
            await ctx.io.write(
                "  He smiles invitingly...\n\n  Hours later.. You saunter "
                "downstairs.  The drunks are mystified!\n\n"
                f"  `0YOU GET `%{p.level * 40} `0EXPERIENCE!\n"
            )
            ctx.news(f"`0  {p.name} `2got laid by `%Seth Able`2!")
        else:
            await ctx.io.write(
                "  He tells you he is too exhausted from last night!  You "
                "saunter around the bar disappointed.\n"
            )
    else:
        p.hp = 1
        await ctx.io.write(
            "  He shoves you away harshly!  He calls you a filthy whore!  "
            "The entire bar laughs at your misfortune!!\n\n"
            "  `4YOUR HITPOINTS GO DOWN TO 1!\n"
        )
        ctx.news(f"`5  {p.name} `2 was called a whore by `%Seth Able`2!")
    await ctx.io.pause()


# (upper exclusive bound, response text) ladders. reference/lord.js:9516-9541
# (Violet) / 8795-8895 (Seth). The final row's bound is unused (charm >= it
# always succeeds).
_VIOLET_MARRIAGE_LADDER = (
    (3, ('`#  "Marry YOU?!" `2She laughs as if she just heard the funniest '
         "joke on earth.")),
    (6, '`#  "Is this a joke?"`2 she asks seriously.'),
    (10, ('`#  "You\'re sweet, but I just don\'t like you in that way." `2she '
          "tells you seriously.")),
    (50, ('`#  "I like you, I really do!  I just don\'t feel ready for that '
          'kind of commitment right now!" `2she explains sadly.')),
    (80, ('`#  "I think I\'m in love with you!  But I can\'t marry you.  My '
          'last marriage was a disaster." `2she explains sadly.')),
    (100, ('`#  "I...I can\'t say yes.  Ask me another time.  Please." `2she '
           "begs.")),
)
_SETH_MARRIAGE_LADDER = (
    (10, '`0  "I will not consider it!"`2'),
    (20, ('`0  "We are just not right for each other.. We are so different - '
          'And in this case opposites DON\'T attract."')),
    (50, ('`0  "I cannot say yes.  I do find you attractive, but my life is '
          'here, serving the people."')),
    (80, ('`0  "I do love you - You are one of the most wonderful women in '
          'the realm!  I still cannot say yes."')),
    (100, ('`0  "You are truly a thing of beauty.  Please have mercy on me '
           'and do not hate me when I tell I cannot."')),
    (120, ('`0  "You are so dear to me... I was married once before.  My '
           "wife was killed many years ago.  I cannot go through that pain "
           'again.  I am so sorry."')),
)


async def _marriage_violet(ctx: GameCtx) -> None:
    """Port of ``marriage()``/``marry()``/``no()``.
    reference/lord.js:9434-9493. No ``player.divorced`` cooldown check --
    this project's ``Player`` has no ``divorced`` field (player-to-player
    marriage/divorce isn't modeled -- see ``conjugality.py``)."""
    p = ctx.player
    p.seen_violet = 1
    await ctx.io.write(
        "\n  You take Violet's hand and squeeze it gently.  \"My sweet "
        "Violet.  Will you make me the happiest man alive?  Will you marry "
        "me?\"\n\n"
    )
    for bound, text in _VIOLET_MARRIAGE_LADDER:
        if p.charm < bound:
            await ctx.io.write(f"{text}\n\n  `%THE ENTIRE BAR LAUGHS AT YOUR MISFORTUNE!\n")
            ctx.news(f"`2  `#Violet`2 has refused to marry `0{p.name}`2!")
            await ctx.io.pause()
            return
    await ctx.io.write('`#  "Yes!  I WILL marry you!" `2she laughs!\n\n')
    await _marry_npc(
        ctx,
        get_current=npc_state.married_to_violet,
        set_current=npc_state.set_married_to_violet,
        elsewhere_text="`2As you walk up to the chapel, you see Violet "
        "walking out...on the arm of {other}!",
    )
    if npc_state.married_to_violet(ctx.conn) == p.id:
        await grant_exp(ctx, p.level * 1000)
        p.seen_violet = 0
        await ctx.io.write(
            "  Violet agrees to marry you!  After a short ceremony you are "
            "finally able to take her into your arms.  She agrees to quit "
            "her job and take care of your house.\n\n"
            f"  `%YOU RECEIVE {p.level * 1000} EXPERIENCE!\n"
        )
        ctx.news(
            f"`2  `#Violet`2 has `%MARRIED `0{p.name}`2!!!!!\n"
            "`2  She `%QUITS`2 her job at the bar to the towns dismay!"
        )
    await ctx.io.pause()


async def _marriage_seth(ctx: GameCtx) -> None:
    """Port of ``marriage()`` (single_seth's). reference/lord.js:8790-8957."""
    p = ctx.player
    p.seen_violet = 1
    await ctx.io.write(
        "\n  Seth Able looks at you seriously...\n\n"
    )
    for bound, text in _SETH_MARRIAGE_LADDER:
        if p.charm < bound:
            await ctx.io.write(f"{text}\n\n")
            await ctx.io.pause()
            return
    await ctx.io.write(
        '`0  "I do love you.  And if you\'ll have me, I will be the best '
        'husband I can be for you."\n\n'
    )
    await _marry_npc(
        ctx,
        get_current=npc_state.married_to_seth,
        set_current=npc_state.set_married_to_seth,
        elsewhere_text="`0Seth Able has just married {other}!  You run away "
        "sobbing.",
    )
    if npc_state.married_to_seth(ctx.conn) == p.id:
        if p.lays > 0:
            await ctx.io.write(
                "  Wearing a slightly off-white dress you walk demurely "
                "down the aisle.\n"
            )
            ctx.news(f"`)  ** `0{p.name} `2has MARRIED `%Seth Able`2!`) **")
        else:
            await grant_exp(ctx, p.level * 5000)
            await ctx.io.write(
                "  Wearing a PURE `%white `0dress you walk demurely down "
                f"the aisle.  You feel heavenly!  You receive {p.level * 5000} "
                "experience!\n"
            )
            ctx.news(
                f"`)  ** `0{p.name} `2has MARRIED `%Seth Able`2 in "
                "`%WHITE`2!`) **"
            )
    await ctx.io.pause()


async def _marry_npc(ctx: GameCtx, *, get_current, set_current, elsewhere_text: str) -> None:
    """Shared "claim the singleton NPC spouse" race: first come, first
    served. reference/lord.js:9459-9468 (Violet) / 8911-8942 (Seth)."""
    p = ctx.player
    current = get_current(ctx.conn)
    if current != npc_state.NONE and current != p.id:
        other = ctx.repo.get(current)
        other_name = other.name if other is not None else "another warrior"
        await ctx.io.write(f"  {elsewhere_text.format(other=other_name)}\n\n")
        return
    set_current(ctx.conn, p.id)


async def _flirt(ctx: GameCtx) -> None:
    """Port of ``flirt_with_violet()``. reference/lord.js:9819-9892
    (male players) plus the ``talk_to_bard()``'s ``F`` case for female
    players (reference/lord.js:9279-9391, trimmed -- see this module's
    docstring)."""
    p = ctx.player
    if p.gender == "F":
        await ctx.io.write("\n\n  You would rather flirt with Seth Able.\n")
        return

    married_to_violet = npc_state.married_to_violet(ctx.conn)
    if married_to_violet != npc_state.NONE:
        if p.seen_violet:
            await ctx.io.write(
                "\n\n  `2You are still shaking from your last encounter "
                "with `4Grizelda`2!\n"
            )
        else:
            p.seen_violet = 1
            await ctx.io.write(
                "\n\n  You whistle loudly for the barmaid, but when you "
                "pat...\n\n  `4YOU FEEL HUGE LUMPS OF CELLULITE!\n\n"
                "`2  The obese barmaid introduces her portly self as "
                "`4Grizelda`2!\n"
            )
        await ctx.io.pause()
        return

    if p.seen_violet:
        await ctx.io.write(
            "\n\n  You feel you had better not go too fast, maybe "
            "tomorrow.\n"
        )
        return

    await _tier_menu(ctx, "Violet", _VIOLET_TIERS, _run_carry_violet, _marriage_violet)


async def _tier_menu(ctx, npc, tiers, carry_fn, marriage_fn) -> None:
    options = {t.key: t.key for t in tiers}
    options["C"] = "carry"
    options["M"] = "marry"
    options["R"] = "return"
    await ctx.io.write(
        f"\n  `2You approach {npc}. What do you do?\n"
        + "\n".join(f"  ({t.key}) {t.label}" for t in tiers)
        + "\n  (C) Carry upstairs\n  (M) Propose marriage\n  (R) Return\n"
    )
    choice = await ctx.io.menu(options, "  `2Your choice? : ")
    if choice == "R":
        return
    if choice == "C":
        await carry_fn(ctx)
        return
    if choice == "M":
        await marriage_fn(ctx)
        return
    tier = next(t for t in tiers if t.key == choice)
    await _run_tier(ctx, tier)


async def _bard_menu(ctx: GameCtx) -> None:
    """Port of ``talk_to_bard()``. reference/lord.js:9238-9396."""
    while True:
        p = ctx.player
        await ctx.io.write(
            "\n  `2Seth Able looks at you expectantly.  (`0? for menu`2)\n"
            "  (`0A`2)sk for a song   (`0F`2)lirt   (`0R`2)eturn\n"
        )
        choice = await ctx.io.menu(
            {"A": "song", "F": "flirt", "R": "return"}, "  `2Your choice? : "
        )
        if choice == "R":
            return
        if choice == "A":
            await _bard_song(ctx)
            continue
        # F -- gender-gated, reference/lord.js:9279-9391.
        if p.gender == "M":
            await ctx.io.write("\n\n  You would rather flirt with Violet.\n")
            continue

        married_to_seth = npc_state.married_to_seth(ctx.conn)
        if married_to_seth != npc_state.NONE:
            if married_to_seth == p.id:
                if p.seen_violet:
                    await ctx.io.write("\n\n  `2You don't wish to interrupt his song.\n")
                else:
                    p.seen_violet = 1
                    # Collapsed to one fixed line -- lord.js picks from an
                    # 8-way switch(random(8)) flavor pool here
                    # (reference/lord.js:9294-9319: "I love you too,
                    # honey!" / a peck on the cheek / "duty calls" / etc.).
                    # See docs/deviations.md.
                    await ctx.io.write('\n\n  `0"I love you too, honey!"\n')
            else:
                # Homewrecking sub-branch (reference/lord.js:9322-9386) --
                # simplified to a status line; the full seduce-someone-else's-
                # spouse mail mechanic is out of scope for this task.
                other = ctx.repo.get(married_to_seth)
                name = other.name if other is not None else "another warrior"
                await ctx.io.write(
                    f"\n\n  `2Seth Able is already spoken for -- he belongs "
                    f"to `0{name}`2.\n"
                )
            continue

        if p.seen_violet:
            await ctx.io.write("\n\n  The Bard seems occupied...Maybe tomorrow...\n")
            continue

        await _tier_menu(ctx, "Seth Able", _SETH_TIERS, _run_seduce_seth, _marriage_seth)


# ((weight-check, field-to-bump, amount, text)) -- reference/lord.js:9064-9234.
async def _bard_song(ctx: GameCtx) -> None:
    """Port of ``bard_song()``. reference/lord.js:9049-9236. One-time-per-day
    (``seen_bard``, reset daily by ``pylord/engine/daily.py``)."""
    p = ctx.player
    await ctx.io.write("\n\n  `%(Seth Able clears his throat)`2\n\n")
    if p.seen_bard:
        await ctx.io.write('  "I\'m sorry, but my throat is too dry..  Perhaps tomorrow."\n')
        await ctx.io.pause()
        return
    p.seen_bard = 1

    if ctx.rng.randrange(2) == 1:
        outcome = ctx.rng.randrange(5)
        if outcome == 0:
            p.player_fights += 1
            text = "  You swear to avenge the children.\n\n  `#YOU RECEIVE AN EXTRA USER BATTLE FOR TODAY!"
        elif outcome == 1:
            p.bank = min(p.bank * 2, 2_000_000_000)
            text = "  You find yourself wishing for more money.\n\n  `#SOMEWHERE, MAGIC HAS HAPPENED!"
        elif outcome == 2:
            p.forest_fights = min(p.forest_fights + 2, 32_000)
            text = "  The song makes you feel sad, yet happy.\n\n  `#YOU RECEIVE TWO MORE FOREST FIGHTS FOR TODAY!"
        elif outcome == 3:
            p.forest_fights = min(p.forest_fights + 1, 32_000)
            text = "  The song makes you feel a strange wonder.\n\n  `#YOU RECEIVE ONE MORE FOREST FIGHT FOR TODAY!"
        else:
            p.hp_max = min(p.hp_max + 1, 32_000)
            text = "  The hero has inspired you.\n\n  `#YOUR HITPOINTS INCREASE BY ONE!"
    elif p.gender == "M":
        outcome = ctx.rng.randrange(4)
        if outcome == 0:
            p.hp = p.hp_max
            text = "  The song makes you feel your heritage.\n\n  `#YOUR HIT POINTS ARE MAXED OUT!"
        elif outcome in (1, 2):
            p.forest_fights = min(p.forest_fights + 3, 32_000)
            text = "  The song makes you feel powerful!\n\n  `#YOU RECEIVE THREE MORE FOREST FIGHTS FOR TODAY!"
        else:
            p.forest_fights = min(p.forest_fights + 2, 32_000)
            text = "  The song makes you glad you are male!\n\n  `#YOU RECEIVE TWO MORE FOREST FIGHTS FOR TODAY!"
    else:
        outcome = ctx.rng.randrange(2)
        if outcome == 0:
            p.charm = min(p.charm + 1, 32_000)
            text = "  The song makes you feel pretty!\n\n  `#YOU RECEIVE A CHARM POINT!"
        else:
            p.forest_fights = min(p.forest_fights + 3, 32_000)
            text = "  The song makes you feel powerful!\n\n  `#YOU RECEIVE THREE MORE FOREST FIGHTS FOR TODAY!"

    await ctx.io.write(f"{text}\n")
    await ctx.io.pause()


async def _rent_room(ctx: GameCtx) -> bool:
    """Port of ``get_a_room()``. reference/lord.js:6384-6456. Returns
    ``True`` if a room was actually taken (caller ends the session, matching
    lord.js's own ``exit(0)``)."""
    p = ctx.player
    cost = _ROOM_COST_PER_LEVEL * p.level
    await ctx.io.write(
        "\n\n  The bartender approaches you at the mention of a room.\n"
        f'  "You want a room, eh?  That\'ll be {cost} gold!"\n'
    )
    choice = await ctx.io.menu({"Y": "yes", "N": "no"}, "  `2Do you agree? [`0Y`2] : `%")
    if choice == "N":
        await ctx.io.write("\n  The bartender grunts, then walks away uninterested.\n")
        return False

    if p.charm > _FREE_ROOM_CHARM:
        await ctx.io.write(
            "\n\n  \"You seem like quite the catch, so tell you what, I'll "
            "just give you the room for free....\"\n\n"
        )
    else:
        if p.gold < cost:
            await ctx.io.write("\n  \"Hey!  You don't have that much gold!\"\n")
            return False
        p.gold -= cost

    p.at_inn = 1
    await ctx.io.write(
        "\n\n  `%The Room At The Inn\n"
        "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
        "  `2You are escorted to a small but cozy room in the Inn.\n"
        "  You relax on the soft bed, and soon fall asleep, still wearing "
        "your armour.\n\n"
    )
    return True


async def _bartender(ctx: GameCtx) -> None:
    """Port of the non-PvP, non-shop parts of ``talk_with_bartender()``.
    reference/lord.js:8090-8437. Only the Violet/Seth gossip (`` `V`/`S` ``)
    and the dragon hint (`` `D`, `` level 12) survive here; the elixir shop
    (`` `G` ``, gem currency), rename (`` `C` ``), and bribe-to-attack-
    sleepers (`` `B` ``) are dropped -- see this module's docstring for
    ``C``/``M``, and the TODO below for ``B``."""
    p = ctx.player
    if p.level == 1:  # reference/lord.js:8149-8156
        await ctx.io.write(
            '\n\n  "I don\'t recall ever hearing the name '
            f'{p.name} before!  Get outta my face!"\n'
        )
        await ctx.io.pause()
        return

    while True:
        await ctx.io.write(
            '\n  "Well?" the bartender inquires.  (`0? for menu`2)\n'
        )
        options = {"R": "return"}
        if p.gender == "M":
            options["V"] = "gossip_violet"
        else:
            options["S"] = "gossip_seth"
        if p.level == 12:
            options["D"] = "dragon_hint"
        # TODO(13b/PvP): lord.js's `B` bribes the barkeep for a room key
        # and attacks a sleeping player (attack_in_inn(),
        # reference/lord.js:8388-8418, :7979-8089) -- that's PvP, Task 13b.
        choice = await ctx.io.menu(options, "  `2Your choice? : ")
        if choice == "R":
            return
        if choice == "V":
            await ctx.io.write(
                '\n\n  "Ya want to know about `#Violet`5 do ya?  She only '
                'goes for the type of guy who would help old people..."\n'
            )
        elif choice == "S":
            await ctx.io.write(
                '\n\n  "Ya want to know about `%Seth Able`5 the Bard, eh?  '
                'He likes the type of girl with a lot of Charm..."\n'
            )
        elif choice == "D":
            await ctx.io.write(
                '\n\n  "Ahhh...If anyone could kill that Dragon, it would '
                "be you.. I have heard strange noises in the forest... You "
                'might try Searching..."\n'
            )
        await ctx.io.pause()


@scene("inn")
async def inn(ctx: GameCtx) -> str | None:
    ctx.player.at_inn = 0  # reference/lord.js:9920 -- walking in clears it.
    while True:
        await ctx.io.write(_MENU)
        choice = await ctx.io.menu(
            {
                "F": "flirt", "H": "bard", "G": "room", "T": "bartender",
                "W": "mail", "D": "news", "V": "stats",
                "R": "town", "Q": "town",
            },
            "  `2Your choice`0? `2",
        )
        if choice in ("R", "Q"):
            return "town"
        if choice in ("W", "D", "V"):
            return {"W": "mail", "D": "news", "V": "stats"}[choice]
        if choice == "F":
            await _flirt(ctx)
        elif choice == "H":
            await _bard_menu(ctx)
        elif choice == "T":
            await _bartender(ctx)
        elif choice == "G" and await _rent_room(ctx):
            return None
