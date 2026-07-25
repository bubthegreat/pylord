"""Kaldor's Court v2.0 -- by Chris Fisher, The Digital Escape BBS
(``igms_to_port/kaldor20.zip``, (c) Digital Software 1995).

**Provenance tier: documented recreation.** ``KALDOR.EXE`` "was written in
QuickBasic 4.5 using QWKIGM programming library for IGMs" (``KALDOR.DOC``)
-- a compiled DOS binary, no source survives, and ``reference/igm-sources/
lordts/`` has no "kaldor"-named IGM in it (checked; its port list is
aratime, barak, felicity, freeworld2, gravyard, lordcave, lotto, lrdevent,
npclord, oorphans, outhouse, sandbar, teamlord, violet -- none of which is
this IGM or a plausible lineage match). So, like WereWolf (``igms/werewolf/
igm.py``) and SunShines' Fairy Land (``igms/sunshines_fairy_land/igm.py``),
no control flow, formula, or odds table survives -- only prose docs plus
one extra source of *data* neither of those two ports had available: running
``strings`` over ``KALDOR.EXE`` itself recovers the literal ASCII text a
QuickBasic compiler emits for every ``PRINT`` statement, including several
numeric literals baked directly into those templates (below). This is not
decompiled logic -- no branch, loop, or comparison was recovered, only the
constant strings/numbers a disassembly-free ``strings`` pass surfaces --
but it is a materially richer *data* source than either sibling port had,
in the same spirit as ``SFAIRY.CFG``'s own default-price bytes for
SunShine's port.

Sources read (Step 1): ``kaldor20.zip`` (v2.0, this port's only surviving
version) -- ``KALDOR.DOC``, ``FILE_ID.DIZ``, ``REGISTER.DOC``,
``WHAT-IS.NEW``, ``PROBLEMS.DOC``, ``UPDATE.DOC``, ``DESQVIEW.TXT``,
``FOSSIL.TXT``, ``QWK-IGM.INI``, ``TALK.DAT``, ``QWKIGM.DAT``, ``LORD.IGM``;
and a ``strings``/hex pass over ``KALDOR.EXE`` and ``INSTALL.EXE`` for any
literal text the QuickBasic compiler embedded.

**Recorded, verbatim:**

* ``KALDOR.DOC``/``FILE_ID.DIZ``: "Kaldor's Court is an IGM for Legend of
  the Red Dragon. Kaldor's features a Marketplace to buy certain things
  (sorry, you cannot buy hitpoints, defense points, etc.. I didn't feel
  that being able to buy those types of things added to the realism of the
  game), a Temple to pray, and an Inn to socialize[, and more!]" -- three
  named locations (Marketplace, Temple, Inn), and an explicit **design
  rule, in the author's own words**: nothing in the Marketplace ever sells
  hitpoints, defense, or (by the same logic) attack/strength -- unlike
  ``igms/sunshines_fairy_land/igm.py``'s General Store, which does sell
  those. Honoured here: Kaldor's Marketplace only ever trades gems, a
  horse, and a fairy.
* ``REGISTER.DOC``: registration payments go to "Chris Fisher, 1611 Osolo
  Rd., Elkhart, IN. 46514" -- read as the author's name (``KALDOR.DOC``'s
  "How to contact me" section is first-person throughout: "you can either
  contact me via my BBS - The Digital Escape ... or netmail me at
  1:2285/30", the same BBS ``QWK-IGM.INI`` names as this IGM's own credit
  line).
* ``WHAT-IS.NEW``, full version history read for numbers later versions
  assume: v1.2 "Changed the amount for the buying and selling of gems. Now
  the number is based on the user's level, rather than a hard-coded
  amount." -- gem prices are level-scaled, confirmed again generically by
  v1.5 "Changed most of the values in the game to reflect the users'
  current level. Shouldn't have anymore Level 1 players gaining 1000+
  experience anywhere!"; v1.3 "Added a maximum amount of gems the dealer
  has to start with each day. Found too many people cheating by buying
  gems real cheap from Kaldor's, and selling them in other IGMs for a
  lot." -- a **recorded anti-arbitrage guardrail**: the gem dealer's daily
  sell-side stock is capped, precisely the "don't let a regenerating/
  refillable resource become free gold elsewhere" shape this project's own
  economy rules already require (see ``igms/sunshines_fairy_land/igm.py``'s
  forest_fights note); v0.2ss "Changed the algorithm for figuring the
  experience a user recieved or lost when they flirted with Hercules or
  Xena. Noticed that a level 3 character lost approx. 4000 exp. points
  when they shouldn't have lost that much." -- confirms the Inn's
  Hercules/Xena flirting exp swing is level-scaled, and that the original
  authors themselves judged a several-thousand-exp swing at level 3
  excessive -- shaping how modest this port's own invented flirt numbers
  are (below).
* ``TALK.DAT`` (the Inn's own seed conversation line, carried into the
  archive verbatim): "`%Hercules:\nHey Bartender, another round for all my
  friends!" -- the one surviving line of the Inn's "Converse with the
  Kaldorians" board.
* ``QWK-IGM.INI`` (the hub's own registered display name/tagline, byte for
  byte): ```0K`2aldor's `0C`2ourt`` / ``  Visit the MarketPlace a
  Kaldor's!``.
* **``KALDOR.EXE``'s own literal strings** (recovered via ``strings``,
  quoted with their surrounding bytes checked in a hex dump to confirm each
  is a real PRINT-statement literal and not a coincidental run-together):

  - The Court's entry flavour and top menu, verbatim: "Boy, does this
    place smell RANK!!!, you think to yourself. As you wander around this
    putrid place, you notice a few little shops to the West. Off to the
    East, you notice the Inn. To the South, the Temple." then ``(I)nn of
    Kaldor`` / ``(M)arketplace`` / ``(T)emple of Daelamar`` / ``(Y)our
    stats`` / ``(Q)uit`` -- both the flavour text and the five menu
    keys/labels are literal, including the recorded ``Q`` quit hotkey
    (unlike every other bundled wave-3 IGM, whose own leave-key was never
    recorded and is invented "L" by project convention -- **this one
    genuinely is** recorded, so ``Q`` is what this port uses at the Court
    and Marketplace levels; see "Invented" below for where it stops).
  - The Marketplace's own two-line gate, verbatim: "You let out a loud
    chuckle when you enter the Marketplace. They call THIS a
    Marketplace???, you say under your breath. Neverless, you decide to
    take a quick look around to see what they have." / ``(E)nter the
    shops`` / ``(Q)uit to the main Court`` -- ``Q`` is, again, a literal
    recorded hotkey.
  - The three shops, verbatim: ``(G)ems Galore``, ``(H)orse Heaven``,
    ``(F)airies `R` Us``.
  - **Gems Galore, verbatim**: "So, you're interested in my gems, eh?,
    asks the shopkeeper. Well, I'm selling `05`2 for [PRICE] gold and
    buying for [PRICE] gold per gem." -- the bundle size (5) is a literal
    digit baked into the template (confirmed against the raw bytes: the
    literal run is `` selling 5 for`% `` with the price variable printed
    immediately after, not before), not a placeholder; "Sorry, I'm all out
    of gems for the day., says the shopkeeper." is the dealer's own
    daily-stock refusal line (the v1.3 cap, above).
  - **Horse Heaven, verbatim**: "Howdy!, shouts the stablemaster. We got us
    some fine, young horses here! You see a sign stating that horses sell
    for [PRICE] gold and are bought for [PRICE] gold." / ``(B)uy a horse``
    / ``(S)ell your horse`` / "You already have a horse!" / "You don't
    have a horse!" / and, selling one back: "Well, it looks pretty shabby,
    but I suppose. Here's your `030000`2 gold." -- **30,000 is a literal
    constant**, not a variable (confirmed in the raw bytes: the digits
    ``30000`` sit directly in the string, with no length-prefixed variable
    descriptor around them, unlike every price elsewhere in this shop) --
    the one hard gold number this entire archive records for a shop price.
  - **Fairies `R` Us, verbatim**: "Hehehehe, laughs the, well, not quite
    sure who (or WHAT) is behind the counter. What can I do for you?,
    asks the, um, it. You see a sign that says: We buy Fairies for [PRICE]
    gold and sell them for [PRICE] gold." / ``(B)uy a fairy`` / ``(S)ell
    your fairy`` / "You already have a fairy!" / "You don't have a fairy!"
    -- no numeric literal survives for either fairy price (both are
    printed variables).
  - **The Temple, verbatim**: "As you enter through the large wooden
    doors, you notice several monks praying at the alter." (sic -- the
    archive's own spelling, kept as-is the same way ``igms/outlands_tavern/
    igm.py``'s docstring preserves that archive's typos) / ``(C)hant with
    the monks`` / ``(P)lay an instrument`` / ``(S)cream loudly``. Each of
    the three has its own recorded once-a-day refusal, proving a daily cap
    existed on every one of them even though no count survives:
    **Chant** -- "You chant a little prayer you thought up on the spot
    and... You receive 1 charm point!" / "...You lose 1 charm point for
    annoying the monks with your silly chant!" (both literal ``1``\\s) /
    refused with "Let's not bug the monks anymore today, ok?" once already
    used. **Play an instrument** -- "Not being from this part of town, you
    don't know exactly what playing an instrument is supposed to do, but
    you feel the urge to try it anyway." then ``Tuba`` / ``Organ`` /
    ``Chimes`` / ``Flute`` / ``Bells`` / ``Gong`` / ``None of them``, each
    followed (in that exact order, matching a ``SELECT CASE`` printing its
    branches in source order) by "Your music was beautiful. You receive
    `%1 charm point! / lose `%1 charm point!" (Tuba), "...`%1 defense
    point!" (Organ), "...`%1 strength point!" (Chimes), "...`%1
    hitpoint!" (Flute), "...`%500 experience points!" (Bells), "...`%1000
    gold!" (Gong) -- **six literal reward/penalty pairs**, all confirmed
    in the raw bytes as hard digits, not variables; refused with "Your not
    THAT talented, now. Give it a rest!" (sic) once already used today.
    **Scream loudly** -- ``(O)bsene scream`` / ``(E)ar-peircing scream`` /
    ``(C)hange your mind and be quite`` (sic, both); Obscene success: "You
    sure do know how to clear out a room! You receive `%[N] experience
    points!" (variable), fail: "You lose `%2 charm points for being SO
    rude!" (literal ``2``); Ear-piercing success: "You send the monks out
    of the Temple crying because of ear aches!" (flavour only, no stated
    reward), fail: "You scream SO loudly that parts of the Temple fall
    from the ceiling and land on your head! You lose `%2 charm points for
    the nasty bump it left!" (literal ``2``); refused with "You decide
    against screaming anymore today." once already used.
  - **The Inn, verbatim**: "As you step into the INN, you vaguely remember
    hearing that this is the place the legendary Hercules and Xena
    frequently visited." / ``(C)onverse with the Kaldorians`` / ``(F)lirt
    with Hercules`` / ``(F)lirt with Xena`` (the source's own hex dump
    shows *both* flirt lines highlighting the same letter, ``F`` -- almost
    certainly a real keybinding collision/cosmetic bug in the original that
    can't be literally reproduced as two distinct hotkeys; this port picks
    non-colliding ``H``/``X`` instead -- see "Invented" below). Flirting is
    refused with "Better not flirt anymore right now." once already used
    today (a recorded daily cap, count not recorded). The escalating
    submenu, verbatim: ``(W)ink`` / ``(B)low him/her a kiss`` / ``(K)iss
    him/her!`` / ``(T)ake him/her to the back room`` / ``(N)evermind``.
    Wink: "He/She winked back!" (win) / "He wasn't interested in your
    advances!" (fail, Hercules; the symmetric "She..." line exists for
    Xena) -- both followed by a variable exp swing, no number recorded.
    Blow a kiss / Kiss share the same shape with their own win lines ("He
    blew a kiss back!"/"He kissed you back!" and the Xena equivalents) but
    no separately recorded fail line -- the Wink fail line is reused for
    all three escalation tiers below Back Room, per the module's own
    "smallest reading" convention. Take to the back room: "You both head
    to the back room, and have a great time together! You receive `%[N]
    experience and `%1 charm point!" (win, literal ``1`` charm) / "You
    lose `%[N] experience and `%2 charm points for being too outgoing!"
    (fail, literal ``2`` charm) -- the only tier with a recorded charm
    swing; the accompanying exp numbers are variables in both directions.
    "Converse with the Kaldorians" itself: ``(A)dd to conversation or
    (C)ontinue [C]:`` then, if adding, "Speak your piece below: (Maximum of
    70 characters)" (``70`` literal) -- a shared conversation board (the
    archive's own ``TALK.DAT``, above, is exactly this board's seed
    content) that any player can read from and add to.
  - **"Your stats"**, verbatim field list: Experience, Level, Hitpoints (X
    of Y), Forest Fights, Player Fights, Gold in Hand, Gold in Bank,
    Weapon, Attack Strength, Armor, Defensive Strength, Charm, Gems, plus
    conditional lines for a fairy in your pocket, N children, and being on
    horseback.
  - **Registration/shareware furniture** (not gameplay): "REGISTERED to
    [name]" / "UNREGISTERED Evaluation Copy" / "Please help your SysOp
    register this IGM!" -- the same "not ported: registration" boundary
    every wave-3 sibling already draws.

**Invented (and why):**

* **Menu keys/labels with no recorded hotkey.** The Court and Marketplace
  levels' ``Q`` uit hotkeys are recorded verbatim (above) and used as-is.
  Nothing below that -- inside the shops, the Temple, or the Inn -- has a
  surviving "leave this room" string; those use this project's established
  "L"eave convention (``igms/werewolf``, ``igms/outlands_tavern``,
  ``igms/sunshines_fairy_land`` all invent the same key for the same
  reason). Hercules/Xena's own hotkeys are invented as ``H``/``X`` for the
  reason given above (the recorded strings collide on ``F`` for both).
* **The Marketplace's "(E)nter the shops" pre-gate is folded away, not
  ported as a separate confirmation.** It adds no choice -- nothing in
  either doc records what declining it does differently from simply not
  visiting the Marketplace at all -- so, like every sibling IGM's own
  "you decide to browse a while" framing, the flavour text is kept and the
  redundant yes/no gate is dropped straight into the shop list.
* **The outer "(E)nter Kaldor's Court / (Q)uit to LORD" title screen is not
  ported.** In the original this was ``KALDOR.EXE``'s own standalone DOS
  title screen, shown before LORD's IGM handshake even reached the Court
  proper -- the exact role pylord's own Other Places doorway
  (``pylord/engine/scenes/other_places.py``) already plays for every IGM.
  Porting it would be a redundant second "do you want to enter?" gate in
  front of the one the engine already provides.
* **Gem prices, level-scaled per the recorded rule, exact multiplier
  invented** (``GEM_BUY_PRICE_PER_GEM_PER_LEVEL`` / ``GEM_SELL_PRICE_
  PER_GEM_PER_LEVEL``) -- only the fact of level-scaling and the 5-gem
  bundle size are recorded, not a number. Chosen so buy strictly exceeds
  sell at every level (this project's own economy guardrail: a round trip
  must always lose gold, ``igms/sunshines_fairy_land/igm.py``'s docstring
  states the same rule for its own wares). **Daily dealer stock**
  (``GEM_DAILY_STOCK_BUNDLES``) -- v1.3 confirms a cap exists, not its
  size; modelled as one realm-shared ``IgmStore`` counter (mirrors
  ``igms/gem_trader/igm.py``'s own single shared daily rate -- "one dealer,
  one stock, shared by everyone") rather than a per-player limit, since the
  recorded bug it fixes ("buying gems real cheap from Kaldor's, and
  selling them...for a lot") is specifically about a *shared* dealer being
  drained, not an individual quota. Like ``gem_trader``'s own shared daily
  rate, this counter is a best-effort cap, not an atomically-decremented
  one -- two visits reading the buffered ``IgmStore`` snapshot in the same
  instant could each see stock available and both spend it, modestly
  over-selling the day's cap. That race can't be exploited for free gold
  (every buyer still pays full, undiscounted price); it only bounds the
  cap's precision, which is the same trade-off this project already
  accepted for ``gem_trader``.
* **Horse buy price, invented, held above the recorded flat sell price at
  every level.** No buy number survives, only that the sign shows one; the
  recorded sell price (30,000 flat) is used as-is, and the buy price is
  chosen (``HORSE_BUY_BASE`` + ``HORSE_BUY_PER_LEVEL`` * level) so it never
  drops below 30,000 -- satisfying the same "sell never profits" guardrail
  the gems above already follow, even though nothing in the archive says
  whether the original's own level-scaled buy price ever dipped under its
  own flat sell price at a low enough level.
* **Fairy buy/sell prices, entirely invented** (flat, not level-scaled --
  nothing records level-scaling for this shop specifically, unlike gems);
  buy kept strictly above sell for the same guardrail *within this shop*.
* **Buying a fairy is gated to once a day, invented, for a cross-IGM
  guardrail reason nothing in this archive could have recorded.**
  ``player.has_fairy`` is a single flag shared realm-wide with
  ``igms/sunshines_fairy_land/igm.py``, whose own General Store pays
  ``FAIRY_SELL_PRICE = 500_000`` for the *same* flag -- ten times this
  shop's invented ``FAIRY_BUY_PRICE = 50_000``. Without a cap, a player
  could buy a fairy here, walk it to SunShine's, sell it there, and repeat
  indefinitely in a single day for unbounded gold -- precisely the
  "buying [something] real cheap from Kaldor's, and selling [it] in other
  IGMs for a lot" exploit shape ``WHAT-IS.NEW`` v1.3 already fixed once for
  gems (above), just recurring here across two ported IGMs that never
  shared a review pass in the original catalogue. A once-a-day buy gate
  (``fairy_buy:<id>``, cleared in ``daily_maint``) bounds the worst case to
  one 450,000-gold round trip per player per day -- the same order of
  magnitude already tolerated by SunShine's own shipped "catch a fairy"
  loop (up to 5 tries/day at a 1-in-4 chance, each immediately sellable for
  500,000), not a new risk class this project hasn't already accepted.
  Selling a fairy here is left uncapped -- the sell side only ever removes
  gold-for-item value from the realm's total fairy count, it cannot mint a
  cheap one to re-arbitrage.
* **Chant/Play an instrument/Scream's daily-cap count (1/day each) and
  their win/lose odds (50/50 each), invented.** The refusal lines above
  prove *a* cap existed for each; nothing records how many attempts it
  allowed, so this port uses the smallest reading (one try, once a day),
  the same convention every daily-gated action in this project's IGMs
  already follows. The "beautiful"/"off-key" and "chant"/"lose a point"
  framing implies some kind of check, but no odds survive, so a flat coin
  flip is used throughout, mirroring how ``igms/outlands_tavern/igm.py``'s
  own Back Room entry roll invents 50/50-shaped odds from equally
  qualitative prose ("hard to get in").
* **The Obscene scream's exp reward, invented, level-scaled** (no number
  survives, only that it's a variable "You receive `%[N] experience
  points!").
* **Hercules/Xena's exp swings, invented, level-scaled and deliberately
  modest.** Nothing survives beyond "a variable amount, escalating with
  the chosen action" -- WHAT-IS.NEW's own v0.2ss bug report (a level-3
  character losing ~4000 exp was judged a bug, not a feature) and v1.5's
  "shouldn't have anymore Level 1 players gaining 1000+ experience
  anywhere" together set the ceiling this port aims under: even the
  richest tier (Take to the back room) grants only ``50 * level`` exp at
  most, well inside both stated bounds. Win chance is charm-scaled
  (``min(80, 40 + charm)`` percent) -- no odds survive, but scaling a
  charm-flavoured social gamble off the player's own ``charm`` stat
  mirrors this project's own precedent for exactly that shape
  (``igms/gem_trader/igm.py``'s ``HAGGLE_CHARM`` gate).
* **The talk board's maximum length (20 entries kept, oldest dropped),
  invented** -- nothing records how ``TALK.DAT`` ever got trimmed; a cap
  is the smallest addition that keeps a realm-shared, ever-growing list
  from becoming unbounded storage. The 70-character line cap is recorded,
  used as-is.
* **"Your stats"' Weapon/Armor lines show the raw ``weapon_num``/
  ``armor_num``, not a resolved name.** ``IgmContext`` gives an IGM no
  name-lookup table for either (only the base game's own scenes reach into
  ``pylord.engine.data`` for that, which is off-limits to a plugin under
  this project's "ctx facade only" convention) -- the same category of gap
  ``igms/outlands_tavern/igm.py``'s docstring already documents for the
  married-spouse lookup ("a missing *capability*, not a missing number").

**Not ported:**

* **Registration/shareware nag** (the delay, the beep -- "Also removed the
  unregistered BEEP at the exit of the IGM" confirms one existed --
  and the "REGISTERED to"/"UNREGISTERED Evaluation Copy" banner) -- this
  project's only IGM configuration surface is the ``[igms]`` enable toggle,
  the same convention every wave-3 sibling's docstring already establishes.
* **``QWKIGM.DAT``/``3RDPARTY.DAT`` install/handshake, FOSSIL/DESQview
  driver notes, node numbers, hardware handshaking flags** -- infrastructure
  for a DOS-door file handshake this project's engine has no analogue for.
"""

