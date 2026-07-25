"""Xenon's Town Square v2.0 -- by Chris Fisher, The Digital Escape BBS
(``igms_to_port/xenon20.zip``, (c) Digital Software 1995).

**Provenance tier: documented recreation.** ``XENON.EXE`` "was written in
QuickBasic 4.5 using QWKIGM programming library for IGMs" (``XENON.DOC``) --
a compiled DOS binary, no source survives, and ``reference/igm-sources/
lordts/`` has no "xenon"-named IGM in it (checked; its port list is aratime,
barak, felicity, freeworld2, gravyard, lordcave, lotto, lrdevent, npclord,
oorphans, outhouse, sandbar, teamlord, violet -- none of which is this IGM
or a plausible lineage match). Like ``igms/kaldors_court/igm.py`` (same
author, same BBS, same publisher line), a ``strings`` pass over
``XENON.EXE`` recovers the literal ASCII text a QuickBasic compiler emits
for every ``PRINT`` statement, including several numeric literals baked
directly into those templates (below) -- real *data*, not decompiled
control flow (no branch, loop or comparison survives). Unlike
``igms/kaldors_court/igm.py``'s own port, no independent hex-dump
byte-adjacency confirmation was done here for the handful of
compiler-split literal pairs quoted below (e.g. ``, claims `` /
``the bank teller.``) -- they are read as attached to the adjacent refusal
line the same way Kaldor's own docstring reads ``KALDOR.EXE``'s splits, but
that specific reading is not independently re-verified against a raw hex
dump for this port.

Sources read (Step 1): ``xenon20.zip`` (v2.0, this port's target) --
``FILE_ID.DIZ``, ``XENON.DOC``, ``WHAT-IS.NEW``, ``UPDATE.DOC``,
``PROBLEMS.DOC``, ``REGISTER.DOC``, ``QWK-IGM.INI``, ``DESQVIEW.TXT``,
``FOSSIL.TXT``, ``TALK.DAT``; and a ``strings`` pass over ``XENON.EXE`` and
``INSTALL.EXE``. Also ``xenon-v1.zip`` (v1.0, an earlier version, same
author/BBS line), checked per this task's brief for numbers an earlier
release records that the later one assumes: the same document set, plus
``LORD.IGM`` and ``TALK.DAT``, and its own ``strings`` pass over
``XENON.EXE``/``INSTALL.EXE``, diffed against v2.0's own strings to see
what actually changed. Two things worth recording plainly from that diff:

* **v1.0's own ``LORD.IGM`` is not IGM data at all.** It is a generic
  "This archive passed... The BBS Archives -- http://www.pcmicro.com/bbs"
  footer a file-archive site stamped into the zip, byte-for-byte the same
  kind of decorative banner some ``.zip``s on a download site carry --
  nothing about Xenon's own registration, menu, or handshake. A red
  herring; noted here so a future reader doesn't waste time on it. (v2.0's
  archive has no ``LORD.IGM`` file at all.)
* **v1.0's registration cost money** (``REGISTER.DOC``: "Registration is
  only $2.00!!!"); v2.0's own ``FILE_ID.DIZ``/``REGISTER.DOC`` both say
  "Now FREEWARE!!!" / "There's no longer a need to register." Every other
  recorded mechanic (menu wording, refusal lines, numeric caps) is
  byte-identical between the two versions' ``strings`` output -- the only
  *structural* difference is which menu keys are exposed at the outermost
  level: v1.0's own top menu strings are only ``(D)eposit`` / ``(E)nter
  square`` / ``(G)o see the Nanny`` / ``(Q)uit to LORD`` / ``(W)ithdraw``,
  while v2.0 additionally surfaces ``(V)isit the stables`` and ``(S)ee what
  the townfolk are saying`` as their own top-level keys. Both versions'
  binaries carry the *same* stables/Nanny/talk-board flavour text and
  refusal lines regardless (confirmed: every string quoted below for those
  three features is present verbatim in both ``strings`` dumps) -- so the
  underlying features are not new in v2.0, only their promotion to
  top-level menu keys is. This port targets v2.0's own menu shape.

**Recorded, verbatim (``XENON.DOC``/``FILE_ID.DIZ``/``strings`` over
``XENON.EXE``):**

* ``FILE_ID.DIZ``/``XENON.DOC``: "Xenon's Town Square...was written to
  provide users with a place to store GOLD, GEMS, CHILDREN and their HORSE.
  To those of you familiar with the IGMs that allow players to steal from
  other players, this IGM can be helpful." Also: "the more experienced
  players know that keeping their children with them can be unwise, because
  they seem to like to get themselves killed in the forest... This IGM
  provides the user with a 'daycare' to keep their children at. (Little
  secret though -- if they don't take them out before they quit the game,
  they won't get the extra forest fights each day!)" -- this project's own
  ``daily.py`` (``forest_fights = min(config forest_fights_per_day +
  player.kids, 32000)`` at daily reset) is exactly the mechanic this line
  describes: a kid parked in Xenon's daycare (subtracted out of
  ``player.kids``) doesn't count toward tomorrow's forest-fight bonus,
  authentically reproducing the "little secret" as a real, self-limiting
  trade-off (it forfeits a bonus; it does not dodge a penalty -- see the
  storage-exposure analysis below).
* The top menu, verbatim (v2.0): ``(D)eposit items into the bank`` /
  ``(W)ithdraw items from the bank`` / ``(G)o see the Nanny`` / ``(V)isit
  the stables`` / ``(S)ee what the townfolk are saying`` / ``(Q)uit to
  LORD``. The outer ``(E)nter square`` / ``(Q)uit to LORD`` title gate
  (``XENON.EXE``'s own standalone entry screen, shown before this menu) is
  **not ported** -- the exact same role this project's Other Places doorway
  (``pylord/engine/scenes/other_places.py``) already plays for every IGM,
  the same call ``igms/kaldors_court/igm.py`` makes for ``KALDOR.EXE``'s
  analogous outer gate.
* **Deposit/Withdraw submenu**, verbatim: ``(M)oney`` / ``(G)ems`` /
  ``(C)heck balances`` / ``(Q)uit?`` and, per the box's own literal prompt,
  "What would you like to do, `#[name]" -- one shared submenu shape reused
  for both directions (both ``Depositing items...`` and ``Withdrawing
  items...`` survive as their own single, generic in-progress lines, not
  duplicated per money/gems, which is why this port shows one shared
  transaction line for either resource inside either direction). Field
  labels, verbatim: "Gold in bank : " / "Gems in bank : " (Xenon's own
  storage -- **not** ``pylord/engine/scenes/bank.py``'s Ye Old Bank, despite
  sharing the word "bank"; see the storage-exposure analysis below for why
  that overlap matters).
* **Deposit prompts/refusals, verbatim**: "How much gold would you like to
  deposit? " / "You don't `5HAVE `2that much gold!" / "If you change your
  mind, just come back." / "`0Sorry. We cannot hold more than 2 billion
  gold pieces.`2" (a **literal, verbatim cap** -- matches
  ``pylord/engine/scenes/bank.py``'s own ``_CAP = 2_000_000_000`` for Ye
  Old Bank, coincidentally or not); "How many gems would you like to
  deposit? " / "You don't `5HAVE `2that many gems!" / "`0Sorry. We cannot
  hold more than 32 thousand gems.`2" (a **literal, verbatim cap** -- also
  matches this project's own ``gems`` field ceiling,
  ``pylord/engine/limits.py``'s ``STAT_CAP = 32_000``). "`0You cannot enter
  a negative number!`2" is recorded too, but a digit-only ``readline``
  charset (this task's own instruction, and this project's established
  convention -- ``pylord/engine/scenes/bank.py``'s own ``_DIGITS``,
  ``igms/kaldors_court/igm.py``'s ``_ask_quantity``) makes typing a negative
  amount structurally impossible, so -- exactly like ``bank.py``'s own
  ``elif amt < 0: # pragma: no cover`` branch for the identical situation --
  this port omits reproducing that line as literal dead code rather than
  keeping an unreachable branch around.
* **Withdraw prompts/refusal, verbatim**: "How much gold would you like to
  withdraw? " / "How many gems would you like to withdraw? " / "We do not
  give loans, and you cannot take more than you put in!" -- one shared
  refusal for both resources (only one such line survives in the binary,
  immediately preceding both withdrawal prompts), meaning withdrawal is a
  flat, no-interest round trip: whatever was put in comes back out, never
  more, and the deposit/withdraw pair never manufactures gold or gems
  either direction -- satisfying this project's own "a round trip must
  never profit" economy rule (``igms/kaldors_court/igm.py``'s gem/horse/
  fairy guardrails) trivially, since it is a zero-sum transfer rather than a
  priced buy/sell.
* **The Nanny / daycare, verbatim**: "`0Well, hello there!`2" / "Have you
  come here to have me watch your children?" / "she asks." and, the
  alternate greeting, "`0You know them children like to get themselves in
  trouble when you are out looking for the Dragon.`2" / ", she proclaims."
  -- two greeting variants, chosen at random each visit (see "Invented"
  below). Submenu, verbatim: ``(L)eave children`` / ``(T)ake children`` /
  ``(C)heck how many children you have in daycare.`` / ``(Q)uit?``. Prompts/
  refusals, verbatim: "How many children would you like to leave with me? "
  / "You don't `5HAVE `2that many kids!" / ", claims the Nanny." / "How many
  kids would you like to take with you? " / "What are you, a kidnapper? You
  can't take more kids than you have!!!" / "`0If you change your mind, I'll
  be here!`2" / ", says the Nanny." / "You don't have any children here." /
  "`2You have `%1 `2child here in daycare." / "`2You have `%[N] `2children in
  daycare." "`0You cannot leave negative kids!`2" and "NO NEGATIVE
  NUMBERS!!!" are recorded too, and dropped as unreachable dead code for the
  same digit-only-charset reason as the deposit section's own negative-number
  line, above.
* **The stables, verbatim**: "You notice the stablemaster on the other side
  of the stables, feeding the other horses. He looks up and asks, `0What can
  I do ya for, pardner?`2". Submenu, verbatim: ``(L)eave your horse`` /
  ``(T)ake your horse`` / ``(C)heck to see if you have a horse in the
  stables`` / ``(Q)uit?``. Prompts/refusals, verbatim: "You don't have a
  horse to leave!" / "You cannot keep more than one horse here at the same
  time!" / "You lock your horse up in its own stable, hoping the
  stablemaster will remember to feed him." / "You already HAVE your
  horse!!!" / "You do NOT have a horse here." / "Here is your horse...
  Please take good care of him." / "`0Shur, pardner. I have yer horse right
  here!`2" / ", says the stablemaster."
* **The townfolk / talk board, verbatim**: "As you make your way through
  the large crowd before you, you notice several people shouting."
  Submenu, verbatim: ``(T)ry to make out what they are saying`` /
  ``(S)hout something of your own`` / ``(Q)uit``. "Shout your message
  below: Maximum of 70 characters" (**a literal, verbatim 70-character
  cap** -- matches ``igms/kaldors_court/igm.py``'s own recorded 70-character
  conversation cap for its Inn) then "Is this what you want to say?" -- a
  Y/N confirmation showing the rendered, color-coded line back to the
  player before it's saved, matching ``WHAT-IS.NEW``'s own v0.8β changelog
  entry: "Now the IGM displays what the user has written with LORD color
  codes before giving them the option of saving." ``TALK.DAT``'s own seed
  content, byte for byte: "`%The Nanny:\n`2`!Let's `#get `3some `7talk
  `2going `1here!" -- the one surviving line of this board, read here as
  ``"The Nanny: Let's get some talk going here!"``.
* **Stats block, verbatim field list**, shown on the way into the square
  (no dedicated hotkey survives for it, unlike ``igms/kaldors_court/
  igm.py``'s own explicit ``(Y)our stats`` key -- see "Invented" below):
  Hitpoints, Forest Fights, Player Fights, Gold in Hand, Gold in Bank,
  Weapon, Attack Strength, Armor, Defensive Strength, Charm, Gems, plus
  conditional lines for N children in daycare. **"Gold in Bank" here is
  ``pylord/engine/scenes/bank.py``'s real Ye Old Bank balance
  (``player.bank``)** -- a different number from this same IGM's own
  "Gold in bank"/"Gems in bank" inside its Deposit/Withdraw submenu (Xenon's
  own storage, kept in ``IgmStore``). The archive genuinely overloads the
  word "bank" for two different piles; both are reproduced as recorded, and
  this docstring flags the overlap so a future maintainer doesn't "fix" it
  into one number by mistake.
* **Version history numbers** (``WHAT-IS.NEW``, both archives): v0.2β
  "will only allow a max. of 2000000000 gold and a max. of 32000 gems to be
  deposited" -- confirms the two caps above existed from the very first
  beta, unchanged through v2.0. v1.6: "Now Xenon's will reset the player's
  Gold in bank and Gems in bank when they win LORD." -- a recorded
  reset-on-win mechanic, addressed below (storage-exposure analysis). v1.7:
  "It also no longer limits the daily withdrawl amount" -- confirms there
  is deliberately **no** per-day withdrawal cap in the version this port
  targets (an earlier one existed and was removed), so ``daily_maint``
  below has no per-day gate of its own to clear for deposit/withdraw.

Nowhere in either archive is there a numeric odds table, an interest rate,
or a fee on deposit/withdraw -- only the two hard caps, the 70-character
talk cap, and the "no loans" no-profit rule above. Everything else below
fills the remaining gaps.

**Invented (and why):**

* **Menu keys/labels/flavor text with no verbatim survivor** -- the
  entry-flavor line walking into the square itself (distinct from the
  Townfolk submenu's own recorded crowd-noise flavor, which *is* recorded
  and used verbatim), and this project's established ``(L)eave``/``(Q)uit``
  conventions where no single letter survives for a given submenu's own
  "back out" case beyond what's quoted above.
* **Two Nanny greetings, chosen at random each visit** -- both survive
  verbatim in the binary (above) with no way to tell which one leads and
  which is a fallback/repeat-visit variant, so a coin flip (``ctx.rng.
  randrange(2)``) picks between them, the same "pick uniformly among
  recorded variants" reading this project already uses elsewhere for
  flavor-only variety (e.g. ``igms/outlands_tavern/igm.py``'s greeting
  rotation).
* **Talk board trim size (20 entries kept, oldest dropped), invented** --
  nothing records how ``TALK.DAT`` ever got trimmed; this mirrors
  ``igms/kaldors_court/igm.py``'s own identical, identically-reasoned
  ``TALK_BOARD_MAX_LINES = 20`` for the same "an ever-growing shared list
  needs *some* bound" reason. The 70-character line cap is recorded, used
  as-is.
* **Compiler-split dialogue-tag assembly** (e.g. reading the separately
  recovered fragments ``, claims `` / ``the bank teller.`` as one attached
  refusal-line tag, or ``, says `` / ``the Nanny.`` the same way) -- a
  plain reading of adjacency in the ``strings`` output, not independently
  hex-confirmed (see the provenance-tier note above).
* **Stats block shown automatically on entry, not behind a menu key** --
  no ``(Y)our stats``-shaped hotkey survives anywhere in either archive's
  ``strings`` output for this IGM (unlike ``igms/kaldors_court/igm.py``'s
  own explicit recorded key for the same kind of screen), so the plainest
  reading of "this text exists and the archive's own menu list doesn't
  have a key for it" is that it's shown automatically, not gated.

**Storage-exposure design call (this task's own "STORAGE IGM WARNING"):**
This IGM's entire premise is parking ``gold``/``gems``/``kids``/``horse``
somewhere the base game's own risk mechanics can't reach mid-visit, so
before porting it, this project's own death/PvP/dragon-win code paths were
read end to end (``pylord/engine/scenes/forest.py``'s ``_death`` and
``_event_troll``, ``pylord/engine/scenes/pvp.py``'s ``_win``/``_lose``,
``pylord/engine/scenes/dragon.py``'s win/defeat tails, and
``pylord/engine/scenes/bank.py``) to see exactly what an IGM stash would
and wouldn't be sheltering a player from, resource by resource:

* **Gold.** Every on-hand-gold-loss path in this project (forest death,
  PvP loss, the troll event, dragon defeat) already zeroes only
  ``player.gold`` -- never ``player.bank``. ``pylord/engine/scenes/
  bank.py``'s Ye Old Bank has sheltered up to 2,000,000,000 gold from every
  one of those losses since Task before this one; Xenon's own gold storage,
  capped at the same recorded 2,000,000,000, does not shelter anything the
  Bank doesn't already shelter -- it is a second, cosmetically-distinct
  bucket with an identical exposure profile, not a new hole. No additional
  bound was invented for gold beyond the archive's own recorded cap.
* **Gems.** This is the one resource where storing it here is genuinely
  new. Exactly two paths in this project ever take on-hand gems
  *involuntarily* (a third, ``forest.py``'s old-woman event, is a
  player-confirmed Y/N trade of a gem for healing -- not a loss to guard
  against, and out of scope for this analysis): ``forest.py``'s troll
  event (``_event_troll``, a death that zeroes ``player.gems`` outright)
  and ``pvp.py``'s ``_win`` (halves the *loser's* on-hand gems). Nothing
  in this project shelters gems from either involuntary path today --
  there is no "gem bank." Parking gems in Xenon's daycare-adjacent
  storage would be the first such shelter. Because ``pylord.hooks.IGM``
  only exposes ``enter``/``daily_maint``/``forest_event``/``inn_event`` (no
  "a death/PvP-loss just happened to this player" callback exists anywhere
  in the plugin surface -- checked ``pylord/hooks.py`` end to end), an IGM
  has no channel to *mirror* the Bank's real-time exposure the way this
  task's brief suggests as the first option. The chosen mitigation is the
  brief's second option: **bound the amount.** ``STORAGE_GEM_CAP`` stays at
  the archive's own recorded, verbatim 32,000 -- the same order of
  magnitude as this project's own single-account ``gems`` field ceiling
  (``pylord/engine/limits.py``'s ``STAT_CAP``), so at most one more
  account's worth of gems can ever be parked here, not an unbounded pile.
* **Reset-on-win gap.** ``WHAT-IS.NEW`` v1.6 records that the original
  reset a player's Xenon's gold/gems "when they win LORD" -- and this
  project's own ``dragon.py`` already has an equivalent per-player "fresh
  start" cycle on a dragon kill (``bank=0``, ``gold=500``, ``gems=10`` flat
  overwrite, ``king_count += 1``; see that module's docstring). But
  ``dragon.py`` mutates the ``Player`` row directly from its own scene --
  there is no hook an IGM can register for "this player just won." The
  closest available inspection point is ``daily_maint``, which does get a
  live snapshot of every player's current fields once per game-day. This
  port uses that: it remembers each player's ``king_count`` as of the last
  maintenance pass (``kc:<id>``) and, the first time it observes that
  number go *up*, clears that player's Xenon's gold/gems stash (matching
  the recorded scope -- gold and gems only, not kids or a stored horse,
  which v1.6's own changelog line never mentions resetting). This is
  necessarily a **next-maintenance-pass approximation**, not an instant
  reaction to the win itself -- disclosed here rather than silently
  passing over the gap, and it is the second reason (alongside the capped
  amount above) this port doesn't treat 32,000 gems / 2,000,000,000 gold as
  numbers to fill and forget: a stash that outlives a dragon-win reset for
  even one maintenance cycle is exactly the scenario the original author
  built v1.6 to prevent.
* **Kids and horse.** Neither field is ever touched by any death, PvP, or
  dragon-loss code path in this project (checked all three modules above --
  no hit). Storing them here doesn't shelter a player from anything
  currently threatened; the one real interaction is the recorded
  forest-fights-bonus mechanic already covered above (a forfeited bonus,
  not a dodged penalty), and it needs no additional guard.

**Not ported:**

* **Registration/shareware furniture** -- v1.0's $2.00 fee, v2.0's own
  "Now FREEWARE!!!" banner -- this project's only IGM configuration surface
  is the ``[igms]`` enable toggle, the same boundary every wave-3 sibling's
  docstring already establishes.
* **``XENON.DAT``'s own on-disk record layout, ``QWKIGM.DAT``/
  ``3RDPARTY.DAT`` install handshake, FOSSIL/DesqView driver notes, node
  numbers** -- infrastructure for a DOS-door file handshake this project's
  engine has no analogue for; ``IgmStore`` replaces the flat-file mechanism
  entirely.
"""

