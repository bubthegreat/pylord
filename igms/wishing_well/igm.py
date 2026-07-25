"""The Wishing Well v1.2 -- by Joseph Watson, Farpoint BBS
(``igms_to_port/wwell12.zip``).

**Provenance tier: documented recreation -- but the thinnest one in this
project's roster.** ``WWELL.WCX`` is a compiled WT-LORD "wcCODE" IGM binary
(``WELL.DOC``: "IGM for WT-LORD v2.5 & Higher"), and unlike ``KALDOR.EXE``
(``igms/kaldors_court/igm.py``, a plain QuickBasic-compiled binary that
still leaks literal ``PRINT``-statement strings under ``strings``),
``WWELL.WCX`` yields **nothing**: a ``strings`` pass at every encoding
``strings -e`` supports (``s``/``S``/``b``/``l``/``B``/``L``, minimum
lengths 4-6) recovered zero printable runs, and a raw byte-frequency check
over the whole 17,696-byte file measures 7.99 bits/byte of Shannon entropy
-- statistically indistinguishable from random data. wcCODE's ``.wcx``
format is evidently encrypted or otherwise obfuscated at rest (consistent
with ``WELL.DOC``'s own shareware nag-screen/registration-code copy
protection -- "This program is SHAREWARE and is crippled! Registration
will take away all the NAG screens."); it simply does not leak plaintext
the way a raw compiled QuickBasic ``.EXE`` does. ``reference/igm-sources/
lordts/`` has no "well"/"wishing"-named IGM either (checked; its port list
is aratime, barak, felicity, freeworld2, gravyard, lordcave, lotto,
lrdevent, npclord, oorphans, outhouse, sandbar, teamlord, violet -- no
match). So this port is built from archive prose alone, and that prose
turns out to describe installation and shareware terms almost exclusively
-- not one menu key, cost, or odds figure survives anywhere in the archive.

Sources read (Step 1): ``wwell12.zip`` (v1.2, this port's target) --
``WELL.DOC``, ``FILE_ID.DIZ``, ``REGISTER.TXT``, ``UPGRADE.TXT``,
``LORD.IGM``; and ``wwell100.zip``, checked per this task's brief
("earlier-version docs often record numbers the later version assumes").
That check turned up a surprise worth recording plainly: **``wwell100.zip``
is not an earlier version of this IGM.** Its own ``FILE_ID.DIZ`` reads in
full: ")-( Wishing Well v1.00a )-( ... Wishing Well is a LORD2 IGM which
allows players to drop their gold down a well and if they are lucky
enough, their wish will come true! [MH97]" -- a different platform (plain
LORD2, not WT-LORD/wcCODE), a different, unidentified author (credited
only as initials "[MH97]", never Joseph Watson), and a different file
lineage (its ``WWELL100.EXE`` is itself a self-extracting RAR archive
containing ``INSTWELL.EXE``/``WISHWELL.REF``, filenames with no
relationship to ``wwell12``'s own ``WWELL.WCX``/``WELL.DOC``). Two
unrelated authors independently wrote a "Wishing Well" IGM for two
different LORD variants; this is coincidence of a generic theme, not a
version lineage. (The nested RAR content itself could not be extracted --
no ``unrar``/``7z``/``bsdtar`` is installed in this environment and
package installation requires root/network neither available here -- so
only its own ``FILE_ID.DIZ``, read directly off the outer SFX stub via
``strings``, was recovered.) Because it shares no code, author, or
platform with this port's target, wwell100 supplies no verbatim numbers
for wwell12 -- but its one recovered line ("drop their gold down a well
... their wish will come true") independently corroborates the plain
reading of wwell12's own ``FILE_ID.DIZ`` line below: two unrelated authors
converged on the same "toss gold in, hope for a wish" premise, which is
some evidence it's the obvious/canonical reading of a "Wishing Well" IGM
rather than this port inventing a shape from nothing.

**Recorded, verbatim (``wwell12.zip``):**

* ``FILE_ID.DIZ``: '"The Wishing Well" v1.2 -=- IGM for WT-LORD in 32bit
  wcCODE!' / '"WT-LORD v2.0 READY" for WT-LORD v2.5 & Higher! Y2K Date
  Checking' / **"Visit the Well and make a Wish! A `VERY POPULAR` IGM on
  my BBS!"** / "Another fun *WT-LORD IGM* by Joseph Watson." The core verb
  -- visit the well, make a wish -- is the one piece of gameplay premise
  that survives anywhere in this archive.
* ``FILE_ID.DIZ`` features list: "SUPPORTS Mutiple WT-LORD Games" (sic),
  "EASY Setup", **"BUILT in Maintenance"**, "EASY ONLINE Registration with
  VISA and MASTERCARD!" -- "BUILT in Maintenance" is corroborated
  independently by ``WELL.DOC``'s own install section (below): the IGM
  manages its own daily state without an external maintenance step, the
  same role this project's ``daily_maint`` hook plays.
* ``WELL.DOC``'s install section, verbatim: "Enter the WT-LORD program on
  your BBS! ... Igm Name: `` `2The `%Wishing `2Well``, Igm File: `WWELL`,
  Igm Maintenance File: [blank] ... **NOTICE: This IGM is written to
  automatically process it's own maintenance! Therefore NO IGM Maintenance
  file is needed!**" -- doubly confirms "BUILT in Maintenance" above: the
  original genuinely carried self-resetting daily state, not just marketing
  copy, which is why this port's own ``daily_maint`` below resets
  something rather than being a no-op.
* ``UPGRADE.TXT``, in full: "If you are running an earlier version of this
  program just overwrite your current WWell.wcx file with the new one and
  delete the WWELL.dte file from you WT-LORD Game directory." -- confirms
  a per-realm persistent data file (``WWELL.dte``) existed and needed
  clearing on upgrade; no field inside it is ever named or valued anywhere
  in the archive.
* ``WELL.DOC`` credits: "By Joseph Watson"; thanks to "Seth Able Robinson
  ... For Creating Legend of the Red Dragon", "Joe Marcelletti and Allan
  Benjamin, Jr. for their coding of Wildcat Tournament LORD ... Porting
  L.O.R.D. to wcCODE!", and "Mark Bappe for his programming expertise!
  ... BapStats". Contact: "Internet Email: joe@farpoint.1starnet.com",
  "Snail Mail: Joseph Watson, 2330 40th S.E., Paris, Texas 75460", "MY BBS:
  Farpoint BBS". Tested only against "WT-LORD v2.7 and v2.8"; "you must be
  running at least WT-LORD v2.5 for this IGM to work."
* ``REGISTER.TXT`` (dated August 1998): "The Wishing Well ... $10.00" --
  priced identically to seven of Joseph Watson's other WT-LORD IGMs
  (Bob's Beer, Our Town, The Witch Doctor's Hut!, The wcX-Files, The Mad
  Mage's Tavern, The Mines of Mt. Avalon, Up Country Fishing, EverGreen
  Cemetary all list at the same $10.00), with bundle discounts for 2/4/12
  IGMs together -- registration paperwork, not a gameplay number; not
  ported (see below).

Nowhere in this archive is there a menu layout, a key binding, a cost, an
odds table, a prize list, or a single sysop-config knob's name or default
-- only the "toss a coin, make a wish" premise, the "self-maintaining"
claim, and shareware/credits furniture. Everything below fills that gap.

**Invented (and why):**

* **Menu keys/labels/flavor text** -- no transcript survives. Laid out as
  a single wishing action plus a free, no-cost "peer into the well" flavor
  screen and this project's established (`L`)eave convention
  (``igms/werewolf``, ``igms/outlands_tavern``, ``igms/sunshines_fairy_land``,
  ``igms/kaldors_court`` all invent the same key for the same reason: no
  leave-key survives in almost any of this catalogue's archives).
* **A coin costs gold, spent whether or not the wish is granted**
  (``WISH_COST``, flat, invented -- no number survives). Framed as a coin
  toss rather than a market purchase, so it is priced low and flat rather
  than level-scaled, unlike Kaldor's Gems Galore (``igms/kaldors_court/
  igm.py``) which the archive explicitly records as level-scaled -- nothing
  here records the same for a wishing well, and "a coin" is the plainest
  reading of "make a Wish" (corroborated by wwell100's independent "drop
  their gold down a well" line above). The well keeps every coin regardless
  of outcome -- the same "the house never returns the wager" shape this
  project's own gambling IGMs already use (``igms/lord_casino/igm.py``'s
  blackjack/slots/roulette, ``igms/gem_trader/igm.py``'s haggle).
* **The wish table itself: six equally likely outcomes** rolled via
  ``ctx.rng.randrange(6)`` -- no count or odds survive anywhere. Six,
  uniform, is deliberately the same shape as ``igms/sunshines_fairy_land/
  igm.py``'s own 8-prize uniform ``ctx.rng.randrange(8)`` table (that
  IGM's prize *count* is separately doc-recorded; this one's is not, so a
  smaller table is chosen rather than borrowing SunShine's larger one
  wholesale). Four outcomes are modest, flat-or-level-scaled grants against
  established fields already priced/granted elsewhere in this catalogue
  (gold, level-scaled exp, a gem, a full heal); one is pure flavor
  ("nothing happens"); one is a folklore-appropriate "monkey's paw"
  backfire that costs the player *more* gold on top of the coin they
  already spent. **Deliberately gold-only, never hp or a stat** -- this
  keeps the one negative outcome fully clear of both the "IGMs cannot
  kill" boundary (``igms/werewolf/igm.py``'s hp-floor-at-1 adaptation
  exists specifically because that IGM has an hp-damaging failure branch;
  this one has none, so that disclosure doesn't apply here) and of
  charm's own cross-IGM entanglement at Kaldor's Court -- gold is floored
  at 0 by ``PlayerView`` regardless, so a backfire can never leave a
  player in an invalid state. Expected value across all six outcomes is
  negative once the up-front coin cost is included (``WISH_GOLD_PRIZE -
  WISH_BACKFIRE_GOLD`` averaged over six equally likely branches is less
  than ``WISH_COST``) -- the well is a net gold sink on average, the same
  house-edge shape every other gamble in this project's roster already
  keeps (see ``igms/lord_casino/igm.py``'s docstring).
* **Deliberately excludes the shared ``has_fairy`` flag from the wish
  table entirely.** A wishing well granting a fairy is an obvious,
  folklore-plausible temptation for a seventh wish outcome -- and exactly
  the trap this session's economy review flags: ``player.has_fairy`` is
  priced realm-wide by two other bundled IGMs (``igms/sunshines_fairy_land/
  igm.py``'s General Store pays ``FAIRY_SELL_PRICE = 500_000``;
  ``igms/kaldors_court/igm.py``'s Fairies `R` Us charges
  ``FAIRY_BUY_PRICE = 550_000``), and a well that could *grant* one for a
  ``WISH_COST``-sized coin toss would let a player farm ``has_fairy`` at
  a wishing-well's gambling odds and cash it in at either shop for many
  orders of magnitude more gold than the well ever charged -- not a
  "capped" exploit like Kaldor's first pricing draft, but an outright
  free-money generator, since a *chance* at a nearly-free fairy is worse
  than a *guaranteed* underpriced one. The smallest safe reading is to
  leave the flag out of this IGM's table altogether rather than try to
  price a lottery ticket high enough to stay under a payout two other
  modules already compete over. ``tests/igms/test_wishing_well.py``'s
  ``test_wish_table_never_touches_shared_fairy_flag`` pins this by
  exhausting every wish-table index with a scripted RNG and asserting
  ``has_fairy`` never moves, so a future edit that reintroduces the
  temptation breaks a test rather than shipping unnoticed.
* **Wish limited to a handful of tries per game-day**
  (``WISH_LIMIT_PER_DAY``, invented count) -- ``WELL.DOC``/``FILE_ID.DIZ``
  both confirm daily self-maintained state exists (above) but never say
  what it resets; a per-player daily wish-count gate, cleared in
  ``daily_maint``, is the smallest reading that gives that recorded
  maintenance claim something real to do, and mirrors this project's own
  established convention for "a cap exists, the count doesn't survive"
  (``igms/sunshines_fairy_land/igm.py``'s ``FAIRY_TRY_LIMIT``,
  ``igms/kaldors_court/igm.py``'s once-a-day Temple/Inn gates).
* **"Peer into the well"**, a free, no-cost, no-gate flavor screen showing
  a realm-wide lifetime total of coins tossed (``coins_tossed``, an
  ``IgmStore`` counter incremented by ``WISH_COST`` every time anyone
  wishes) and the player's own wishes remaining today. Nothing records
  this screen or a running total; it exists to give ``UPGRADE.TXT``'s
  recorded ``WWELL.dte`` persistent-data-file claim something visible to
  show, in the same spirit as ``igms/kaldors_court/igm.py``'s
  ``talk_board``: a realm-shared counter that **is not** cleared in
  ``daily_maint`` (a lifetime total that reset nightly wouldn't be a
  lifetime total).
* **Full heal (outcome index 3) reads onto ``hp = hp_max``**, the same
  "wish for good health" mapping this project already uses for a costed
  full heal (``igms/apothecary/igm.py``'s pricier Salve, ``igms/
  sunshines_fairy_land/igm.py``'s number-game prize) -- no separate
  formula is invented since one already exists to reuse.

**Not ported:**

* **Registration/shareware nag** (the 30-day trial, nag screens, "EASY
  ONLINE Registration with VISA and MASTERCARD") and ``REGISTER.TXT``'s
  order form -- this project's only IGM configuration surface is the
  ``[igms]`` enable toggle in ``config.toml``/``deploy/values``, the same
  boundary every wave-3 sibling's docstring already establishes.
  "SUPPORTS Multiple WT-LORD Games" -- a multi-BBS-instance install claim
  with no per-realm gameplay content of its own.
* **``WWELL.dte``'s own on-disk layout / node-file handshake** -- this
  project's ``IgmStore`` already replaces the flat-file mechanism
  entirely; there is no byte layout to preserve since none of it survives
  in the archive regardless.
"""

