"""WereWolf -- transform, hunt, feed. Original by Jay Hodges, BackAlley
Software (Task 3: first documented-recreation port, ``igms_to_port/ww301.zip``).

**Provenance tier: documented recreation.** Unlike Barak's House (Turbo
Pascal source recovered, ``docs/deviations.md``'s "Barak's House vs.
BARAK.PAS" section) this port has no source -- ``WEREWOLF.EXE`` is a
compiled DOS binary and stays one. But unlike the from-brief recreations
(Sandtiger's Bar, the LORD Gambling Casino, ...), real archive documentation
does survive and is quoted below verbatim. Everything quoted is **recorded**;
everything else in this module is **invented**, flagged as such, and chosen
to be the smallest addition that makes the recorded mechanic playable.

Sources read (Task 3 brief Step 1): ``ww301.zip`` (v3.01, this port's
target) -- ``WEREWOLF.DOC``, ``FILE_ID.DIZ``, ``DOORQUES.DOC``,
``REGISTER.FRM``, ``WINSTALL.DOC``, ``LORD.IGM``; and ``ww101.zip`` (v1.01,
an earlier surviving version whose own docs were checked for numbers the
later version's docs assume) -- ``FILE_ID.DIZ``, ``INSTALL.DOC``,
``WWFAIL.BAT``, ``LORD.IGM``. No mechanic-relevant number in ww101 turned
out to differ from or add to what ww301 already records.

**Recorded, verbatim (``WEREWOLF.DOC``, ww301.zip):**

* "WereWolf is an IGM that gives the user a maximum of 10% of their total
  experience for each thing they do." -- the per-action exp reward is
  capped at 10% of the player's *current* exp.
* "They can attack players in werewolf form in the forest, the inn, and
  then desecrate the dead bodies!" -- attack lives in two flavors (forest /
  Inn), and a kill can be followed up with a desecration.
* "Eat kids, kill horses, all around wicked good fun!" -- two more actions.
* "Most choices cost 2 Forest + 2 Human." -- most (not all) menu choices
  spend 2 of the player's forest-fight allowance and 2 of their player-fight
  allowance (this project's ``forest_fights``/``player_fights`` fields --
  the only two "fight" resources ``Player`` has, and the natural reading of
  "Forest"/"Human" fights in LORD's own vocabulary).
* "Players can get killed." -- attacking was not a safe action in the
  original.
* Version history (``WEREWOLF.DOC``): v1.00 "Added horse and kid eating";
  v2.00 "Fixes for LORD v3.52. Less Reward. More Cost. Get Killed."
  (death risk was tightened in, not present from the start); v3.00 "Faster
  Data File Access. SysOp Config expanded."; v3.01 "Fixed Status Line."
* ``FILE_ID.DIZ`` (ww301): "Transform into a werewolf to kill other players
  and desecrate their dead bodies, eat kids, kill horses! More SysOp
  configurable!" -- ww101's own ``FILE_ID.DIZ`` carries the identical first
  four lines *without* the "More SysOp configurable!" clause, confirming
  that clause (and the config-file install step ``WINSTALL.DOC`` describes)
  is new/expanded in v3.01, not a paraphrase.

Nowhere in either archive is there a menu layout, a key binding, an exp/gold
number, an odds table, a transformation cost, or a single sysop-config
knob's name or default -- only the mechanics list, the "10% max" and "2+2"
figures, and the fact that death and sysop-configurability exist. Everything
below fills that gap.

**Invented (and why):**

* **Menu keys/labels/flavor text** -- no transcript survives; laid out as
  (F)orest / (I)nn attack, (D)esecrate, (K)ill a horse, (E)at a kid, (L)eave.
* **Forest vs. Inn attack are mechanically identical**, differing only in
  flavor text. The doc names both locations but gives no location-specific
  rule, and ``IgmContext.other_players()`` exposes no "asleep at the Inn"
  flag (``PlayerSummary`` is ``name, level, alive, class_type`` only) to
  gate an Inn-specific eligibility check against, unlike the real Inn
  bribe-attack's ``at_inn`` gate (``pylord/engine/scenes/pvp.py``).
* **Reward formula**: ``randint(1, max(1, exp // 10))`` -- the doc states a
  *maximum* ("a maximum of 10%"), not a formula, so a roll up to that cap
  was chosen over a flat 10% grant. The ``max(1, ...)`` floor is invented
  because a strict 10%-of-current-exp cap is 0 for a freshly rolled
  character (``Player.exp`` defaults to 1, see ``pylord/models.py``),
  which would make the whole IGM a permanent no-op at the level every
  player starts at.
* **Cost application**: "most choices" (not all) cost 2 forest_fights + 2
  player_fights -- applied to Forest attack, Inn attack, Kill a horse and
  Eat a kid. Desecrate is the one recorded exception: it is a bonus
  follow-up to a kill already paid for, not a fresh "choice", so it costs
  nothing further -- this reading is what "most" (rather than "all")
  choices requires there to be room for.
* **"Kill other players" / "Players can get killed", structurally
  reinterpreted.** ``IgmContext`` gives an IGM only a read-only
  :class:`~pylord.hooks.PlayerSummary` for every other player (name, level,
  alive, class_type -- no hp/strength/defense to run a real fight against),
  and can only affect a remote player asynchronously through
  :meth:`~pylord.hooks.IgmContext.mail`'s ``effect`` dict, whose supported
  keys (``pylord/engine/effects.py``) do not include ``hp`` or ``alive`` --
  there is no channel through which any IGM can mark another player's row
  dead. This project already has an established answer for exactly this
  boundary (``igms/warriors_graveyard/igm.py``'s documented "no-kill
  guard": real death/scoring is the Forest's -- and only the Forest's --
  job); this port extends the same boundary to PvP. Concretely: a
  successful attack here never touches ``alive``, ``hp`` (of the target),
  or ``pvp_kills`` (``pylord/engine/scenes/pvp.py``'s real attack path owns
  that stat exclusively) -- it drains a slice of the victim's ``exp`` via a
  mailed effect and leaves a flavor-only "you have a body to desecrate"
  marker for the attacker. A failed attack floors the *attacker's own* hp
  at 1 rather than letting it reach 0, the same floor
  ``warriors_graveyard`` uses for its own no-kill guard. This is the single
  largest invented adaptation in this port, and it is a direct,
  unavoidable consequence of the guardrail architecture (see
  ``pylord/hooks.py``'s module docstring), not a reading of the docs.
* **Victim exp drain is level-scaled** (``target.level *
  VICTIM_EXP_DRAIN_PER_LEVEL``), unlike the attacker's own
  current-exp-percentage reward -- because ``PlayerSummary`` never exposes
  the victim's live ``exp``, ``level`` is the only numeric signal available
  to scale a remote mail effect against.
* **Attack win roll** (``rng.randrange(attacker.level + ATTACK_EDGE)`` vs.
  ``rng.randrange(target.level)``) -- no odds survive; mirrors the same
  "randrange vs. randrange, one side gets a fixed edge" shape already
  established by ``igms/old_skull_inn/igm.py``'s arm wrestle, with the
  werewolf form itself supplying the edge over an unaware human target.
* **Failed-attack hp damage** (a random fraction of the attacker's own
  ``hp_max``) -- no numbers recorded.
* **Eat a kid / Kill a horse are flavor-only, untargeted actions** -- no
  specific victim, and no interaction with any player's own ``kids``/
  ``horse`` fields (both already carry unrelated meaning elsewhere in this
  project: a player's own children and their own mount). The doc names the
  acts but not a target or a mechanical effect beyond the shared
  10%-cap/2+2-cost formula that applies to "most choices"; reaching into
  another player's row for either would be a bigger invention than the
  docs support.
* **Desecrate window**: a per-attacker ``corpse:<id>`` store flag, set on a
  successful kill and cleared at day's end by :meth:`daily_maint` if never
  used -- the doc only says desecration follows a kill, not how long the
  opportunity lasts.
* **Not ported: sysop configuration.** v3.00's "SysOp Config expanded" and
  ww301's ``FILE_ID.DIZ`` "More SysOp configurable!" both confirm a config
  surface existed, but neither archive records a single knob's name or
  default anywhere. Per this project's convention (an IGM's only config
  surface is its ``config.toml``/``deploy/values`` enable toggle), every
  number in this module is a pylord-side hardcoded default rather than a
  sysop setting.
* **Not ported: transformation as a separate costed action.** Entering the
  IGM already narrates becoming a werewolf, the same convention every
  "Other Places" IGM's entry flavor text follows; no cost is recorded for
  transforming itself, only for "choices" made afterward.
"""

