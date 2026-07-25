"""The Outlands Tavern v1.3 -- by Jason Brown (``igms_to_port/outs13.zip``,
version date 10/11/1999).

**Provenance tier: script-port, hybrid.** ``outs13.zip`` is shelved Shelf A
(direct-portable) because it ships two real ``.RHP`` "Random Happening
Program" scripts in the archive's own readable script language -- but
``OUTLANDS.EXE`` itself, the Tavern's main hub (rooms, the Back Room, the
sneak-upstairs attack, the BarKeep), is a compiled Turbo Pascal 6.0 binary
with no surviving source, exactly like WereWolf's ``WEREWOLF.EXE``
(``igms/werewolf/igm.py``). So this port is genuinely split down the
middle: **direct script-port** for the one mechanic recorded in executable
script logic (the Wander action, below), and **documented recreation**
(verbatim numbers from ``OUTLANDS.TXT``/``WHATSNEW.TXT``/``FILE_ID.DIZ``)
for everything else. Both halves are disclosed separately below.

Sources read: ``OUTLANDS.TXT`` (the main doc, "RENAMED FROM
OUTLANDS.DOC!"), ``FILE_ID.DIZ``, ``WHATSNEW.TXT`` (full revision history
v.alpha through v1.3), ``CODES.TXT`` (the RHP scripting language
reference), ``SAMPLE.RHP`` and ``SHINY.RHP`` (the two bundled RHP scripts).
``CODES.TXT`` documents the same ``@``-directive language used by
``reference/igm-sources/lordts/lordcave``'s own RHP scripts (its
``@PROGRAM@`` directive literally names "LORDCAVE or OUTLANDS" as the two
hosts one script can target) -- ``reference/igm-sources/lordts/lordcave/
rhp.ts`` (an in-repo reimplementation of that same interpreter) was read to
confirm two directives' exact semantics against ``CODES.TXT``'s prose:
``@RANDOM@ x`` branches uniformly 1-in-``x`` into the following ``@##n``
sections, and a bare ``@GOLD@``/``@GEMS@`` value (no ``=``/``%`` prefix) is
an **additive** delta, with ``N*LEVEL`` meaning ``N`` multiplied by the
player's current level (``rhp.ts``'s ``applyStat``/``evaluateExpr``,
lines ~474-535) -- exactly what ``CODES.TXT`` states ("NEW: Putting *LEVEL
multiplies the number times the player's level").

--------------------------------------------------------------------------
**Direct script-port: the Wander action, from ``SHINY.RHP`` verbatim.**
--------------------------------------------------------------------------

``SHINY.RHP``'s own header calls it "The Strange Shiny Thing" and says
"This is included so your users have an extra Random Happening" -- unlike
its sibling ``SAMPLE.RHP`` ("RHP_name: Sample Program... Fell [sic] free to
use this in writing your own random happening"), which is explicitly a
sysop-facing scripting tutorial that narrates its own scripting language
in-fiction ("This is a sample of...`0`0's new built in programing
language") -- not in-world content. Only ``SHINY.RHP`` is ported; the
tutorial script is not (see "Not ported" below).

``SHINY.RHP``'s script, quoted in full:

    You look around, and in the back of the room you see a strange
    looking shiny object. Pick it up?
    @YESNO@
    @##Y
    You walk over and find
    @RANDOM@ 4
    @##1 / @##2:  a piece of tin foil. You throw the piece of foil away
                  and scowl.
    @##3:         some gold coins! Not much, but it helps.
                  @GOLD@ 10*LEVEL
    @##4:         a pile of gems! Wow, what a find!
                  @GEMS@ 2*LEVEL
    @##N:         You decide you'd rather pay attension to your beer.

This is ported exactly: a 1-in-4 uniform roll, where two of the four
outcomes (branches 1 and 2) are the *same* "nothing" result, one grants
``10 * player.level`` gold, and one grants ``2 * player.level`` gems --
these three numbers (10, 2, and the 1-in-4 odds, with "nothing" getting a
double share) are recorded, not invented.

**Invented for the Wander action:** the original RHP engine rolled this
kind of Random Happening on its own schedule (LordCave's own equivalent
random-event table reserves a slot for RHP scripts entirely -- see
``reference/igm-sources/lordts/lordcave/README.md``'s probability table);
``IgmContext`` gives an IGM's ``enter()`` no background/ambient trigger
comparable to that (only the separate, opt-in ``forest_event``/
``inn_event`` hooks, which this doesn't fit -- the shiny object is
narrated as being in the room, not the Forest or the Inn), so this port
exposes Wander as a menu action instead, gated to once per day
(``daily_maint`` clears it) so a player can't grind it for infinite gold --
the original's real trigger frequency is not recorded anywhere in this
archive.

--------------------------------------------------------------------------
**Documented recreation: everything else, from ``OUTLANDS.TXT`` /
``WHATSNEW.TXT`` / ``FILE_ID.DIZ``.**
--------------------------------------------------------------------------

Recorded, verbatim:

* ``FILE_ID.DIZ``: "A nice little place to visit or perhaps to stay the
  night! Keeps users (mostly) save [sic] and warm during the night, plus
  they can talk and PARTY! ... includes a hard to get in Back Room!" --
  overnight rooms, conversation, and a gated Back Room all exist.
* ``WHATSNEW.TXT`` v1.1: "If user has 100 or more charm they only pay 33%
  normal prices to stay overnight." -- the room-price charm discount's
  threshold (100) and fraction (33%) are both literal.
* ``WHATSNEW.TXT`` v1.0: "Can once again ask The BarKeep about the Drunk
  Meter." -- a Drunk Meter exists and the BarKeep is who you ask about it.
* ``WHATSNEW.TXT`` v1.1: "Added The Backroom." / v1.2: "The fairies in the
  Backroom now actually put people into high spirits when they say they
  do." -- the Back Room's fairies grant high spirits; this project's
  ``Player.high_spirits`` field (``pylord/models.py``, the same flag
  ``pylord/engine/scenes/jennie.py`` and ``daily.py`` read/write) is a
  direct, literal match for this recorded effect -- no adaptation needed.
* ``WHATSNEW.TXT`` v1.2: "Added (V)iew your stats to many of the menus."
  -- a stats view exists and is bound to the ``V`` key.
* ``WHATSNEW.TXT`` v1.1: "If player has a fairy, they can sneak by the
  BarKeep with no chance of being caught, and they lose the fairy." -- a
  fairy is a guaranteed, single-use bypass for the sneak-upstairs risk.
* ``WHATSNEW.TXT`` v1.1: "If a user sneaks upstairs and tries to attack
  someone that is too weak, it lets them choose another right away." --
  a "too weak" check exists and refusing it doesn't cost another risk-roll.
* ``WHATSNEW.TXT`` v1.2: "Killing someone in both a fight and in the
  dungeon now counts as a player kill." -- confirms the sneak-upstairs
  encounter was a real, lethal PvP fight in the original.
* ``WHATSNEW.TXT`` v1.1: "Users staying in the Tavern will never lose
  thier [sic] rooms after maintence is ran now!" -- a rented room survives
  the daily-maintenance boundary; this port's ``daily_maint`` deliberately
  does **not** clear the room flag, unlike every other per-day gate here.
* ``WHATSNEW.TXT`` v1.2: "Removed the Order Stuff Menu, can no longer
  order stuff." -- confirms v1.3 (this port's target) has no item shop.
* ``WHATSNEW.TXT`` v1.3: "Stuff from the Party Menu removed." -- the one
  feature named in ``OUTLANDS.TXT``'s closing credits that had a concrete
  mechanic, Dancing, is not recorded with any number or effect anywhere in
  either doc and is presumed folded into whatever "stuff" v1.3 removed;
  not ported (see "Not ported" below).
* ``OUTLANDS.TXT``'s own introduction: "do not use this IGM with other
  IGMs that let users kill other users, it will screw everything up! The
  only one I know of is Werewolf!!, but be warned!" -- a wry detail: the
  original Outlands Tavern is *itself* one of the two lethal-PvP IGMs it's
  warning about pairing with another lethal-PvP IGM. This project's
  no-two-IGMs-can-kill guardrail (below) makes that warning moot by
  construction.

**No-kill guard (why the sneak-upstairs attack can never actually end a
character), same adaptation as ``igms/werewolf/igm.py`` and
``igms/warriors_graveyard/igm.py``:** ``IgmContext.other_players()`` hands
an IGM only a read-only :class:`~pylord.hooks.PlayerSummary` (name, level,
alive, class_type -- no hp/strength/defense to run a real fight against,
and no id to key a store entry against beyond the player's own name), and
``ctx.mail()``'s ``effect`` dict has no ``hp``/``alive`` key
(``pylord/engine/effects.py``) -- there is no channel through which this
IGM could mark another player's row dead. A successful sneak-upstairs
attack here never touches the victim's ``alive``, ``hp``, or
``pvp_kills`` (``pvp_kills`` is the real attack path's -- and only the
real attack path's, ``pylord/engine/scenes/pvp.py`` -- stat to own, per
the same precedent WereWolf's docstring establishes); it drains a
level-scaled slice of the victim's exp via a mailed effect instead
(``VICTIM_EXP_DRAIN_PER_LEVEL``, the same value WereWolf uses, reused
rather than re-invented since both face the identical "no live exp
visible" constraint). A failed attack floors the *attacker's* own hp at 1,
the same floor ``warriors_graveyard``/``werewolf`` use for their own
no-kill guards.

**Invented (and why), for everything not covered above:**

* **Menu keys/labels/flavor text and the overall Tavern hub structure**
  (``(R)oom``, ``(T)alk``, ``(B)ackroom``, ``(W)ander``, ``(S)neak``,
  ``(V)iew stats``, ``(L)eave``) -- no transcript or screenshot survives,
  only the feature list above.
* **Room base price** (``ROOM_COST_PER_LEVEL = 400``) -- no number
  survives in ``outs13.zip`` itself; chosen to match this project's own
  Red Dragon Inn's identical "pay gold, sleep safely" mechanic
  (``pylord/engine/scenes/inn.py``'s ``_ROOM_COST_PER_LEVEL = 400``)
  rather than invent an unrelated figure for what is functionally the
  same trade. The Inn waives the fee entirely above 99 charm
  (``_FREE_ROOM_CHARM``); this Tavern is deliberately stingier, per its
  own recorded 33%-not-100%-discount, at a rougher, cheaper establishment.
* **Talk / Drunk Meter**: no formula for how drinking raises the meter
  survives, only that you can ask about it. Modeled as a private per-IGM
  counter (this project's ``ctx.store``, mirroring how the real
  ``OUTLANDS.DAT``/``EXTRA.CFG`` kept the Tavern's own state separate from
  LORD's own ``PLAYER.DAT`` -- ``CODES.TXT``'s ``DRUNKLEVEL`` RHP variable
  confirms a drunk-level stat existed in that separate file), incremented
  by 1 per Talk, reset nightly (a hangover fading by morning is invented
  flavor, not a recorded rule).
* **Back Room entry odds** (``BACKROOM_ENTRY_CHANCE_DENOM = 4``, a 1-in-4
  chance) -- no odds survive for "hard to get in," only the adjective
  itself; gated to one attempt per day like every other daily gate in this
  project's IGMs.
* **Sneak-upstairs catch odds** (``SNEAK_CATCH_CHANCE_DENOM = 4``, a
  1-in-4 chance of being caught without a fairy) and **the "too weak"
  bound** (``target.level + 1 < attacker.level``) -- no odds survive
  either; the too-weak bound is borrowed verbatim from this project's own
  real sleeper-attack precedent, the Inn bartender's bribe-to-attack
  ("A child could beat that wimp!", ``pylord/engine/scenes/inn.py``'s
  ``_bribe_attack``), the closest analog this codebase has to Outlands'
  own "sneak upstairs and attack a sleeping guest" mechanic.
* **The return-trip catch risk, and why "upstairs" is read as "downstairs."**
  ``WHATSNEW.TXT`` v1.1 says, verbatim: "If user can't find someone in the
  rooms to kill, they must risk sneaking back upstairs." Read literally
  this doesn't parse -- the player is already upstairs at that point, per
  the same doc's own "sneaks upstairs and tries to attack someone" wording
  a few lines above it -- so there is nothing to "sneak back upstairs"
  *to*. This port reads it as a typo for "downstairs": the archive's prose
  is typo-heavy throughout (e.g. "thier" and "save" for "safe" quoted
  elsewhere in this docstring, plus "completly," "intresting," "awnser,"
  and "orginally" in ``OUTLANDS.TXT`` itself), and "the return trip out of
  the rooms also carries a catch-risk" is the only reading that fits the
  surrounding sentence and the sneak-in risk it's paired with. Implemented
  as a second ``SNEAK_CATCH_CHANCE_DENOM`` roll (skipped, like the entry
  roll, when a fairy is protecting the whole excursion) after the sneak
  loop ends with no attack resolved.
* **A caught sneak (either direction) costs nothing beyond the wasted
  trip** -- no penalty is recorded, so none beyond "no kill, try again
  another day" is invented.
* **Attack win roll** (``rng.randrange(attacker.level + SNEAK_ATTACK_EDGE)``
  vs. ``rng.randrange(target.level)``) -- no odds survive; the same
  "randrange vs. randrange, one side gets a fixed edge" shape WereWolf's
  own attack already established, with a smaller edge
  (``SNEAK_ATTACK_EDGE = 2`` vs. WereWolf's 3) since a sneaking mortal's
  advantage over a sleeping mortal is invented as slighter than a
  werewolf's advantage over an unaware human.
* **Reward for a successful sneak attack** (``REWARD_GOLD_PER_LEVEL = 50``
  gold, ``rng.randint(1, target.level * REWARD_EXP_PER_LEVEL_MAX)`` exp,
  ``REWARD_EXP_PER_LEVEL_MAX = 20``) -- no numbers survive; level-scaled
  off the *victim* (the only stat ``PlayerSummary`` exposes), the same
  shape ``warriors_graveyard``'s undead-fight reward already uses.
* **A successful sneak attack clears the victim's room flag** -- invented
  for coherence (a guest who was just attacked in their room is no longer
  a repeatable "asleep in room N" target until they rent again); not
  recorded either way.
* **Room checkout**: a room persists until the same player next enters
  the Tavern (per the "never lose their rooms" quote above, it survives
  ``daily_maint``, but nothing records how it eventually clears) -- this
  port clears it at the top of the *player's own next visit* ("gathering
  your things" flavor), the smallest rule that both satisfies the quote
  and stops a single stay from flagging someone as an eternal target.
* **View Stats' exact field list** -- level/exp/gold/gems/hp/strength/
  defense/charm -- no screenshot of the real stats screen survives; this
  is the same subset of ``Player`` fields every other bundled IGM already
  reads through ``PlayerView``.

**Not ported:**

* **``SAMPLE.RHP``** ("Sample Program") -- explicitly a sysop-facing
  scripting tutorial ("Fell [sic] free to use this in writing your own
  random happening"), not in-world Tavern content; its own narration
  breaks the fourth wall to describe the scripting language itself.
  Porting its text as a real Tavern encounter would put words about
  pylord's own implementation into a fictional BarKeep's mouth.
* **BADWORDS.DAT profanity filtering** (v1.1: "Uses LORD v3.55
  BADWORDS.DAT file in the conversation if it exists...") -- this port
  takes no free-text conversational input for the BarKeep to filter, and
  pylord has no BADWORDS.DAT equivalent; there is nothing here for a
  filter to apply to.
* **The married-spouse free stay** (v1.1: "If user is married to another
  user and the spouse is in a Tavern room, they sleep for free!") --
  ``PlayerView.married_to`` exposes only the spouse's numeric player id,
  and ``IgmContext`` gives an IGM no id-to-name (or id-to-``PlayerSummary``)
  lookup to resolve it against the room roster (``other_players()`` and
  ``ctx.mail()`` both key strictly by name) -- there is no way to check
  "is my spouse currently in a room" through the facade this project
  gives IGMs, unlike every other invented gap above, which was a missing
  *number*, not a missing *capability*.
* **The Order Stuff Menu / an item shop** -- v1.2 removed it in the real
  archive; not reintroduced here.
* **Dancing / the ATM** -- ``OUTLANDS.TXT``'s closing credits ("Dancing,
  the Stats, and the ATM were orginally from that ill-fated IGM") name
  Dancing and an ATM alongside Stats (which *is* ported, above) but record
  no menu key, cost, or effect for either. The ATM is additionally
  redundant with this project's own real bank/deposit scene
  (``pylord/engine/scenes/bank.py``); Dancing has no mechanic anywhere in
  either archive doc to adopt.
* **The BBS-vs-LORD-return exit-text branch** (v1.1: "'You walk back to
  town.' if user is returning to LORD and 'Returning to the Mundane
  World...' if going to BBS.") -- pylord has no concept of "exiting to a
  wider BBS door menu" distinct from "returning to the Realm"; only the
  LORD-return line applies here.
"""