from __future__ import annotations

from pylord.hooks import IGM, IgmContext, IgmMaintContext

_COURT_MENU = (
    "\n  `5Kaldor's Court`2\n"
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
    "  `2(`0I`2)nn of Kaldor\n"
    "  `2(`0M`2)arketplace\n"
    "  `2(`0T`2)emple of Daelamar\n"
    "  `2(`0Y`2)our stats\n"
    "  `2(`0Q`2)uit\n"
)

_MARKET_MENU = (
    "\n  `5The Marketplace`2\n"
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
    "  `2(`0G`2)ems Galore\n"
    "  `2(`0H`2)orse Heaven\n"
    "  `2(`0F`2)airies `R` Us\n"
    "  `2(`0Q`2)uit to the main Court\n"
)

_TEMPLE_MENU = (
    "\n  `5Temple of Daelamar`2\n"
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
    "  `2(`0C`2)hant with the monks\n"
    "  `2(`0P`2)lay an instrument\n"
    "  `2(`0S`2)cream loudly\n"
    "  `2(`0L`2)eave\n"
)

_INN_MENU = (
    "\n  `5The Inn of Kaldor`2\n"
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
    "  `2(`0C`2)onverse with the Kaldorians\n"
    "  `2Flirt with (`0H`2)ercules\n"
    "  `2Flirt with (`0X`2)ena\n"
    "  `2(`0L`2)eave\n"
)

