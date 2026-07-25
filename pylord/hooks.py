"""Public IGM (In-Game Module) plugin surface.

This is the drop-in replacement for the original LORD's ``3RDPARTY.DAT`` /
``INFO.<node>`` IGM mechanism (reference/lord.js's ``do_igm()`` /
``third_party()`` file-handshake protocol). Where the DOS game shelled out
to a separate ``.EXE`` and exchanged the player's stats through a flat
``INFO`` file, a pylord IGM is just a Python subclass of :class:`IGM`
dropped into an ``igms/<name>/igm.py`` file and toggled on in ``config.toml``.

The engine never hands an IGM the live :class:`~pylord.engine.game.GameCtx`.
It gets an :class:`IgmContext` -- a guardrailed façade that (a) validates
every player-stat write so a buggy or hostile plugin can't corrupt a
character (negative gold, an impossible level, a rewritten name), (b) scopes
persistent storage to the plugin's own key, and (c) buffers news so a plugin
that crashes mid-visit leaves no trace (the whole visit is one DB
transaction -- see ``pylord/engine/scenes/other_places.py``).

Hook methods an IGM may override:

* ``enter(ctx)``     -- required. Runs when a player walks into the IGM from
  the forest's "Other Places" menu.
* ``daily_maint(ctx)`` -- optional. Runs once per game-day during global
  maintenance (:mod:`pylord.engine.daily`).
* ``forest_event(rng)`` -- optional. Returns a :class:`ForestEvent` (or
  ``None``) to inject into the forest's random-event table.
* ``inn_event(rng)`` -- optional. Returns an :class:`InnEvent` (or
  ``None``) to add a numbered key to the Inn's menu.

Every hook runs behind the same sandbox as ``enter`` (one transaction, the
player restored in place if it raises -- see
``pylord/engine/scenes/other_places.py``'s ``run_guarded``).
"""

from __future__ import annotations

import json
from collections import namedtuple
from typing import TYPE_CHECKING, Any

from pylord.engine import limits

if TYPE_CHECKING:
    import random
    
    from pylord.engine.game import GameCtx
    from pylord.models import Player
    from pylord.terminal import TermIO

# A forest random-event contributed by an IGM. ``weight`` is a relative
# selection weight within the collected event pool; ``run`` is an
# ``async (IgmContext) -> None`` coroutine invoked when the event fires.
ForestEvent = namedtuple("ForestEvent", "weight run")

# The Inn's counterpart, offered to the player as an extra key on the Inn
# menu rather than rolled at random: ``label`` is the menu line, ``run`` an
# ``async (IgmContext) -> None``.
InnEvent = namedtuple("InnEvent", "label run")

# A read-only view of another player handed to IGMs via
# ``IgmContext.other_players()``.
PlayerSummary = namedtuple("PlayerSummary", "name level alive class_type")


class IgmViolation(Exception):
    """Raised when an IGM attempts a forbidden player mutation.

    Two kinds of write raise this rather than being silently clamped:
    writing an *immutable* attribute (``id``/``name``/``password_hash`` --
    identity fields an IGM must never rewrite) and writing ``level``
    (levels are earned at Turgon's, never handed out by a plugin -- an IGM
    grants ``exp`` instead, which is clamped/capped like every other stat).

    The "Other Places" visit protocol catches this like any other
    exception: the visit's transaction rolls back and the player is
    restored, so a plugin that trips a violation simply gets bounced back
    to the forest with no lasting effect.
    """


class IGM:
    """Base class for a pylord In-Game Module.

    Subclass this in ``igms/<name>/igm.py``, set ``key``/``name`` (and
    optionally ``author``/``default_enabled``), and override :meth:`enter`.
    The loader (:mod:`pylord.igm_loader`) discovers exactly one ``IGM``
    subclass per module.
    """

    key: str = ""
    name: str = ""
    author: str = ""
    default_enabled: bool = False

    async def enter(self, ctx: IgmContext) -> None:
        """Run the IGM for a visiting player. **Required override.**"""
        raise NotImplementedError

    async def daily_maint(self, ctx: IgmMaintContext) -> None:
        """Optional once-per-game-day hook. Default: no-op."""

    def forest_event(self, rng: random.Random) -> ForestEvent | None:
        """Optional forest random-event contribution. Default: none.

        The returned event's ``weight`` buys it that many slots alongside
        lord.js's own 15 (16 mounted) forest-event cases -- see
        ``pylord/engine/scenes/forest.py``'s ``_forest_event``.
        """
        return None

    def inn_event(self, rng: random.Random) -> InnEvent | None:
        """Optional Inn contribution: an extra numbered key on the Inn's
        menu (``pylord/engine/scenes/inn.py``). Default: none."""
        return None


