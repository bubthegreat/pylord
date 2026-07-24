"""LORD Gambling Casino, by Tobin Fricke (Task 20).

Like the rest of the starter six, the original IGM's binary/source is
lost -- no surviving screen transcript exists to port line-for-line, and
``reference/lord.js`` never modeled any IGM's internals (they were always
separate ``.EXE`` files reached through the ``3RDPARTY.DAT`` handshake).
This is a **from-brief recreation** of Blackjack, Slots, and Roulette.

**Reconstruction notes (invented filler):**

* **Blackjack.** A real single 52-card deck (``_new_deck()``, no jokers)
  is shuffled fresh every hand via ``ctx.rng.shuffle`` per the brief.
  Dealing order (player, dealer, player, dealer) is the standard real-world
  convention, invented here since no transcript specifies it. Dealer plays
  standard American casino rules: hits on any total below 17, **stands on
  17 including a soft 17** (an ace counted as 11) per the brief's explicit
  "soft-17 stands" instruction -- there's no extra hit-on-soft-17 branch.
  A natural (ace + ten-value card in the first two cards) pays 3:2,
  floor-divided (``bet + bet * 3 // 2``: e.g. a 10-gold bet returns 25
  total, a 15-gold profit; a 3-gold bet returns 3 + 4 = 7 total, a floored
  4-gold profit) per the brief. Both player and dealer natural is a push
  (bet returned, no profit) -- the brief doesn't say, but "the house never
  grants free gold" (this project's economy guard, shared with Sandtiger's
  Bar/the Warrior's Graveyard) rules out treating a double-natural as a
  player win. A player/dealer tie after both stand is likewise a push.
* **Slots.** Symbols and their odds are uniform per-reel
  (``ctx.rng.choice`` over the five symbols, independently per reel) --
  the brief says "uniform rng" but doesn't specify per-reel vs. weighted;
  uniform-per-reel is the simplest reading and the standard slot-machine
  shape. The paytable is taken verbatim from the brief (3x Seven 10x, 3x
  Bell 5x, 3x Bar 4x, 3x Cherry 3x, any-2-matching 1x/push). **Notable
  invented consequence, not a bug:** the brief's paytable has no 3-of-a-
  kind tier for Lemon -- three Lemons still satisfy "any 2 matching"
  (three-of-a-kind trivially contains a matching pair), so it resolves as
  a push rather than a loss *or* a jackpot. Documented rather than silently
  "fixed" by inventing a Lemon jackpot tier the brief never asked for.
* **Roulette.** Modeled as an American-style 38-pocket wheel (0 through
  37, where "37" stands in for the American wheel's "00") per the brief's
  own "0-37" number range and "18/38" red/black odds -- both only add up
  on a 38-pocket wheel, not the 37-pocket European single-zero wheel. The
  18 "red" numbers (``_RED_NUMBERS``) are the real standard American
  roulette red set; 0 and 37 ("00") are green/house numbers that lose
  every color bet, matching the real wheel and the brief's 18/38 (not
  18/37) odds. A number bet pays the brief's literal "35x" as a **total
  return** multiplier (``bet * 35``, i.e. 34x profit) for consistency with
  how every other payout in this IGM/Sandtiger's Bar expresses "Nx" as a
  total-return multiplier, not a profit-only one.

**Economy guard**, same convention as Sandtiger's Bar: every bet is
validated ``0 < bet <= gold on hand`` *and* ``bet <= player.level * 1000``
before any random outcome is rolled -- the house never grants free gold,
and a bet failing either check is refused with no partial deduction.
"""

from __future__ import annotations

from pylord.hooks import IGM, IgmContext

_MENU = (
    "\n  `5LORD Gambling Casino   `8(? for menu)\n"
    "  `2(`0B`2)lackjack   (`0S`2)lots   (`0R`2)oulette   (`0L`2)eave\n"
)

_DIGITS = "0123456789"

_RANKS = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
_SUITS = ("S", "H", "D", "C")

_SLOT_SYMBOLS = ("Cherry", "Lemon", "Bell", "Bar", "Seven")
_SLOT_PAYTABLE = {"Seven": 10, "Bell": 5, "Bar": 4, "Cherry": 3}