_INSTRUMENT_MENU = (
    "\n  `2(`0T`2)uba          (`0O`2)rgan         (`0C`2)himes\n"
    "  `2(`0F`2)lute         (`0B`2)ells         (`0G`2)ong\n"
    "  `2(`0N`2)one of them\n"
)

_SCREAM_MENU = (
    "\n  `2(`0O`2)bscene scream\n"
    "  `2(`0E`2)ar-piercing scream\n"
    "  `2(`0C`2)hange your mind and be quiet\n"
)

_FLIRT_MENU = (
    "\n  `2(`0W`2)ink\n"
    "  `2(`0B`2)low {pronoun} a kiss\n"
    "  `2(`0K`2)iss {pronoun}!\n"
    "  `2(`0T`2)ake {pronoun} to the back room\n"
    "  `2(`0N`2)evermind\n"
)

_NAME_MAXLEN = 20
_DIGITS = "0123456789"

# "Well, I'm selling 5 for [PRICE] gold..." (KALDOR.EXE) -- literal.
GEM_BUNDLE_SIZE = 5
# Invented -- see module docstring's "Gem prices" note. Buy strictly
# exceeds sell at every level (this project's economy guardrail).
GEM_BUY_PRICE_PER_GEM_PER_LEVEL = 50
GEM_SELL_PRICE_PER_GEM_PER_LEVEL = 20
# Invented -- v1.3's recorded anti-arbitrage cap, size not recorded.
GEM_DAILY_STOCK_BUNDLES = 3

