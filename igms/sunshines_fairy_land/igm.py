"""SunShines' Fairy Land v2.6 -- by Becky Benjamin (``igms_to_port/sfairy26.zip``,
Copyright 1995).

**Provenance tier: documented recreation.** ``SFAIRY.EXE`` "was compiled with
Korombos' IGMDRV in Borland Pascal" (``SFAIRY.DOC``) -- a compiled DOS
binary, no source survives, and ``reference/igm-sources/lordts/`` has no
"fairy"-named IGM in it (checked; its port list is aratime, barak,
felicity, freeworld2, gravyard, lordcave, lotto, lrdevent, npclord,
oorphans, outhouse, sandbar, teamlord, violet -- none of which is this
IGM or a plausible lineage match). So, like WereWolf (``igms/werewolf/
igm.py``), this is built entirely from surviving archive prose plus one
piece of surviving *data*: ``SFAIRY.CFG``'s own default-price bytes.

Sources read (Step 1): ``sfairy26.zip`` (v2.6, this port's target) --
``FILE_ID.DIZ``, ``SFAIRY.DOC``, ``WHATS.NEW``, ``READ.ME``, ``SFAIRY.CFG``,
``SFAIRY.REG``, ``SFAIRY.DAT``, ``LORD.IGM``; and ``sfairy23.zip`` (v2.3, an
earlier surviving version) -- the same file set. Per this task's brief
("earlier-version docs often record numbers the later version assumes"):
v2.3's ``WHATS.NEW`` and ``SFAIRY.CFG`` were checked line-for-line against
v2.6's and found to record the **same** feature text and the **same** 15
default prices -- nothing in v2.3 supplies a number v2.6 lacks. v2.6's own
``SFAIRY.DOC`` still opens its file-list section with "Files that should be
found in the SFAIRY23.ZIP:" (an un-updated leftover from the v2.3 doc,
carried forward verbatim), which is itself the evidence the two versions
share one doc lineage rather than v2.6 being independently rewritten.

**Recorded, verbatim:**

* ``FILE_ID.DIZ``: "Visit SunShines' Fairy Land and try to catch a Fairy.
  Checkout Sunshines' General Store or try to win one of 8 different
  prizes, by guessing the number SunShine is thinking of." -- the IGM's
  three activities (catch a fairy, a General Store, an 8-prize
  number-guessing game) and the prize count (8) are literal.
  ``SFAIRY.DOC``: "Programed & Designed by Becky Benjamin" / "Copyright (C)
  1995" / "SFAIRY.EXE was compiled with Korombos' IGMDRV in Borland
  Pascal."
* ``FILE_ID.DIZ``: "Now limits fairy tries to 5" -- corroborated by
  ``SFAIRY.DOC``'s own file-list entry, present verbatim in *both*
  archives: "SFAIRY.DAT    Player dat file for keeping track of player
  who've tried for a fairy 5 times, changes each day." -- 5 tries, reset
  daily, is doubly confirmed (the feature blurb and the file-list
  description agree independently).
* ``WHATS.NEW`` (v2.0, present unchanged through v2.6): "Sysops can now set
  prices in the General Store." / "All selling prices (with the exception
  of a fairy) are 1/2 the purchase price." -- a buy price and a half-price
  sell-back exist for the store's wares, except a fairy (sellable, but not
  at half price -- see "fairy selling price" below).
* ``WHATS.NEW`` (v2.2): "Lee Lint sysop of BYTE ME BBS requested player
  fights....so I replaced Lays with player fights." -- confirms the cfg
  field labelled "player fights" (below) maps onto this project's own
  ``player_fights`` (not ``lays``, which the real IGM used to charge
  before this rename).
* ``WHATS.NEW`` (v2.3): "Added a bank to the main menu." / "Players at
  level 12 can not enter SunShines Market." -- both literal; "Market" is
  read as the same feature ``FILE_ID.DIZ`` calls the "General Store" (the
  archive's own prose is inconsistent about the name across versions, the
  same kind of drift ``igms/outlands_tavern/igm.py``'s docstring already
  catalogs for this IGM catalogue's amateur writing).
* **The default price list, from ``SFAIRY.CFG``'s own bytes** (identical in
  both archives) **and ``WHATS.NEW``'s labelled cut-here template**, which
  names each value in order:

  .. code-block:: text

      35000    {attack strength}
      35000    {charm}
      35000    {defense points}
      35000    {experience}
      35000    {forest fights}
      35000    {gem}
      35000    {hit points}
      35000    {player fights....previously LAYS}
      45000    {horse}
      500000   {skill point}
      35000    {kids}
      350000   {resurrection}
      500000   {sex change}
      500000   {master fight}
      500000   {fairy selling price}

  Both the labels and the values are archive data, not paraphrase -- the
  15 numbers below (``PRICE_*``/``FAIRY_SELL_PRICE``) are these, verbatim.

**Invented (and why):**

* **What each store category actually does.** The doc/cfg record a *label*
  and a *price* for each of the 15 wares above, never a formula for what
  buying one unit grants. Eight of them (attack strength, charm, defense
  points, experience, forest fights, gem, hit points, player fights) share
  the "a point of X" framing and are modelled uniformly as a per-unit
  price against an established ``Player`` field -- the same quantity-prompt
  shape ``igms/gem_trader/igm.py``'s ``_sell`` already uses. "Hit Points"
  reads onto ``hp_max`` (a permanent ceiling raise, consistent with the
  other seven being permanent character-stat increases) rather than a
  one-off partial heal, which ``igms/apothecary/igm.py``'s Salve already
  covers far more cheaply -- a sale can never take ``hp_max`` to 0 (a live
  player with no hit-point ceiling is a state nothing else in this
  project's engine expects); the sale is refused outright rather than
  silently clamped, the same all-or-nothing shape every other insufficient-
  quantity refusal in this store already uses. "Experience" alone is
  scaled by ``EXP_UNIT`` (1,000 exp per unit bought/sold) rather than a
  literal +1 -- a raw single point of exp would make the one recorded
  price for it a complete no-op against an ``exp`` field that starts at 1
  and is measured in the thousands everywhere else in this project (e.g.
  the forest's own fairy blessing grants ``10 * level * level``).
* **Sellable vs. buy-only.** Six of the eight point-wares (attack strength,
  charm, defense points, experience, gem, hit points) are sellable at the
  recorded half-price, in any quantity, per the doc's own halving rule.
  "Forest Fights" and "Player Fights" are **buy-only** -- fixed in review
  (see "Fix pass" in ``.superpowers/sdd/task-sfairy-report.md``): both
  credit *today's* count directly (apothecary's Tonic of Vigour precedent)
  rather than this project's own permanent ``fight_bonus``/
  ``endurance_cost`` capacity system (``pylord/engine/fights.py``) -- that
  system already has its own escalating price, and a flat 35,000-gold
  buy-in would make it pointless. ``forest_fights`` specifically also
  regenerates for free in real time (``fights.py``'s ``apply_regen``, run
  on nearly every scene transition, refills toward
  ``max_forest_fights`` every ``fight_regen_minutes``) -- a sell-back at
  this store's flat half-price rate would let a player sell, wait for the
  free regen to top back up, and sell again, for unbounded gold (~70k/hr
  at prod's 15-minute regen). The sell side of this table was always this
  port's own invention, not a recorded mechanic (the archive records buy
  prices only), so removing it for these two violates nothing recorded.
  ``player_fights`` has no such regen and is individually bounded, but it
  is priced/shaped identically to ``forest_fights`` in the recorded cfg
  (both "most choices" style daily-fight resources) -- keeping the two
  consistent with each other, rather than carving an exception only the
  regen bug strictly requires, is the smaller line to draw.
* **The remaining six wares are one-time, non-quantity purchases**, each
  mapped onto the one existing ``Player``/game mechanic its label most
  plainly names:

  * *Horse* -> ``player.horse = 1`` (the flag ``pylord/engine/scenes/
    stats.py`` already reads: "You are on horseback").
  * *Skill point* -> ``player.skill_uses += 1``, the same field
    ``pylord/engine/scenes/training.py``'s class-skill system spends (not
    the permanent mastery rank).
  * *Kids* -> ``player.kids += 1`` (the field ``stats.py`` already
    displays as "You have N children").
  * *Sex change* -> toggles ``player.gender`` between ``"M"``/``"F"`` --
    a stock joke-shop trope this same archive index also ships as its own
    dedicated IGM (``clinic15.zip``, "The Surgical Clinic... Tired of
    being manly? Womanly?"), so SunShine's single flat-price version of it
    is a modest, not a novel, invention.
    ``pylord/hooks.py``'s ``PlayerView`` neither immunises nor validates
    ``gender``, so nothing stops a plugin from writing it.
  * *Master fight* -> resets ``player.seen_master`` to ``0``, letting a
    player who already faced Turgon's Master today (``training.py``) do
    so again -- gated on having actually seen the Master first (a fresh
    reset would be a sale of nothing).
  * *Resurrection* -> only offered to a dead player (``player.alive ==
    0``); sets ``alive = 1`` and ``hp = hp_max``, the exact "no gold/exp
    penalty" shape this project's own two existing free-resurrection
    paths already use (``pylord/engine/daily.py``'s automatic overnight
    revival, and ``training.py``'s ``_mercy`` when the Master spares a
    loser) -- reused rather than inventing a third formula. This does
    **not** run afoul of the "IGMs cannot kill" boundary
    (``igms/werewolf/igm.py``/``igms/warriors_graveyard/igm.py``'s no-kill
    guard): that guard is about an IGM *taking* a life it has no business
    ending; restoring one, in the one direction this project's own engine
    already treats as free and unconditional, isn't the mirror-image
    hazard. A dead player *can* reach this IGM in the first place --
    ``pylord/engine/scenes/town.py``'s Town Square offers "Other Places"
    unconditionally, with no ``alive`` gate -- so the purchase is reachable
    in practice, not just in theory.
  * *Sell a fairy* -> only offered to a player already holding one
    (``player.has_fairy``); pays the full recorded "fairy selling price"
    (not halved -- the doc's own "with the exception of a fairy" clause).
* **Catching a fairy's odds** (``FAIRY_CATCH_CHANCE_DENOM = 4``, a 1-in-4
  chance per try) -- no odds survive; reuses the same 1-in-4 this project
  already established for its own "try to catch/receive a fairy" gate
  (``igms/outlands_tavern/igm.py``'s Back Room). A player who already
  holds a fairy is simply refused a try (``has_fairy`` is a single flag,
  not a counter -- there is nowhere to put a second one).
* **The number-guessing game's range and 8 prizes.** Neither the range
  SunShine picks from nor a single prize is recorded anywhere -- only the
  count (8, quoted above). ``NUMBER_GAME_RANGE = 20`` (SunShine thinks of a
  number from 1 to 20) is an invented, winnable-but-not-trivial spread.
  The 8 prizes are invented as one flat reward apiece against eight
  different established fields (gold, gems, exp, a full heal, and a point
  each of strength/defense/charm/today's forest fights) -- deliberately
  the same shape as the General Store's own categories, since nothing
  about "8 different prizes" from a fairy-themed IGM suggests they should
  be anything stranger than what the rest of the archive already prices.
  Gated to one guess per day (no count survives either; a single daily
  guess is the smallest reading of "guessing the number" as a discrete
  event rather than free unlimited retries).
* **The Bank.** "Added a bank to the main menu" names a feature with zero
  recorded mechanic -- no interest rate, no cap beyond what this project's
  fields already enforce. Rather than invent a rate from nothing, it is
  implemented as the exact deposit/withdraw shape this project's own real
  Ye Old Bank already uses (``pylord/engine/scenes/bank.py``: `` `1` ``
  typed as the amount means "all of it"; both directions clamp the
  *destination* pile at the same 2,000,000,000 cap ``gold``/``bank``
  already validate to) -- it operates on the identical ``player.gold``/
  ``player.bank`` fields the real bank scene does, so this is a second
  doorway onto the same account, not a parallel invented ledger.
* **The level-12 Market gate reads as ``>= 12``, not literally ``== 12``.**
  This project's own level cap is 12 (``pylord/engine/scenes/dragon.py``:
  "at level 12" is the Dragon-eligible ceiling; ``training.py`` never lets
  ``level`` exceed it) -- no player can ever be above 12, so the two
  readings are equivalent in practice; ``>=`` is used defensively rather
  than for any difference in behavior.

**Not ported:**

* **``SFAIRCFG.EXE`` / registration keys / ``3RDPARTY.DAT`` install-uninstall
  flow** (``READ.ME``, ``SFAIRY.REG``, the install/uninstall sections of
  ``SFAIRY.DOC``) -- pylord's only IGM configuration surface is the
  ``[igms]`` enable toggle in ``config.toml``/``deploy/values`` (the same
  convention ``igms/werewolf/igm.py``'s docstring already establishes for
  "not ported: sysop configuration"); there is no registration-key gate or
  per-realm price override mechanism to port it onto.
* **Registered-vs-unregistered price tiers** (``WHATS.NEW`` v2.0:
  "Default prices are not higher, for non-registered versions.") -- with
  no registration concept in this project, every realm simply gets the one
  price list above.
* **"Registered by" credit line** (new in v2.6, ``WHATS.NEW``: "The request
  was made to include a Registered by option") -- paperwork, not gameplay.
* **"What's planned for 2.7"** (``WHATS.NEW``: sysop control of guess
  attempts, level-sensitive Market prices) -- explicitly future work never
  shipped in v2.6, this port's target version.
* **``SFAIRY.REG``'s registration order form** -- a mail-in payment form,
  not IGM content.
"""