from __future__ import annotations

from pylord.engine.limits import GOLD_CAP, STAT_CAP
from pylord.hooks import IGM, IgmContext, IgmMaintContext

_MENU = (
    "\n  `5Xenon's Town Square`2\n"
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
    "  `2(`0D`2)eposit items into the bank\n"
    "  `2(`0W`2)ithdraw items from the bank\n"
    "  `2(`0G`2)o see the Nanny\n"
    "  `2(`0V`2)isit the stables\n"
    "  `2(`0S`2)ee what the townfolk are saying\n"
    "  `2(`0Q`2)uit to LORD\n"
)

_BANK_SUBMENU = (
    "\n  `2(`0M`2)oney\n  `2(`0G`2)ems\n  `2(`0C`2)heck balances\n  `2(`0Q`2)uit?\n"
)

_NANNY_MENU = (
    "\n  `2(`0L`2)eave children\n"
    "  `2(`0T`2)ake children\n"
    "  `2(`0C`2)heck how many children you have in daycare\n"
    "  `2(`0Q`2)uit?\n"
)

_STABLES_MENU = (
    "\n  `2(`0L`2)eave your horse\n"
    "  `2(`0T`2)ake your horse\n"
    "  `2(`0C`2)heck to see if you have a horse in the stables\n"
    "  `2(`0Q`2)uit?\n"
)