# "Here's your 30000 gold." (KALDOR.EXE) -- literal, flat, not level-scaled.
HORSE_SELL_PRICE = 30_000
# Invented -- see module docstring's "Horse buy price" note. Always above
# HORSE_SELL_PRICE for every level 1-12.
HORSE_BUY_BASE = 40_000
HORSE_BUY_PER_LEVEL = 5_000

# Invented -- see module docstring's "Fairy buy/sell prices" note.
FAIRY_BUY_PRICE = 50_000
FAIRY_SELL_PRICE = 20_000

# "You receive/lose 1 charm point!" (Chant, KALDOR.EXE) -- literal.
CHANT_CHARM_DELTA = 1

# Play an instrument's six recorded reward/penalty pairs -- literal.
INSTRUMENT_POINT_DELTA = 1  # charm / defense / strength / hitpoint
INSTRUMENT_EXP_DELTA = 500
INSTRUMENT_GOLD_DELTA = 1000

# Scream's recorded charm penalties -- literal (both branches).
SCREAM_CHARM_PENALTY = 2
# Invented -- see module docstring's "Obscene scream's exp reward" note.
SCREAM_EXP_PER_LEVEL = 25

# "You receive/lose ... 1/2 charm point(s)..." (Take to the back room,
# KALDOR.EXE) -- literal.
FLIRT_BACKROOM_CHARM_GAIN = 1
FLIRT_BACKROOM_CHARM_LOSS = 2
# Invented -- see module docstring's "Hercules/Xena's exp swings" note.
FLIRT_EXP_PER_LEVEL = {
    "W": 10,  # Wink
    "B": 20,  # Blow a kiss
    "K": 30,  # Kiss
    "T": 50,  # Take to the back room
}
# Invented -- charm-scaled, mirrors gem_trader's HAGGLE_CHARM precedent.
FLIRT_WIN_CHANCE_BASE = 40
FLIRT_WIN_CHANCE_MAX = 80