from __future__ import annotations

from pylord.hooks import IGM, IgmContext, IgmMaintContext

_MENU = (
    "\n  `5SunShines' Fairy Land`2\n"
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
    "  `2(`0C`2)atch a fairy\n"
    "  `2(`0G`2)eneral Store\n"
    "  `2(`0N`2)umber game\n"
    "  `2(`0B`2)ank\n"
    "  `2(`0L`2)eave\n"
)

_STORE_MENU = (
    "\n  `5SunShines' General Store`2\n"
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
    "  `2(`0S`2)trength   (`0C`2)harm      (`0D`2)efense    (`0E`2)xperience\n"
    "  `2(`0F`2)orest fights (today)      (`0G`2)ems       (`0H`2)it points (max)\n"
    "  `2(`0P`2)layer fights (today)      (`0O`2) a Horse\n"
    "  `2(`0K`2) a Skill point            (`0I`2) a Kid\n"
    "  `2(`0R`2)esurrection               se(`0X`2) change\n"
    "  `2(`0M`2)aster fight reset         (`0Z`2)ell your fairy\n"
    "  `2(`0L`2)eave\n"
)

_NAME_MAXLEN = 20
_DIGITS = "0123456789"

# "Players are only allowed to try 5 times to win a Fairy." (WHATS.NEW,
# v2.0), corroborated by SFAIRY.DOC's SFAIRY.DAT file description in both
# archives -- see module docstring.
FAIRY_TRY_LIMIT = 5
# Invented -- see module docstring's "Catching a fairy's odds" note.
# Reused from igms/outlands_tavern/igm.py's own 1-in-4 fairy-related gate.
FAIRY_CATCH_CHANCE_DENOM = 4