_ROULETTE_POCKETS = 38  # 0-37, "37" standing in for American "00"
_RED_NUMBERS = frozenset(
    {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
)
_NUMBER_BET_PAYOUT = 35
_COLOR_BET_PAYOUT = 2


def _new_deck() -> list[tuple[str, str]]:
    return [(r, s) for r in _RANKS for s in _SUITS]


def _card_value(rank: str) -> int:
    if rank == "A":
        return 11
    if rank in ("J", "Q", "K"):
        return 10
    return int(rank)


def _hand_value(cards: list[tuple[str, str]]) -> int:
    total = sum(_card_value(r) for r, _ in cards)
    aces = sum(1 for r, _ in cards if r == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def _is_natural(cards: list[tuple[str, str]]) -> bool:
    return len(cards) == 2 and _hand_value(cards) == 21


def _fmt_card(card: tuple[str, str]) -> str:
    return f"{card[0]}{card[1]}"


def _fmt_hand(cards: list[tuple[str, str]]) -> str:
    return " ".join(_fmt_card(c) for c in cards)


class LordCasino(IGM):
    key = "lord_casino"
    name = "LORD Gambling Casino"
    author = "Tobin Fricke"
    default_enabled = True

    async def enter(self, ctx: IgmContext) -> None:
        while True:
            await ctx.term.write(_MENU)
            choice = await ctx.term.menu(
                {"B": "blackjack", "S": "slots", "R": "roulette", "L": "leave"},
                "  `2Your choice? : ",
            )
            if choice == "L":
                await ctx.term.write(
                    "\n  `2The pit boss nods as you cash out and head for the door.\n"
                )
                return
            if choice == "B":
                await self._blackjack(ctx)
            elif choice == "S":
                await self._slots(ctx)
            elif choice == "R":
                await self._roulette(ctx)

    async def _prompt_bet(self, ctx: IgmContext) -> int | None:
        p = ctx.player
        max_bet = p.level * 1000
        await ctx.term.write(
            f"\n  `2You have `0{p.gold} `2gold on hand.  (Max bet: `0{max_bet}`2)\n"
        )
        raw = await ctx.term.readline(
            "  `0How much gold will you wager? : ", maxlen=10, charset=_DIGITS
        )
        bet = int(raw) if raw else 0
        if bet <= 0:
            await ctx.term.write("\n  `2You decide not to bet after all.\n")
            return None
        if bet > p.gold:
            await ctx.term.write("\n  `4You don't have that much gold on you!\n")
            return None
        if bet > max_bet:
            await ctx.term.write(
                f"\n  `4The pit boss refuses a bet over `0{max_bet} `4gold!\n"
            )
            return None
        return bet

    async def _blackjack(self, ctx: IgmContext) -> None:
        p = ctx.player
        bet = await self._prompt_bet(ctx)
        if bet is None:
            return
        p.gold -= bet

        deck = _new_deck()
        ctx.rng.shuffle(deck)
        player_cards = [deck.pop(0)]
        dealer_cards = [deck.pop(0)]
        player_cards.append(deck.pop(0))
        dealer_cards.append(deck.pop(0))

        await ctx.term.write(
            f"\n  `2Your hand: `0{_fmt_hand(player_cards)} "
            f"(`2{_hand_value(player_cards)}`0)\n"
        )

        player_natural = _is_natural(player_cards)
        dealer_natural = _is_natural(dealer_cards)
        if player_natural or dealer_natural:
            await ctx.term.write(
                f"  `2Dealer's hand: `0{_fmt_hand(dealer_cards)} "
                f"(`2{_hand_value(dealer_cards)}`0)\n"
            )
            if player_natural and dealer_natural:
                p.gold += bet
                await ctx.term.write(
                    "\n  `2Both blackjack!  Push -- your bet is returned.\n"
                )
            elif player_natural:
                payout = bet + bet * 3 // 2
                p.gold += payout
                await ctx.term.write(
                    f"\n  `0BLACKJACK!  YOU WIN {payout - bet} GOLD! (3:2 payout)\n"
                )
            else:
                await ctx.term.write("\n  `4Dealer has blackjack.  YOU LOSE.\n")
            await ctx.term.pause()
            return

        await ctx.term.write(f"  `2Dealer shows: `0{_fmt_card(dealer_cards[0])}\n")
        while _hand_value(player_cards) <= 21:
            action = await ctx.term.menu(
                {"H": "hit", "S": "stand"},
                f"\n  `2Your hand: `0{_fmt_hand(player_cards)} "
                f"(`2{_hand_value(player_cards)}`0)  "
                "`2(`0H`2)it or (`0S`2)tand? : ",
            )
            if action == "S":
                break
            player_cards.append(deck.pop(0))

        player_value = _hand_value(player_cards)
        if player_value > 21:
            await ctx.term.write(
                f"\n  `4You bust with `0{_fmt_hand(player_cards)}`4!  "
                f"YOU LOSE {bet} GOLD.\n"
            )
            await ctx.term.pause()
            return

        while _hand_value(dealer_cards) < 17:
            dealer_cards.append(deck.pop(0))
        dealer_value = _hand_value(dealer_cards)
        await ctx.term.write(
            f"\n  `2Dealer's hand: `0{_fmt_hand(dealer_cards)} (`2{dealer_value}`0)\n"
        )

        if dealer_value > 21 or player_value > dealer_value:
            p.gold += bet * 2
            await ctx.term.write(f"  `0YOU WIN {bet} GOLD!\n")
        elif player_value == dealer_value:
            p.gold += bet
            await ctx.term.write("  `2Push -- your bet is returned.\n")
        else:
            await ctx.term.write(f"  `4YOU LOSE {bet} GOLD.\n")
        await ctx.term.pause()

    async def _slots(self, ctx: IgmContext) -> None:
        p = ctx.player
        bet = await self._prompt_bet(ctx)
        if bet is None:
            return
        reels = [ctx.rng.choice(_SLOT_SYMBOLS) for _ in range(3)]
        p.gold -= bet
        await ctx.term.write(f"\n  `2[ {reels[0]} | {reels[1]} | {reels[2]} ]\n")

        if reels[0] == reels[1] == reels[2] and reels[0] in _SLOT_PAYTABLE:
            mult = _SLOT_PAYTABLE[reels[0]]
            payout = bet * mult
            p.gold += payout
            await ctx.term.write(
                f"  `0JACKPOT!  Triple {reels[0]}s -- YOU WIN "
                f"{payout - bet} GOLD! ({mult}x)\n"
            )
        elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
            p.gold += bet
            await ctx.term.write("  `2Two match -- your bet is returned.\n")
        else:
            await ctx.term.write(f"  `4No match.  YOU LOSE {bet} GOLD.\n")
        await ctx.term.pause()

    async def _roulette(self, ctx: IgmContext) -> None:
        bet = await self._prompt_bet(ctx)
        if bet is None:
            return
        kind = await ctx.term.menu(
            {"C": "color", "N": "number"},
            "\n  `2Bet on a (`0C`2)olor or a (`0N`2)umber? : ",
        )
        if kind == "C":
            await self._roulette_color(ctx, bet)
        else:
            await self._roulette_number(ctx, bet)

    async def _roulette_color(self, ctx: IgmContext, bet: int) -> None:
        p = ctx.player
        color = await ctx.term.menu(
            {"R": "red", "B": "black"}, "  `2(`0R`2)ed or (`0B`2)lack? : "
        )
        p.gold -= bet
        spin = ctx.rng.randrange(_ROULETTE_POCKETS)
        spin_color = "R" if spin in _RED_NUMBERS else "B" if 1 <= spin <= 36 else None
        await ctx.term.write(f"\n  `2The wheel stops on `0{spin}`2!\n")
        if spin_color == color:
            payout = bet * _COLOR_BET_PAYOUT
            p.gold += payout
            await ctx.term.write(f"  `0YOU WIN {payout - bet} GOLD!\n")
        else:
            await ctx.term.write(f"  `4YOU LOSE {bet} GOLD.\n")
        await ctx.term.pause()

    async def _roulette_number(self, ctx: IgmContext, bet: int) -> None:
        p = ctx.player
        raw = await ctx.term.readline(
            "  `2Pick a number (0-37) : ", maxlen=2, charset=_DIGITS
        )
        number = int(raw) if raw and raw.isdigit() else -1
        if not (0 <= number <= 37):
            await ctx.term.write("\n  `2Not a valid number -- no bet placed.\n")
            await ctx.term.pause()
            return
        p.gold -= bet
        spin = ctx.rng.randrange(_ROULETTE_POCKETS)
        await ctx.term.write(f"\n  `2The wheel stops on `0{spin}`2!\n")
        if spin == number:
            payout = bet * _NUMBER_BET_PAYOUT
            p.gold += payout
            await ctx.term.write(f"  `0YOU WIN {payout - bet} GOLD!\n")
        else:
            await ctx.term.write(f"  `4YOU LOSE {bet} GOLD.\n")
        await ctx.term.pause()
