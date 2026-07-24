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

TODO(Task 13): an ``inn_event(rng)`` hook (mirroring ``forest_event``) lands
with the Inn scene; not part of this task's surface.
"""

from __future__ import annotations

import json
from collections import namedtuple
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import random
    import sqlite3

    from pylord.engine.game import GameCtx
    from pylord.models import Player
    from pylord.terminal import TermIO

# A forest random-event contributed by an IGM. ``weight`` is a relative
# selection weight within the collected event pool; ``run`` is an
# ``async (IgmContext) -> None`` coroutine invoked when the event fires.
ForestEvent = namedtuple("ForestEvent", "weight run")

# A read-only view of another player handed to IGMs via
# ``IgmContext.other_players()``.
PlayerSummary = namedtuple("PlayerSummary", "name level alive class_type")

# lord.js caps exp at 2,000,000,000 everywhere it's credited
# (reference/lord.js:15108-15110); IgmContext applies the same ceiling to
# any exp an IGM grants, matching ``pylord.engine.game.grant_exp``.
_EXP_CAP = 2_000_000_000


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
        """Optional forest random-event contribution. Default: none."""
        return None


class PlayerView:
    """Guardrailed proxy over a :class:`~pylord.models.Player`.

    Reads pass straight through. Writes are validated:

    * ``gold`` / ``gems``           -> floored at 0.
    * ``exp``                       -> floored at 0, capped at 2,000,000,000
                                       (same ceiling as ``grant_exp``).
    * ``hp``                        -> clamped to ``[0, hp_max]``.
    * ``hp_max``                    -> floored at 1.
    * ``strength``/``defense``/``charm`` -> floored at 1.
    * ``level``                     -> :class:`IgmViolation` (immutable;
                                       leveling happens at Turgon's).
    * ``id`` / ``name`` / ``password_hash`` -> :class:`IgmViolation`
                                       (identity is immutable).

    **Chosen floors, and why.** lord.js never stores these below the values
    a brand-new warrior starts with, and this project's ``Player`` model
    encodes those newborn minimums as its field defaults
    (``strength=10``, ``defense=1``, ``charm=2``, ``hp_max=20`` --
    ``pylord/models.py``). No lower bound is discoverable in
    ``reference/lord.js`` beyond "a live warrior always has a positive
    combat stat", so the floors here are the conservative, documented
    choice of **1** for every combat stat (``strength``/``defense``/
    ``charm``/``hp_max``) -- the smallest value that keeps a character
    functional (a 0-strength or 0-hp_max player can neither fight nor be
    healed) -- and **0** for the spendable resources (``gold``/``gems``/
    ``exp``), matching lord.js's own "gold on hand lost -> 0" flooring in
    combat death (reference/lord.js:15071). Any field *not* listed above
    (``bank``, ``forest_fights``, ``weapon_num``, the ``seen_*`` flags,
    ...) passes through unvalidated: IGMs are semi-trusted drop-ins, and
    the brief scopes validation to the stats a corrupt value would most
    damage.

    ``dirty`` reports whether any successful write has occurred, so the
    visit protocol can skip persisting an untouched player.
    """

    _IMMUTABLE = frozenset({"id", "name", "password_hash"})
    _FLOOR_ZERO = frozenset({"gold", "gems"})
    _FLOOR_ONE = frozenset({"strength", "defense", "charm", "hp_max"})

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

        if name in self._FLOOR_ZERO:
            value = max(0, int(value))
        elif name == "exp":
            value = min(max(0, int(value)), _EXP_CAP)
        elif name == "hp_max":
            value = max(1, int(value))
        elif name == "hp":
            value = max(0, min(int(value), player.hp_max))
        elif name in self._FLOOR_ONE:
            value = max(1, int(value))

        setattr(player, name, value)
        object.__setattr__(self, "_dirty", True)


class IgmStore:
    """Per-IGM persistent key/value store backed by the ``igm_data`` table.

    Values are JSON-serializable Python objects, scoped to a single IGM's
    ``key`` (so two IGMs may use the same key names without collision).
    Writes (:meth:`set`/:meth:`delete`) are buffered in memory during a
    visit and only touch the DB when :meth:`flush` is called -- which the
    visit protocol does inside the visit's single transaction on a clean
    exit, so a crashing IGM's store writes are never persisted.
    """

    _MISSING = object()

    def __init__(self, conn: sqlite3.Connection, igm_key: str) -> None:
        self._conn = conn
        self._key = igm_key
        self._loaded: dict[str, Any] = {}
        self._pending: dict[str, tuple[str, Any]] = {}

    def get(self, k: str, default: Any = None) -> Any:
        if k in self._pending:
            op, val = self._pending[k]
            return default if op == "delete" else val
        if k not in self._loaded:
            row = self._conn.execute(
                "SELECT v FROM igm_data WHERE igm_key = ? AND k = ?",
                (self._key, k),
            ).fetchone()
            self._loaded[k] = json.loads(row["v"]) if row is not None else self._MISSING
        val = self._loaded[k]
        return default if val is self._MISSING else val

    def set(self, k: str, v: Any) -> None:
        self._pending[k] = ("set", v)

    def delete(self, k: str) -> None:
        self._pending[k] = ("delete", None)

    def flush(self) -> None:
        """Apply buffered writes via raw ``execute`` (no commit of its own).

        Must run inside the caller's open transaction so the whole visit
        commits or rolls back atomically.
        """
        for k, (op, val) in self._pending.items():
            if op == "delete":
                self._conn.execute(
                    "DELETE FROM igm_data WHERE igm_key = ? AND k = ?",
                    (self._key, k),
                )
            else:
                self._conn.execute(
                    "INSERT INTO igm_data (igm_key, k, v) VALUES (?, ?, ?) "
                    "ON CONFLICT(igm_key, k) DO UPDATE SET v = excluded.v",
                    (self._key, k, json.dumps(val)),
                )
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

    News is buffered (see :meth:`news`) and flushed by the visit protocol
    on a clean exit. Mail and store writes execute against the DB during
    the visit but inside its single transaction, so a crash rolls them
    back.
    """

    def __init__(self, gctx: GameCtx, igm: IGM) -> None:
        self._gctx = gctx
        self._igm = igm
        self.player = PlayerView(gctx.player)
        self.term: TermIO = gctx.io
        self.store = IgmStore(gctx.conn, igm.key)
        self.rng = gctx.rng
        self._news_buffer: list[str] = []

    def news(self, text: str) -> None:
        """Buffer a line for today's news; flushed on a clean visit exit."""
        self._news_buffer.append(text)

    def mail(
        self, to_name: str, text: str | None = None, effect: dict | None = None
    ) -> None:
        """Send in-game mail to ``to_name`` from this IGM.

        ``effect`` is an arbitrary JSON dict stored verbatim; it is applied
        at the recipient's next login (Task 13). Runs a raw INSERT inside
        the visit transaction (rolled back on a crashing visit).
        """
        recipient = self._gctx.repo.get_by_name(to_name)
        if recipient is None:
            raise ValueError(f"no such player to mail: {to_name!r}")
        self._gctx.conn.execute(
            "INSERT INTO mail (to_id, from_name, text, effect, created, read) "
            "VALUES (?, ?, ?, ?, ?, 0)",
            (
                recipient.id,
                self._igm.name,
                text,
                json.dumps(effect) if effect is not None else None,
                datetime.now(UTC).isoformat(),
            ),
        )

    def other_players(self) -> list[PlayerSummary]:
        """Read-only summaries of every *other* player (self excluded)."""
        me = self._gctx.player.id
        return [
            PlayerSummary(p.name, p.level, p.alive, p.class_type)
            for p in self._gctx.repo.all_players()
            if p.id != me
        ]

    # -- internal: called by the visit protocol on a clean exit ---------

    def flush_news(self) -> None:
        """Write buffered news lines via raw execute (no commit)."""
        if not self._news_buffer:
            return
        row = self._gctx.conn.execute(
            "SELECT value FROM game_state WHERE key = 'day'"
        ).fetchone()
        day = row["value"] if row is not None else "1"
        for text in self._news_buffer:
            self._gctx.conn.execute(
                "INSERT INTO daily_news (day, text) VALUES (?, ?)", (day, text)
            )
        self._news_buffer.clear()


class IgmMaintContext:
    """Context handed to :meth:`IGM.daily_maint` during global maintenance.

    Simpler than :class:`IgmContext` -- there's no visiting player to
    guard. Exposes the DB ``conn``, the resolved ``config`` dict, a
    ``repo`` for bulk player reads/writes, and a per-IGM ``store``. The
    registry commits each IGM's store after a clean ``daily_maint`` and
    rolls it back on a crash (see
    :meth:`pylord.igm_loader.IgmRegistry.run_daily_maint`).
    """

    def __init__(
        self, conn: sqlite3.Connection, config: dict[str, Any], igm_key: str
    ) -> None:
        from pylord.models import PlayerRepo

        self.conn = conn
        self.config = config
        self.repo = PlayerRepo(conn)
        self.store = IgmStore(conn, igm_key)