from __future__ import annotations

from pylord.hooks import IGM, IgmContext, IgmMaintContext

_MENU = (
    "\n  `5WereWolf`2\n"
    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
    "  `2(`0F`2)orest prowl -- hunt a warrior in the woods\n"
    "  `2(`0I`2)nn stalk    -- hunt a warrior at the Inn\n"
    "  `2(`0D`2)esecrate a body you left behind\n"
    "  `2(`0K`2)ill a horse\n"
    "  `2(`0E`2)at a kid\n"
    "  `2(`0L`2)eave\n"
)

_NAME_MAXLEN = 20

# "Most choices cost 2 Forest + 2 Human." (WEREWOLF.DOC) -- Desecrate is the
# recorded exception; see the module docstring.
FOREST_FIGHTS_COST = 2
PLAYER_FIGHTS_COST = 2

# "a maximum of 10% of their total experience for each thing they do."
MAX_EXP_REWARD_PCT = 0.10
MIN_EXP_REWARD = 1  # invented floor -- see module docstring

# Invented -- no odds recorded. The werewolf form's edge over an unaware
# human target, mirrored on old_skull_inn's arm-wrestle shape.
ATTACK_EDGE = 3
# Invented -- no numbers recorded for a failed attack's cost.
FAIL_HP_DAMAGE_MIN_DIV = 5  # hp_max // 5
FAIL_HP_DAMAGE_MAX_DIV = 3  # hp_max // 3
# Invented -- PlayerSummary exposes no live exp for a remote target, so the
# victim's drain scales off the one number that is available: level.
VICTIM_EXP_DRAIN_PER_LEVEL = 10