from __future__ import annotations

from pylord.hooks import IGM, IgmContext, IgmMaintContext

_MENU = (
    "\n  `5The Outlands Tavern`2\n"
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
    "  `2(`0R`2)oom for the night\n"
    "  `2(`0T`2)alk to the BarKeep\n"
    "  `2(`0B`2)ack Room\n"
    "  `2(`0W`2)ander around the room\n"
    "  `2(`0S`2)neak upstairs\n"
    "  `2(`0V`2)iew your stats\n"
    "  `2(`0L`2)eave\n"
)

_NAME_MAXLEN = 20

# "If user has 100 or more charm they only pay 33% normal prices to stay
# overnight." (WHATSNEW.TXT, v1.1) -- both literal.
CHARM_DISCOUNT_THRESHOLD = 100
DISCOUNT_PRICE_FRACTION = 0.33

# Invented -- see module docstring's "Room base price" note. Matches
# pylord/engine/scenes/inn.py's own _ROOM_COST_PER_LEVEL.
ROOM_COST_PER_LEVEL = 400

# Invented -- see module docstring's "Talk / Drunk Meter" note.
DRUNK_INCREMENT = 1

# Invented -- see module docstring's "Back Room entry odds" note.
BACKROOM_ENTRY_CHANCE_DENOM = 4

