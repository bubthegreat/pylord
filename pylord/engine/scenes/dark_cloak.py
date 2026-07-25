"""The Dark Cloak Tavern -- port of ``darkhorse_tavern()``
(``reference/lord.js:12240-12915``).

A roadhouse hidden in the forest, reached from the forest's random-event
table (lord.js's ``look_to_kill()`` case 15) -- **only on horseback**: the
roll is ``random(15 + (player.horse ? 1 : 0))`` (:14482), so slot 15 does
not exist for a player on foot. It was listed in
``docs/deviations.md`` as unported, and it is the only *place* in the base
game that was missing -- the "Other Places" hub itself ships empty in
vanilla LORD (``create_other_places()``, :16774, reads a ``3rdparty.lrd``
list of external programs).

What's here:

* ``(G)amble`` -- the old man's three betting games, chosen at random
  (:12263-12470). Two per visit; a third refusal is the joke about making
  light of the word honor.
* ``(T)alk to Chance`` -- the information broker (:12512-12725). Two gems
  buys another player's weapon, armour, strength, defense, looks, worth,
  gems, offspring and horse.
* ``(W)ise old man`` -- view what the realm says about a player, or write
  the two lines it says about you (:12726-12809).
* ``(C)onversation`` -- the tavern's message wall, kept in ``igm_data``
  rather than lord.js's ``darkbar.lrd`` file.
* ``(E)`` -- the Old Man's Ranking, by lays then charm (:12811-12846).
* ``(D)aily happenings`` and ``(Y)our stats``, which route to the existing
  scenes.

**Deviations**, recorded in ``docs/deviations.md``:

1. The screen body is reconstructed. lord.js draws it from ``lrdfile('CLOAK')``
   -- an external asset not in this repo, like every other menu here (see
   ``town.py``).
2. ``(V)`` appears in lord.js's own advertised key list (:12856) but has no
   ``case`` in the switch, so it does nothing there. It is left out rather
   than invented.
3. The 1-in-25 ``blackjack()`` on the way out (:12912) is not ported --
   blackjack is a whole sub-game, and the Casino IGM already deals cards.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pylord.engine.data.armor import ARMOR
from pylord.engine.data.weapons import WEAPONS
from pylord.engine.game import scene
from pylord.engine.scenes import news as news_scene
from pylord.engine.scenes import stats as stats_scene

if TYPE_CHECKING:
    from pylord.engine.game import GameCtx
    from pylord.models import Player

_GOLD_CAP = 2_000_000_000

#: lord.js refuses a third game in one visit (:12298-12310).
_GAMES_PER_VISIT = 2

#: What Chance charges to talk (:12578).
_CHANCE_PRICE_GEMS = 2

#: The tavern's shared conversation wall lives here instead of
#: ``darkbar.lrd``. Namespaced like an IGM's store so it needs no table.
_WALL_KEY = "dark_cloak"
_WALL_FIELD = "conversation"
_WALL_MAX = 15
_WALL_LINE_MAX = 75

_CLASS_NAMES = {1: "Warrior", 2: "Mystical Skills User", 3: "Thief"}


def _item_name(table, num: int) -> str:
    if 0 <= num < len(table):
        return table[num].name
    return "nothing at all"


def _looks(other: Player) -> str:
    """lord.js:12619-12645. The two top tiers read the *other* player's
    gender; lord.js used the viewer's, which its own port marks as a bug
    (``// DIFF: This used the *players* sex!``)."""
    charm = other.charm
    if charm < 3:
        return f'"{other.name} is very ugly."'
    if charm < 5:
        return f'"{other.name} is kind of blah looking."'
    if charm < 10:
        return f'"{other.name} is fairly good looking."'
    if charm < 50:
        return f'"{other.name} has a very fair countenance."'
    if charm < 90:
        if other.gender == "F":
            return f'"{other.name} is a very good looking woman."'
        return f'"{other.name} gets all the women...The lucky brute!"'
    if other.gender == "F":
        return f'"I have heard {other.name} has the face and body of a Goddess."'
    return f'"{other.name} is a good looking bastard."'


async def _find_player(ctx: GameCtx) -> Player | None:
    """The same full-or-partial name prompt the Mail scene uses
    (``find_player()``, lord.js:4890-4926)."""
    from pylord.engine.scenes.mail import _find_player as find

    return await find(ctx)


async def _wager(ctx: GameCtx) -> int:
    """lord.js:12268-12291. Re-asks until the bet is affordable; 0 backs
    out."""
    p = ctx.player
    while True:
        await ctx.io.write(
            f"\n  `2How much gold of your `%{p.gold:,}`2 will you hazard? "
            "(`00`2 to chicken out)\n"
        )
        raw = await ctx.io.readline("  `2WAGER : `0", maxlen=11)
        try:
            bet = int(raw.strip() or 0)
        except ValueError:
            bet = 0
        if bet > p.gold:
            await ctx.io.write(
                "\n  `2Betting what you don't have is `4NOT`2 a good idea.\n"
            )
            continue
        if bet < 0:
            await ctx.io.write("\n  `2You don't think that will go over too big.\n")
            continue
        return bet


def _win(p: Player, bet: int) -> None:
    p.gold = min(p.gold + bet, _GOLD_CAP)


async def _guess_the_number(ctx: GameCtx) -> None:
    """lord.js:12314-12374. The old man guesses your number.

    lord.js's own port fixed a bug here (``// DIFF: This was clearly
    broken, and he always guess right``): he guesses right only when the
    roll is 55 or under, so the player wins a little more often than not.
    """
    p = ctx.player
    await ctx.io.write(
        "\n  The old man stops etching on the table he is at and walks over to you.\n\n"
        "  `0\"I'll play a game with ya, kid!  I'll bet I can guess what number\n"
        '  you are thinkin\'!"\n\n'
    )
    await ctx.io.pause()
    bet = await _wager(ctx)
    if bet == 0:
        await ctx.io.write(
            "\n  `2The old man laughs in your face then continues his carving in the\n"
            "  table.\n"
        )
        return

    await ctx.io.write(
        f'\n  `0"Fine!  `%{bet:,}`0 it is!  Concentrate on a number."`2\n'
    )
    mine = ctx.rng.randrange(100) + 1
    await ctx.io.write(f"\n  `2You concentrate on the number...`%{mine}\n")
    await ctx.io.write(
        "\n  `2The old man studies you quietly for a moment.  "
        "Then screams in delight.\n"
    )
    await ctx.io.pause()

    if ctx.rng.randrange(100) + 1 > 55:
        his = ctx.rng.randrange(100) + 1
        while his == mine:
            his = ctx.rng.randrange(100) + 1
    else:
        his = mine

    await ctx.io.write(f'\n  `0"The number is...`%{his}`0 isn\'t it?!!!!!!!!!!!\n\n')
    if his != mine:
        await ctx.io.write(
            "  `2You sadly inform the Old Man of his mistake, and he grudgingly gives\n"
            f"  you `%{bet:,}`2 gold from his pouch.\n"
        )
        _win(p, bet)
        return
    await ctx.io.write(
        "  `2You feel obliged to admit that he chose correctly.  You count out\n"
        f"  `%{bet:,}`2 gold and give it to him with a scowl.\n\n"
        "  `2The old man dances a jig of joy!\n"
    )
    p.gold -= bet


async def _which_mug(ctx: GameCtx) -> None:
    """lord.js:12375-12429. His teeth are under one of two mugs -- and the
    roll that decides it is 45, not a fair coin."""
    p = ctx.player
    await ctx.io.write(
        "\n  The old man stops etching on the table he is at and walks over to you.\n\n"
        '  `0"I\'ll play a game with ya, kid!"\n\n'
        "  `2The old man grabs two wooden mugs from a table and slaps them down\n"
        '  in front of you upside down.  `0"Guess which one I hid muh teeth in!"\n\n'
    )
    await ctx.io.pause()
    bet = await _wager(ctx)
    if bet == 0:
        await ctx.io.write(
            "\n  `2The old man laughs in your face then continues his carving in the\n"
            "  table.\n"
        )
        return

    await ctx.io.write('\n  `0"Agreed!" `2The old man waits for your response.\n')
    await ctx.io.pause()
    which = "first" if ctx.rng.randrange(2) == 0 else "second"
    await ctx.io.write(f"\n  `2You demand to see what's in the {which} mug!\n")
    await ctx.io.write("\n  `2The old man slowly turns over the mug...")
    if ctx.rng.randrange(100) + 1 > 45:
        await ctx.io.write("`%IT HAS HIS WOODEN TEETH IN IT!\n")
        _win(p, bet)
        await ctx.io.write(
            "\n  `2The entire bar cheers at your success!\n\n"
            "  The old man groans and hands you the gold you've won.\n"
        )
        return
    await ctx.io.write("`4IT IS EMPTY SAVE SOME STALE BEER!\n")
    p.gold -= bet
    await ctx.io.write("\n  `2The old man howls in delight as you pay him.\n")


async def _knock_the_mug(ctx: GameCtx) -> None:
    """lord.js:12430-12470. Throw a dagger at the tankard on his head."""
    p = ctx.player
    await ctx.io.write(
        "\n  The old man stops etching on the table he is at and walks over to you.\n\n"
        '  `0"I\'ll play a game with ya, kid!"\n\n'
        "  `2The old man walks over to you and hands you a small dagger.  Then he\n"
        "  moves to the other side of the Tavern, and picks up a tankard of brew.\n\n"
        '  `0"I\'ll bet you can\'t knock this off my head without getting me wet!"\n\n'
    )
    await ctx.io.pause()
    bet = await _wager(ctx)
    if bet == 0:
        await ctx.io.write(
            "\n  `2The old man laughs in your face then continues his carving in the\n"
            "  table.\n"
        )
        return

    await ctx.io.write(
        "\n  `2The old man positions himself carefully, and places the Mug on his head.\n\n"
        '  `0"You\'ll never hit it, sharpshooter!  Throw it already!"\n\n'
    )
    await ctx.io.pause()
    await ctx.io.write(
        "  `2You give it your best shot.\n\n  `%** `0WHO" + "O" * 15 + "SH `%**\n\n"
    )
    if ctx.rng.randrange(100) + 1 > 44:
        await ctx.io.write(
            "  `2YOU HAVE KNOCKED IT OFF LEAVING THE OLD MAN HIGH AND DRY!\n\n"
            f"  The old man swears sourly, but pays you the `%{bet:,}`2 gold.\n"
        )
        _win(p, bet)
        return
    await ctx.io.write(
        "  `2You soak the old man to the bone, and he demands his winnings.\n\n"
        f"  You hand over `%{bet:,}`2 gold.\n"
    )
    p.gold -= bet


_GAMES = (_guess_the_number, _which_mug, _knock_the_mug)


async def _gamble(ctx: GameCtx, played: int) -> int:
    """lord.js:12263-12470. Returns the new games-played count."""
    await ctx.io.write("\n`%  ** GAMBLE TIME! **\n\n")
    await ctx.io.write(
        "  You saunter over to the bar and demand that someone gamble with you.\n\n"
    )
    if played >= _GAMES_PER_VISIT:
        await ctx.io.write(
            "  No one seems too thrilled at the prospect.  Perhaps if you came back\n"
            "  another time.\n\n"
        )
        if played > _GAMES_PER_VISIT:
            await ctx.io.write(
                "  (You wonder if it had anything to do with your making a joke out\n"
                "  of the word honor)\n\n"
            )
        return played + 1

    await _GAMES[ctx.rng.randrange(3)](ctx)
    return played + 1


async def _chance(ctx: GameCtx) -> None:
    """Chance the information broker (lord.js:12512-12725)."""
    while True:
        await ctx.io.write(
            "\n  `2Chance leans back against the bar, watching the room.\n\n"
            "  `2(`0L`2)ook up an enemy\n"
            "  `2(`0R`2)eturn to the tavern\n\n"
        )
        choice = await ctx.io.menu(
            {"L": "look up", "R": "return"},
            "  `2Your command? (`0? `2for menu)  [`0R`2] : `%",
            default="R",
        )
        if choice != "L":
            return

        await ctx.io.write(
            '\n  `0"I know many things about many people.  Who is your enemy?"`2\n'
        )
        other = await _find_player(ctx)
        if other is None:
            await ctx.io.write(
                "\n  `0\"I don't know anyone with a name even close to that.\"`2\n"
            )
            continue
        if other.id == ctx.player.id:
            him = "him" if ctx.player.gender == "M" else "her"
            he = "he" if ctx.player.gender == "M" else "she"
            await ctx.io.write(
                f'\n  `0"Yes..I know {him}.  {he.capitalize()} is a favorite '
                'customer of mine!"\n  `2Chance laughs heartily.\n'
            )
            continue

        profession = _CLASS_NAMES.get(other.class_type, "Warrior")
        await ctx.io.write(
            f"\n  `2Chance's face turns somber.\n"
            f'  `0"{other.name}`0 the {profession}?  I know who that is."\n\n'
            "  `0\"This information was not easily come by, and I am going to have to\n"
            "  charge two `%Gems`0 for it.  Now you know why this tavern is REALLY\n"
            '  here."\n\n'
        )
        if ctx.player.gems < _CHANCE_PRICE_GEMS:
            await ctx.io.write(
                "  `2Not having two `%Gems`2, you decline.\n"
            )
            continue

        agreed = await ctx.io.menu(
            {"Y": "yes", "N": "no"},
            "  `2Pay Chance two `%Gems`2 for the info? [`0Pay 'Em`2] : `%",
            default="Y",
        )
        if agreed != "Y":
            await ctx.io.write('\n  `0"No problem!  I know how it is these days."\n')
            continue

        ctx.player.gems -= _CHANCE_PRICE_GEMS
        he = "he" if other.gender == "M" else "she"
        await ctx.io.write(
            '\n  `0"Alright.  Come with me."\n\n'
            "  `2Chance leads you to a small room in back of the tavern, and you take\n"
            "  a comfortable seat.\n\n"
            f'  `0"Well...Here is everthing I know about {other.name}`0."\n\n'
        )
        await ctx.io.pause()
        await ctx.io.write(
            f'\n  `0"Fights with a {_item_name(WEAPONS, other.weapon_num)}`0 and has a '
            f'total Strength of `%{other.strength:,}`0."\n'
            f'  `0"Wears a {_item_name(ARMOR, other.armor_num)}`0 and has a total '
            f'Defense of `%{other.defense:,}`0."\n\n'
            f"  `0{_looks(other)}\n\n"
            f'  `0"Total worth in gold is {other.gold + other.bank:,}."\n\n'
            f'  `0"Last time we checked, {he} had {other.gems:,} `%Gems`0."\n\n'
        )
        if other.kids == 0:
            await ctx.io.write(f'  `0"{other.name} has no offspring."\n')
        else:
            await ctx.io.write(f'  `0"{other.name} has `%{other.kids:,} `2offspring.\n')
        if other.horse:
            await ctx.io.write("  `0That person owns a horse.\n")
        await ctx.io.pause()


async def _old_man(ctx: GameCtx) -> None:
    """The wise old man (lord.js:12726-12809): what the realm says about
    someone, and what it says about you."""
    while True:
        await ctx.io.write(
            "\n  `2An ancient man sits carving something into the table.\n\n"
            "  `2(`0V`2)iew what he knows of someone\n"
            "  `2(`0E`2)tch something about yourself\n"
            "  `2(`0R`2)eturn to the tavern\n\n"
        )
        choice = await ctx.io.menu(
            {"V": "view", "E": "etch", "R": "return"},
            "  `2Your command? (`0? `2for menu)  [`0R`2] : `%",
            default="R",
        )
        if choice == "R":
            return

        if choice == "V":
            await ctx.io.write('\n  `0"Who would you like to know more about?"`2\n')
            other = await _find_player(ctx)
            if other is None:
                await ctx.io.write(
                    "\n  `0\"I don't know anyone with a name even close to that.\"`2\n"
                )
                continue
            if other.id == ctx.player.id:
                await ctx.io.write(
                    '\n  `0"Why, Id hope you know what you\'ve said about yourself.."`2,\n'
                    "  the old man cackles.\n"
                )
                continue
            him = "him" if other.gender == "M" else "her"
            await ctx.io.write("\n  `2The Old Man thinks for a minute..\n")
            if not other.description1 and not other.description2:
                await ctx.io.write(
                    f'  `0"{other.name}?  I haven\'t heard anything about {him}."\n'
                )
            else:
                await ctx.io.write(
                    f'  `0"{other.name}?  I know who that is. Last I heard.."\n\n'
                    f"    `2{other.description1}\n    `2{other.description2}\n"
                )
            continue

        await ctx.io.write('\n  `0"What do you want me to remember about you?"\n')
        first = (await ctx.io.readline(" `2-> `%", maxlen=70)).strip()
        if not first:
            continue
        ctx.player.description1 = first
        second = (await ctx.io.readline(" `2-> `%", maxlen=70)).strip()
        ctx.player.description2 = second
        await ctx.io.write('\n  `2"`0It has been noted..`2"\n')


async def _conversation(ctx: GameCtx) -> None:
    """The tavern's message wall -- lord.js's ``converse(darkhorse=true)``
    (:8459-8574), which keeps its lines in ``darkbar.lrd``. Here they live
    in ``igm_data`` so there is no file to share between pods."""
    raw = await ctx.db.igm_data.get_raw(_WALL_KEY, _WALL_FIELD)
    lines = raw.split("\n") if raw else []

    await ctx.io.write("\n  `%Conversation at the Bar`#\n\n")
    if lines:
        for line in lines:
            await ctx.io.write(f"  {line}\n")
    else:
        await ctx.io.write("  `2The bar is quiet. No one has said a thing.\n")

    choice = await ctx.io.menu(
        {"C": "continue", "A": "add"},
        "\n  `2(`5C`2)ontinue  (`5A`2)dd to Conversation `0[`5C`0] : `%",
        default="C",
    )
    if choice != "A":
        return

    await ctx.io.write(
        "\n `2Share your feelings now.. (Max 75 char!)\n"
    )
    said = (await ctx.io.readline(" `0>`2", maxlen=_WALL_LINE_MAX)).strip()
    if len(said) < 2:
        await ctx.io.write(
            "  You decide not to speak..You really don't have anything to say.\n"
            "  (ENTRY NOT ENTERED)\n"
        )
        return

    lines.append(f"`0{ctx.player.name}`2: {said}")
    async with ctx.db.transaction() as tx:
        await tx.igm_data.set_raw(
            _WALL_KEY, _WALL_FIELD, "\n".join(lines[-_WALL_MAX:])
        )


async def _rankings(ctx: GameCtx) -> None:
    """The Old Man's Ranking (lord.js:12811-12846): by lays, then charm."""
    everyone = [p for p in await ctx.db.players.all_players() if p.lays > 0]
    everyone.sort(key=lambda p: (-p.lays, -p.charm))

    clean = bool(ctx.config.get("clean_mode", False))
    heading = "Evil Deeds" if clean else "Lays"
    await ctx.io.write(
        "\n\n                          `%The Old Man's Ranking\n\n"
        f"  `0Name                             {heading:<12}        Player Kills\n"
        "`#" + "-=" * 38 + "\n"
    )
    if not everyone:
        await ctx.io.write(
            "  `0Sad times indeed, no one has managed to make this list.\n"
        )
    for other in everyone:
        await ctx.io.write(
            f"  `0{other.name:<22}            `%{other.lays:>5}"
            f"                      `4 {other.pvp_kills:>6}\n"
        )
    await ctx.io.pause()


async def _screen(ctx: GameCtx) -> None:
    """Reconstructed from lord.js's RIP fallback text (:12248-12256); the
    text-mode version comes from ``lrdfile('CLOAK')``, absent here."""
    await ctx.io.write(
        "\n`%  The Dark Cloak Tavern\n"
        "`2  A blazing fire warms your heart as well as your body in this fragrant\n"
        "  roadhouse.  Many a weary traveler has had the fortune to find this cozy\n"
        "  hostel, to escape the harsh reality of the dense forest for a few\n"
        "  moments.  You notice someone has etched something in the table you are\n"
        "  sitting at.\n"
    )


@scene("dark_cloak")
async def dark_cloak(ctx: GameCtx) -> str:
    """lord.js:12847-12915.

    Always returns to the forest: the tavern is reached from the forest's
    own random-event table, and every sub-screen it offers is drawn inline
    rather than by leaving.
    """
    await _screen(ctx)
    played = 0

    while True:
        await ctx.io.write(
            "\n  `2(`0G`2)amble with the old man\n"
            "  `2(`0T`2)alk to Chance\n"
            "  `2(`0W`2)ise old man\n"
            "  `2(`0C`2)onversation at the bar\n"
            "  `2(`0E`2) The Old Man's Ranking\n"
            "  `2(`0D`2)aily happenings\n"
            "  `2(`0Y`2)our stats\n"
            "  `2(`0R`2)eturn to the forest\n"
        )
        choice = await ctx.io.menu(
            {
                "G": "gamble",
                "T": "chance",
                "W": "old man",
                "C": "conversation",
                "E": "rankings",
                "D": "news",
                "Y": "stats",
                "?": "menu",
                "R": "return",
            },
            "\n  `2DarkCloak Tavern `2(C,E,T,D,G,W,R) (? for menu)\n"
            "  `2Your command? [`0R`2] : `%",
            default="R",
        )

        if choice == "G":
            played = await _gamble(ctx, played)
        elif choice == "T":
            await _chance(ctx)
        elif choice == "W":
            await _old_man(ctx)
        elif choice == "C":
            await _conversation(ctx)
        elif choice == "E":
            await _rankings(ctx)
        elif choice == "D":
            # lord.js calls show_log()/show_stats() inline here rather than
            # leaving the tavern (:12864, :12869), so these do too.
            await news_scene.news(ctx)
        elif choice == "Y":
            await stats_scene.stats(ctx)
        elif choice == "?":
            await _screen(ctx)
        else:
            await ctx.save()
            return "forest"