# "Players at level 12 can not enter SunShines Market." (WHATS.NEW, v2.3).
MARKET_LEVEL_BAN = 12

# The 15 default prices, verbatim from SFAIRY.CFG / WHATS.NEW's labelled
# template -- see module docstring's "recorded, verbatim" price table.
PRICE_STRENGTH = 35_000
PRICE_CHARM = 35_000
PRICE_DEFENSE = 35_000
PRICE_EXPERIENCE = 35_000
PRICE_FOREST_FIGHTS = 35_000
PRICE_GEM = 35_000
PRICE_HIT_POINTS = 35_000
PRICE_PLAYER_FIGHTS = 35_000
PRICE_HORSE = 45_000
PRICE_SKILL_POINT = 500_000
PRICE_KIDS = 35_000
PRICE_RESURRECTION = 350_000
PRICE_SEX_CHANGE = 500_000
PRICE_MASTER_FIGHT = 500_000
FAIRY_SELL_PRICE = 500_000

# "All selling prices (with the exception of a fairy) are 1/2 the purchase
# price." (WHATS.NEW, v2.0).
SELL_PRICE_FRACTION = 0.5

# Invented -- see module docstring's "What each store category actually
# does" note: a raw +1 exp per unit would make the recorded price a no-op.
EXP_UNIT = 1_000