# Invented -- see module docstring's "Wander action" note. SHINY.RHP's own
# @RANDOM@ 4 / @GOLD@ 10*LEVEL / @GEMS@ 2*LEVEL are recorded, verbatim.
WANDER_OUTCOME_COUNT = 4
WANDER_GOLD_PER_LEVEL = 10
WANDER_GEMS_PER_LEVEL = 2

# Invented -- see module docstring's "Sneak-upstairs catch odds" note.
SNEAK_CATCH_CHANCE_DENOM = 4
# Borrowed verbatim from pylord/engine/scenes/inn.py's own sleeper-attack
# precedent ("A child could beat that wimp!") -- see module docstring.
TOO_WEAK_LEVEL_MARGIN = 1
# Invented -- see module docstring's "Attack win roll" note.
SNEAK_ATTACK_EDGE = 2
# Invented -- see module docstring's "Reward for a successful sneak
# attack" note.
REWARD_GOLD_PER_LEVEL = 50
REWARD_EXP_PER_LEVEL_MAX = 20
# Reused from igms/werewolf/igm.py -- see module docstring's no-kill guard
# note on why the same value applies here.
VICTIM_EXP_DRAIN_PER_LEVEL = 10


class OutlandsTavern(IGM):
    key = "outlands_tavern"
    name = "The Outlands Tavern"
    author = "Jason Brown"
    default_enabled = True

    async def enter(self, ctx: IgmContext) -> None:
        p = ctx.player
        room_key = f"room:{p.name.lower()}"
        if ctx.store.get(room_key, False):
            ctx.store.delete(room_key)
            await ctx.term.write(
                "\n  `2You gather your things from last night's room and head\n"
                "  back downstairs.\n"
            )
        await ctx.term.write(
            "\n  `2You push through the door of the Outlands Tavern, off the\n"
            "  beaten path at the edge of the Realm.\n"
        )
        while True:
            await ctx.term.write(_MENU)
            choice = await ctx.term.menu(
                {
                    "R": "room",
                    "T": "talk",
                    "B": "backroom",
                    "W": "wander",
                    "S": "sneak",
                    "V": "stats",
                    "L": "leave",
                },
                "  `2Your choice? [`0L`2] : `%",
            )
            if choice == "L":
                await ctx.term.write("\n  `2You walk back to town.\n")
                return
            if choice == "R":
                if await self._room(ctx):
                    return
            elif choice == "T":
                await self._talk(ctx)
            elif choice == "B":
                await self._backroom(ctx)
            elif choice == "W":
                await self._wander(ctx)
            elif choice == "S":
                await self._sneak(ctx)
            else:
                await self._view_stats(ctx)

    async def _room(self, ctx: IgmContext) -> bool:
        """Returns ``True`` if a room was actually taken (caller ends the
        visit, same convention as ``inn.py``'s ``_rent_room``)."""
        p = ctx.player
        cost = ROOM_COST_PER_LEVEL * p.level
        if p.charm >= CHARM_DISCOUNT_THRESHOLD:
            cost = int(cost * DISCOUNT_PRICE_FRACTION)
        await ctx.term.write(
            f'\n  `2The BarKeep looks you over.  `0"A room for the night?  '
            f"That'll be {cost} gold.\"`2\n"
        )
        choice = await ctx.term.menu({"Y": "yes", "N": "no"}, "  `2Do you agree? [`0Y`2] : `%")
        if choice == "N":
            await ctx.term.write("\n  `2The BarKeep shrugs and turns away.\n")
            return False
        if p.gold < cost:
            await ctx.term.write("\n  `0\"Hey!  You don't have that much gold!\"`2\n")
            await ctx.term.pause()
            return False
        p.gold -= cost
        ctx.store.set(f"room:{p.name.lower()}", True)
        await ctx.term.write(
            "\n  `2You are shown to a small room upstairs.  You bar the door\n"
            "  and fall fast asleep.\n"
        )
        return True

    async def _talk(self, ctx: IgmContext) -> None:
        p = ctx.player
        gate = f"drunk:{p.name.lower()}"
        level = ctx.store.get(gate, 0) + DRUNK_INCREMENT
        ctx.store.set(gate, level)
        await ctx.term.write(
            '\n  `2You ask the BarKeep about the Drunk Meter.  `0"Reading you\n'
            f'  about a `%{level}`0 tonight,"`2 he says, refilling your cup anyway.\n'
        )
        await ctx.term.pause()

    async def _backroom(self, ctx: IgmContext) -> None:
        p = ctx.player
        gate = f"backroom:{p.name.lower()}"
        if ctx.store.get(gate, False):
            await ctx.term.write(
                "\n  `2The curtain to the Back Room stays shut for you tonight.\n"
            )
            await ctx.term.pause()
            return
        ctx.store.set(gate, True)
        if ctx.rng.randrange(BACKROOM_ENTRY_CHANCE_DENOM) == 0:
            p.high_spirits = 1
            await ctx.term.write(
                "\n  `2A fairy slips out from behind the curtain and dances\n"
                "  around your head.  `%YOU FEEL IN HIGH SPIRITS!`2\n"
            )
        else:
            await ctx.term.write(
                "\n  `2You try the curtain to the Back Room.  It doesn't budge --\n"
                "  hard to get into, just like they say.\n"
            )
        await ctx.term.pause()

    async def _wander(self, ctx: IgmContext) -> None:
        p = ctx.player
        gate = f"shiny:{p.name.lower()}"
        if ctx.store.get(gate, False):
            await ctx.term.write(
                "\n  `2You look around the room again, but nothing new catches\n"
                "  your eye tonight.\n"
            )
            await ctx.term.pause()
            return
        ctx.store.set(gate, True)
        await ctx.term.write(
            "\n  `2You look around, and in the back of the room you see a\n"
            "  strange looking shiny object.  Pick it up?\n"
        )
        choice = await ctx.term.menu({"Y": "yes", "N": "no"}, "  `2[`0Y`2] : `%")
        if choice == "N":
            await ctx.term.write(
                "\n  `2You decide you'd rather pay attention to your beer.\n"
            )
            await ctx.term.pause()
            return
        outcome = ctx.rng.randrange(WANDER_OUTCOME_COUNT)
        if outcome <= 1:
            await ctx.term.write(
                "\n  `2You walk over and find a piece of tin foil.  You throw\n"
                "  it away and scowl.\n"
            )
        elif outcome == 2:
            gold = WANDER_GOLD_PER_LEVEL * p.level
            p.gold += gold
            await ctx.term.write(
                "\n  `2You walk over and find some gold coins!  Not much, but\n"
                f"  it helps.\n  `0YOU GAIN {gold} GOLD!\n"
            )
        else:
            gems = WANDER_GEMS_PER_LEVEL * p.level
            p.gems += gems
            await ctx.term.write(
                "\n  `2You walk over and find a pile of gems!  Wow, what a find!\n"
                f"  `0YOU GAIN {gems} GEMS!\n"
            )
        await ctx.term.write(
            "\n  `2You return to your seat and act like nothing happened.\n"
        )
        await ctx.term.pause()

    async def _sneak(self, ctx: IgmContext) -> None:
        p = ctx.player
        protected = bool(p.has_fairy)
        if protected:
            p.has_fairy = 0
            await ctx.term.write(
                "\n  `2Your fairy flits ahead of you, and the BarKeep somehow\n"
                "  never looks up as you slip past.\n"
            )
        elif ctx.rng.randrange(SNEAK_CATCH_CHANCE_DENOM) == 0:
            await ctx.term.write(
                "\n  `4The BarKeep catches you sneaking for the stairs and\n"
                "  tosses you back out into the common room.\n"
            )
            await ctx.term.pause()
            return
        else:
            await ctx.term.write("\n  `2You slip past the BarKeep and creep upstairs.\n")

        while True:
            sleepers = [
                o for o in ctx.other_players() if o.alive and ctx.store.get(f"room:{o.name.lower()}", False)
            ]
            if not sleepers:
                await ctx.term.write(
                    "\n  `2Every room upstairs is empty tonight.\n"
                )
                break

            raw = (
                await ctx.term.readline(
                    "\n  `2Sneak into whose room? : `%", maxlen=_NAME_MAXLEN
                )
            ).strip()
            if not raw:
                await ctx.term.write("\n  `2You lose your nerve.\n")
                break

            by_name = {o.name.lower(): o for o in sleepers}
            target = by_name.get(raw.lower())
            if target is None:
                await ctx.term.write(
                    f"\n  `2No one named `0{raw} `2is renting a room tonight.\n"
                )
                continue
            if target.level + TOO_WEAK_LEVEL_MARGIN < p.level:
                await ctx.term.write(
                    f"\n  `2{target.name} `2is far too weak to bother with -- you\n"
                    "  pick another door.\n"
                )
                continue

            confirm = await ctx.term.menu(
                {"Y": "yes", "N": "no"},
                f"  `2Attack `0{target.name}`2? [`0N`2] : `%",
            )
            if confirm == "N":
                continue

            await self._resolve_attack(ctx, target)
            return

        # Found no one to rob, or lost their nerve -- must risk the trip
        # back down. "If user can't find someone in the rooms to kill,
        # they must risk sneaking back upstairs." (WHATSNEW.TXT, v1.1) --
        # "upstairs" read as a typo for "downstairs"; see the module
        # docstring's "The return-trip catch risk" note for why.
        if not protected and ctx.rng.randrange(SNEAK_CATCH_CHANCE_DENOM) == 0:
            await ctx.term.write(
                "\n  `4The BarKeep spots you sneaking back down and gives you a\n"
                "  scolding, but lets you go.\n"
            )
        else:
            await ctx.term.write("\n  `2You slip back downstairs, unnoticed.\n")
        await ctx.term.pause()

    async def _resolve_attack(self, ctx: IgmContext, target) -> None:
        p = ctx.player
        mine = ctx.rng.randrange(max(1, p.level + SNEAK_ATTACK_EDGE))
        his = ctx.rng.randrange(max(1, target.level))
        if mine >= his:
            gold = REWARD_GOLD_PER_LEVEL * target.level
            exp = ctx.rng.randint(1, max(1, target.level * REWARD_EXP_PER_LEVEL_MAX))
            p.gold += gold
            p.exp += exp
            drain = target.level * VICTIM_EXP_DRAIN_PER_LEVEL
            ctx.store.delete(f"room:{target.name.lower()}")
            ctx.mail(
                target.name,
                text=(
                    "  `%YOU HAVE BEEN ATTACKED IN YOUR ROOM!\n"
                    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
                    "  `0Someone crept in while you slept and rifled through your\n"
                    "  things.\n"
                    f"  `4YOU LOSE {drain} EXPERIENCE!\n"
                ),
                effect={"exp": -drain},
            )
            await ctx.term.write(
                f"\n  `2You catch `0{target.name} `2fast asleep and clean out their\n"
                f"  pockets before they wake.\n"
                f"  `0YOU RECEIVE {gold} GOLD AND {exp} EXPERIENCE!\n"
            )
        else:
            hp_max = max(1, p.hp_max)
            p.hp = max(1, p.hp - hp_max // 3)
            await ctx.term.write(
                f"\n  `4{target.name} `4wakes with a shout and fights you off before\n"
                "  you can get away clean.\n"
            )
        await ctx.term.pause()

    async def _view_stats(self, ctx: IgmContext) -> None:
        p = ctx.player
        await ctx.term.write(
            "\n  `5Your Stats`2\n"
            f"  `2Level: `0{p.level}`2   Experience: `0{p.exp}`2\n"
            f"  `2Gold: `0{p.gold}`2   Gems: `0{p.gems}`2\n"
            f"  `2Hitpoints: `0{p.hp}/{p.hp_max}`2\n"
            f"  `2Strength: `0{p.strength}`2   Defense: `0{p.defense}`2   "
            f"Charm: `0{p.charm}`2\n"
        )
        await ctx.term.pause()

    async def daily_maint(self, ctx: IgmMaintContext) -> None:
        for player in ctx.repo.all_players():
            key = player.name.lower()
            ctx.store.delete(f"drunk:{key}")
            ctx.store.delete(f"backroom:{key}")
            ctx.store.delete(f"shiny:{key}")
            # room:<key> intentionally NOT cleared -- "Users staying in
            # the Tavern will never lose thier rooms after maintence is
            # ran now!" (WHATSNEW.TXT, v1.1). See module docstring.