# "Speak your piece below: (Maximum of 70 characters)" (KALDOR.EXE) --
# literal. Board length cap is invented -- see module docstring.
TALK_LINE_MAXLEN = 70
TALK_BOARD_MAX_LINES = 20
_SEED_TALK_LINE = "Hercules: Hey Bartender, another round for all my friends!"


def _gem_buy_price(level: int) -> int:
    return GEM_BUNDLE_SIZE * GEM_BUY_PRICE_PER_GEM_PER_LEVEL * max(1, level)


def _gem_sell_price(level: int) -> int:
    return GEM_SELL_PRICE_PER_GEM_PER_LEVEL * max(1, level)


def _horse_buy_price(level: int) -> int:
    return HORSE_BUY_BASE + HORSE_BUY_PER_LEVEL * max(1, level)


class KaldorsCourt(IGM):
    key = "kaldors_court"
    name = "Kaldor's Court"
    author = "Chris Fisher"
    default_enabled = True

    async def enter(self, ctx: IgmContext) -> None:
        await ctx.term.write(
            "\n  `#Boy, does this place smell RANK!!!`0, you think to yourself.\n"
            "  `0As you wander around this putrid place, you notice a few\n"
            "  little shops to the West.  Off to the East, you notice the Inn.\n"
            "  To the South, the Temple.\n"
        )
        while True:
            await ctx.term.write(_COURT_MENU)
            choice = await ctx.term.menu(
                {"I": "inn", "M": "market", "T": "temple", "Y": "stats", "Q": "quit"},
                f"  `2What is your wish, `#{ctx.player.name}`2? [`0Q`2] : `%",
            )
            if choice == "Q":
                await ctx.term.write("\n  `2You head back out of Kaldor's Court.\n")
                return
            if choice == "I":
                await self._inn(ctx)
            elif choice == "M":
                await self._marketplace(ctx)
            elif choice == "T":
                await self._temple(ctx)
            else:
                await self._stats(ctx)

    # -- Your stats ----------------------------------------------------------

    async def _stats(self, ctx: IgmContext) -> None:
        p = ctx.player
        lines = [
            "\n  `5Your Stats`2\n",
            f"  `2Experience   : `0{p.exp}`2   Level: `0{p.level}\n",
            f"  `2Hitpoints    : `0{p.hp} `2of `0{p.hp_max}\n",
            f"  `2Forest Fights: `0{p.forest_fights}`2   Player Fights: `0{p.player_fights}\n",
            f"  `2Gold in Hand : `0{p.gold}`2   Gold in Bank: `0{p.bank}\n",
            f"  `2Weapon       : `0#{p.weapon_num}`2   Attack Strength    : `0{p.strength}\n",
            f"  `2Armor        : `0#{p.armor_num}`2   Defensive Strength : `0{p.defense}\n",
            f"  `2Charm        : `0{p.charm}`2   Gems: `0{p.gems}\n",
        ]
        if p.has_fairy:
            lines.append("  `2You have a `#fairy `2in your pocket...\n")
        if p.kids == 1:
            lines.append("  `2You have `%1 `2child...\n")
        elif p.kids > 1:
            lines.append(f"  `2You have `%{p.kids} `2children...\n")
        if p.horse:
            lines.append("  `2You are on `%horseback`2...\n")
        await ctx.term.write("".join(lines))
        await ctx.term.pause()

    # -- Marketplace -----------------------------------------------------

    async def _marketplace(self, ctx: IgmContext) -> None:
        await ctx.term.write(
            "\n  `0You let out a loud chuckle when you enter the Marketplace.\n"
            '  `#They call THIS a Marketplace???`0, you say under your breath.\n'
            "  Neverless, you decide to take a quick look around to see what\n"
            "  they have.\n"
        )
        while True:
            await ctx.term.write(_MARKET_MENU)
            choice = await ctx.term.menu(
                {"G": "gems", "H": "horse", "F": "fairy", "Q": "quit"},
                "  `2Your choice? [`0Q`2] : `%",
            )
            if choice == "Q":
                return
            if choice == "G":
                await self._gems_galore(ctx)
            elif choice == "H":
                await self._horse_heaven(ctx)
            else:
                await self._fairies_r_us(ctx)

    async def _gems_galore(self, ctx: IgmContext) -> None:
        p = ctx.player
        while True:
            buy_price = _gem_buy_price(p.level)
            sell_price = _gem_sell_price(p.level)
            stock = ctx.store.get("gem_stock", GEM_DAILY_STOCK_BUNDLES)
            await ctx.term.write(
                "\n  `#So, you're interested in my gems, eh?`0, asks the shopkeeper.\n"
                f"  `#Well, I'm selling {GEM_BUNDLE_SIZE} for`%{buy_price} `#gold and\n"
                f"  buying for`%{sell_price} `#gold per gem.`0\n"
            )
            choice = await ctx.term.menu(
                {"B": "buy", "S": "sell", "L": "leave"},
                "  `2(`0B`2)uy gems, (`0S`2)ell gems, or (`0L`2)eave? : `%",
            )
            if choice == "L":
                return
            if choice == "B":
                if stock < 1:
                    await ctx.term.write(
                        "\n  `#Sorry, I'm all out of gems for the day.`0, says the\n"
                        "  shopkeeper.\n"
                    )
                    await ctx.term.pause()
                    continue
                if p.gold < buy_price:
                    await ctx.term.write("\n  You don't have enough money for them!\n")
                    await ctx.term.pause()
                    continue
                p.gold -= buy_price
                p.gems += GEM_BUNDLE_SIZE
                ctx.store.set("gem_stock", stock - 1)
                await ctx.term.write(
                    "\n  `#Thank you for purchasing my fine gems!`0\n"
                )
                await ctx.term.pause()
            else:
                if p.gems < 1:
                    await ctx.term.write("\n  You don't have any gems!\n")
                    await ctx.term.pause()
                    continue
                qty = await self._ask_quantity(
                    ctx, f"\n  `2How many gems do you want to sell? : `%"
                )
                if qty < 1:
                    continue
                if qty > p.gems:
                    await ctx.term.write("\n  You don't have that many gems!\n")
                    await ctx.term.pause()
                    continue
                p.gems -= qty
                paid = qty * sell_price
                p.gold += paid
                await ctx.term.write(f"\n  `#Thanks for the gem, `0you get {paid} gold!\n")
                await ctx.term.pause()

    async def _horse_heaven(self, ctx: IgmContext) -> None:
        p = ctx.player
        buy_price = _horse_buy_price(p.level)
        await ctx.term.write(
            "\n  `#Howdy!`0, shouts the stablemaster.\n"
            "  `#We got us some fine, young horses here!`0\n"
            f"  `0You see a sign stating that horses sell for`%{buy_price} `0gold\n"
            f"  and are bought for`%{HORSE_SELL_PRICE} `0gold.\n"
        )
        choice = await ctx.term.menu(
            {"B": "buy", "S": "sell", "L": "leave"},
            "  `2(`0B`2)uy a horse, (`0S`2)ell your horse, or (`0L`2)eave? : `%",
        )
        if choice == "L":
            return
        if choice == "B":
            if p.horse:
                await ctx.term.write("\n  You already have a horse!\n")
                await ctx.term.pause()
                return
            if p.gold < buy_price:
                await ctx.term.write("\n  You don't have enough money!\n")
                await ctx.term.pause()
                return
            p.gold -= buy_price
            p.horse = 1
            await ctx.term.write("\n  Here is your fine young mount!\n")
            await ctx.term.pause()
        else:
            if not p.horse:
                await ctx.term.write("\n  You don't have a horse!\n")
                await ctx.term.pause()
                return
            p.horse = 0
            p.gold += HORSE_SELL_PRICE
            await ctx.term.write(
                "\n  `#Well, it looks pretty shabby, but I suppose.`0\n"
                f"  Here's your {HORSE_SELL_PRICE} gold.\n"
            )
            await ctx.term.pause()

    async def _fairies_r_us(self, ctx: IgmContext) -> None:
        p = ctx.player
        await ctx.term.write(
            "\n  `#Hehehehe`0, laughs the, well, not quite sure who (or WHAT) is\n"
            "  behind the counter. `#What can I do for you?`0, asks the, um, it.\n"
            "  `0You see a sign that says:\n"
            f"  We buy Fairies for`%{FAIRY_SELL_PRICE} `#gold and sell them for`%"
            f"{FAIRY_BUY_PRICE} `#gold.\n"
        )
        choice = await ctx.term.menu(
            {"B": "buy", "S": "sell", "L": "leave"},
            "  `2(`0B`2)uy a fairy, (`0S`2)ell your fairy, or (`0L`2)eave? : `%",
        )
        if choice == "L":
            return
        if choice == "B":
            if p.has_fairy:
                await ctx.term.write("\n  You already have a fairy!\n")
                await ctx.term.pause()
                return
            gate = f"fairy_buy:{p.id}"
            if ctx.store.get(gate, False):
                await ctx.term.write(
                    "\n  `2The, um, it has sold you all the fairies it can spare\n"
                    "  for one day.\n"
                )
                await ctx.term.pause()
                return
            if p.gold < FAIRY_BUY_PRICE:
                await ctx.term.write("\n  You don't have enough money for them!\n")
                await ctx.term.pause()
                return
            p.gold -= FAIRY_BUY_PRICE
            p.has_fairy = 1
            ctx.store.set(gate, True)
            await ctx.term.write("\n  Here is your fairy!\n")
            await ctx.term.pause()
        else:
            if not p.has_fairy:
                await ctx.term.write("\n  You don't have a fairy!\n")
                await ctx.term.pause()
                return
            p.has_fairy = 0
            p.gold += FAIRY_SELL_PRICE
            await ctx.term.write(
                "\n  `#Well, I suppose. But you must remember to take better care\n"
                "  of Fairies in the future!`0, it scowls at you.\n"
            )
            await ctx.term.pause()

    async def _ask_quantity(self, ctx: IgmContext, prompt: str) -> int:
        raw = await ctx.term.readline(prompt, maxlen=6, charset=_DIGITS)
        digits = "".join(c for c in raw if c.isdigit())
        return int(digits) if digits else 0

    # -- Temple of Daelamar ------------------------------------------------

    async def _temple(self, ctx: IgmContext) -> None:
        await ctx.term.write(
            "\n  `0As you enter through the large wooden doors, you notice\n"
            "  several monks praying at the alter.\n"
        )
        while True:
            await ctx.term.write(_TEMPLE_MENU)
            choice = await ctx.term.menu(
                {"C": "chant", "P": "instrument", "S": "scream", "L": "leave"},
                "  `2Your choice? [`0L`2] : `%",
            )
            if choice == "L":
                return
            if choice == "C":
                await self._chant(ctx)
            elif choice == "P":
                await self._play_instrument(ctx)
            else:
                await self._scream(ctx)

    async def _chant(self, ctx: IgmContext) -> None:
        p = ctx.player
        gate = f"chant:{p.id}"
        if ctx.store.get(gate, False):
            await ctx.term.write(
                "\n  `2Let's not bug the monks anymore today, ok?\n"
            )
            await ctx.term.pause()
            return
        ctx.store.set(gate, True)
        if ctx.rng.randrange(2) == 0:
            p.charm += CHANT_CHARM_DELTA
            await ctx.term.write(
                "\n  `0You chant a little prayer you thought up on the spot and\n"
                f"  `%YOU RECEIVE {CHANT_CHARM_DELTA} CHARM POINT!\n"
            )
        else:
            p.charm -= CHANT_CHARM_DELTA
            await ctx.term.write(
                "\n  `4You lose "
                f"{CHANT_CHARM_DELTA} charm point for annoying the monks with your\n"
                "  silly chant!\n"
            )
        await ctx.term.pause()

    async def _play_instrument(self, ctx: IgmContext) -> None:
        p = ctx.player
        gate = f"instrument:{p.id}"
        if ctx.store.get(gate, False):
            await ctx.term.write(
                "\n  `2Your not THAT talented, now.  Give it a rest!\n"
            )
            await ctx.term.pause()
            return
        await ctx.term.write(
            "\n  `0Not being from this part of town, you don't know exactly what\n"
            "  playing an instrument is supposed to do, but you feel the urge\n"
            "  to try it anyway.\n"
        )
        await ctx.term.write(_INSTRUMENT_MENU)
        _INSTRUMENT_ATTR = {
            "T": "charm",
            "O": "defense",
            "C": "strength",
            "F": "hp_max",
            "B": "exp",
            "G": "gold",
        }
        choice = await ctx.term.menu(
            {**_INSTRUMENT_ATTR, "N": "none"},
            f"  `2Play which instrument, `#{p.name}`2? [`0N`2] : `%",
        )
        if choice == "N":
            return
        ctx.store.set(gate, True)
        attr = _INSTRUMENT_ATTR[choice]
        delta = INSTRUMENT_EXP_DELTA if attr == "exp" else (
            INSTRUMENT_GOLD_DELTA if attr == "gold" else INSTRUMENT_POINT_DELTA
        )
        label = {
            "charm": "charm point",
            "defense": "defense point",
            "strength": "strength point",
            "hp_max": "hitpoint",
            "exp": "experience points",
            "gold": "gold",
        }[attr]
        if ctx.rng.randrange(2) == 0:
            setattr(p, attr, getattr(p, attr) + delta)
            await ctx.term.write(
                f"\n  `0Your music was beautiful.  `%YOU RECEIVE {delta} {label.upper()}!\n"
            )
        else:
            setattr(p, attr, getattr(p, attr) - delta)
            await ctx.term.write(
                f"\n  `4Your music was off-key.  You lose {delta} {label}!\n"
            )
        await ctx.term.pause()

    async def _scream(self, ctx: IgmContext) -> None:
        p = ctx.player
        gate = f"scream:{p.id}"
        if ctx.store.get(gate, False):
            await ctx.term.write(
                "\n  `2You decide against screaming anymore today.\n"
            )
            await ctx.term.pause()
            return
        await ctx.term.write(
            "\n  `0Exploring your mischievious side, you decide to let out a\n"
            "  loud scream to see what would happen.\n"
        )
        await ctx.term.write(_SCREAM_MENU)
        choice = await ctx.term.menu(
            {"O": "obscene", "E": "earpierce", "C": "nevermind"},
            "  `2Your choice? [`0C`2] : `%",
        )
        if choice == "C":
            return
        ctx.store.set(gate, True)
        win = ctx.rng.randrange(2) == 0
        if choice == "O":
            if win:
                gained = SCREAM_EXP_PER_LEVEL * max(1, p.level)
                p.exp += gained
                await ctx.term.write(
                    "\n  `0You sure do know how to clear out a room!\n"
                    f"  `%YOU RECEIVE {gained} EXPERIENCE POINTS!\n"
                )
            else:
                p.charm -= SCREAM_CHARM_PENALTY
                await ctx.term.write(
                    f"\n  `4You lose {SCREAM_CHARM_PENALTY} charm points for being\n"
                    "  SO rude!\n"
                )
        else:
            if win:
                await ctx.term.write(
                    "\n  `0You send the monks out of the Temple crying because of\n"
                    "  ear aches!\n"
                )
            else:
                p.charm -= SCREAM_CHARM_PENALTY
                await ctx.term.write(
                    "\n  `4You scream SO loudly that parts of the Temple fall from\n"
                    "  the ceiling and land on your head!  You lose "
                    f"{SCREAM_CHARM_PENALTY} charm points for the nasty bump it left!\n"
                )
        await ctx.term.pause()

    # -- Inn of Kaldor ------------------------------------------------------

    async def _inn(self, ctx: IgmContext) -> None:
        await ctx.term.write(
            "\n  `0As you step into the INN, you vaguely remember hearing that\n"
            "  this is the place the legendary Hercules and Xena frequently\n"
            "  visited.\n"
        )
        while True:
            await ctx.term.write(_INN_MENU)
            choice = await ctx.term.menu(
                {"C": "converse", "H": "hercules", "X": "xena", "L": "leave"},
                "  `2Your choice? [`0L`2] : `%",
            )
            if choice == "L":
                return
            if choice == "C":
                await self._converse(ctx)
            elif choice == "H":
                await self._flirt(ctx, "Hercules", "him")
            else:
                await self._flirt(ctx, "Xena", "her")

    async def _converse(self, ctx: IgmContext) -> None:
        board = ctx.store.get("talk_board", [_SEED_TALK_LINE])
        line = board[ctx.rng.randrange(len(board))] if board else _SEED_TALK_LINE
        await ctx.term.write(f"\n  `2You hear someone say:\n  `0{line}\n")
        choice = await ctx.term.menu(
            {"A": "add", "C": "continue"},
            "  `2(`0A`2)dd to conversation or (`0C`2)ontinue [`0C`2] : `%",
        )
        if choice != "A":
            return
        raw = await ctx.term.readline(
            f"\n  `2Speak your piece below: (Maximum of {TALK_LINE_MAXLEN} characters)\n"
            "  `0: `%",
            maxlen=TALK_LINE_MAXLEN,
        )
        text = raw.strip()
        if not text:
            return
        entry = f"{ctx.player.name}: {text}"
        new_board = (board + [entry])[-TALK_BOARD_MAX_LINES:]
        ctx.store.set("talk_board", new_board)
        await ctx.term.write("\n  `2Your words join the conversation.\n")
        await ctx.term.pause()

    async def _flirt(self, ctx: IgmContext, npc: str, pronoun: str) -> None:
        p = ctx.player
        gate = f"flirt:{p.id}"
        if ctx.store.get(gate, False):
            await ctx.term.write(
                "\n  `2Better not flirt anymore right now.\n"
            )
            await ctx.term.pause()
            return
        await ctx.term.write(_FLIRT_MENU.format(pronoun=pronoun))
        choice = await ctx.term.menu(
            {"W": "wink", "B": "kiss", "K": "kiss2", "T": "backroom", "N": "nevermind"},
            f"  `2What do you do to {pronoun}, `#{p.name}`2? [`0N`2] : `%",
        )
        if choice == "N":
            return
        ctx.store.set(gate, True)

        chance = min(FLIRT_WIN_CHANCE_MAX, FLIRT_WIN_CHANCE_BASE + p.charm)
        win = ctx.rng.randrange(100) < chance
        exp = FLIRT_EXP_PER_LEVEL[choice] * max(1, p.level)

        if choice == "T":
            if win:
                p.exp += exp
                p.charm += FLIRT_BACKROOM_CHARM_GAIN
                await ctx.term.write(
                    "\n  `0You both head to the back room, and have a great time\n"
                    "  together!\n"
                    f"  `%YOU RECEIVE {exp} EXPERIENCE AND {FLIRT_BACKROOM_CHARM_GAIN} "
                    "CHARM POINT!\n"
                )
            else:
                p.exp -= exp
                p.charm -= FLIRT_BACKROOM_CHARM_LOSS
                await ctx.term.write(
                    f"\n  `4You lose {exp} experience and {FLIRT_BACKROOM_CHARM_LOSS}\n"
                    "  charm points for being too outgoing!\n"
                )
        else:
            success_line = {
                "W": f"{npc} winked back!",
                "B": f"{npc} blew a kiss back!",
                "K": f"{npc} kissed you back!",
            }[choice]
            if win:
                p.exp += exp
                await ctx.term.write(
                    f"\n  `0{success_line}\n  `%YOU RECEIVE {exp} EXPERIENCE!\n"
                )
            else:
                p.exp -= exp
                await ctx.term.write(
                    f"\n  `4{npc} wasn't interested in your advances!\n"
                    f"  You lose {exp} experience for being too outgoing!\n"
                )
        await ctx.term.pause()

    # -- Maintenance ----------------------------------------------------

    async def daily_maint(self, ctx: IgmMaintContext) -> None:
        ctx.store.delete("gem_stock")
        for player in ctx.repo.all_players():
            ctx.store.delete(f"chant:{player.id}")
            ctx.store.delete(f"instrument:{player.id}")
            ctx.store.delete(f"scream:{player.id}")
            ctx.store.delete(f"flirt:{player.id}")
            ctx.store.delete(f"fairy_buy:{player.id}")
        # talk_board intentionally NOT cleared -- TALK.DAT's own board
        # persisted across days in the original; see module docstring.