# Invented -- see module docstring's "number-guessing game" note.
NUMBER_GAME_RANGE = 20
NUMBER_GAME_GOLD_PRIZE = 5_000
NUMBER_GAME_GEM_PRIZE = 5
NUMBER_GAME_EXP_PER_LEVEL = 500

# ware key -> (Player field, label, unit price, units per purchase, sellable).
#
# Forest Fights / Player Fights are buy-only -- fixed post-review (see
# "Fix pass" in .superpowers/sdd/task-sfairy-report.md). The sell side of
# this table is entirely this port's own invention (the archive only
# records buy prices, see the module docstring's "What each store category
# actually does" note), so restricting it violates nothing recorded.
# ``forest_fights`` specifically also regenerates for free in real time
# (``pylord/engine/fights.py``'s ``apply_regen``, run on nearly every scene
# transition, refills toward ``max_forest_fights`` every
# ``fight_regen_minutes``) -- selling it back at this store's flat
# half-price rate would let a player sell, wait for the free regen to top
# back up, and sell again, for unbounded gold. ``player_fights`` has no
# such regen and is individually bounded, but it is priced/shaped
# identically to ``forest_fights`` in the recorded cfg (both "most choices"
# style daily-fight resources) -- keeping the two consistent with each
# other, rather than carving out an exception only the regen bug strictly
# requires, is the smaller and more defensible line to draw.
_POINT_WARES: dict[str, tuple[str, str, int, int, bool]] = {
    "S": ("strength", "Attack Strength", PRICE_STRENGTH, 1, True),
    "C": ("charm", "Charm", PRICE_CHARM, 1, True),
    "D": ("defense", "Defense Points", PRICE_DEFENSE, 1, True),
    "E": ("exp", "Experience", PRICE_EXPERIENCE, EXP_UNIT, True),
    "F": ("forest_fights", "Forest Fights", PRICE_FOREST_FIGHTS, 1, False),
    "G": ("gems", "Gems", PRICE_GEM, 1, True),
    "H": ("hp_max", "Hit Points", PRICE_HIT_POINTS, 1, True),
    "P": ("player_fights", "Player Fights", PRICE_PLAYER_FIGHTS, 1, False),
}