from __future__ import annotations

from pylord.hooks import IGM, IgmContext, IgmMaintContext

_MENU = (
    "\n  `5The Wishing Well`2\n"
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
    "  `2(`0W`2)ish -- toss a coin into the well\n"
    "  `2(`0P`2)eer into the well\n"
    "  `2(`0L`2)eave\n"
)

# "Visit the Well and make a Wish!" (FILE_ID.DIZ) -- the coin cost itself
# is invented, see module docstring's "A coin costs gold" note.
WISH_COST = 250

# Invented -- see module docstring's "self-maintained" note.
WISH_LIMIT_PER_DAY = 5

# The wish table -- six equally likely outcomes, invented. See module
# docstring's "wish table" note.
WISH_GOLD_PRIZE = 1_000
WISH_EXP_PER_LEVEL = 250
WISH_GEM_PRIZE = 3
WISH_BACKFIRE_GOLD = 500

_WISH_OUTCOME_COUNT = 6


class WishingWell(IGM):
    key = "wishing_well"
    name = "The Wishing Well"
    author = "Joseph Watson"
    default_enabled = True

    async def enter(self, ctx: IgmContext) -> None:
        await ctx.term.write(
            "\n  `2An old stone well stands mossy and worn in a quiet clearing,\n"
            "  coins glinting faintly at the bottom of the dark water.\n"
            "  `%Visit the Well and make a Wish!`2\n"
        )
        while True:
            await ctx.term.write(_MENU)
            choice = await ctx.term.menu(
                {"W": "wish", "P": "peer", "L": "leave"},
                "  `2Your choice? [`0L`2] : `%",
            )
            if choice == "L":
                await ctx.term.write("\n  `2You leave the well to its silence.\n")
                return
            if choice == "W":
                await self._wish(ctx)
            else:
                await self._peer(ctx)

    async def _peer(self, ctx: IgmContext) -> None:
        p = ctx.player
        total = ctx.store.get("coins_tossed", 0)
        gate = f"wishes:{p.id}"
        used = ctx.store.get(gate, 0)
        remaining = max(0, WISH_LIMIT_PER_DAY - used)
        await ctx.term.write(
            f"\n  `2You peer into the dark water.  `0{total} coins have vanished\n"
            "  into its depths over the years.\n"
            f"  `0{remaining} wish{'es' if remaining != 1 else ''} left today.\n"
        )
        await ctx.term.pause()

    async def _wish(self, ctx: IgmContext) -> None:
        p = ctx.player
        gate = f"wishes:{p.id}"
        used = ctx.store.get(gate, 0)
        if used >= WISH_LIMIT_PER_DAY:
            await ctx.term.write(
                "\n  `2The well has heard enough from you today.  It stays silent.\n"
            )
            await ctx.term.pause()
            return
        if p.gold < WISH_COST:
            await ctx.term.write(
                "\n  `2You dig through your pockets, but you haven't even got a\n"
                "  coin to spare.\n"
            )
            await ctx.term.pause()
            return

        p.gold -= WISH_COST
        ctx.store.set(gate, used + 1)
        ctx.store.set("coins_tossed", ctx.store.get("coins_tossed", 0) + WISH_COST)

        await ctx.term.write(
            "\n  `2You toss a coin into the well and close your eyes to make a wish...\n"
        )
        outcome = ctx.rng.randrange(_WISH_OUTCOME_COUNT)
        if outcome == 0:
            p.gold += WISH_GOLD_PRIZE
            await ctx.term.write(
                "  `0The water glimmers -- you find a handful of old coins caught\n"
                "  in the mud!\n"
                f"  `%YOU RECEIVE {WISH_GOLD_PRIZE} GOLD!\n"
            )
        elif outcome == 1:
            gained = WISH_EXP_PER_LEVEL * max(1, p.level)
            p.exp += gained
            await ctx.term.write(
                "  `0You wish for wisdom, and for a moment you understand a little\n"
                "  more about the world.\n"
                f"  `%YOU RECEIVE {gained} EXPERIENCE!\n"
            )
        elif outcome == 2:
            p.gems += WISH_GEM_PRIZE
            await ctx.term.write(
                "  `0Something small and hard catches the light as it rises to the\n"
                "  surface -- gems!\n"
                f"  `%YOU RECEIVE {WISH_GEM_PRIZE} GEMS!\n"
            )
        elif outcome == 3:
            p.hp = p.hp_max
            await ctx.term.write(
                "  `0You wish for good health, and warmth spreads through your\n"
                "  tired limbs.\n"
                "  `%YOU ARE FULLY HEALED!\n"
            )
        elif outcome == 4:
            await ctx.term.write(
                "  `2The well is silent.  Your coin sinks without a ripple.\n"
            )
        else:
            p.gold -= WISH_BACKFIRE_GOLD
            await ctx.term.write(
                "  `4The water clouds over, dark and cold, and you feel like you've\n"
                "  made a terrible mistake.\n"
                f"  You lose {WISH_BACKFIRE_GOLD} gold for your trouble.\n"
            )
        await ctx.term.pause()

    async def daily_maint(self, ctx: IgmMaintContext) -> None:
        for player in ctx.repo.all_players():
            ctx.store.delete(f"wishes:{player.id}")
        # coins_tossed intentionally NOT cleared -- a lifetime total, the
        # same convention igms/kaldors_court/igm.py's talk_board follows
        # for its own realm-shared, never-reset counter; see module
        # docstring's "Peer into the well" note.