_TALK_MENU = (
    "\n  `2(`0T`2)ry to make out what they are saying\n"
    "  `2(`0S`2)hout something of your own\n"
    "  `2(`0Q`2)uit\n"
)

_DIGITS = "0123456789"

# "Sorry. We cannot hold more than 2 billion gold pieces." (XENON.EXE) --
# literal, and matches pylord/engine/scenes/bank.py's own _CAP. See module
# docstring's storage-exposure analysis for why this is not a new bound.
STORAGE_GOLD_CAP = 2_000_000_000
GOLD_MAXLEN = 11  # matches bank.py's own maxlen for the same cap

# "Sorry. We cannot hold more than 32 thousand gems." (XENON.EXE) --
# literal, and deliberately kept at this size rather than raised: see
# module docstring's storage-exposure analysis (the one genuinely new
# shelter this IGM introduces).
STORAGE_GEM_CAP = 32_000
GEM_MAXLEN = 6

# No recorded cap on how many kids can be left at once; player.kids itself
# is already floored/capped [0, 32000] by PlayerView on the way back out.
KIDS_MAXLEN = 6

# "Shout your message below: Maximum of 70 characters" (XENON.EXE) --
# literal. Board trim size is invented -- see module docstring.
TALK_LINE_MAXLEN = 70
TALK_BOARD_MAX_LINES = 20
_SEED_TALK_LINE = "The Nanny: Let's get some talk going here!"