class PlayerView:
    """Guardrailed proxy over a :class:`~pylord.models.Player`.

    Reads pass straight through. Writes are validated:

    * ``gold`` / ``bank``           -> floored at 0, capped at 2,000,000,000.
    * ``exp``                       -> floored at 0, capped at 2,000,000,000
                                       (same ceiling as ``grant_exp``).
    * ``hp``                        -> clamped to ``[0, hp_max]``.
    * ``hp_max``/``strength``/``defense``/``charm``/``gems``/``lays``/
      ``kids``/``forest_fights``/``player_fights`` -> floored at 0, capped
                                       at 32,000.
    * ``level``                     -> :class:`IgmViolation` (immutable;
                                       leveling happens at Turgon's).
    * ``id`` / ``name`` / ``password_hash`` -> :class:`IgmViolation`
                                       (identity is immutable).

    Every bound above lives in ``pylord/engine/limits.py`` -- the same
    module :func:`pylord.engine.effects.apply_effect` (Task 13a's mail
    "effect" channel) validates against, so a stat can't end up with a
    different validated range depending on which channel wrote it (a
    review finding: this class and ``effects.py`` used to each carry their
    own, independently-drifted copy of these bounds -- see
    ``docs/deviations.md``). See that module's docstring for each bound's
    reasoning/lord.js citation. Any field *not* covered there (``bank``,
    ``weapon_num``, the ``seen_*`` flags, ...) passes through unvalidated:
    IGMs are semi-trusted drop-ins, and the brief scopes validation to the
    stats a corrupt value would most damage.

    ``dirty`` reports whether any successful write has occurred, so the
    visit protocol can skip persisting an untouched player.
    """

    _IMMUTABLE = frozenset({"id", "name", "password_hash"})

    def __init__(self, player: Player) -> None:
        object.__setattr__(self, "_player", player)
        object.__setattr__(self, "_dirty", False)

    @property
    def dirty(self) -> bool:
        return object.__getattribute__(self, "_dirty")

    def __getattr__(self, name: str) -> Any:
        # __getattr__ only fires for names not found normally, so this
        # cleanly forwards player attributes without shadowing _player /
        # _dirty / dirty (which live on the instance / class).
        return getattr(object.__getattribute__(self, "_player"), name)

    def __setattr__(self, name: str, value: Any) -> None:
        player = object.__getattribute__(self, "_player")

        if name in self._IMMUTABLE:
            raise IgmViolation(f"IGMs may not modify player.{name}")
        if name == "level":
            raise IgmViolation(
                "IGMs may not modify player.level -- grant exp instead"
            )

        if name == "hp":
            value = limits.clamp_hp(value, player.hp_max)
        elif name in limits.VALIDATED_FIELDS:
            value = limits.clamp(name, value)

        setattr(player, name, value)
        object.__setattr__(self, "_dirty", True)


class IgmStore:
    """Per-IGM persistent key/value store, namespaced by the IGM's ``key``.

    Values are JSON-serialisable Python objects. The store a plugin sees is
    a **snapshot loaded before the visit begins**, with writes buffered in
    memory -- that is what lets ``get``/``set`` stay synchronous now the
    database is async, and it keeps a crashing plugin from leaving anything
    behind (the visit protocol simply drops the buffer).
    """

    _MISSING = object()

    def __init__(self, igm_key: str, rows: dict[str, str] | None = None) -> None:
        self._key = igm_key
        self._loaded: dict[str, Any] = {
            k: json.loads(v) for k, v in (rows or {}).items()
        }
        self._pending: dict[str, tuple[str, Any]] = {}

    @property
    def igm_key(self) -> str:
        return self._key

    def get(self, k: str, default: Any = None) -> Any:
        if k in self._pending:
            op, val = self._pending[k]
            return default if op == "delete" else val
        return self._loaded.get(k, default)

    def set(self, k: str, v: Any) -> None:
        self._pending[k] = ("set", v)

    def delete(self, k: str) -> None:
        self._pending[k] = ("delete", None)

    async def flush(self, tx: Any) -> None:
        """Apply the buffered writes inside the caller's transaction."""
        for k, (op, val) in self._pending.items():
            if op == "delete":
                await tx.igm_data.delete(self._key, k)
                self._loaded.pop(k, None)
            else:
                await tx.igm_data.set_raw(self._key, k, json.dumps(val))
                self._loaded[k] = val
        self._pending.clear()