def _exp_reward_cap(exp: int) -> int:
    return max(MIN_EXP_REWARD, int(exp * MAX_EXP_REWARD_PCT))


class WereWolf(IGM):
    key = "werewolf"
    name = "WereWolf"
    author = "Jay Hodges"
    default_enabled = True

    async def enter(self, ctx: IgmContext) -> None:
        await ctx.term.write(
            "\n  `2The moon is fat and yellow tonight, and something under your\n"
            "  skin answers it.  Fur, claws, a hunger with no bottom --\n"
            "  `%YOU ARE THE WEREWOLF.`2\n"
        )
        while True:
            await ctx.term.write(_MENU)
            choice = await ctx.term.menu(
                {
                    "F": "forest",
                    "I": "inn",
                    "D": "desecrate",
                    "K": "horse",
                    "E": "kid",
                    "L": "leave",
                },
                "  `2Your choice? [`0L`2] : `%",
            )
            if choice == "L":
                await ctx.term.write(
                    "\n  `2The hunger fades.  Your skin is your own again, for now.\n"
                )
                return
            if choice == "F":
                await self._attack(ctx, "the forest")
            elif choice == "I":
                await self._attack(ctx, "the Inn")
            elif choice == "D":
                await self._desecrate(ctx)
            elif choice == "K":
                await self._kill_horse(ctx)
            else:
                await self._eat_kid(ctx)

    def _has_fight_budget(self, p) -> bool:
        return p.forest_fights >= FOREST_FIGHTS_COST and p.player_fights >= PLAYER_FIGHTS_COST

    async def _refuse_no_budget(self, ctx: IgmContext) -> None:
        await ctx.term.write(
            "\n  `2You are too spent to hunt again tonight -- your legs and your\n"
            "  nerve have both run out.\n"
        )
        await ctx.term.pause()

    async def _spend_budget(self, ctx: IgmContext) -> None:
        p = ctx.player
        p.forest_fights -= FOREST_FIGHTS_COST
        p.player_fights -= PLAYER_FIGHTS_COST

    async def _grant_reward(self, ctx: IgmContext) -> int:
        p = ctx.player
        reward = ctx.rng.randint(MIN_EXP_REWARD, _exp_reward_cap(p.exp))
        p.exp += reward
        return reward

    async def _attack(self, ctx: IgmContext, location_label: str) -> None:
        p = ctx.player
        if not self._has_fight_budget(p):
            await self._refuse_no_budget(ctx)
            return

        others = ctx.other_players()
        if not others:
            await ctx.term.write(
                "\n  `2You prowl, but there is no one else out here tonight.\n"
            )
            await ctx.term.pause()
            return

        raw = (
            await ctx.term.readline(f"\n  `2Hunt who in {location_label}? : `%", maxlen=_NAME_MAXLEN)
        ).strip()
        if not raw:
            await ctx.term.write("\n  `2You lose the scent.\n")
            await ctx.term.pause()
            return

        by_name = {o.name.lower(): o for o in others}
        target = by_name.get(raw.lower())
        if target is None:
            await ctx.term.write(f"\n  `2No warrior named `0{raw} `2is out here.\n")
            await ctx.term.pause()
            return
        if not target.alive:
            await ctx.term.write(
                f"\n  `2{target.name} `2is already a rotting corpse -- too late to hunt.\n"
            )
            await ctx.term.pause()
            return

        await self._spend_budget(ctx)

        mine = ctx.rng.randrange(max(1, p.level + ATTACK_EDGE))
        his = ctx.rng.randrange(max(1, target.level))
        if mine >= his:
            reward = await self._grant_reward(ctx)
            drain = target.level * VICTIM_EXP_DRAIN_PER_LEVEL
            ctx.mail(
                target.name,
                text=(
                    "  `%YOU HAVE BEEN ATTACKED!\n"
                    "`0-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n"
                    "  `0Something with too many teeth found you in the dark and left you\n"
                    "  for dead.\n"
                    f"  `4YOU LOSE {drain} EXPERIENCE!\n"
                ),
                effect={"exp": -drain},
            )
            ctx.store.set(f"corpse:{p.id}", target.name)
            await ctx.term.write(
                f"\n  `2You bring `0{target.name} `2down in {location_label} and leave the\n"
                "  body behind.\n"
                f"  `0YOU RECEIVE {reward} EXPERIENCE!\n"
            )
        else:
            hp_max = max(1, p.hp_max)
            dmg = ctx.rng.randint(
                max(1, hp_max // FAIL_HP_DAMAGE_MIN_DIV),
                max(1, hp_max // FAIL_HP_DAMAGE_MAX_DIV),
            )
            p.hp = max(1, p.hp - dmg)
            await ctx.term.write(
                f"\n  `4{target.name} `4fights back harder than you expected -- you barely\n"
                "  stagger away.\n"
            )
        await ctx.term.pause()

    async def _desecrate(self, ctx: IgmContext) -> None:
        p = ctx.player
        gate = f"corpse:{p.id}"
        victim_name = ctx.store.get(gate, None)
        if victim_name is None:
            await ctx.term.write(
                "\n  `2There is no body left behind for you to desecrate.\n"
            )
            await ctx.term.pause()
            return
        ctx.store.delete(gate)
        reward = await self._grant_reward(ctx)
        await ctx.term.write(
            f"\n  `2You desecrate {victim_name}'s corpse.  Wicked good fun.\n"
            f"  `0YOU RECEIVE {reward} EXPERIENCE!\n"
        )
        await ctx.term.pause()

    async def _kill_horse(self, ctx: IgmContext) -> None:
        p = ctx.player
        if not self._has_fight_budget(p):
            await self._refuse_no_budget(ctx)
            return
        await self._spend_budget(ctx)
        reward = await self._grant_reward(ctx)
        await ctx.term.write(
            "\n  `2You run down a horse in a moonlit pasture and tear it apart.\n"
            f"  `0YOU RECEIVE {reward} EXPERIENCE!\n"
        )
        await ctx.term.pause()

    async def _eat_kid(self, ctx: IgmContext) -> None:
        p = ctx.player
        if not self._has_fight_budget(p):
            await self._refuse_no_budget(ctx)
            return
        await self._spend_budget(ctx)
        reward = await self._grant_reward(ctx)
        await ctx.term.write(
            "\n  `2You catch a stray child out past curfew.  Wicked good fun.\n"
            f"  `0YOU RECEIVE {reward} EXPERIENCE!\n"
        )
        await ctx.term.pause()

    async def daily_maint(self, ctx: IgmMaintContext) -> None:
        for player in ctx.repo.all_players():
            ctx.store.delete(f"corpse:{player.id}")