_BANK_CAP = 2_000_000_000


class SunshinesFairyLand(IGM):
    key = "sunshines_fairy_land"
    name = "SunShines' Fairy Land"
    author = "Becky Benjamin"
    default_enabled = True

    async def enter(self, ctx: IgmContext) -> None:
        await ctx.term.write(
            "\n  `2A field of toadstools and drifting motes of light opens up\n"
            "  past the tree line -- `%SunShines' Fairy Land`2.\n"
        )
        while True:
            await ctx.term.write(_MENU)
            choice = await ctx.term.menu(
                {"C": "fairy", "G": "store", "N": "number", "B": "bank", "L": "leave"},
                "  `2Your choice? [`0L`2] : `%",
            )
            if choice == "L":
                await ctx.term.write("\n  `2You wander back out of the toadstool ring.\n")
                return
            if choice == "C":
                await self._catch_fairy(ctx)
            elif choice == "G":
                await self._general_store(ctx)
            elif choice == "N":
                await self._number_game(ctx)
            else:
                await self._bank(ctx)

    # -- Catch a fairy -----------------------------------------------------

    async def _catch_fairy(self, ctx: IgmContext) -> None:
        p = ctx.player
        if p.has_fairy:
            await ctx.term.write(
                "\n  `2You already have a fairy tucked away -- no room for another.\n"
            )
            await ctx.term.pause()
            return
        gate = f"fairy_tries:{p.id}"
        tries = ctx.store.get(gate, 0)
        if tries >= FAIRY_TRY_LIMIT:
            await ctx.term.write(
                "\n  `2You've tried your luck with the fairies enough for one day.\n"
            )
            await ctx.term.pause()
            return
        ctx.store.set(gate, tries + 1)
        if ctx.rng.randrange(FAIRY_CATCH_CHANCE_DENOM) == 0:
            p.has_fairy = 1
            await ctx.term.write(
                "\n  `2A flash of silver light, a startled squeak -- and you close\n"
                "  your hands around a fairy!\n"
                "  `%YOU CAUGHT A FAIRY!\n"
            )
        else:
            await ctx.term.write(
                "\n  `2You lunge at a glimmer of light and come up with empty hands.\n"
            )
        await ctx.term.pause()

    # -- General Store -------------------------------------------------------

    async def _general_store(self, ctx: IgmContext) -> None:
        p = ctx.player
        if p.level >= MARKET_LEVEL_BAN:
            await ctx.term.write(
                '\n  `0"You\'ve outgrown my little shop,"`2 SunShine says, waving you off.\n'
            )
            await ctx.term.pause()
            return
        while True:
            await ctx.term.write(_STORE_MENU)
            await ctx.term.write(f"  `2You carry `%{p.gold}`2 gold.\n\n")
            choice = await ctx.term.menu(
                {
                    **{k: "ware" for k in _POINT_WARES},
                    "O": "horse",
                    "K": "skill",
                    "I": "kid",
                    "R": "resurrection",
                    "X": "sexchange",
                    "M": "master",
                    "Z": "sellfairy",
                    "L": "leave",
                },
                "  `2Your choice? [`0L`2] : `%",
            )
            if choice == "L":
                await ctx.term.write("\n  `2You step back out of the shop.\n")
                return
            if choice in _POINT_WARES:
                await self._trade_point_ware(ctx, choice)
            elif choice == "O":
                await self._buy_horse(ctx)
            elif choice == "K":
                await self._buy_skill_point(ctx)
            elif choice == "I":
                await self._buy_kid(ctx)
            elif choice == "R":
                await self._buy_resurrection(ctx)
            elif choice == "X":
                await self._buy_sex_change(ctx)
            elif choice == "M":
                await self._buy_master_reset(ctx)
            else:
                await self._sell_fairy(ctx)

    async def _ask_quantity(self, ctx: IgmContext, prompt: str) -> int:
        raw = await ctx.term.readline(prompt, maxlen=6, charset=_DIGITS)
        digits = "".join(c for c in raw if c.isdigit())
        return int(digits) if digits else 0

    async def _trade_point_ware(self, ctx: IgmContext, key: str) -> None:
        attr, label, price, unit, sellable = _POINT_WARES[key]
        p = ctx.player
        if sellable:
            options = {"B": "buy", "S": "sell", "L": "leave"}
            prompt = f"\n  `2(`0B`2)uy or (`0S`2)ell {label}, or (`0L`2)eave? : `%"
        else:
            # Buy-only -- see the module docstring's "Forest/Player Fights
            # are buy-only" note (post-review fix: selling these back would
            # combine with the engine's own free real-time regen for
            # unbounded gold).
            options = {"B": "buy", "L": "leave"}
            prompt = f"\n  `2(`0B`2)uy {label}, or (`0L`2)eave? : `%"
        choice = await ctx.term.menu(options, prompt)
        if choice == "L":
            return
        if choice == "B":
            qty = await self._ask_quantity(
                ctx,
                f"\n  `2How many units of {label} would you like to buy "
                f"(`0{price}`2 gold each)? : `%",
            )
            if qty < 1:
                return
            cost = qty * price
            if p.gold < cost:
                await ctx.term.write('\n  `0"You have not got that much gold."`2\n')
                await ctx.term.pause()
                return
            p.gold -= cost
            setattr(p, attr, getattr(p, attr) + qty * unit)
            await ctx.term.write(
                f"\n  `2SunShine counts out your purchase.\n"
                f"  `0YOU GAIN {qty * unit} {label.upper()}!\n"
            )
            await ctx.term.pause()
            return

        # choice == "S" -- only reachable when sellable is True (the menu
        # above never offers "S" otherwise).
        sell_price = int(price * SELL_PRICE_FRACTION)
        qty = await self._ask_quantity(
            ctx,
            f"\n  `2How many units of {label} would you like to sell "
            f"(`0{sell_price}`2 gold each)? : `%",
        )
        if qty < 1:
            return
        have_units = getattr(p, attr) // unit
        if attr == "hp_max":
            # Never let a sell take hp_max to 0 -- fixed post-review (see
            # "Fix pass" in .superpowers/sdd/task-sfairy-report.md). A live
            # player with hp_max == 0 is a nonsense state nothing else in
            # this project's engine expects.
            have_units = max(0, have_units - 1)
        if qty > have_units:
            await ctx.term.write(f'\n  `0"You have not got that much {label} to sell."`2\n')
            await ctx.term.pause()
            return
        setattr(p, attr, getattr(p, attr) - qty * unit)
        if attr == "hp_max" and p.hp > p.hp_max:
            p.hp = p.hp_max
        p.gold += qty * sell_price
        await ctx.term.write(
            f"\n  `2SunShine takes your {label.lower()} and hands over gold.\n"
            f"  `0YOU RECEIVE {qty * sell_price} GOLD!\n"
        )
        await ctx.term.pause()

    async def _confirm_and_charge(self, ctx: IgmContext, price: int, prompt: str) -> bool:
        """Shared "here's the price, do you agree, can you afford it" flow
        for the one-time wares below. Returns ``True`` (and has already
        deducted the gold) only if the purchase went through."""
        p = ctx.player
        await ctx.term.write(prompt)
        choice = await ctx.term.menu({"Y": "yes", "N": "no"}, "  `2Do you agree? [`0N`2] : `%")
        if choice == "N":
            await ctx.term.write("\n  `2SunShine shrugs.\n")
            await ctx.term.pause()
            return False
        if p.gold < price:
            await ctx.term.write('\n  `0"You have not got that much gold."`2\n')
            await ctx.term.pause()
            return False
        p.gold -= price
        return True

    async def _buy_horse(self, ctx: IgmContext) -> None:
        p = ctx.player
        if p.horse:
            await ctx.term.write("\n  `2You already have a horse.\n")
            await ctx.term.pause()
            return
        if not await self._confirm_and_charge(
            ctx, PRICE_HORSE, f'\n  `0"A fine horse, only {PRICE_HORSE} gold."`2\n'
        ):
            return
        p.horse = 1
        await ctx.term.write("\n  `0YOU BUY A HORSE!\n")
        await ctx.term.pause()

    async def _buy_skill_point(self, ctx: IgmContext) -> None:
        p = ctx.player
        if not await self._confirm_and_charge(
            ctx,
            PRICE_SKILL_POINT,
            f'\n  `0"A skill point, {PRICE_SKILL_POINT} gold."`2\n',
        ):
            return
        p.skill_uses += 1
        await ctx.term.write("\n  `0YOU GAIN A SKILL POINT!\n")
        await ctx.term.pause()

    async def _buy_kid(self, ctx: IgmContext) -> None:
        p = ctx.player
        if not await self._confirm_and_charge(
            ctx, PRICE_KIDS, f'\n  `0"A bouncing baby, {PRICE_KIDS} gold."`2\n'
        ):
            return
        p.kids += 1
        await ctx.term.write("\n  `0YOU GAIN A CHILD!\n")
        await ctx.term.pause()

    async def _buy_resurrection(self, ctx: IgmContext) -> None:
        p = ctx.player
        if p.alive:
            await ctx.term.write('\n  `0"You look plenty alive to me."`2\n')
            await ctx.term.pause()
            return
        if not await self._confirm_and_charge(
            ctx,
            PRICE_RESURRECTION,
            f'\n  `0"I can bring you back, for {PRICE_RESURRECTION} gold."`2\n',
        ):
            return
        p.alive = 1
        p.hp = p.hp_max
        await ctx.term.write("\n  `%YOU HAVE BEEN RESURRECTED!\n")
        await ctx.term.pause()

    async def _buy_sex_change(self, ctx: IgmContext) -> None:
        p = ctx.player
        if not await self._confirm_and_charge(
            ctx,
            PRICE_SEX_CHANGE,
            f'\n  `0"A new you, for {PRICE_SEX_CHANGE} gold."`2\n',
        ):
            return
        p.gender = "F" if p.gender == "M" else "M"
        await ctx.term.write("\n  `%YOU FEEL VERY DIFFERENT!\n")
        await ctx.term.pause()

    async def _buy_master_reset(self, ctx: IgmContext) -> None:
        p = ctx.player
        if not p.seen_master:
            await ctx.term.write(
                "\n  `2You haven't even seen the Master yet today.\n"
            )
            await ctx.term.pause()
            return
        if not await self._confirm_and_charge(
            ctx,
            PRICE_MASTER_FIGHT,
            f'\n  `0"I can get you back in front of the Master, {PRICE_MASTER_FIGHT} gold."`2\n',
        ):
            return
        p.seen_master = 0
        await ctx.term.write("\n  `0YOU MAY FACE THE MASTER AGAIN TODAY!\n")
        await ctx.term.pause()

    async def _sell_fairy(self, ctx: IgmContext) -> None:
        p = ctx.player
        if not p.has_fairy:
            await ctx.term.write("\n  `2You haven't got a fairy to sell.\n")
            await ctx.term.pause()
            return
        choice = await ctx.term.menu(
            {"Y": "yes", "N": "no"},
            f'\n  `0"I\'ll give you {FAIRY_SELL_PRICE} gold for that fairy."`2  '
            "`2Sell? [`0N`2] : `%",
        )
        if choice == "N":
            await ctx.term.write("\n  `2You keep your fairy.\n")
            await ctx.term.pause()
            return
        p.has_fairy = 0
        p.gold += FAIRY_SELL_PRICE
        await ctx.term.write(f"\n  `0YOU RECEIVE {FAIRY_SELL_PRICE} GOLD!\n")
        await ctx.term.pause()

    # -- Number game ---------------------------------------------------------

    async def _number_game(self, ctx: IgmContext) -> None:
        p = ctx.player
        gate = f"numbergame:{p.id}"
        if ctx.store.get(gate, False):
            await ctx.term.write(
                '\n  `0"I already told you my number today,"`2 SunShine says.\n'
            )
            await ctx.term.pause()
            return
        ctx.store.set(gate, True)
        raw = await ctx.term.readline(
            f"\n  `2SunShine is thinking of a number between `01 `2and `0{NUMBER_GAME_RANGE}`2.\n"
            "  `2Your guess? : `%",
            maxlen=6,
            charset=_DIGITS,
        )
        digits = "".join(c for c in raw if c.isdigit())
        guess = int(digits) if digits else 0
        answer = ctx.rng.randint(1, NUMBER_GAME_RANGE)
        if guess != answer:
            await ctx.term.write(
                f"\n  `4Nope!  SunShine was thinking of `0{answer}`4.  Try again tomorrow.\n"
            )
            await ctx.term.pause()
            return
        await ctx.term.write("\n  `%YOU GUESSED IT!\n")
        await self._award_number_game_prize(ctx, ctx.rng.randrange(8))

    async def _award_number_game_prize(self, ctx: IgmContext, prize: int) -> None:
        p = ctx.player
        if prize == 0:
            p.gold += NUMBER_GAME_GOLD_PRIZE
            await ctx.term.write(f"  `0YOU WIN {NUMBER_GAME_GOLD_PRIZE} GOLD!\n")
        elif prize == 1:
            p.gems += NUMBER_GAME_GEM_PRIZE
            await ctx.term.write(f"  `0YOU WIN {NUMBER_GAME_GEM_PRIZE} GEMS!\n")
        elif prize == 2:
            gained = NUMBER_GAME_EXP_PER_LEVEL * p.level
            p.exp += gained
            await ctx.term.write(f"  `0YOU WIN {gained} EXPERIENCE!\n")
        elif prize == 3:
            p.hp = p.hp_max
            await ctx.term.write("  `0YOU ARE FULLY HEALED!\n")
        elif prize == 4:
            p.strength += 1
            await ctx.term.write("  `0YOUR STRENGTH INCREASES BY 1!\n")
        elif prize == 5:
            p.defense += 1
            await ctx.term.write("  `0YOUR DEFENSE INCREASES BY 1!\n")
        elif prize == 6:
            p.charm += 1
            await ctx.term.write("  `0YOUR CHARM INCREASES BY 1!\n")
        else:
            p.forest_fights += 1
            await ctx.term.write("  `0YOU GAIN A FOREST FIGHT FOR TODAY!\n")
        await ctx.term.pause()

    # -- Bank ------------------------------------------------------------

    async def _bank(self, ctx: IgmContext) -> None:
        p = ctx.player
        while True:
            await ctx.term.write(
                f"\n  `2Gold In Hand: `0{p.gold}\n  `2Gold In Bank: `0{p.bank}\n"
                "  `2(`0D`2)eposit   (`0W`2)ithdraw   (`0L`2)eave\n"
            )
            choice = await ctx.term.menu(
                {"D": "deposit", "W": "withdraw", "L": "leave"},
                "  `2Your choice? [`0L`2] : `%",
            )
            if choice == "L":
                return
            if choice == "D":
                await self._deposit(ctx)
            else:
                await self._withdraw(ctx)

    async def _deposit(self, ctx: IgmContext) -> None:
        p = ctx.player
        raw = await ctx.term.readline(
            '\n  `2How much gold would you like to deposit? `0(1 for ALL of it)\n'
            "  `0AMOUNT : `%",
            maxlen=11,
            charset=_DIGITS,
        )
        amt = int(raw) if raw else 0
        if amt == 1:
            amt = p.gold
        if p.bank + amt > _BANK_CAP:
            amt = _BANK_CAP - p.bank
        if amt <= 0 or amt > p.gold:
            await ctx.term.write("\n  `2SunShine shakes her head -- you haven't got that.\n")
            await ctx.term.pause()
            return
        p.gold -= amt
        p.bank += amt
        await ctx.term.write(f"\n  `2Done!  {amt} deposited.\n")
        await ctx.term.pause()

    async def _withdraw(self, ctx: IgmContext) -> None:
        p = ctx.player
        raw = await ctx.term.readline(
            '\n  `2How much gold would you like to withdraw? `0(1 for ALL of it)\n'
            "  `0AMOUNT : `%",
            maxlen=11,
            charset=_DIGITS,
        )
        amt = int(raw) if raw else 0
        if amt == 1:
            amt = p.bank
        if p.gold + amt > _BANK_CAP:
            amt = _BANK_CAP - p.gold
        if amt <= 0 or amt > p.bank:
            await ctx.term.write("\n  `2SunShine shakes her head -- your account hasn't got that.\n")
            await ctx.term.pause()
            return
        p.bank -= amt
        p.gold += amt
        await ctx.term.write(f"\n  `2Done!  {amt} withdrawn.\n")
        await ctx.term.pause()

    async def daily_maint(self, ctx: IgmMaintContext) -> None:
        for player in ctx.repo.all_players():
            ctx.store.delete(f"fairy_tries:{player.id}")
            ctx.store.delete(f"numbergame:{player.id}")