class IgmContext:
    """Guardrailed façade an IGM receives in :meth:`IGM.enter`.

    Wraps the session's :class:`~pylord.engine.game.GameCtx` but exposes
    only a safe subset:

    * ``player``  -- a :class:`PlayerView` (validated writes).
    * ``term``    -- the session's :class:`~pylord.terminal.TermIO`.
    * ``store``   -- a per-IGM :class:`IgmStore`.
    * ``rng``     -- the session RNG.
    * ``mail``/``news``/``other_players`` -- helper methods below.

    **Everything here is synchronous**, which is the contract published to
    plugin authors. That works against an async database because a visit
    loads what a plugin can read (its store rows, the roster) before
    ``enter`` is called, and buffers everything it writes until the visit
    ends cleanly -- see ``pylord/engine/scenes/other_places.py``.
    """

    def __init__(
        self,
        gctx: GameCtx,
        igm: IGM,
        store: IgmStore,
        roster: list[PlayerSummary],
    ) -> None:
        self._gctx = gctx
        self._igm = igm
        self.player = PlayerView(gctx.player)
        self.term: TermIO = gctx.io
        self.store = store
        self.rng = gctx.rng
        self._roster = roster
        self._news_buffer: list[str] = []
        self._mail_buffer: list[tuple[str, str | None, dict | None]] = []

    @classmethod
    async def create(cls, gctx: GameCtx, igm: IGM) -> IgmContext:
        """Load the snapshot a synchronous plugin will read from."""
        rows = await gctx.db.igm_data.all_for(igm.key)
        me = gctx.player.id
        roster = [
            PlayerSummary(p.name, p.level, p.alive, p.class_type)
            for p in await gctx.db.players.all_players()
            if p.id != me
        ]
        return cls(gctx, igm, IgmStore(igm.key, rows), roster)

    def news(self, text: str) -> None:
        """Buffer a line for today's news; flushed on a clean visit exit."""
        self._news_buffer.append(text)

    def mail(
        self, to_name: str, text: str | None = None, effect: dict | None = None
    ) -> None:
        """Send in-game mail to ``to_name`` from this IGM.

        Buffered like everything else: a plugin that crashes afterwards
        sends nothing. An unknown recipient still raises immediately, so
        the mistake surfaces in the plugin rather than silently at flush.
        """
        known = {p.name.lower() for p in self._roster}
        known.add(self._gctx.player.name.lower())
        if to_name.lower() not in known:
            raise ValueError(f"no such player to mail: {to_name!r}")
        self._mail_buffer.append((to_name, text, effect))

    def other_players(self) -> list[PlayerSummary]:
        """Read-only summaries of every *other* player (self excluded)."""
        return list(self._roster)

    # -- internal: called by the visit protocol on a clean exit ---------

    async def flush(self, tx: Any) -> None:
        """Land the store, news and mail this visit produced."""
        await self.store.flush(tx)

        if self._news_buffer:
            day = await tx.state.get("day", "1")
            for text in self._news_buffer:
                await tx.news.add(day, text)
            self._news_buffer.clear()

        for to_name, text, effect in self._mail_buffer:
            recipient = await tx.players.get_by_name(to_name)
            if recipient is not None:
                await tx.mail.send(
                    recipient.id, self._igm.name, text=text, effect=effect
                )
        self._mail_buffer.clear()


class StateView:
    """A read-only snapshot of the realm's ``game_state`` rows.

    Loaded before a hook runs so an IGM can read realm-wide state -- the
    game day, who Violet and Seth Able are married to -- without awaiting
    and without a handle on the database. Writes are not offered: shared
    realm state belongs to the engine, not to a plugin.
    """

    def __init__(self, rows: dict[str, str]) -> None:
        self._rows = dict(rows)

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._rows.get(key, default)

    def get_int(self, key: str, default: int) -> int:
        try:
            return int(self._rows[key])
        except (KeyError, TypeError, ValueError):
            return default


class IgmMaintContext:
    """Context handed to :meth:`IGM.daily_maint` during global maintenance.

    Simpler than :class:`IgmContext` -- there's no visiting player to
    guard -- and synchronous for the same reason: the roster, this IGM's
    rows and the realm's ``game_state`` are loaded before the hook runs,
    and its writes are buffered until the maintenance pass commits them.
    """

    def __init__(
        self,
        igm_key: str,
        config: dict[str, Any],
        store: IgmStore,
        players: list[Player],
        state: StateView | None = None,
    ) -> None:
        self.config = config
        self.store = store
        self.state = state if state is not None else StateView({})
        self._players = players
        self.repo = _MaintRoster(players)

    @classmethod
    async def create(
        cls, db: Any, config: dict[str, Any], igm_key: str
    ) -> IgmMaintContext:
        rows = await db.igm_data.all_for(igm_key)
        players = await db.players.all_players()
        state = StateView(await db.state.all_rows())
        return cls(igm_key, config, IgmStore(igm_key, rows), players, state)

    async def flush(self, tx: Any) -> None:
        await self.store.flush(tx)
        for player in self.repo.dirty:
            await tx.players.save(player)
        self.repo.dirty.clear()


class _MaintRoster:
    """The roster a ``daily_maint`` hook sees: every player, loaded up
    front, with saves buffered so the hook can stay synchronous."""

    def __init__(self, players: list[Player]) -> None:
        self._players = players
        self.dirty: list[Player] = []

    def all_players(self) -> list[Player]:
        return list(self._players)

    def get_by_name(self, name: str) -> Player | None:
        return next(
            (p for p in self._players if p.name.lower() == name.lower()), None
        )

    def get(self, player_id: int) -> Player | None:
        return next((p for p in self._players if p.id == player_id), None)

    def save(self, player: Player) -> None:
        if player not in self.dirty:
            self.dirty.append(player)
