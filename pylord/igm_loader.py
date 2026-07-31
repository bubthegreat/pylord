"""Discovery + registry for IGM plugins.

:func:`discover` walks an ``igms/`` directory, imports each
``<name>/igm.py`` as an isolated module, finds its single :class:`IGM`
subclass, validates it, and resolves its enabled/disabled state from the
``[igms]`` table in ``config.toml``. A broken plugin (import error,
malformed class, duplicate key) is logged and skipped -- :func:`discover`
never raises, so one bad drop-in can't take the whole game down.

The resulting :class:`IgmRegistry` is the single object the engine threads
through every session (``GameCtx.igms``) and through daily maintenance.

**Module import strategy.** A plugin is an ordinary Python package:
``igms/<name>/`` with an ``__init__.py`` and an ``igm.py``. Discovery
enumerates subpackages with :func:`pkgutil.iter_modules` and imports
``<package>.<name>.igm`` with :func:`importlib.import_module`, which means
a plugin's own modules can import each other -- relatively or absolutely --
like any other Python code.

This replaces an earlier scheme that executed ``igm.py`` alone via
``spec_from_file_location`` under a synthetic module name with no parent
package. That made relative imports impossible and confined every IGM to
one file. It also meant a second ``discover()`` re-executed the module;
now the second call gets the same module object out of ``sys.modules``,
which is simply what importing twice means in Python.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pylord.hooks import IGM, ForestEvent, IgmMaintContext, InnEvent

if TYPE_CHECKING:
    import random

logger = logging.getLogger("pylord.igm")

# A valid IGM key is a lowercase slug: starts alphanumeric, then
# alphanumerics / underscores / hyphens.
_SLUG_RE = re.compile(r"[a-z0-9][a-z0-9_-]*\Z")


def _load_one(package: str, name: str) -> IGM:
    """Import ``<package>.<name>.igm`` and return its validated IGM instance.

    Raises on any problem (import error, wrong subclass count, validation
    failure); the caller is responsible for catching + logging.
    """
    module = importlib.import_module(f"{package}.{name}.igm")

    subclasses = [
        obj
        for obj in vars(module).values()
        if isinstance(obj, type)
        and issubclass(obj, IGM)
        and obj is not IGM
        and obj.__module__ == module.__name__
    ]
    if len(subclasses) != 1:
        raise ValueError(
            f"expected exactly one IGM subclass in {package}.{name}.igm, "
            f"found {len(subclasses)}"
        )
    instance = subclasses[0]()
    # Relative imports work now, but a plugin still needs its directory to
    # reach non-Python files it ships -- data tables, .ANS screens.
    instance.dir = Path(module.__file__).parent
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


def load_all(package: str) -> list[IGM]:
    """Every valid IGM in ``package``, whether or not it is enabled.

    Sorted by subpackage name so duplicate-key resolution is deterministic:
    the first to claim a key wins and later claimants are logged and
    skipped. Never raises -- an unimportable root or a broken plugin is
    logged and skipped, because one bad plugin must never take the game
    down.
    """
    try:
        root = importlib.import_module(package)
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException:
        logger.warning("no IGMs loaded: cannot import %r", package, exc_info=True)
        return []

    path = getattr(root, "__path__", None)
    if path is None:
        logger.warning("no IGMs loaded: %r is not a package", package)
        return []

    loaded: list[IGM] = []
    seen_keys: set[str] = set()
    names = sorted(n for _, n, ispkg in pkgutil.iter_modules(path) if ispkg)

    for name in names:
        try:
            instance = _load_one(package, name)
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException:
            logger.warning("skipping broken IGM %s.%s", package, name, exc_info=True)
            continue
        if instance.key in seen_keys:
            logger.info(
                "ignoring %s.%s: key %r is already taken", package, name, instance.key
            )
            continue
        seen_keys.add(instance.key)
        loaded.append(instance)
    return loaded


def discover(package: str, config: dict[str, Any]) -> IgmRegistry:
    """Discover, validate, and enable the IGMs in ``package``.

    IGMs are *code*: they ship inside the image alongside the engine, and a
    new one arrives the way any other change does -- a folder in ``igms/``,
    a pull request, the next release.

    Returns an :class:`IgmRegistry` of the enabled instances. Enable state
    for each IGM key is ``config["igms"].get(key, instance.default_enabled)``.
    Never raises.
    """
    toggles = (config or {}).get("igms", {})
    if not isinstance(toggles, dict):
        toggles = {}
    enabled = [
        igm for igm in load_all(package) if toggles.get(igm.key, igm.default_enabled)
    ]
    return IgmRegistry(enabled)


class IgmRegistry:
    """The set of enabled IGMs, plus the collection helpers the engine uses."""

    def __init__(self, enabled: list[IGM]) -> None:
        self.enabled = enabled

    def other_places(self) -> list[IGM]:
        """Enabled IGMs, sorted by display name (the 'Other Places' menu)."""
        return sorted(self.enabled, key=lambda igm: igm.name)

    def forest_events(self, rng: random.Random) -> list[tuple[IGM, ForestEvent]]:
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

    async def run_daily_maint(self, db: Any, config: dict[str, Any]) -> None:
        """Run each enabled IGM's ``daily_maint`` hook, containing failures.

        Each plugin gets its own transaction: on a clean return its
        buffered store writes and player saves land; on an exception
        nothing of that plugin's does, and the error is logged, so one bad
        plugin never aborts the others or the surrounding maintenance pass.

        The hook itself is synchronous by design (see
        :class:`pylord.hooks.IgmMaintContext`) even though it is declared
        ``async`` for symmetry with ``enter`` -- it reads a roster loaded
        up front and writes into buffers, so it completes on the first
        coroutine step.
        """
        for igm in self.enabled:
            try:
                mctx = await IgmMaintContext.create(db, config, igm.key)
                await igm.daily_maint(mctx)
                async with db.transaction() as tx:
                    await mctx.flush(tx)
            except Exception:
                logger.exception("IGM %s daily_maint() failed", igm.key)