async def _ask_amount(ctx: IgmContext, prompt: str, maxlen: int) -> int:
    raw = await ctx.term.readline(prompt, maxlen=maxlen, charset=_DIGITS)
    digits = "".join(c for c in raw if c.isdigit())
    return int(digits) if digits else 0


class XenonsTownSquare(IGM):
    key = "xenons_town_square"
    name = "Xenon's Town Square"
    author = "Chris Fisher"
    default_enabled = True

    async def enter(self, ctx: IgmContext) -> None:
        p = ctx.player
        await ctx.term.write(
            "\n  `2The square bustles with vendors, a daycare, and a stable --\n"
            "  `0Xenon's Town Square`2, a safe place to leave a few things\n"
            "  behind while you go looking for the Dragon.\n"
        )
        await self._show_stats(ctx)
        while True:
            await ctx.term.write(_MENU)
            choice = await ctx.term.menu(
                {
                    "D": "deposit",
                    "W": "withdraw",
                    "G": "nanny",
                    "V": "stables",
                    "S": "townfolk",
                    "Q": "quit",
                },
                f"  `2What would you like to do, `#{p.name}`2? [`0Q`2] : `%",
            )
            if choice == "Q":
                await ctx.term.write("\n  `2Returning to LORD...\n")
                return
            if choice == "D":
                await self._bank(ctx, "deposit")
            elif choice == "W":
                await self._bank(ctx, "withdraw")
            elif choice == "G":
                await self._nanny(ctx)
            elif choice == "V":
                await self._stables(ctx)
            else:
                await self._townfolk(ctx)

    # -- Stats snapshot (shown on entry, no dedicated key -- see docstring) --

    async def _show_stats(self, ctx: IgmContext) -> None:
        p = ctx.player
        gold_stored = ctx.store.get(f"gold:{p.id}", 0)
        gems_stored = ctx.store.get(f"gems:{p.id}", 0)
        lines = [
            f"  `2Hitpoints          : `0{p.hp} `2of `0{p.hp_max}",
            f"  `2Forest Fights      : `0{p.forest_fights}",
            f"  `2Player Fights      : `0{p.player_fights}",
            f"  `2Gold in Hand       : `0{p.gold}",
            f"  `2Gold in Bank       : `0{p.bank}",
            f"  `2Weapon             : `0#{p.weapon_num}",
            f"  `2Attack Strength    : `0{p.strength}",
            f"  `2Armor              : `0#{p.armor_num}",
            f"  `2Defensive Strength : `0{p.defense}",
            f"  `2Charm              : `0{p.charm}",
            f"  `2Gems               : `0{p.gems}",
        ]
        kids_stored = ctx.store.get(f"kids:{p.id}", 0)
        if kids_stored == 1:
            lines.append("  `2You have `%1 `2child here in daycare.")
        elif kids_stored > 1:
            lines.append(f"  `2You have `%{kids_stored} `2children in daycare.")
        if ctx.store.get(f"horse:{p.id}", False):
            lines.append("  `2Your horse is here in the stables.")
        lines.append(
            f"  `2(Xenon's) Gold in bank : `0{gold_stored}`2   Gems in bank: `0{gems_stored}"
        )
        await ctx.term.write("\n".join(lines) + "\n")

    # -- Deposit / Withdraw ("the bank") --------------------------------

    async def _bank(self, ctx: IgmContext, mode: str) -> None:
        p = ctx.player
        while True:
            await ctx.term.write(_BANK_SUBMENU)
            choice = await ctx.term.menu(
                {"M": "money", "G": "gems", "C": "check", "Q": "quit"},
                f"  `2What would you like to do, `#{p.name}`2? [`0Q`2] : `%",
            )
            if choice == "Q":
                return
            if choice == "C":
                await self._check_balances(ctx)
            elif choice == "M":
                if mode == "deposit":
                    await self._deposit_money(ctx)
                else:
                    await self._withdraw_money(ctx)
            else:
                if mode == "deposit":
                    await self._deposit_gems(ctx)
                else:
                    await self._withdraw_gems(ctx)

    async def _check_balances(self, ctx: IgmContext) -> None:
        p = ctx.player
        gold_stored = ctx.store.get(f"gold:{p.id}", 0)
        gems_stored = ctx.store.get(f"gems:{p.id}", 0)
        await ctx.term.write(
            f"\n  `2Gold in bank  : `0{gold_stored}\n"
            f"  `2Gems in bank  : `0{gems_stored}\n"
        )
        await ctx.term.pause()

    async def _deposit_money(self, ctx: IgmContext) -> None:
        p = ctx.player
        amt = await _ask_amount(
            ctx, "\n  `2How much gold would you like to deposit? `%", GOLD_MAXLEN
        )
        if amt < 1:
            return
        if amt > p.gold:
            await ctx.term.write(
                "\n  `2You don't `5HAVE `2that much gold!\n"
                "  `0If you change your mind, just come back.\n"
            )
            await ctx.term.pause()
            return
        stored = ctx.store.get(f"gold:{p.id}", 0)
        if stored + amt > STORAGE_GOLD_CAP:
            await ctx.term.write(
                "\n  `0Sorry. We cannot hold more than 2 billion gold pieces.`2\n"
            )
            await ctx.term.pause()
            return
        p.gold -= amt
        ctx.store.set(f"gold:{p.id}", stored + amt)
        await ctx.term.write("\n  `2Depositing items...\n")
        await ctx.term.pause()

    async def _deposit_gems(self, ctx: IgmContext) -> None:
        p = ctx.player
        amt = await _ask_amount(
            ctx, "\n  `2How many gems would you like to deposit? `%", GEM_MAXLEN
        )
        if amt < 1:
            return
        if amt > p.gems:
            await ctx.term.write("\n  `2You don't `5HAVE `2that many gems!\n")
            await ctx.term.pause()
            return
        stored = ctx.store.get(f"gems:{p.id}", 0)
        if stored + amt > STORAGE_GEM_CAP:
            await ctx.term.write(
                "\n  `0Sorry. We cannot hold more than 32 thousand gems.`2\n"
            )
            await ctx.term.pause()
            return
        p.gems -= amt
        ctx.store.set(f"gems:{p.id}", stored + amt)
        await ctx.term.write("\n  `2Depositing items...\n")
        await ctx.term.pause()

    async def _withdraw_money(self, ctx: IgmContext) -> None:
        p = ctx.player
        amt = await _ask_amount(
            ctx, "\n  `2How much gold would you like to withdraw? `%", GOLD_MAXLEN
        )
        if amt < 1:
            return
        stored = ctx.store.get(f"gold:{p.id}", 0)
        if amt > stored:
            await ctx.term.write(
                "\n  `2We do not give loans, and you cannot take more than\n"
                "  you put in!\n"
            )
            await ctx.term.pause()
            return
        # Never take out more than actually fits on hand. PlayerView clamps
        # p.gold at GOLD_CAP regardless, so debiting the store by the full
        # amt while only crediting the clamped remainder would silently
        # destroy the difference; keep whatever doesn't fit safely in
        # storage instead (bank.py's own withdraw clamps the request down
        # the same way before applying it).
        actual = min(amt, max(0, GOLD_CAP - p.gold))
        if actual < 1:
            await ctx.term.write(
                "\n  `2You're already carrying all the gold you can hold.\n"
            )
            await ctx.term.pause()
            return
        p.gold += actual
        ctx.store.set(f"gold:{p.id}", stored - actual)
        await ctx.term.write("\n  `2Withdrawing items...\n")
        await ctx.term.pause()

    async def _withdraw_gems(self, ctx: IgmContext) -> None:
        p = ctx.player
        amt = await _ask_amount(
            ctx, "\n  `2How many gems would you like to withdraw? `%", GEM_MAXLEN
        )
        if amt < 1:
            return
        stored = ctx.store.get(f"gems:{p.id}", 0)
        if amt > stored:
            await ctx.term.write(
                "\n  `2We do not give loans, and you cannot take more than\n"
                "  you put in!\n"
            )
            await ctx.term.pause()
            return
        # See _withdraw_money's identical comment: never destroy the
        # overflow, keep it in storage.
        actual = min(amt, max(0, STAT_CAP - p.gems))
        if actual < 1:
            await ctx.term.write(
                "\n  `2You're already carrying all the gems you can hold.\n"
            )
            await ctx.term.pause()
            return
        p.gems += actual
        ctx.store.set(f"gems:{p.id}", stored - actual)
        await ctx.term.write("\n  `2Withdrawing items...\n")
        await ctx.term.pause()

    # -- The Nanny / daycare ---------------------------------------------

    async def _nanny(self, ctx: IgmContext) -> None:
        p = ctx.player
        if ctx.rng.randrange(2) == 0:
            await ctx.term.write(
                "\n  `0Well, hello there!`2, shouts the Nanny.\n"
                "  `0Have you come here to have me watch your children?`2 she\n"
                "  asks.\n"
            )
        else:
            await ctx.term.write(
                "\n  `0You know them children like to get themselves in trouble\n"
                "  when you are out looking for the Dragon.`2, she proclaims.\n"
            )
        while True:
            await ctx.term.write(_NANNY_MENU)
            choice = await ctx.term.menu(
                {"L": "leave", "T": "take", "C": "check", "Q": "quit"},
                f"  `2What would you like to do, `#{p.name}`2? [`0Q`2] : `%",
            )
            if choice == "Q":
                return
            if choice == "L":
                await self._leave_children(ctx)
            elif choice == "T":
                await self._take_children(ctx)
            else:
                await self._check_children(ctx)

    async def _leave_children(self, ctx: IgmContext) -> None:
        p = ctx.player
        amt = await _ask_amount(
            ctx,
            "\n  `2How many children would you like to leave with me? `%",
            KIDS_MAXLEN,
        )
        if amt < 1:
            return
        if amt > p.kids:
            await ctx.term.write(
                "\n  `2You don't `5HAVE `2that many kids!`0, claims the Nanny.\n"
            )
            await ctx.term.pause()
            return
        p.kids -= amt
        stored = ctx.store.get(f"kids:{p.id}", 0)
        ctx.store.set(f"kids:{p.id}", stored + amt)
        await ctx.term.write(
            "\n  `0If you change your mind, I'll be here!`2, says the Nanny.\n"
        )
        await ctx.term.pause()

    async def _take_children(self, ctx: IgmContext) -> None:
        p = ctx.player
        amt = await _ask_amount(
            ctx,
            "\n  `2How many kids would you like to take with you? `%",
            KIDS_MAXLEN,
        )
        if amt < 1:
            return
        stored = ctx.store.get(f"kids:{p.id}", 0)
        if amt > stored:
            await ctx.term.write(
                "\n  `2What are you, a kidnapper? You can't take more kids than\n"
                "  you have!!!\n"
            )
            await ctx.term.pause()
            return
        # See _withdraw_money's identical comment: never destroy the
        # overflow, keep it in daycare.
        actual = min(amt, max(0, STAT_CAP - p.kids))
        if actual < 1:
            await ctx.term.write(
                "\n  `2You can't watch after any more kids than you already\n  have!\n"
            )
            await ctx.term.pause()
            return
        p.kids += actual
        ctx.store.set(f"kids:{p.id}", stored - actual)
        await ctx.term.write("\n  `2Depositing items...\n")
        await ctx.term.pause()

    async def _check_children(self, ctx: IgmContext) -> None:
        p = ctx.player
        stored = ctx.store.get(f"kids:{p.id}", 0)
        if stored == 0:
            await ctx.term.write("\n  `2You don't have any children here.\n")
        elif stored == 1:
            await ctx.term.write("\n  `2You have `%1 `2child here in daycare.\n")
        else:
            await ctx.term.write(f"\n  `2You have `%{stored} `2children in daycare.\n")
        await ctx.term.pause()

    # -- The stables -------------------------------------------------------

    async def _stables(self, ctx: IgmContext) -> None:
        p = ctx.player
        await ctx.term.write(
            "\n  `0You notice the stablemaster on the other side of the\n"
            "  stables, feeding the other horses.  He looks up and asks,\n"
            "  `0What can I do ya for, pardner?`2\n"
        )
        while True:
            await ctx.term.write(_STABLES_MENU)
            choice = await ctx.term.menu(
                {"L": "leave", "T": "take", "C": "check", "Q": "quit"},
                f"  `2What would you like to do, `#{p.name}`2? [`0Q`2] : `%",
            )
            if choice == "Q":
                return
            if choice == "L":
                await self._leave_horse(ctx)
            elif choice == "T":
                await self._take_horse(ctx)
            else:
                await self._check_horse(ctx)

    async def _leave_horse(self, ctx: IgmContext) -> None:
        p = ctx.player
        if not p.horse:
            await ctx.term.write("\n  `2You don't have a horse to leave!\n")
            await ctx.term.pause()
            return
        if ctx.store.get(f"horse:{p.id}", False):
            await ctx.term.write(
                "\n  `2You cannot keep more than one horse here at the same\n  time!\n"
            )
            await ctx.term.pause()
            return
        p.horse = 0
        ctx.store.set(f"horse:{p.id}", True)
        await ctx.term.write(
            "\n  `2You lock your horse up in its own stable, hoping the\n"
            "  stablemaster will remember to feed him.\n"
        )
        await ctx.term.pause()

    async def _take_horse(self, ctx: IgmContext) -> None:
        p = ctx.player
        if p.horse:
            await ctx.term.write("\n  `2You already HAVE your horse!!!\n")
            await ctx.term.pause()
            return
        if not ctx.store.get(f"horse:{p.id}", False):
            await ctx.term.write("\n  `2You do NOT have a horse here.\n")
            await ctx.term.pause()
            return
        p.horse = 1
        ctx.store.set(f"horse:{p.id}", False)
        await ctx.term.write(
            "\n  `2Here is your horse... Please take good care of him.\n"
            "  `0Shur, pardner. I have yer horse right here!`2, says the\n"
            "  stablemaster.\n"
        )
        await ctx.term.pause()

    async def _check_horse(self, ctx: IgmContext) -> None:
        p = ctx.player
        if ctx.store.get(f"horse:{p.id}", False):
            await ctx.term.write(
                "\n  `0Shur, pardner. I have yer horse right here!`2, says the\n"
                "  stablemaster.\n"
            )
        else:
            await ctx.term.write("\n  `2You do NOT have a horse here.\n")
        await ctx.term.pause()

    # -- The townfolk / talk board -----------------------------------------

    async def _townfolk(self, ctx: IgmContext) -> None:
        await ctx.term.write(
            "\n  `2As you make your way through the large crowd before you,\n"
            "  you notice several people shouting.\n"
        )
        while True:
            await ctx.term.write(_TALK_MENU)
            choice = await ctx.term.menu(
                {"T": "listen", "S": "shout", "Q": "quit"},
                "  `2Your choice? [`0Q`2] : `%",
            )
            if choice == "Q":
                return
            if choice == "T":
                await self._listen(ctx)
            else:
                await self._shout(ctx)

    async def _listen(self, ctx: IgmContext) -> None:
        board = ctx.store.get("talk_board", [_SEED_TALK_LINE])
        line = board[ctx.rng.randrange(len(board))] if board else _SEED_TALK_LINE
        await ctx.term.write(
            f"\n  `2You strain to make out what they're saying:\n  `0{line}\n"
        )
        await ctx.term.pause()

    async def _shout(self, ctx: IgmContext) -> None:
        raw = await ctx.term.readline(
            f"\n  `2Shout your message below: (Maximum of {TALK_LINE_MAXLEN} "
            "characters)\n  `0: `%",
            maxlen=TALK_LINE_MAXLEN,
        )
        text = raw.strip()
        if not text:
            return
        await ctx.term.write(f"\n  `0{text}`2\n")
        choice = await ctx.term.menu(
            {"Y": "yes", "N": "no"}, "  `2Is this what you want to say? [`0Y`2] : `%"
        )
        if choice != "Y":
            return
        board = ctx.store.get("talk_board", [_SEED_TALK_LINE])
        entry = f"{ctx.player.name}: {text}"
        new_board = (board + [entry])[-TALK_BOARD_MAX_LINES:]
        ctx.store.set("talk_board", new_board)
        await ctx.term.write("\n  `2Your words join the crowd's noise.\n")
        await ctx.term.pause()

    # -- Maintenance ---------------------------------------------------

    async def daily_maint(self, ctx: IgmMaintContext) -> None:
        """Clears no per-day gate (``WHAT-IS.NEW`` v1.7 -- deposit/withdraw
        are deliberately unlimited per day in this version). Instead
        approximates the recorded "resets...Gold in bank and Gems in bank
        when they win LORD" mechanic (``WHAT-IS.NEW`` v1.6) the only way an
        IGM can: by noticing, once per game-day, that a player's
        ``king_count`` has gone up since the last pass -- see the module
        docstring's storage-exposure analysis for why this is a
        next-maintenance-pass approximation, not an instant reaction to the
        win itself, and why only gold/gems (not kids/horse) are cleared."""
        for player in ctx.repo.all_players():
            key = f"kc:{player.id}"
            last_seen = ctx.store.get(key, player.king_count)
            if player.king_count > last_seen:
                ctx.store.delete(f"gold:{player.id}")
                ctx.store.delete(f"gems:{player.id}")
            ctx.store.set(key, player.king_count)
