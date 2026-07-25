"""Discovery + registry for IGM plugins.

:func:`discover` walks an ``igms/`` directory, imports each
``<name>/igm.py`` as an isolated module, finds its single :class:`IGM`
subclass, validates it, and resolves its enabled/disabled state from the
``[igms]`` table in ``config.toml``. A broken plugin (import error,
malformed class, duplicate key) is logged and skipped -- :func:`discover`
never raises, so one bad drop-in can't take the whole game down.

The resulting :class:`IgmRegistry` is the single object the engine threads
through every session (``GameCtx.igms``) and through daily maintenance.

**Module import strategy.** Each plugin is loaded with
``importlib.util.spec_from_file_location`` under a synthetic, unique module
name ``igms.<dirname>`` (directory names are unique within one ``igms/``
tree, so the names don't collide). The module object is registered in
``sys.modules`` *before* ``exec_module`` (so dataclasses / typing /
``from __future__`` machinery that looks the module up by name works) and
popped again if execution raises, leaving no half-initialized module
behind. Re-running ``discover`` (as the tests do) simply re-execs a fresh
module object over the same name.
"""

from __future__ import annotations

import importlib.util
import logging
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pylord.hooks import IGM, ForestEvent, IgmMaintContext, InnEvent

if TYPE_CHECKING:
    import random
    import sqlite3

logger = logging.getLogger("pylord.igm")

# A valid IGM key is a lowercase slug: starts alphanumeric, then
# alphanumerics / underscores / hyphens.
_SLUG_RE = re.compile(r"[a-z0-9][a-z0-9_-]*\Z")


def _load_one(igm_file: Path, dirname: str) -> IGM:
    """Import ``igm_file`` and return its validated IGM instance.

    Raises on any problem (import error, wrong subclass count, validation
    failure); :func:`discover` is responsible for catching + logging.
    """
    mod_name = f"igms.{dirname}"
    spec = importlib.util.spec_from_file_location(mod_name, igm_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not build import spec for {igm_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(mod_name, None)
        raise

    subclasses = [
        obj
        for obj in vars(module).values()
        if isinstance(obj, type) and issubclass(obj, IGM) and obj is not IGM
    ]
    if len(subclasses) != 1:
        raise ValueError(
            f"expected exactly one IGM subclass in {igm_file}, "
            f"found {len(subclasses)}"
        )
    instance = subclasses[0]()
    _validate(instance)
    return instance


def _validate(instance: IGM) -> None:
    key = getattr(instance, "key", "")
    if not key or not _SLUG_RE.match(key):
        raise ValueError(f"invalid IGM key: {key!r} (must be a lowercase slug)")
    if not getattr(instance, "name", ""):
        raise ValueError("IGM name must be non-empty")
    if type(instance).enter is IGM.enter:
        raise ValueError("IGM must override enter()")


def discover(
    igms_dir: Path | Iterable[Path], config: dict[str, Any]
) -> IgmRegistry:
    """Discover, validate, and enable IGMs under ``igms_dir``.

    IGMs are *code*: they ship inside the image alongside the engine, and a
    new one arrives the way any other change does -- a folder in ``igms/``,
    a pull request, the next release. (They were briefly loaded from the
    data volume as well, which meant a fix to a bundled IGM could never
    reach a realm that had already been seeded; see docs/deviations.md.)

    Several directories may still be passed -- the first to claim a key
    wins -- because the test harness uses that to isolate fixtures.

    Returns an :class:`IgmRegistry` of the enabled instances. Enable state
    for each IGM key is ``config["igms"].get(key, instance.default_enabled)``.
    Never raises: a broken or duplicate plugin is logged and skipped.
    """
    dirs = (
        [Path(igms_dir)]
        if isinstance(igms_dir, str | Path)
        else [Path(d) for d in igms_dir]
    )
    toggles: dict[str, Any] = (config or {}).get("igms", {}) or {}

    loaded: list[IGM] = []
    seen_keys: set[str] = set()

    for directory in dirs:
        if not directory.is_dir():
            continue
        _load_dir(directory, loaded, seen_keys)

    enabled = [igm for igm in loaded if toggles.get(igm.key, igm.default_enabled)]
    return IgmRegistry(enabled)


def _load_dir(igms_dir: Path, loaded: list[IGM], seen_keys: set[str]) -> None:
    for sub in sorted(igms_dir.iterdir()):
        igm_file = sub / "igm.py"
        if not sub.is_dir() or not igm_file.is_file():
            continue
        try:
            instance = _load_one(igm_file, sub.name)
        except BaseException:
            logger.warning("skipping broken IGM in %s", sub, exc_info=True)
            continue
        if instance.key in seen_keys:
            # Already provided by an earlier directory -- the bundled copy
            # wins, so a stale seeded copy on a data volume is ignored
            # rather than shadowing the fixed one.
            logger.info(
                "ignoring %s: key %r already loaded from an earlier directory",
                sub, instance.key,
            )
            continue
        seen_keys.add(instance.key)
        loaded.append(instance)


class IgmRegistry:
    """The set of enabled IGMs, plus the collection helpers the engine uses."""

    def __init__(self, enabled: list[IGM]) -> None:
        self.enabled = enabled

    def other_places(self) -> list[IGM]:
        """Enabled IGMs, sorted by display name (the 'Other Places' menu)."""
        return sorted(self.enabled, key=lambda igm: igm.name)

    def forest_events(
        self, rng: random.Random
    ) -> list[tuple[IGM, ForestEvent]]:
        """Collect every enabled IGM's forest event (``None`` filtered out),
        paired with the IGM that produced it -- the caller needs the owner
        to build that plugin's guardrailed context.

        Each IGM's ``forest_event(rng)`` may consult ``rng`` to decide
        whether/what to contribute this session.
        """
        return self._collect(rng, "forest_event")

    def inn_events(self, rng: random.Random) -> list[tuple[IGM, InnEvent]]:
        """Same, for the Inn (``IGM.inn_event``)."""
        return self._collect(rng, "inn_event")

    def _collect(self, rng: random.Random, hook: str) -> list[tuple[IGM, Any]]:
        events: list[tuple[IGM, Any]] = []
        for igm in self.enabled:
            try:
                event = getattr(igm, hook)(rng)
            except Exception:
                logger.exception("IGM %s %s() failed", igm.key, hook)
                continue
            if event is not None:
                events.append((igm, event))
        return events

    def run_daily_maint(
        self, conn: sqlite3.Connection, config: dict[str, Any]
    ) -> None:
        """Run each enabled IGM's ``daily_maint`` hook, containing failures.

        Each IGM runs in its own try/except: on a clean return its store is
        flushed and committed; on an exception the transaction is rolled
        back and the error logged, so one plugin's failure never aborts the
        others or the surrounding maintenance pass.

        ``daily_maint`` is declared ``async`` for interface symmetry with
        ``enter``, but the maintenance pass is synchronous and is itself
        called from inside the server's running event loop (via
        :func:`pylord.engine.daily.maintenance`), where ``asyncio.run``
        would raise "cannot be called from a running event loop". The maint
        context exposes no terminal, so a well-formed hook does only
        synchronous DB work and completes on the first coroutine step --
        :func:`_drive_sync` runs it without an event loop (and without a
        second thread, keeping the sqlite connection on its owning thread).
        """
        for igm in self.enabled:
            mctx = IgmMaintContext(conn, config, igm.key)
            try:
                _drive_sync(igm.daily_maint(mctx))
                mctx.store.flush()
                conn.commit()
            except Exception:
                conn.rollback()
                logger.exception("IGM %s daily_maint() failed", igm.key)


def _drive_sync(coro) -> None:
    """Run a coroutine that performs no real ``await`` to completion.

    Used for ``IGM.daily_maint``: it has no terminal I/O to await, so a
    well-formed hook finishes on the first ``send(None)``. If a hook *does*
    suspend on a real awaitable, that's a programming error (the sync
    maintenance pass can't pump an event loop here) and is surfaced loudly.
    """
    try:
        coro.send(None)
    except StopIteration:
        return
    else:
        coro.close()
        raise RuntimeError(
            "IGM.daily_maint awaited real async I/O; daily_maint must be "
            "synchronous DB-only work (no terminal, no awaiting)"
        )
